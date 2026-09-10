from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DominioAutorizado(Base):
    __tablename__ = "dominios_autorizados"

    dominio: Mapped[str] = mapped_column(String(255), primary_key=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
