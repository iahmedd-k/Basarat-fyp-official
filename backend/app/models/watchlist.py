from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Watchlist(Base):
    __tablename__ = "watchlists"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid4().hex)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), default="My Watchlist", nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("User", back_populates="watchlists", lazy="selectin")
    items = relationship(
        "WatchlistItem",
        back_populates="watchlist",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="WatchlistItem.created_at.desc()",
    )

    __table_args__ = (
        Index("ix_watchlists_user_id_is_default", "user_id", "is_default"),
    )


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid4().hex)
    watchlist_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("watchlists.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    symbol: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    added_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    target_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    watchlist = relationship("Watchlist", back_populates="items", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("watchlist_id", "symbol", name="uq_watchlist_symbol"),
        Index("ix_watchlist_items_watchlist_symbol", "watchlist_id", "symbol"),
    )
