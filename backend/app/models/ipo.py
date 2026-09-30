from datetime import datetime, date
from uuid import uuid4
from sqlalchemy import String, Text, Float, Boolean, DateTime, Date, BigInteger, Index, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IPO(Base):
    __tablename__ = "ipos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid4().hex)
    symbol: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sector: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(40), default="UPCOMING", nullable=False, index=True
    )  # UPCOMING, OPEN_FOR_BOOK_BUILDING, OPEN_FOR_PUBLIC_SUBSCRIPTION, LISTED, CLOSED

    issue_size_shares: Mapped[float | None] = mapped_column(Float, nullable=True)
    issue_size_pkr: Mapped[float | None] = mapped_column(Float, nullable=True)
    floor_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    strike_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    listing_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_price: Mapped[float | None] = mapped_column(Float, nullable=True)

    book_building_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    book_building_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    public_subscription_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    public_subscription_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    listing_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)

    lead_manager: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_shariah_compliant: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    prospectus_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    subscription_multiplier: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.utcnow()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), default=lambda: datetime.utcnow()
    )

    __table_args__ = (
        Index("ix_ipos_status_listing_date", "status", "listing_date"),
    )
