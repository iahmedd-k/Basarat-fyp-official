from datetime import date, datetime
from decimal import Decimal
from enum import Enum as PyEnum
from uuid import uuid4

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TransactionType(PyEnum):
    BUY = "BUY"
    SELL = "SELL"


class MarketStatus(PyEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid4().hex)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    type: Mapped[TransactionType] = mapped_column(Enum(TransactionType), nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    fees: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PriceCache(Base):
    __tablename__ = "price_cache"
    __table_args__ = (UniqueConstraint("symbol", name="uq_price_cache_symbol"),)

    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    ldcp: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    current_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    change: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    change_percent: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=0)
    market_status: Mapped[MarketStatus] = mapped_column(Enum(MarketStatus), default=MarketStatus.CLOSED)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid4().hex)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "symbol", name="uq_watchlist_user_symbol"),)


# Legacy models for backward compatibility with risk_assessments table
class Portfolio(Base):
    __tablename__ = "portfolios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid4().hex)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), default="My Portfolio")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="portfolios")
    holdings = relationship("PortfolioHolding", back_populates="portfolio", lazy="selectin")


class PortfolioHolding(Base):
    __tablename__ = "portfolio_holdings"
    __table_args__ = (UniqueConstraint("portfolio_id", "stock_id", name="uq_portfolio_stock"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid4().hex)
    portfolio_id: Mapped[str] = mapped_column(String(36), ForeignKey("portfolios.id"), index=True, nullable=False)
    stock_id: Mapped[str] = mapped_column(String(36), ForeignKey("stocks.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(default=0)
    avg_buy_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    purchase_date: Mapped[date] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    portfolio = relationship("Portfolio", back_populates="holdings")