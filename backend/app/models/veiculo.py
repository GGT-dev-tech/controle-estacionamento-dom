from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Veiculo(Base):
    """Um veículo vinculado a um Cliente — um cadastro pode ter mais de um."""

    __tablename__ = "veiculos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"))
    placa: Mapped[str | None] = mapped_column(String(10), unique=True, index=True, nullable=True)
    veiculo: Mapped[str] = mapped_column(String(100))
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
