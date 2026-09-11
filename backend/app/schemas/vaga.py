from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.vaga import StatusVaga
from app.schemas.ocupante import OcupanteRead
from app.schemas.reserva import ReservaRead


class VagaBase(BaseModel):
    numero: str
    andar: str
    posicao: str | None = None
    tipo: str = "normal"


class VagaCreate(VagaBase):
    id: str


class VagaUpdate(BaseModel):
    numero: str | None = None
    andar: str | None = None
    posicao: str | None = None
    tipo: str | None = None
    ativo: bool | None = None


class VagaRead(VagaBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: StatusVaga
    ativo: bool
    criado_em: datetime


class VagaComDetalhes(VagaRead):
    ocupante: OcupanteRead | None = None
    reserva_ativa: ReservaRead | None = None
