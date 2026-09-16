"""Training Run — records every retraining attempt and its outcome."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TrainingRun(Base):
    __tablename__ = "training_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    run_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "weekly", "manual"
    status: Mapped[str] = mapped_column(String(20), default="running")  # running, completed, failed

    # What was trained
    gru_model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    xgb_model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Promotion decision
    promotion_decision: Mapped[str | None] = mapped_column(String(20), nullable=True)  # promoted, rejected, skipped
    promotion_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Candidate vs production comparison (JSON)
    comparison: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Timestamps
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
