from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.security.auth import require_role
from app.services.relatorios import disparar_relatorio_diario, montar_relatorio_diario

router = APIRouter(prefix="/relatorios", tags=["Relatórios"])


@router.get("/diario")
async def obter_relatorio_diario(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_role("admin")),
) -> dict:
    return await montar_relatorio_diario(db)


@router.post("/diario/enviar")
async def enviar_relatorio_diario_endpoint(
    db: AsyncSession = Depends(get_db),
    x_cron_secret: str | None = Header(default=None, alias="X-Cron-Secret"),
) -> dict:
    """Disparado por uma tarefa agendada externa (ex.: Railway Cron) uma vez por dia."""
    if not settings.cron_secret or x_cron_secret != settings.cron_secret:
        raise HTTPException(status_code=404)

    destinatarios = [e.strip() for e in settings.relatorio_destinatarios.split(",") if e.strip()]
    enviado = await disparar_relatorio_diario(db, destinatarios)
    return {"enviado": enviado, "destinatarios": len(destinatarios)}
