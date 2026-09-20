from datetime import datetime, date
from uuid import uuid4

from sqlalchemy import Date, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MarketEvent(Base):
    __tablename__ = "market_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid4().hex)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    symbol: Mapped[str | None] = mapped_column(String(20), index=True)
    company_name: Mapped[str | None] = mapped_column(String(255))
    event_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(100))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    metadata_json: Mapped[str | None] = mapped_column(Text)  # JSON for extra fields
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_event_date_range", "event_date", "event_type"),
    )
