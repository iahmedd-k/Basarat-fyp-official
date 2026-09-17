from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NewsArticle(Base):
    __tablename__ = "news_articles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid4().hex)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), unique=True, nullable=False)
    source: Mapped[str | None] = mapped_column(String(100))
    source_type: Mapped[str | None] = mapped_column(String(50))  # official | financial_media
    summary: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    symbols: Mapped[str | None] = mapped_column(Text)  # JSON array of PSX symbols
    company_names: Mapped[str | None] = mapped_column(Text)  # JSON array of company names
    sector: Mapped[str | None] = mapped_column(String(100))
    event_type: Mapped[str | None] = mapped_column(String(50), index=True)
    sentiment_label: Mapped[str | None] = mapped_column(String(20))  # positive|negative|neutral
    sentiment_score: Mapped[float | None] = mapped_column(Numeric(4, 3))
    impact_score: Mapped[int | None] = mapped_column(Integer)  # 0-100
    published_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_news_source", "source"),
        Index("ix_news_sentiment_label", "sentiment_label"),
    )
