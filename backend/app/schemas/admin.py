from pydantic import BaseModel, ConfigDict

from app.schemas.common import UTCDatetime


class DominioAutorizadoCreate(BaseModel):
    dominio: str


class DominioAutorizadoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dominio: str
    ativo: bool
    criado_em: UTCDatetime


class AdminEmailCreate(BaseModel):
    email: str


class AdminEmailRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email: str
    criado_em: UTCDatetime


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario_id: str
    acao: str
    recurso: str
    recurso_id: str | None
    ip: str | None
    timestamp: UTCDatetime
    detalhes: str | None
