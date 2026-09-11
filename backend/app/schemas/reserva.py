from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, field_validator


def _para_naive_utc(valor: datetime) -> datetime:
    """O frontend manda `Date.toISOString()` (ex.: 2026-09-11T04:39:36.000Z), que o
    Pydantic interpreta como timezone-aware. O resto do app (datetime.utcnow(), colunas
    DateTime sem timezone) é sempre naive — misturar os dois na mesma linha faz o asyncpg
    recusar o INSERT (DataError: can't subtract offset-naive and offset-aware datetimes).
    Normaliza pra naive UTC aqui, na borda de entrada, antes que a diferença chegue ao ORM.
    """
    if valor.tzinfo is not None:
        return valor.astimezone(timezone.utc).replace(tzinfo=None)
    return valor


class ReservaBase(BaseModel):
    nome: str
    telefone: str | None = None
    email: str | None = None
    placa: str | None = None
    inicio: datetime
    fim: datetime

    @field_validator("inicio")
    @classmethod
    def _inicio_naive_utc(cls, inicio: datetime) -> datetime:
        return _para_naive_utc(inicio)

    @field_validator("fim")
    @classmethod
    def fim_apos_inicio(cls, fim: datetime, info) -> datetime:
        fim = _para_naive_utc(fim)
        inicio = info.data.get("inicio")
        if inicio and fim <= inicio:
            raise ValueError("Data/hora de término deve ser após o início.")
        return fim


class ReservaCreate(ReservaBase):
    vaga_id: str
    canal: str = "webapp"


class ReservaRead(ReservaBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vaga_id: str
    status: str
    canal: str
    criado_em: datetime
