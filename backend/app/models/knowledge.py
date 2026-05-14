import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, JSON, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class KnowledgeDoc(Base):
    __tablename__ = "knowledge_docs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[str] = mapped_column(String(32), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    file_path: Mapped[str | None] = mapped_column(String(1024), default=None)
    status: Mapped[str] = mapped_column(String(16), default="uploading")
    inspect: Mapped[bool] = mapped_column(default=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[str | None] = mapped_column(Text, default=None)
    category: Mapped[str | None] = mapped_column(String(128), default=None)
    graph_status: Mapped[str | None] = mapped_column(String(16), default=None)  # building/built/failed
    error_msg: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class DocChunk(Base):
    __tablename__ = "doc_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    doc_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_metadata: Mapped[dict | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
