import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class StatusVaga(str, enum.Enum):
    livre = "livre"
    ocupada = "ocupada"
    reservada = "reservada"
    manutencao = "manutencao"


class Vaga(Base):
    __tablename__ = "vagas"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)  # ex: "S2-49"
    numero: Mapped[str] = mapped_column(String(10))
    andar: Mapped[str] = mapped_column(String(5))
    posicao: Mapped[str | None] = mapped_column(String(50))
    tipo: Mapped[str] = mapped_column(String(20), default="normal")
    status: Mapped[StatusVaga] = mapped_column(
        SAEnum(StatusVaga, name="status_vaga"), default=StatusVaga.livre
    )
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
