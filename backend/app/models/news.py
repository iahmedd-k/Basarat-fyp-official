from datetime import datetime, timezone
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy import DateTime, Index, Integer, Numeric, String, Text, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class NewsArticle(Base):
    __tablename__ = "news_articles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid4().hex)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    source: Mapped[str | None] = mapped_column(String(100))
    source_key: Mapped[str | None] = mapped_column(String(50), index=True, nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # official | news
    external_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    external_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    symbols: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array of PSX symbols (backward compat)
    company_names: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array of company names (backward compat)
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    event_type: Mapped[str | None] = mapped_column(String(50), index=True, nullable=True)
    sentiment_label: Mapped[str | None] = mapped_column(String(20), nullable=True)  # bullish|bearish|neutral
    sentiment_score: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    sentiment_method: Mapped[str | None] = mapped_column(String(20), nullable=True)  # finbert|eps_rule|none
    sentiment_status: Mapped[str | None] = mapped_column(String(20), nullable=True)  # ok|failed|skipped
    impact_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    published_at_estimated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=sa.func.now(),
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, onupdate=sa.func.now())

    # Relationship to link table
    article_symbols = relationship("NewsArticleSymbol", back_populates="article", lazy="selectin", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_news_source", "source"),
        Index("ix_news_sentiment_label", "sentiment_label"),
        Index("ix_news_articles_published_at_id_desc", "published_at", "id", postgresql_where=sa.text("published_at IS NOT NULL")),
        Index("ix_news_articles_source_key_published_at_desc", "source_key", "published_at"),
        UniqueConstraint("content_hash", name="uq_news_articles_content_hash"),
        # Unique constraint on (source_key, external_id) where external_id is not null - created via migration
    )


class NewsArticleSymbol(Base):
    __tablename__ = "news_article_symbols"

    article_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("news_articles.id", ondelete="CASCADE"), primary_key=True, nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), primary_key=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=sa.func.now())

    article = relationship("NewsArticle", back_populates="article_symbols", lazy="selectin")

    __table_args__ = (
        Index("ix_news_article_symbols_symbol_article_id", "symbol", "article_id"),
    )


class NewsSourceState(Base):
    __tablename__ = "news_source_state"

    source_key: Mapped[str] = mapped_column(String(50), primary_key=True, nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_new_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    healthy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now())


class SymbolBackfillState(Base):
    __tablename__ = "symbol_backfill_state"

    symbol: Mapped[str] = mapped_column(String(20), primary_key=True, nullable=False)
    last_backfill_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending|done|failed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class MarketHoursConfig(Base):
    __tablename__ = "market_hours_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    config_json: Mapped[dict] = mapped_column(sa.JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=sa.func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now())
