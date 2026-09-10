import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TipoCliente(str, enum.Enum):
    mensalista = "mensalista"
    rotativo = "rotativo"
    visitante = "visitante"
    prestador = "prestador"


class Ocupante(Base):
    __tablename__ = "ocupantes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vaga_id: Mapped[str] = mapped_column(ForeignKey("vagas.id"))
    nome: Mapped[str] = mapped_column(String(100))
    placa: Mapped[str] = mapped_column(String(10))
    veiculo: Mapped[str] = mapped_column(String(100))
    tipo_cliente: Mapped[TipoCliente] = mapped_column(SAEnum(TipoCliente, name="tipo_cliente"))
    hora_entrada: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    observacoes: Mapped[str | None] = mapped_column(Text)
    operador_id: Mapped[str] = mapped_column(String(200))  # Auth0 sub
