from datetime import datetime, date, timezone
from decimal import Decimal
from enum import Enum as PyEnum
from uuid import uuid4

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TransactionType(str, PyEnum):
    BUY = "BUY"
    SELL = "SELL"


class PortfolioTransaction(Base):
    __tablename__ = "portfolio_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid4().hex)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), ForeignKey("stocks.symbol", ondelete="RESTRICT"), index=True, nullable=False)
    transaction_type: Mapped[TransactionType] = mapped_column(Enum(TransactionType), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    fee: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), default=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="portfolio_transactions", lazy="selectin")
    stock = relationship("Stock", lazy="selectin")

    __table_args__ = (
        Index("ix_portfolio_transactions_user_symbol", "user_id", "symbol"),
        Index("ix_portfolio_transactions_user_date", "user_id", "transaction_date"),
    )