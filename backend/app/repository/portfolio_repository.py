from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.portfolio import Transaction, PriceCache, WatchlistItem, TransactionType
from app.models.stock import Stock


class PortfolioRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # Transaction CRUD
    async def create_transaction(
        self,
        user_id: str,
        symbol: str,
        type: TransactionType,
        quantity: int,
        price: float,
        fees: float,
        transaction_date: date,
    ) -> Transaction:
        transaction = Transaction(
            user_id=user_id,
            symbol=symbol.upper(),
            type=type,
            quantity=quantity,
            price=Decimal(str(price)),
            fees=Decimal(str(fees)),
            transaction_date=transaction_date,
        )
        self.db.add(transaction)
        await self.db.flush()
        await self.db.refresh(transaction)
        return transaction

    async def get_transaction(self, transaction_id: str, user_id: str) -> Optional[Transaction]:
        result = await self.db.execute(
            select(Transaction).where(
                Transaction.id == transaction_id,
                Transaction.user_id == user_id,
            )
        )
        return result.scalars().first()

    async def list_transactions(
        self,
        user_id: str,
        symbol: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[Transaction], int]:
        query = select(Transaction).where(Transaction.user_id == user_id)
        if symbol:
            query = query.where(Transaction.symbol == symbol.upper())
        query = query.order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc())

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Paginate
        query = query.offset((page - 1) * limit).limit(limit)
        result = await self.db.execute(query)
        transactions = list(result.scalars().all())

        return transactions, total

    async def update_transaction(
        self,
        transaction: Transaction,
        quantity: Optional[int] = None,
        price: Optional[float] = None,
        fees: Optional[float] = None,
        transaction_date: Optional[date] = None,
    ) -> Transaction:
        if quantity is not None:
            transaction.quantity = quantity
        if price is not None:
            transaction.price = Decimal(str(price))
        if fees is not None:
            transaction.fees = Decimal(str(fees))
        if transaction_date is not None:
            transaction.transaction_date = transaction_date
        await self.db.flush()
        await self.db.refresh(transaction)
        return transaction

    async def delete_transaction(self, transaction: Transaction) -> None:
        await self.db.delete(transaction)
        await self.db.flush()

    # Holdings computation (derived from transactions)
    async def get_user_holdings(self, user_id: str) -> list[dict]:
        """
        Compute holdings from transactions using average-cost method.
        Returns list of dicts with: symbol, quantity, avg_cost, total_invested, transactions
        """
        result = await self.db.execute(
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .order_by(Transaction.symbol, Transaction.transaction_date, Transaction.created_at)
        )
        transactions = list(result.scalars().all())

        holdings = {}
        for txn in transactions:
            sym = txn.symbol
            if sym not in holdings:
                holdings[sym] = {
                    "symbol": sym,
                    "quantity": 0,
                    "total_cost": Decimal("0"),
                    "transactions": [],
                }
            h = holdings[sym]
            if txn.type == TransactionType.BUY:
                h["quantity"] += txn.quantity
                h["total_cost"] += (txn.price * txn.quantity) + txn.fees
            else:  # SELL
                h["quantity"] -= txn.quantity
                # For average cost, we don't reduce total_cost proportionally
                # The average cost remains the same for remaining shares
            h["transactions"].append(txn)

        # Filter out zero-quantity holdings and compute avg_cost
        result_holdings = []
        for h in holdings.values():
            if h["quantity"] > 0:
                avg_cost = float(h["total_cost"] / h["quantity"]) if h["quantity"] > 0 else 0
                result_holdings.append({
                    "symbol": h["symbol"],
                    "quantity": h["quantity"],
                    "avg_cost": avg_cost,
                    "invested_value": float(h["total_cost"]),
                    "transactions": h["transactions"],
                })

        return result_holdings

    async def get_holding_by_symbol(self, user_id: str, symbol: str) -> Optional[dict]:
        holdings = await self.get_user_holdings(user_id)
        for h in holdings:
            if h["symbol"] == symbol.upper():
                return h
        return None

    async def get_net_quantity(self, user_id: str, symbol: str) -> int:
        """Get net quantity held for a symbol (for sell validation)"""
        result = await self.db.execute(
            select(
                func.sum(
                    func.case(
                        (Transaction.type == TransactionType.BUY, Transaction.quantity),
                        else_=-Transaction.quantity,
                    )
                )
            ).where(
                Transaction.user_id == user_id,
                Transaction.symbol == symbol.upper(),
            )
        )
        net_qty = result.scalar() or 0
        return int(net_qty)

    # PriceCache operations
    async def get_price_cache(self, symbol: str) -> Optional[PriceCache]:
        result = await self.db.execute(
            select(PriceCache).where(PriceCache.symbol == symbol.upper())
        )
        return result.scalars().first()

    async def upsert_price_cache(
        self,
        symbol: str,
        ldcp: float,
        current_price: float,
        change: float,
        change_percent: float,
        market_status: str,
    ) -> PriceCache:
        cache = await self.get_price_cache(symbol)
        if cache:
            cache.ldcp = Decimal(str(ldcp))
            cache.current_price = Decimal(str(current_price))
            cache.change = Decimal(str(change))
            cache.change_percent = Decimal(str(change_percent))
            cache.market_status = market_status
        else:
            cache = PriceCache(
                symbol=symbol.upper(),
                ldcp=Decimal(str(ldcp)),
                current_price=Decimal(str(current_price)),
                change=Decimal(str(change)),
                change_percent=Decimal(str(change_percent)),
                market_status=market_status,
            )
            self.db.add(cache)
        await self.db.flush()
        await self.db.refresh(cache)
        return cache

    async def get_bulk_price_cache(self, symbols: list[str]) -> dict[str, PriceCache]:
        if not symbols:
            return {}
        upper_symbols = [s.upper() for s in symbols]
        result = await self.db.execute(
            select(PriceCache).where(PriceCache.symbol.in_(upper_symbols))
        )
        return {p.symbol: p for p in result.scalars().all()}

    # Watchlist operations (optional)
    async def get_watchlist(self, user_id: str) -> list[WatchlistItem]:
        result = await self.db.execute(
            select(WatchlistItem).where(WatchlistItem.user_id == user_id)
        )
        return list(result.scalars().all())

    async def add_to_watchlist(self, user_id: str, symbol: str) -> WatchlistItem:
        item = WatchlistItem(user_id=user_id, symbol=symbol.upper())
        self.db.add(item)
        await self.db.flush()
        await self.db.refresh(item)
        return item

    async def remove_from_watchlist(self, user_id: str, symbol: str) -> bool:
        result = await self.db.execute(
            select(WatchlistItem).where(
                WatchlistItem.user_id == user_id,
                WatchlistItem.symbol == symbol.upper(),
            )
        )
        item = result.scalars().first()
        if item:
            await self.db.delete(item)
            await self.db.flush()
            return True
        return False