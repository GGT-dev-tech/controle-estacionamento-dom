from datetime import datetime, timezone
from zoneinfo import ZoneInfo

FUSO_BR = ZoneInfo("America/Sao_Paulo")


def horario_br(dt: datetime) -> datetime:
    """Converte um datetime naive-mas-UTC (datetime.utcnow(), como tudo no app é
    armazenado) para o horário de Brasília, pronto pra formatar (:%H:%M etc.) em
    qualquer mensagem — WhatsApp, e-mail — voltada pro usuário final.

    Sem isso, uma reserva feita "por 1 hora" às 14h (Brasília) mostrava "até 18h" na
    mensagem de confirmação (a hora UTC crua, 3h à frente) — os cálculos e o que fica
    salvo no banco continuam certos, só a exibição direto em texto não convertia.
    """
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.replace(tzinfo=timezone.utc).astimezone(FUSO_BR)
