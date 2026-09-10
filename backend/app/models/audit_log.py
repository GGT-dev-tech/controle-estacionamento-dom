from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    usuario_id: Mapped[str] = mapped_column(String(200))
    acao: Mapped[str] = mapped_column(String(100))
    recurso: Mapped[str] = mapped_column(String(50))
    recurso_id: Mapped[str | None] = mapped_column(String(50))
    ip: Mapped[str | None] = mapped_column(String(45))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    detalhes: Mapped[str | None] = mapped_column(Text)  # JSON serializado
