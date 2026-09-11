from datetime import datetime, timezone
from typing import Annotated

from pydantic import PlainSerializer


def _serializar_utc(valor: datetime) -> str:
    """Todo datetime armazenado no banco é naive mas representa um instante UTC
    (datetime.utcnow() em todo o app). Serializado sem indicar timezone, o JSON vira
    algo como "2026-09-11T07:20:00" — sem "Z"/offset, o navegador (`new Date(...)`)
    interpreta como horário LOCAL, não UTC, e exibe a hora errada. Marca explicitamente
    como UTC aqui, na borda de saída, antes de virar JSON.
    """
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=timezone.utc)
    return valor.isoformat()


UTCDatetime = Annotated[datetime, PlainSerializer(_serializar_utc, return_type=str, when_used="json")]
