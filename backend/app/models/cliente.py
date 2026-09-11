from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.ocupante import TipoCliente


class Cliente(Base):
    """Cliente pré-cadastrado (mensalista/rotativo/etc.) autorizado a usar o bot do WhatsApp."""

    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(100))
    telefone: Mapped[str] = mapped_column(String(20), unique=True, index=True)  # normalizado: DDD+número, sem "55"
    email: Mapped[str | None] = mapped_column(String(100))
    # sub do Auth0 — liga este cadastro a um login corporativo. Nulo até a pessoa logar
    # pela primeira vez e "adotar" um cadastro que só existia por telefone (feito pelo admin).
    auth0_sub: Mapped[str | None] = mapped_column(String(200), unique=True)
    tipo_cliente: Mapped[TipoCliente] = mapped_column(SAEnum(TipoCliente, name="tipo_cliente"))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
