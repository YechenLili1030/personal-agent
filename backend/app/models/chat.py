import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, JSON, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(256), default="新对话")
    mode: Mapped[str] = mapped_column(String(16), default="normal")  # normal / rag
    status: Mapped[str] = mapped_column(String(16), default="active")  # active / archived
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    session_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user / assistant / system / tool
    content: Mapped[str] = mapped_column(Text, nullable=False)
    msg_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
