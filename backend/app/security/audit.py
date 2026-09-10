import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


async def registrar_auditoria(
    db: AsyncSession,
    usuario_id: str,
    acao: str,
    recurso: str,
    recurso_id: str | None = None,
    ip: str | None = None,
    detalhes: dict | None = None,
) -> None:
    log = AuditLog(
        usuario_id=usuario_id,
        acao=acao,
        recurso=recurso,
        recurso_id=recurso_id,
        ip=ip,
        detalhes=json.dumps(detalhes, ensure_ascii=False) if detalhes else None,
    )
    db.add(log)
    await db.commit()
    logger.info("audit: usuario=%s acao=%s recurso=%s/%s", usuario_id, acao, recurso, recurso_id)
