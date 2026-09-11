from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.reserva import Reserva
from app.schemas.reserva import ReservaCreate, ReservaRead
from app.security.audit import registrar_auditoria
from app.security.auth import get_current_user
from app.services.notificacoes import (
    notificar_reserva_cancelada,
    notificar_reserva_criada,
    notificar_reserva_expirada,
    notificar_reserva_proxima_do_vencimento,
)
from app.services.sync import (
    ConflitoOperacaoError,
    PermissaoNegadaError,
    RecursoNaoEncontradoError,
    aplicar_cancelamento,
    aplicar_reserva,
    expirar_reservas_vencidas,
    lembrar_reservas_proximas_do_vencimento,
)

router = APIRouter(prefix="/reservas", tags=["Reservas"])


@router.get("", response_model=list[ReservaRead])
async def listar_reservas(
    vaga_id: str | None = None,
    status_filtro: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> list[Reserva]:
    query = select(Reserva).order_by(Reserva.inicio.desc())
    if vaga_id:
        query = query.where(Reserva.vaga_id == vaga_id)
    if status_filtro:
        query = query.where(Reserva.status == status_filtro)
    result = await db.execute(query.limit(200))
    return list(result.scalars().all())


@router.post("", response_model=ReservaRead, status_code=201)
async def criar_reserva(
    payload: ReservaCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> Reserva:
    try:
        reserva = await aplicar_reserva(db, payload, user["sub"])
    except RecursoNaoEncontradoError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConflitoOperacaoError as e:
        raise HTTPException(status_code=409, detail=str(e))

    await registrar_auditoria(
        db, user["sub"], "criar_reserva", "reserva", str(reserva.id), request.client.host if request.client else None
    )
    await notificar_reserva_criada(reserva)
    return reserva


@router.post("/{reserva_id}/cancelar", response_model=ReservaRead)
async def cancelar_reserva(
    reserva_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> Reserva:
    try:
        reserva = await aplicar_cancelamento(db, reserva_id, user["sub"])
    except RecursoNaoEncontradoError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConflitoOperacaoError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except PermissaoNegadaError as e:
        raise HTTPException(status_code=403, detail=str(e))

    await registrar_auditoria(
        db,
        user["sub"],
        "cancelar_reserva",
        "reserva",
        str(reserva.id),
        request.client.host if request.client else None,
    )
    await notificar_reserva_cancelada(reserva)
    return reserva


@router.post("/expirar-vencidas")
async def expirar_vencidas(
    db: AsyncSession = Depends(get_db),
    x_cron_secret: str | None = Header(default=None, alias="X-Cron-Secret"),
) -> dict:
    """Disparado por uma tarefa agendada externa (ex.: Railway Cron) periodicamente."""
    if not settings.cron_secret or x_cron_secret != settings.cron_secret:
        raise HTTPException(status_code=404)

    expiradas = await expirar_reservas_vencidas(db)
    for reserva in expiradas:
        await notificar_reserva_expirada(reserva)
    return {"expiradas": len(expiradas)}


@router.post("/lembrar-vencimento")
async def lembrar_vencimento(
    db: AsyncSession = Depends(get_db),
    x_cron_secret: str | None = Header(default=None, alias="X-Cron-Secret"),
) -> dict:
    """Disparado por uma tarefa agendada externa (ex.: Railway Cron), com mais frequência
    que /expirar-vencidas — avisa por WhatsApp quem tem reserva perto do vencimento."""
    if not settings.cron_secret or x_cron_secret != settings.cron_secret:
        raise HTTPException(status_code=404)

    proximas = await lembrar_reservas_proximas_do_vencimento(db)
    for reserva in proximas:
        await notificar_reserva_proxima_do_vencimento(reserva)
    return {"lembretes_enviados": len(proximas)}

@router.post("/reset-diario")
async def resetar_diario(
    db: AsyncSession = Depends(get_db),
    x_cron_secret: str | None = Header(default=None, alias="X-Cron-Secret"),
) -> dict:
    """Zera as ocupações e reservas ativas (recomendado rodar às 03:00 da manhã)."""
    if not settings.cron_secret or x_cron_secret != settings.cron_secret:
        raise HTTPException(status_code=404)

    from app.services.sync import reset_diario
    vagas_liberadas = await reset_diario(db)
    return {"vagas_resetadas": vagas_liberadas, "status": "ok"}
