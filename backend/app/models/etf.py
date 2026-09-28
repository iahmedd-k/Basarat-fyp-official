from datetime import datetime, date
from uuid import uuid4
from sqlalchemy import String, Text, Float, Boolean, DateTime, Date, Index, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ETF(Base):
    __tablename__ = "etfs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid4().hex)
    symbol: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    fund_manager: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), default="Equity ETF", nullable=False)
    benchmark_index: Mapped[str] = mapped_column(String(100), nullable=False)
    
    is_shariah_compliant: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    expense_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    inception_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    total_assets_pkr: Mapped[float | None] = mapped_column(Float, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.utcnow()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), default=lambda: datetime.utcnow()
    )

    __table_args__ = (
        Index("ix_etfs_category", "category"),
        Index("ix_etfs_shariah_active", "is_shariah_compliant", "is_active"),
    )
