from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StockFundamentals(Base):
    __tablename__ = "stock_fundamentals"
    __table_args__ = (UniqueConstraint("symbol", name="uq_stock_fundamentals_symbol"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid4().hex)
    stock_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("stocks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    data_status: Mapped[str] = mapped_column(String(30), nullable=False, default="complete")
    source_as_of_date: Mapped[str | None] = mapped_column(String(30))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_successful_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refresh_run_id: Mapped[str | None] = mapped_column(String(36), index=True)
    payload_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_error: Mapped[str | None] = mapped_column(Text)


class FundamentalsRefreshRun(Base):
    __tablename__ = "fundamentals_refresh_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid4().hex)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    partial_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="running")
    error: Mapped[str | None] = mapped_column(Text)
