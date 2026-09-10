from datetime import datetime, date
from uuid import uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Forecast(Base):
    __tablename__ = "forecasts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid4().hex)
    stock_id: Mapped[str] = mapped_column(String(36), ForeignKey("stocks.id"), index=True, nullable=False)
    forecast_date: Mapped[date] = mapped_column(Date, nullable=False)
    predicted_close: Mapped[float] = mapped_column(Numeric(12, 2))
    confidence_lower: Mapped[float | None] = mapped_column(Numeric(12, 2))
    confidence_upper: Mapped[float | None] = mapped_column(Numeric(12, 2))
    model_version: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
