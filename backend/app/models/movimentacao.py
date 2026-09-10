from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Movimentacao(Base):
    __tablename__ = "movimentacoes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vaga_id: Mapped[str] = mapped_column(ForeignKey("vagas.id"))
    tipo: Mapped[str] = mapped_column(String(20))  # entrada/saida/reserva
    placa: Mapped[str] = mapped_column(String(10))
    motorista: Mapped[str] = mapped_column(String(100))
    veiculo: Mapped[str] = mapped_column(String(100))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    operador_id: Mapped[str] = mapped_column(String(200))
    tempo_permanencia_min: Mapped[int | None] = mapped_column(Integer)
    sincronizado: Mapped[bool] = mapped_column(Boolean, default=True)
