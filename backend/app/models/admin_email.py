from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AdminEmail(Base):
    __tablename__ = "admin_emails"

    email: Mapped[str] = mapped_column(String(255), primary_key=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
