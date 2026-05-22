import uuid
from datetime import datetime, date
from sqlalchemy import String, DateTime, JSON, Date, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from ..core.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class DailyBriefing(Base):
    __tablename__ = "daily_briefings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    news_items: Mapped[list | None] = mapped_column(JSON, default=None)
    keywords_used: Mapped[list | None] = mapped_column(JSON, default=None)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_user_date"),
    )
