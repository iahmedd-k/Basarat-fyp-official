from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.portfolio import PortfolioTransaction, TransactionType
from app.models.stock import Stock


class PortfolioRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_transaction(
        self,
        user_id: str,
        symbol: str,
        transaction_type: TransactionType,
        quantity: Decimal,
        price: Decimal,
        fee: Decimal,
        transaction_date: date,
    ) -> PortfolioTransaction:
        transaction = PortfolioTransaction(
            user_id=user_id,
            symbol=symbol.upper(),
            transaction_type=transaction_type,
            quantity=quantity,
            price=price,
            fee=fee,
            transaction_date=transaction_date,
        )
        self.db.add(transaction)
        await self.db.flush()
        await self.db.refresh(transaction)
        return transaction

    async def get_transaction(self, transaction_id: str, user_id: str) -> PortfolioTransaction | None:
        result = await self.db.execute(
            select(PortfolioTransaction)
            .options(selectinload(PortfolioTransaction.stock))
            .where(
                PortfolioTransaction.id == transaction_id,
                PortfolioTransaction.user_id == user_id,
            )
        )
        return result.scalars().first()

    async def get_transactions(
        self,
        user_id: str,
        page: int = 1,
        limit: int = 20,
        symbol: str | None = None,
        transaction_type: TransactionType | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> tuple[list[PortfolioTransaction], int]:
        stmt = select(PortfolioTransaction).where(PortfolioTransaction.user_id == user_id)

        if symbol:
            stmt = stmt.where(PortfolioTransaction.symbol == symbol.upper())
        if transaction_type:
            stmt = stmt.where(PortfolioTransaction.transaction_type == transaction_type)
        if from_date:
            stmt = stmt.where(PortfolioTransaction.transaction_date >= from_date)
        if to_date:
            stmt = stmt.where(PortfolioTransaction.transaction_date <= to_date)

        stmt = stmt.order_by(PortfolioTransaction.transaction_date.desc(), PortfolioTransaction.created_at.desc())

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = await self.db.scalar(count_stmt) or 0

        stmt = stmt.offset((page - 1) * limit).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def update_transaction(
        self,
        transaction_id: str,
        user_id: str,
        quantity: Decimal | None = None,
        price: Decimal | None = None,
        fee: Decimal | None = None,
        transaction_date: date | None = None,
    ) -> PortfolioTransaction | None:
        transaction = await self.get_transaction(transaction_id, user_id)
        if not transaction:
            return None

        if quantity is not None:
            transaction.quantity = quantity
        if price is not None:
            transaction.price = price
        if fee is not None:
            transaction.fee = fee
        if transaction_date is not None:
            transaction.transaction_date = transaction_date

        await self.db.flush()
        await self.db.refresh(transaction)
        return transaction

    async def delete_transaction(self, transaction_id: str, user_id: str) -> bool:
        result = await self.db.execute(
            delete(PortfolioTransaction).where(
                PortfolioTransaction.id == transaction_id,
                PortfolioTransaction.user_id == user_id,
            )
        )
        return result.rowcount > 0

    async def get_user_transactions_for_symbol(
        self,
        user_id: str,
        symbol: str,
        exclude_transaction_id: str | None = None,
    ) -> list[PortfolioTransaction]:
        """Get all transactions for a user's symbol, ordered by date then created_at."""
        stmt = (
            select(PortfolioTransaction)
            .where(
                PortfolioTransaction.user_id == user_id,
                PortfolioTransaction.symbol == symbol.upper(),
            )
            .order_by(PortfolioTransaction.transaction_date.asc(), PortfolioTransaction.created_at.asc())
        )
        if exclude_transaction_id:
            stmt = stmt.where(PortfolioTransaction.id != exclude_transaction_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_user_symbols(self, user_id: str) -> list[str]:
        """Get distinct symbols a user has transacted in."""
        result = await self.db.execute(
            select(PortfolioTransaction.symbol)
            .where(PortfolioTransaction.user_id == user_id)
            .distinct()
        )
        return [row[0] for row in result.all()]

    async def get_stock_info(self, symbols: list[str]) -> dict[str, Stock]:
        """Get stock metadata for a list of symbols."""
        if not symbols:
            return {}
        result = await self.db.execute(
            select(Stock).where(Stock.symbol.in_([s.upper() for s in symbols]))
        )
        stocks = result.scalars().all()
        return {s.symbol: s for s in stocks}

    async def get_latest_transaction_date(self, user_id: str) -> date | None:
        result = await self.db.execute(
            select(func.max(PortfolioTransaction.transaction_date)).where(
                PortfolioTransaction.user_id == user_id
            )
        )
        return result.scalar()

    async def get_transactions_after_date(
        self,
        user_id: str,
        from_date: date,
    ) -> list[PortfolioTransaction]:
        """Get all transactions after a certain date for performance calculation."""
        result = await self.db.execute(
            select(PortfolioTransaction)
            .where(
                PortfolioTransaction.user_id == user_id,
                PortfolioTransaction.transaction_date >= from_date,
            )
            .order_by(PortfolioTransaction.transaction_date.asc(), PortfolioTransaction.created_at.asc())
        )
        return list(result.scalars().all())