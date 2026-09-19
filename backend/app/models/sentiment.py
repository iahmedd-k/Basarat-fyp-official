"""Sentiment analysis models."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SentimentResult(Base):
    """Sentiment analysis result for a news article."""

    __tablename__ = "sentiment_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid4().hex)
    news_article_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("news_articles.id", ondelete="CASCADE"), index=True, nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(20), ForeignKey("stocks.symbol"), index=True, nullable=False)
    model_name: Mapped[str] = mapped_column(String(50), nullable=False)  # finbert_api, heuristic
    label: Mapped[str] = mapped_column(String(20), nullable=False)  # positive, negative, neutral
    score: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)  # -1 to 1
    positive_score: Mapped[float | None] = mapped_column(Numeric(4, 3))
    neutral_score: Mapped[float | None] = mapped_column(Numeric(4, 3))
    negative_score: Mapped[float | None] = mapped_column(Numeric(4, 3))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    news_article = relationship("NewsArticle", lazy="selectin")
    stock = relationship("Stock", lazy="selectin")

    __table_args__ = (
        Index("ix_sentiment_results_symbol_created", "symbol", "created_at"),
        Index("ix_sentiment_results_news_symbol", "news_article_id", "symbol"),
    )


class SentimentAggregate(Base):
    """Pre-computed aggregated sentiment for a stock (rolling windows)."""

    __tablename__ = "sentiment_aggregates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid4().hex)
    symbol: Mapped[str] = mapped_column(String(20), ForeignKey("stocks.symbol"), index=True, nullable=False)
    period: Mapped[str] = mapped_column(String(10), nullable=False)  # 1D, 1W, 1M, 3M, 6M, 1Y
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    overall_score: Mapped[float] = mapped_column(Numeric(4, 3))
    label: Mapped[str] = mapped_column(String(20))  # positive, negative, neutral
    article_count: Mapped[int] = mapped_column(default=0)
    positive_ratio: Mapped[float | None] = mapped_column(Numeric(4, 3))
    neutral_ratio: Mapped[float | None] = mapped_column(Numeric(4, 3))
    negative_ratio: Mapped[float | None] = mapped_column(Numeric(4, 3))
    trend: Mapped[str | None] = mapped_column(String(20))  # improving, declining, stable
    daily_scores: Mapped[str | None] = mapped_column(Text)  # JSON array of {date, score, count}
    source_breakdown: Mapped[str | None] = mapped_column(Text)  # JSON {news: N, community: M}
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    stock = relationship("Stock", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("symbol", "period", "period_end", name="uq_sentiment_agg_symbol_period"),
        Index("ix_sentiment_aggregates_symbol_period", "symbol", "period"),
    )