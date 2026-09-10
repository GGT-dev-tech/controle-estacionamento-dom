from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.vaga import StatusVaga


class VagaBase(BaseModel):
    numero: str
    andar: str
    posicao: str | None = None
    tipo: str = "normal"


class VagaCreate(VagaBase):
    id: str


class VagaRead(VagaBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: StatusVaga
    ativo: bool
    criado_em: datetime
