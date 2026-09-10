import logging

import resend

from app.config import settings
from app.services.email_templates import (
    template_cancelamento_reserva,
    template_confirmacao_reserva,
    template_relatorio_diario,
)

logger = logging.getLogger(__name__)

resend.api_key = settings.resend_api_key


async def enviar_confirmacao_reserva(reserva: dict) -> bool:
    if not settings.resend_api_key:
        logger.warning("Resend não configurado — email de confirmação não enviado.")
        return False
    try:
        resend.Emails.send(
            {
                "from": settings.email_from,
                "to": [reserva["email"]],
                "subject": f"✅ Reserva confirmada — Vaga {reserva['vaga_id']} | Dom Estacionamento",
                "html": template_confirmacao_reserva(reserva),
            }
        )
        return True
    except Exception:
        logger.exception("Falha ao enviar email de confirmação de reserva")
        return False


async def enviar_cancelamento_reserva(reserva: dict) -> bool:
    if not settings.resend_api_key:
        logger.warning("Resend não configurado — email de cancelamento não enviado.")
        return False
    try:
        resend.Emails.send(
            {
                "from": settings.email_from,
                "to": [reserva["email"]],
                "subject": f"❌ Reserva cancelada — Vaga {reserva['vaga_id']} | Dom Estacionamento",
                "html": template_cancelamento_reserva(reserva),
            }
        )
        return True
    except Exception:
        logger.exception("Falha ao enviar email de cancelamento de reserva")
        return False


async def enviar_relatorio_diario(destinatarios: list[str], relatorio: dict) -> bool:
    if not settings.resend_api_key:
        logger.warning("Resend não configurado — relatório diário não enviado.")
        return False
    try:
        resend.Emails.send(
            {
                "from": settings.email_from,
                "to": destinatarios,
                "subject": f"📊 Relatório diário — {relatorio['data']:%d/%m/%Y} | Dom Estacionamento",
                "html": template_relatorio_diario(relatorio),
            }
        )
        return True
    except Exception:
        logger.exception("Falha ao enviar relatório diário")
        return False
