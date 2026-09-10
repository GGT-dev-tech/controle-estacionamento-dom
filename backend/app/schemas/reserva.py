from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class ReservaBase(BaseModel):
    nome: str
    telefone: str | None = None
    email: str | None = None
    placa: str | None = None
    inicio: datetime
    fim: datetime

    @field_validator("fim")
    @classmethod
    def fim_apos_inicio(cls, fim: datetime, info) -> datetime:
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
