from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.movimentacao import Movimentacao
from app.models.ocupante import Ocupante
from app.models.reserva import Reserva
from app.models.vaga import StatusVaga, Vaga
from app.schemas.movimentacao import EntradaCreate, MovimentacaoRead, SaidaCreate
from app.security.audit import registrar_auditoria
from app.security.auth import get_current_user
from app.services.redis_cache import invalidate_vagas_cache
from app.services.ws_manager import notificar_vaga_atualizada

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
    vaga = await db.get(Vaga, payload.vaga_id)
    if not vaga or not vaga.ativo:
        raise HTTPException(status_code=404, detail="Vaga não encontrada.")
    if vaga.status not in (StatusVaga.livre, StatusVaga.reservada):
        raise HTTPException(status_code=409, detail="Vaga não está disponível para ocupação.")

    agora = datetime.utcnow()

    ocupante = Ocupante(
        vaga_id=vaga.id,
        nome=payload.nome,
        placa=payload.placa.upper(),
        veiculo=payload.veiculo,
        tipo_cliente=payload.tipo_cliente,
        observacoes=payload.observacoes,
        hora_entrada=agora,
        operador_id=user["sub"],
    )
    db.add(ocupante)

    if vaga.status == StatusVaga.reservada:
        reservas_ativas = (
            await db.execute(
                select(Reserva).where(Reserva.vaga_id == vaga.id, Reserva.status == "ativa")
            )
        ).scalars().all()
        for reserva in reservas_ativas:
            reserva.status = "concluida"

    vaga.status = StatusVaga.ocupada

    movimentacao = Movimentacao(
        vaga_id=vaga.id,
        tipo="entrada",
        placa=payload.placa.upper(),
        motorista=payload.nome,
        veiculo=payload.veiculo,
        timestamp=agora,
        operador_id=user["sub"],
    )
    db.add(movimentacao)

    await db.commit()
    await db.refresh(movimentacao)
    await invalidate_vagas_cache()
    await notificar_vaga_atualizada(vaga.id, vaga.status.value)
    await registrar_auditoria(
        db, user["sub"], "entrada", "vaga", vaga.id, request.client.host if request.client else None
    )
    return movimentacao


@router.post("/saida", response_model=MovimentacaoRead, status_code=201)
async def registrar_saida(
    payload: SaidaCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> Movimentacao:
    vaga = await db.get(Vaga, payload.vaga_id)
    if not vaga:
        raise HTTPException(status_code=404, detail="Vaga não encontrada.")
    if vaga.status != StatusVaga.ocupada:
        raise HTTPException(status_code=409, detail="Vaga não está ocupada.")

    ocupante = (
        await db.execute(select(Ocupante).where(Ocupante.vaga_id == vaga.id))
    ).scalar_one_or_none()
    if not ocupante:
        raise HTTPException(status_code=409, detail="Nenhum ocupante registrado para esta vaga.")

    agora = datetime.utcnow()
    tempo_permanencia_min = int((agora - ocupante.hora_entrada).total_seconds() // 60)

    movimentacao = Movimentacao(
        vaga_id=vaga.id,
        tipo="saida",
        placa=ocupante.placa,
        motorista=ocupante.nome,
        veiculo=ocupante.veiculo,
        timestamp=agora,
        operador_id=user["sub"],
        tempo_permanencia_min=tempo_permanencia_min,
    )
    db.add(movimentacao)

    await db.delete(ocupante)
    vaga.status = StatusVaga.livre

    await db.commit()
    await db.refresh(movimentacao)
    await invalidate_vagas_cache()
    await notificar_vaga_atualizada(vaga.id, vaga.status.value)
    await registrar_auditoria(
        db, user["sub"], "saida", "vaga", vaga.id, request.client.host if request.client else None
    )
    return movimentacao
