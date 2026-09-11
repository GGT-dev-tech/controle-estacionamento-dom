from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.admin_email import AdminEmail
from app.models.audit_log import AuditLog
from app.models.cliente import Cliente
from app.models.dominio_autorizado import DominioAutorizado
from app.schemas.admin import (
    AdminEmailCreate,
    AdminEmailRead,
    AuditLogRead,
    DominioAutorizadoCreate,
    DominioAutorizadoRead,
)
from app.schemas.cliente import ClienteCreate, ClienteRead
from app.security.auth import require_role
from app.services.whatsapp import normalizar_telefone

router = APIRouter(prefix="/admin", tags=["Admin"])


def _verificar_segredo_interno(x_internal_secret: str | None) -> None:
    """Usado pelas rotas /verificar, chamadas pela Auth0 Post-Login Action antes de existir um JWT."""
    if not settings.auth0_action_secret or x_internal_secret != settings.auth0_action_secret:
        raise HTTPException(status_code=404)


# ── Domínios autorizados ─────────────────────────────────────────────────


@router.get("/dominios", response_model=list[DominioAutorizadoRead])
async def listar_dominios(
    db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("admin"))
) -> list[DominioAutorizado]:
    result = await db.execute(select(DominioAutorizado).order_by(DominioAutorizado.dominio))
    return list(result.scalars().all())


@router.post("/dominios", response_model=DominioAutorizadoRead, status_code=201)
async def adicionar_dominio(
    payload: DominioAutorizadoCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
) -> DominioAutorizado:
    dominio = payload.dominio.strip().lower()
    if await db.get(DominioAutorizado, dominio):
        raise HTTPException(status_code=409, detail="Domínio já cadastrado.")
    registro = DominioAutorizado(dominio=dominio)
    db.add(registro)
    await db.commit()
    await db.refresh(registro)
    return registro


@router.delete("/dominios/{dominio}", status_code=204)
async def remover_dominio(
    dominio: str, db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("admin"))
) -> None:
    registro = await db.get(DominioAutorizado, dominio.strip().lower())
    if not registro:
        raise HTTPException(status_code=404, detail="Domínio não encontrado.")
    await db.delete(registro)
    await db.commit()


@router.get("/dominios/{dominio}/verificar")
async def verificar_dominio(
    dominio: str,
    db: AsyncSession = Depends(get_db),
    x_internal_secret: str | None = Header(default=None, alias="X-Internal-Secret"),
) -> dict:
    _verificar_segredo_interno(x_internal_secret)
    registro = await db.get(DominioAutorizado, dominio.strip().lower())
    return {"autorizado": bool(registro and registro.ativo)}


# ── E-mails com papel de admin ───────────────────────────────────────────


@router.get("/admins", response_model=list[AdminEmailRead])
async def listar_admins(
    db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("admin"))
) -> list[AdminEmail]:
    result = await db.execute(select(AdminEmail).order_by(AdminEmail.email))
    return list(result.scalars().all())


@router.post("/admins", response_model=AdminEmailRead, status_code=201)
async def adicionar_admin(
    payload: AdminEmailCreate, db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("admin"))
) -> AdminEmail:
    email = payload.email.strip().lower()
    if await db.get(AdminEmail, email):
        raise HTTPException(status_code=409, detail="E-mail já é admin.")
    registro = AdminEmail(email=email)
    db.add(registro)
    await db.commit()
    await db.refresh(registro)
    return registro


@router.delete("/admins/{email}", status_code=204)
async def remover_admin(
    email: str, db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("admin"))
) -> None:
    registro = await db.get(AdminEmail, email.strip().lower())
    if not registro:
        raise HTTPException(status_code=404, detail="E-mail não encontrado.")
    await db.delete(registro)
    await db.commit()


@router.get("/admins/{email}/verificar")
async def verificar_admin(
    email: str,
    db: AsyncSession = Depends(get_db),
    x_internal_secret: str | None = Header(default=None, alias="X-Internal-Secret"),
) -> dict:
    _verificar_segredo_interno(x_internal_secret)
    registro = await db.get(AdminEmail, email.strip().lower())
    return {"admin": registro is not None}


# ── Audit log ─────────────────────────────────────────────────────────────


@router.get("/audit-logs", response_model=list[AuditLogRead])
async def listar_audit_logs(
    limite: int = 100,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
) -> list[AuditLog]:
    limite = min(max(limite, 1), 500)
    result = await db.execute(select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limite))
    return list(result.scalars().all())


# ── Clientes cadastrados (mensalistas/rotativos autorizados no bot WhatsApp) ──


@router.get("/clientes", response_model=list[ClienteRead])
async def listar_clientes(
    db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("admin"))
) -> list[Cliente]:
    result = await db.execute(select(Cliente).order_by(Cliente.nome))
    return list(result.scalars().all())


@router.post("/clientes", response_model=ClienteRead, status_code=201)
async def adicionar_cliente(
    payload: ClienteCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
) -> Cliente:
    telefone = normalizar_telefone(payload.telefone)
    existente = (
        await db.execute(select(Cliente).where(Cliente.telefone == telefone))
    ).scalar_one_or_none()
    if existente:
        raise HTTPException(status_code=409, detail="Já existe um cliente com este telefone.")
    cliente = Cliente(nome=payload.nome, telefone=telefone, tipo_cliente=payload.tipo_cliente)
    db.add(cliente)
    await db.commit()
    await db.refresh(cliente)
    return cliente


@router.delete("/clientes/{cliente_id}", status_code=204)
async def remover_cliente(
    cliente_id: int, db: AsyncSession = Depends(get_db), user: dict = Depends(require_role("admin"))
) -> None:
    cliente = await db.get(Cliente, cliente_id)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    await db.delete(cliente)
    await db.commit()
