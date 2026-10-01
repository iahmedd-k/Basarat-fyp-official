from datetime import datetime, date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint, JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Stock(Base):
    __tablename__ = "stocks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid4().hex)
    symbol: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(100))
    market: Mapped[str] = mapped_column(String(50), default="PSX")
    is_active: Mapped[bool] = mapped_column(default=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StockPrice(Base):
    __tablename__ = "stock_prices"
    __table_args__ = (UniqueConstraint("stock_id", "date", name="uq_stock_prices_stock_date"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid4().hex)
    stock_id: Mapped[str] = mapped_column(String(36), ForeignKey("stocks.id"), index=True, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    open: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    high: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    low: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    close: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    volume: Mapped[int] = mapped_column(default=0)
    adjusted_close: Mapped[Decimal] = mapped_column(Numeric(12, 2))


class StockReferenceData(Base):
    """Latest durable, source-backed company/profile/fundamental/dividend payloads."""

    __tablename__ = "stock_reference_data"

    stock_id: Mapped[str] = mapped_column(String(36), ForeignKey("stocks.id", ondelete="CASCADE"), primary_key=True)
    profile_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    fundamentals_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    dividends_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    fundamentals_response_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    profile_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fundamentals_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dividends_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class StockDailyAnalysis(Base):
    """Durable per-symbol daily technical, risk, and recommendation snapshot."""

    __tablename__ = "stock_daily_analysis"
    __table_args__ = (UniqueConstraint("stock_id", "as_of_date", name="uq_stock_daily_analysis_stock_date"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid4().hex)
    stock_id: Mapped[str] = mapped_column(String(36), ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    technical_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    risk_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    recommendation_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
