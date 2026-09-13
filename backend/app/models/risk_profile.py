# app/models/risk_profile.py
import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RiskTolerance(str, enum.Enum):
    conservative = "Conservative"
    moderate = "Moderate"
    aggressive = "Aggressive"


class RiskProfile(Base):
    __tablename__ = "risk_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid4().hex)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), unique=True, index=True, nullable=False
    )
    risk_tolerance: Mapped[RiskTolerance] = mapped_column(
        Enum(RiskTolerance, name="risk_tolerance_enum"), nullable=False
    )
    sector_preferences: Mapped[list[str]] = mapped_column(ARRAY(String(100)), default=list)
    investment_horizon: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = relationship("User", back_populates="risk_profile")