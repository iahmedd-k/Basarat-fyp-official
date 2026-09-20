"""Prediction ORM model — stores every forecast served by the API.

Preserves individual GRU and XGB model outputs alongside the ensemble
result for audit trail and model comparison purposes.
"""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    horizon: Mapped[str] = mapped_column(String(10), default="1D")
    predicted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    predicted_direction: Mapped[str] = mapped_column(String(20), nullable=False)
    bullish_pct: Mapped[float] = mapped_column(Float, nullable=False)
    bearish_pct: Mapped[float] = mapped_column(Float, nullable=False)
    sideways_pct: Mapped[float] = mapped_column(Float, nullable=False)
    top_class_probability: Mapped[float] = mapped_column(Float, nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    target_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    model_version: Mapped[str] = mapped_column(String(50), default="gru_v1")
    actual_direction: Mapped[str | None] = mapped_column(String(20), nullable=True)
    was_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Individual model outputs (for audit trail)
    gru_direction: Mapped[str | None] = mapped_column(String(20), nullable=True)
    gru_bullish_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    gru_bearish_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    gru_sideways_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    gru_gap_pp: Mapped[float | None] = mapped_column(Float, nullable=True)
    xgb_direction: Mapped[str | None] = mapped_column(String(20), nullable=True)
    xgb_bullish_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    xgb_bearish_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    xgb_sideways_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    xgb_gap_pp: Mapped[float | None] = mapped_column(Float, nullable=True)
    gate_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
