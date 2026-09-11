from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.ocupante import TipoCliente


class ClienteCreate(BaseModel):
    nome: str
    telefone: str
    tipo_cliente: TipoCliente


class ClienteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    telefone: str
    tipo_cliente: TipoCliente
    ativo: bool
    criado_em: datetime
