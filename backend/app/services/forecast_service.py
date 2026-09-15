from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.forecast import Forecast
from app.models.stock import Stock


class ForecastService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_latest_forecast(self, symbol: str) -> Forecast | None:
        stock_result = await self.db.execute(
            select(Stock).where(Stock.symbol == symbol.upper())
        )
        stock = stock_result.scalars().first()
        if not stock:
            return None

        result = await self.db.execute(
            select(Forecast)
            .where(Forecast.stock_id == stock.id)
            .order_by(Forecast.created_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def get_forecast_history(self, symbol: str, limit: int = 30) -> list[Forecast]:
        stock_result = await self.db.execute(
            select(Stock).where(Stock.symbol == symbol.upper())
        )
        stock = stock_result.scalars().first()
        if not stock:
            return []

        result = await self.db.execute(
            select(Forecast)
            .where(Forecast.stock_id == stock.id)
            .order_by(Forecast.forecast_date.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
