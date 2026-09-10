import logging

import resend

from app.config import settings

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
                "html": _template_confirmacao(reserva),
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
                "html": _template_cancelamento(reserva),
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
                "html": _template_relatorio_diario(relatorio),
            }
        )
        return True
    except Exception:
        logger.exception("Falha ao enviar relatório diário")
        return False


def _template_confirmacao(r: dict) -> str:
    return f"""
    <div style="font-family:sans-serif;max-width:600px;margin:0 auto">
      <h2>✅ Reserva Confirmada</h2>
      <p>Olá, <strong>{r['nome']}</strong>!</p>
      <table>
        <tr><td>📍 Vaga:</td><td><strong>{r['vaga_id']}</strong></td></tr>
        <tr><td>📅 Início:</td><td>{r['inicio']:%d/%m/%Y %H:%M}</td></tr>
        <tr><td>⏰ Término:</td><td>{r['fim']:%d/%m/%Y %H:%M}</td></tr>
        <tr><td>🚗 Placa:</td><td>{r.get('placa') or 'N/A'}</td></tr>
      </table>
      <p style="color:#666">Dom Pagamentos — Sistema de Estacionamento</p>
    </div>
    """


def _template_cancelamento(r: dict) -> str:
    return f"""
    <div style="font-family:sans-serif;max-width:600px;margin:0 auto">
      <h2>❌ Reserva Cancelada</h2>
      <p>Olá, <strong>{r['nome']}</strong>!</p>
      <p>Sua reserva da vaga <strong>{r['vaga_id']}</strong> foi cancelada.</p>
      <p style="color:#666">Dom Pagamentos — Sistema de Estacionamento</p>
    </div>
    """


def _template_relatorio_diario(r: dict) -> str:
    tempo_medio = f"{r['tempo_medio_permanencia_min']} min" if r["tempo_medio_permanencia_min"] is not None else "N/A"
    return f"""
    <div style="font-family:sans-serif;max-width:600px;margin:0 auto">
      <h2>📊 Relatório Diário — {r['data']:%d/%m/%Y}</h2>
      <table cellpadding="6">
        <tr><td>Total de vagas:</td><td><strong>{r['total_vagas']}</strong></td></tr>
        <tr><td>🟢 Livres:</td><td>{r['livres']}</td></tr>
        <tr><td>🔴 Ocupadas:</td><td>{r['ocupadas']}</td></tr>
        <tr><td>🟡 Reservadas:</td><td>{r['reservadas']}</td></tr>
        <tr><td>⚫ Manutenção:</td><td>{r['manutencao']}</td></tr>
        <tr><td>🚗 Entradas hoje:</td><td>{r['entradas_hoje']}</td></tr>
        <tr><td>🚙 Saídas hoje:</td><td>{r['saidas_hoje']}</td></tr>
        <tr><td>⏱️ Tempo médio de permanência:</td><td>{tempo_medio}</td></tr>
      </table>
      <p style="color:#666">Dom Pagamentos — Sistema de Estacionamento</p>
    </div>
    """
