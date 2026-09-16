"""Model Registry — tracks every trained model version with status and metrics."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ModelRegistry(Base):
    __tablename__ = "model_registry"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    model_version: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    model_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "gru" or "xgboost"
    horizon: Mapped[str] = mapped_column(String(10), default="1D")
    status: Mapped[str] = mapped_column(String(20), default="candidate")  # candidate, production, rejected, archived

    # Training info
    training_start_date: Mapped[str | None] = mapped_column(String(30), nullable=True)
    training_end_date: Mapped[str | None] = mapped_column(String(30), nullable=True)
    validation_start_date: Mapped[str | None] = mapped_column(String(30), nullable=True)
    validation_end_date: Mapped[str | None] = mapped_column(String(30), nullable=True)
    training_sample_count: Mapped[int] = mapped_column(Integer, default=0)
    validation_sample_count: Mapped[int] = mapped_column(Integer, default=0)

    # Metrics (JSON blob)
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Feature version reference
    feature_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Model artifact paths
    model_path: Mapped[str | None] = mapped_column(String(200), nullable=True)
    scaler_path: Mapped[str | None] = mapped_column(String(200), nullable=True)
    metadata_path: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Promotion info
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
