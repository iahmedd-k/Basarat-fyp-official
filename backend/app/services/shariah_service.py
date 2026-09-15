from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.shariah import ShariahScreening
from app.models.stock import Stock


class ShariahService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_screening(self, symbol: str) -> ShariahScreening | None:
        stock_result = await self.db.execute(
            select(Stock).where(Stock.symbol == symbol.upper())
        )
        stock = stock_result.scalars().first()
        if not stock:
            return None

        result = await self.db.execute(
            select(ShariahScreening)
            .where(ShariahScreening.stock_id == stock.id)
            .order_by(ShariahScreening.screened_at.desc())
            .limit(1)
        )
        return result.scalars().first()
