from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ShariahScreening(Base):
    __tablename__ = "shariah_screenings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid4().hex)
    stock_id: Mapped[str] = mapped_column(String(36), ForeignKey("stocks.id"), index=True, nullable=False)
    is_shariah_compliant: Mapped[bool] = mapped_column(Boolean, default=False)
    debt_ratio: Mapped[float | None] = mapped_column(Numeric(6, 4))
    interest_income_ratio: Mapped[float | None] = mapped_column(Numeric(6, 4))
    screening_method: Mapped[str | None] = mapped_column(String(100))
    screened_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
