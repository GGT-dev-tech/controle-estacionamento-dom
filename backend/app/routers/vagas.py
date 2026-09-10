from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.vaga import Vaga
from app.schemas.vaga import VagaCreate, VagaRead
from app.security.auth import get_current_user, require_role

router = APIRouter(prefix="/vagas", tags=["Vagas"])


@router.get("", response_model=list[VagaRead])
async def listar_vagas(
    andar: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> list[Vaga]:
    query = select(Vaga)
    if andar:
        query = query.where(Vaga.andar == andar)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/{vaga_id}", response_model=VagaRead)
async def obter_vaga(
    vaga_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> Vaga:
    vaga = await db.get(Vaga, vaga_id)
    if not vaga:
        raise HTTPException(status_code=404, detail="Vaga não encontrada.")
    return vaga


@router.post("", response_model=VagaRead, status_code=201)
async def criar_vaga(
    payload: VagaCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
) -> Vaga:
    if await db.get(Vaga, payload.id):
        raise HTTPException(status_code=409, detail="Já existe uma vaga com este ID.")
    vaga = Vaga(**payload.model_dump())
    db.add(vaga)
    await db.commit()
    await db.refresh(vaga)
    return vaga
