import logging

from pydantic import ValidationError
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.movimentacao import Movimentacao
from app.schemas.movimentacao import EntradaCreate, MovimentacaoRead, SaidaCreate
from app.schemas.reserva import ReservaCreate
from app.schemas.sync import ResultadoOperacao, SincronizarRequest, SincronizarResponse
from app.security.audit import registrar_auditoria
from app.security.auth import get_current_user
from app.services.notificacoes import notificar_reserva_cancelada, notificar_reserva_criada
from app.services.sync import (
    ConflitoOperacaoError,
    RecursoNaoEncontradoError,
    aplicar_cancelamento,
    aplicar_entrada,
    aplicar_reserva,
    aplicar_saida,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/movimentacoes", tags=["Movimentações"])


@router.get("", response_model=list[MovimentacaoRead])
async def listar_movimentacoes(
    vaga_id: str | None = None,
    placa: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> list[Movimentacao]:
    query = select(Movimentacao).order_by(Movimentacao.timestamp.desc())
    if vaga_id:
        query = query.where(Movimentacao.vaga_id == vaga_id)
    if placa:
        query = query.where(Movimentacao.placa == placa.upper())
    result = await db.execute(query.limit(200))
    return list(result.scalars().all())


@router.post("/entrada", response_model=MovimentacaoRead, status_code=201)
async def registrar_entrada(
    payload: EntradaCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> Movimentacao:
    try:
        movimentacao = await aplicar_entrada(db, payload, user["sub"])
    except RecursoNaoEncontradoError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConflitoOperacaoError as e:
        raise HTTPException(status_code=409, detail=str(e))

    await registrar_auditoria(
        db, user["sub"], "entrada", "vaga", payload.vaga_id, request.client.host if request.client else None
    )
    return movimentacao


@router.post("/saida", response_model=MovimentacaoRead, status_code=201)
async def registrar_saida(
    payload: SaidaCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> Movimentacao:
    try:
        movimentacao = await aplicar_saida(db, payload.vaga_id, user["sub"])
    except RecursoNaoEncontradoError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConflitoOperacaoError as e:
        raise HTTPException(status_code=409, detail=str(e))

    await registrar_auditoria(
        db, user["sub"], "saida", "vaga", payload.vaga_id, request.client.host if request.client else None
    )
    return movimentacao


@router.post("/sync", response_model=SincronizarResponse)
async def sincronizar_operacoes(
    payload: SincronizarRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> SincronizarResponse:
    """Recebe a fila de operações pendentes gravadas offline (IndexedDB/Dexie) e as aplica em lote.

    Cada item é processado de forma independente — uma falha não interrompe o restante do lote.
    """
    ip = request.client.host if request.client else None
    resultados: list[ResultadoOperacao] = []

    for operacao in payload.operacoes:
        try:
            if operacao.tipo == "entrada":
                await aplicar_entrada(db, EntradaCreate.model_validate(operacao.payload), user["sub"])
            elif operacao.tipo == "saida":
                await aplicar_saida(db, str(operacao.payload["vaga_id"]), user["sub"])
            elif operacao.tipo == "reserva":
                reserva = await aplicar_reserva(db, ReservaCreate.model_validate(operacao.payload), user["sub"])
                await notificar_reserva_criada(reserva)
            elif operacao.tipo == "cancelamento":
                reserva = await aplicar_cancelamento(db, int(operacao.payload["reserva_id"]), user["sub"])
                await notificar_reserva_cancelada(reserva)

            resultados.append(ResultadoOperacao(id=operacao.id, sucesso=True))
            await registrar_auditoria(db, user["sub"], f"sync_{operacao.tipo}", "vaga", None, ip)
        except (RecursoNaoEncontradoError, ConflitoOperacaoError, ValidationError, KeyError) as e:
            await db.rollback()
            resultados.append(ResultadoOperacao(id=operacao.id, sucesso=False, mensagem=str(e)))
        except Exception:
            await db.rollback()
            logger.exception("Erro inesperado ao sincronizar operação %s (id=%s)", operacao.tipo, operacao.id)
            resultados.append(
                ResultadoOperacao(id=operacao.id, sucesso=False, mensagem="Erro ao processar operação.")
            )

    return SincronizarResponse(resultados=resultados)
