from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.ocupante import TipoCliente


class OcupanteBase(BaseModel):
    nome: str
    placa: str
    veiculo: str
    tipo_cliente: TipoCliente
    observacoes: str | None = None


class OcupanteRead(OcupanteBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vaga_id: str
    hora_entrada: datetime
    operador_id: str
