import asyncio
import logging

from app.config import settings
from app.database import SessionLocal
from app.services.notificacoes import notificar_reserva_expirada, notificar_reserva_proxima_do_vencimento
from app.services.sync import expirar_reservas_vencidas, lembrar_reservas_proximas_do_vencimento

logger = logging.getLogger(__name__)


async def _executar_ciclo() -> None:
    async with SessionLocal() as db:
        expiradas = await expirar_reservas_vencidas(db)
    for reserva in expiradas:
        await notificar_reserva_expirada(reserva)

    async with SessionLocal() as db:
        proximas = await lembrar_reservas_proximas_do_vencimento(db)
    for reserva in proximas:
        await notificar_reserva_proxima_do_vencimento(reserva)


async def loop_verificacao_reservas() -> None:
    """Substitui os Cron Jobs externos do Railway pra expiração/lembrete de reserva: aqui
    roda no próprio processo, a cada `scheduler_intervalo_segundos` (bem abaixo do piso de
    5 min de um Cron Job do Railway), sem depender de uma imagem/curl à parte pra disparar.

    Cada worker gunicorn roda seu próprio loop — não há eleição de líder — mas isso é
    seguro: expirar_reservas_vencidas/lembrar_reservas_proximas_do_vencimento usam
    SELECT ... FOR UPDATE SKIP LOCKED, então workers concorrentes nunca processam a
    mesma reserva duas vezes; só custa um SELECT ocioso a mais por ciclo nos outros workers.
    """
    while True:
        try:
            await _executar_ciclo()
        except Exception:
            logger.exception("Erro no ciclo de verificação de reservas (expiração/lembrete)")
        await asyncio.sleep(settings.scheduler_intervalo_segundos)
