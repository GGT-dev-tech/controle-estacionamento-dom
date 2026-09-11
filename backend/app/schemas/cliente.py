from pydantic import BaseModel, ConfigDict

from app.models.ocupante import TipoCliente
from app.schemas.common import UTCDatetime


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
    criado_em: UTCDatetime


class VeiculoCreate(BaseModel):
    placa: str | None = None
    veiculo: str


class VeiculoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    placa: str | None
    veiculo: str
    criado_em: UTCDatetime


class MeuCadastroCreate(BaseModel):
    nome: str
    telefone: str
    email: str | None = None


class MeuCadastroUpdate(BaseModel):
    nome: str | None = None
    telefone: str | None = None
    email: str | None = None


class MeuCadastroRead(BaseModel):
    id: int
    nome: str
    telefone: str
    email: str | None
    tipo_cliente: TipoCliente
    ativo: bool
    criado_em: UTCDatetime
    veiculos: list[VeiculoRead] = []
