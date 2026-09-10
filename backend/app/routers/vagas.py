import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.ocupante import Ocupante
from app.models.reserva import Reserva
from app.models.vaga import Vaga
from app.schemas.vaga import VagaComDetalhes, VagaCreate, VagaRead, VagaUpdate
from app.security.audit import registrar_auditoria
from app.security.auth import get_current_user, require_role
from app.services.redis_cache import get_vagas_cache, invalidate_vagas_cache, set_vagas_cache

router = APIRouter(prefix="/vagas", tags=["Vagas"])


async def _montar_vagas_com_detalhes(db: AsyncSession, andar: str | None) -> list[VagaComDetalhes]:
    query = select(Vaga).where(Vaga.ativo.is_(True))
    if andar:
        query = query.where(Vaga.andar == andar)
    vagas = list((await db.execute(query)).scalars().all())

    ocupantes = {
        o.vaga_id: o for o in (await db.execute(select(Ocupante))).scalars().all()
    }
    reservas_ativas = {
        r.vaga_id: r
        for r in (await db.execute(select(Reserva).where(Reserva.status == "ativa"))).scalars().all()
    }

    return [
        VagaComDetalhes.model_validate(
            {
                **VagaRead.model_validate(vaga).model_dump(),
                "ocupante": ocupantes.get(vaga.id),
                "reserva_ativa": reservas_ativas.get(vaga.id),
            }
        )
        for vaga in vagas
    ]


@router.get("", response_model=list[VagaComDetalhes])
async def listar_vagas(
    andar: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> list[VagaComDetalhes]:
    cached = await get_vagas_cache(andar)
    if cached:
        return json.loads(cached)

    vagas = await _montar_vagas_com_detalhes(db, andar)
    await set_vagas_cache(andar, json.dumps([v.model_dump(mode="json") for v in vagas]))
    return vagas


@router.get("/{vaga_id}", response_model=VagaComDetalhes)
async def obter_vaga(
    vaga_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> VagaComDetalhes:
    vaga = await db.get(Vaga, vaga_id)
    if not vaga:
        raise HTTPException(status_code=404, detail="Vaga não encontrada.")
    ocupante = (
        await db.execute(select(Ocupante).where(Ocupante.vaga_id == vaga_id))
    ).scalar_one_or_none()
    reserva = (
        await db.execute(
            select(Reserva).where(Reserva.vaga_id == vaga_id, Reserva.status == "ativa")
        )
    ).scalar_one_or_none()
    return VagaComDetalhes.model_validate(
        {**VagaRead.model_validate(vaga).model_dump(), "ocupante": ocupante, "reserva_ativa": reserva}
    )


@router.post("", response_model=VagaRead, status_code=201)
async def criar_vaga(
    payload: VagaCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
) -> Vaga:
    if await db.get(Vaga, payload.id):
        raise HTTPException(status_code=409, detail="Já existe uma vaga com este ID.")
    vaga = Vaga(**payload.model_dump())
    db.add(vaga)
    await db.commit()
    await db.refresh(vaga)
    await invalidate_vagas_cache()
    await registrar_auditoria(
        db, user["sub"], "criar_vaga", "vaga", vaga.id, request.client.host if request.client else None
    )
    return vaga


@router.patch("/{vaga_id}", response_model=VagaRead)
async def atualizar_vaga(
    vaga_id: str,
    payload: VagaUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
) -> Vaga:
    vaga = await db.get(Vaga, vaga_id)
    if not vaga:
        raise HTTPException(status_code=404, detail="Vaga não encontrada.")
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(vaga, campo, valor)
    await db.commit()
    await db.refresh(vaga)
    await invalidate_vagas_cache()
    await registrar_auditoria(
        db, user["sub"], "atualizar_vaga", "vaga", vaga.id, request.client.host if request.client else None
    )
    return vaga


@router.delete("/{vaga_id}", status_code=204)
async def desativar_vaga(
    vaga_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
) -> None:
    vaga = await db.get(Vaga, vaga_id)
    if not vaga:
        raise HTTPException(status_code=404, detail="Vaga não encontrada.")
    vaga.ativo = False
    await db.commit()
    await invalidate_vagas_cache()
    await registrar_auditoria(
        db, user["sub"], "desativar_vaga", "vaga", vaga.id, request.client.host if request.client else None
    )
