from pydantic import BaseModel, ConfigDict

from app.models.ocupante import TipoCliente
from app.schemas.common import UTCDatetime


class EntradaCreate(BaseModel):
    vaga_id: str
    nome: str
    placa: str
    veiculo: str
    tipo_cliente: TipoCliente
    observacoes: str | None = None


class SaidaCreate(BaseModel):
    vaga_id: str


class MovimentacaoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vaga_id: str
    tipo: str
    placa: str
    motorista: str
    veiculo: str
    timestamp: UTCDatetime
    operador_id: str
    tempo_permanencia_min: int | None
    sincronizado: bool
