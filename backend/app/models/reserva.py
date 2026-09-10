from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Reserva(Base):
    __tablename__ = "reservas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vaga_id: Mapped[str] = mapped_column(ForeignKey("vagas.id"))
    nome: Mapped[str] = mapped_column(String(100))
    telefone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(100))
    placa: Mapped[str | None] = mapped_column(String(10))
    inicio: Mapped[datetime] = mapped_column(DateTime)
    fim: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="ativa")
    canal: Mapped[str] = mapped_column(String(20), default="webapp")
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
