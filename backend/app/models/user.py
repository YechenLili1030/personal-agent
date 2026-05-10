import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, JSON, Integer, func
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    nickname: Mapped[str | None] = mapped_column(String(128), default=None)
    avatar: Mapped[str | None] = mapped_column(String(512), default=None)
    preferences: Mapped[dict | None] = mapped_column(JSON, default=None)
    status: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
