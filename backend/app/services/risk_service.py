from sqlalchemy.ext.asyncio import AsyncSession

from app.models.risk import RiskAssessment
from app.models.portfolio import Portfolio, PortfolioHolding
from sqlalchemy import select


class RiskService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_portfolio_risk(self, user_id: str) -> RiskAssessment | None:
        portfolio_result = await self.db.execute(
            select(Portfolio).where(Portfolio.user_id == user_id).limit(1)
        )
        portfolio = portfolio_result.scalars().first()
        if not portfolio:
            return None

        result = await self.db.execute(
            select(RiskAssessment)
            .where(RiskAssessment.portfolio_id == portfolio.id)
            .order_by(RiskAssessment.created_at.desc())
            .limit(1)
        )
        return result.scalars().first()
