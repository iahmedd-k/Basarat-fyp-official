from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.portfolio import Portfolio, PortfolioHolding
from app.models.stock import Stock


class PortfolioRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_portfolio(self, user_id: str) -> Portfolio:
        result = await self.db.execute(
            select(Portfolio)
            .options(selectinload(Portfolio.holdings))
            .where(Portfolio.user_id == user_id)
            .limit(1)
        )
        portfolio = result.scalars().first()
        if portfolio is None:
            portfolio = Portfolio(user_id=user_id, name="My Portfolio")
            self.db.add(portfolio)
            await self.db.flush()
            await self.db.refresh(portfolio)
        return portfolio

    async def get_holding(self, holding_id: str, portfolio_id: str) -> PortfolioHolding | None:
        result = await self.db.execute(
            select(PortfolioHolding)
            .where(
                PortfolioHolding.id == holding_id,
                PortfolioHolding.portfolio_id == portfolio_id,
            )
        )
        return result.scalars().first()

    async def get_holding_with_stock(self, holding_id: str, portfolio_id: str) -> PortfolioHolding | None:
        result = await self.db.execute(
            select(PortfolioHolding)
            .options(selectinload(PortfolioHolding.portfolio))
            .where(
                PortfolioHolding.id == holding_id,
                PortfolioHolding.portfolio_id == portfolio_id,
            )
        )
        return result.scalars().first()

    async def get_stock_by_symbol(self, symbol: str) -> Stock | None:
        result = await self.db.execute(
            select(Stock).where(Stock.symbol == symbol.upper())
        )
        return result.scalars().first()

    async def create_holding(
        self,
        portfolio_id: str,
        stock_id: str,
        quantity: int,
        avg_buy_price: float,
        purchase_date: date | None = None,
    ) -> PortfolioHolding:
        holding = PortfolioHolding(
            portfolio_id=portfolio_id,
            stock_id=stock_id,
            quantity=quantity,
            avg_buy_price=Decimal(str(avg_buy_price)),
            purchase_date=purchase_date,
        )
        self.db.add(holding)
        await self.db.flush()
        await self.db.refresh(holding)
        return holding

    async def update_holding(
        self,
        holding: PortfolioHolding,
        quantity: int | None = None,
        avg_buy_price: float | None = None,
        purchase_date: date | None = None,
    ) -> PortfolioHolding:
        if quantity is not None:
            holding.quantity = quantity
        if avg_buy_price is not None:
            holding.avg_buy_price = Decimal(str(avg_buy_price))
        if purchase_date is not None:
            holding.purchase_date = purchase_date
        await self.db.flush()
        await self.db.refresh(holding)
        return holding

    async def delete_holding(self, holding: PortfolioHolding) -> None:
        await self.db.delete(holding)
        await self.db.flush()

    async def get_all_holdings(self, portfolio_id: str) -> list[PortfolioHolding]:
        result = await self.db.execute(
            select(PortfolioHolding)
            .where(PortfolioHolding.portfolio_id == portfolio_id)
            .order_by(PortfolioHolding.created_at.desc())
        )
        return list(result.scalars().all())

    async def upsert_holding(
        self,
        portfolio_id: str,
        stock_id: str,
        quantity: int,
        avg_buy_price: float,
        purchase_date: date | None = None,
    ) -> PortfolioHolding:
        existing = await self.get_holding_by_stock(portfolio_id, stock_id)
        if existing is not None:
            existing.quantity = quantity
            existing.avg_buy_price = Decimal(str(avg_buy_price))
            if purchase_date is not None:
                existing.purchase_date = purchase_date
            await self.db.flush()
            await self.db.refresh(existing)
            return existing
        return await self.create_holding(
            portfolio_id=portfolio_id,
            stock_id=stock_id,
            quantity=quantity,
            avg_buy_price=avg_buy_price,
            purchase_date=purchase_date,
        )

    async def get_holding_by_stock(self, portfolio_id: str, stock_id: str) -> PortfolioHolding | None:
        result = await self.db.execute(
            select(PortfolioHolding).where(
                PortfolioHolding.portfolio_id == portfolio_id,
                PortfolioHolding.stock_id == stock_id,
            )
        )
        return result.scalars().first()
