from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shariah import ShariahScreening
from app.models.stock import Stock


class ShariahService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_stock_by_symbol(self, symbol: str) -> Stock | None:
        result = await self.db.execute(
            select(Stock).where(Stock.symbol == symbol.upper())
        )
        return result.scalars().first()

    async def get_latest_screening(self, stock_id: str) -> ShariahScreening | None:
        result = await self.db.execute(
            select(ShariahScreening)
            .where(ShariahScreening.stock_id == stock_id)
            .order_by(ShariahScreening.screened_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def get_screening(self, symbol: str) -> ShariahScreening | None:
        stock = await self.get_stock_by_symbol(symbol)
        if not stock:
            return None
        return await self.get_latest_screening(stock.id)

    def build_criteria(self, screening: ShariahScreening | None) -> list[dict]:
        debt_ratio = float(screening.debt_ratio) if screening and screening.debt_ratio else None
        interest_ratio = float(screening.interest_income_ratio) if screening and screening.interest_income_ratio else None

        return [
            {
                "name": "Debt Ratio",
                "threshold": 0.33,
                "value": debt_ratio,
                "passed": debt_ratio is not None and debt_ratio < 0.33,
            },
            {
                "name": "Interest Income Ratio",
                "threshold": 0.05,
                "value": interest_ratio,
                "passed": interest_ratio is not None and interest_ratio < 0.05,
            },
        ]

    @staticmethod
    def calculate_purification(holding_value: float, rate: float = 0.025) -> float:
        return round(holding_value * rate, 2)
