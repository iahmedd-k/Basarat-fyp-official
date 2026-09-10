from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid4().hex)
    portfolio_id: Mapped[str] = mapped_column(String(36), ForeignKey("portfolios.id"), index=True, nullable=False)
    var_95: Mapped[float | None] = mapped_column(Numeric(12, 4))
    var_99: Mapped[float | None] = mapped_column(Numeric(12, 4))
    cvar_95: Mapped[float | None] = mapped_column(Numeric(12, 4))
    sharpe_ratio: Mapped[float | None] = mapped_column(Numeric(8, 4))
    beta: Mapped[float | None] = mapped_column(Numeric(8, 4))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
