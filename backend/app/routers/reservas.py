from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.reserva import Reserva
from app.models.vaga import StatusVaga, Vaga
from app.schemas.reserva import ReservaCreate, ReservaRead
from app.security.audit import registrar_auditoria
from app.security.auth import get_current_user
from app.services.redis_cache import invalidate_vagas_cache
from app.services.ws_manager import notificar_vaga_atualizada

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
    vaga = await db.get(Vaga, payload.vaga_id)
    if not vaga or not vaga.ativo:
        raise HTTPException(status_code=404, detail="Vaga não encontrada.")
    if vaga.status != StatusVaga.livre:
        raise HTTPException(status_code=409, detail="Vaga não está livre para reserva.")

    reserva = Reserva(**payload.model_dump(), status="ativa", criado_em=datetime.utcnow())
    db.add(reserva)
    vaga.status = StatusVaga.reservada

    await db.commit()
    await db.refresh(reserva)
    await invalidate_vagas_cache()
    await notificar_vaga_atualizada(vaga.id, vaga.status.value)
    await registrar_auditoria(
        db, user["sub"], "criar_reserva", "reserva", str(reserva.id), request.client.host if request.client else None
    )
    return reserva


@router.post("/{reserva_id}/cancelar", response_model=ReservaRead)
async def cancelar_reserva(
    reserva_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> Reserva:
    reserva = await db.get(Reserva, reserva_id)
    if not reserva:
        raise HTTPException(status_code=404, detail="Reserva não encontrada.")
    if reserva.status != "ativa":
        raise HTTPException(status_code=409, detail="Reserva não está ativa.")

    reserva.status = "cancelada"

    vaga = await db.get(Vaga, reserva.vaga_id)
    if vaga and vaga.status == StatusVaga.reservada:
        outras_ativas = (
            await db.execute(
                select(Reserva).where(
                    Reserva.vaga_id == vaga.id, Reserva.status == "ativa", Reserva.id != reserva.id
                )
            )
        ).scalars().all()
        if not outras_ativas:
            vaga.status = StatusVaga.livre

    await db.commit()
    await db.refresh(reserva)
    await invalidate_vagas_cache()
    if vaga:
        await notificar_vaga_atualizada(vaga.id, vaga.status.value)
    await registrar_auditoria(
        db, user["sub"], "cancelar_reserva", "reserva", str(reserva.id), request.client.host if request.client else None
    )
    return reserva
