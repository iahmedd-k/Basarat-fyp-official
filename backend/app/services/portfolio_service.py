"""Portfolio Service - Business logic for portfolio operations."""

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    BadRequestError,
    NotFoundError,
    ServiceUnavailableError,
    ValidationFailedError,
)
from app.models.portfolio import PortfolioTransaction, TransactionType
from app.models.stock import Stock
from app.repository.portfolio_repository import PortfolioRepository
from app.services.market_service import MarketService
from app.services.portfolio_calculation import (
    InsufficientHoldingError,
    InvalidTransactionHistoryError,
    PortfolioError,
    SymbolNotFoundError,
    calculate_allocation,
    calculate_performance_time_series,
    calculate_portfolio_summary,
    calculate_position,
    validate_transaction_sequence,
)
from app.services.stock_service import StockService

logger = logging.getLogger(__name__)


class PortfolioService:
    def __init__(
        self,
        db: AsyncSession,
        repo: PortfolioRepository | None = None,
        stock_service: StockService | None = None,
        market_service: MarketService | None = None,
    ):
        self.db = db
        self.repo = repo or PortfolioRepository(db)
        self.stock_service = stock_service or StockService()
        self.market_service = market_service or MarketService()

    # ── Transaction Operations ────────────────────────────────────────────────

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
        """Create a new portfolio transaction with validation."""
        symbol = symbol.upper()

        # Validate symbol exists
        stock = await self._get_stock(symbol)
        if not stock:
            raise SymbolNotFoundError(f"Symbol '{symbol}' not found in stock universe")

        # Get existing transactions for this symbol
        existing_txns = await self.repo.get_user_transactions_for_symbol(user_id, symbol)

        # Create new transaction object for validation
        new_txn = PortfolioTransaction(
            user_id=user_id,
            symbol=symbol,
            transaction_type=transaction_type,
            quantity=quantity,
            price=price,
            fee=fee,
            transaction_date=transaction_date,
        )

        # Validate the sequence
        try:
            validate_transaction_sequence(existing_txns, new_txn)
        except ValueError as e:
            raise InsufficientHoldingError(str(e))

        # Create the transaction
        return await self.repo.create_transaction(
            user_id=user_id,
            symbol=symbol,
            transaction_type=transaction_type,
            quantity=quantity,
            price=price,
            fee=fee,
            transaction_date=transaction_date,
        )

    async def get_transaction(self, transaction_id: str, user_id: str) -> PortfolioTransaction:
        """Get a single transaction by ID."""
        txn = await self.repo.get_transaction(transaction_id, user_id)
        if not txn:
            raise NotFoundError("Transaction not found")
        return txn

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
        """Get paginated transaction history with optional filters."""
        return await self.repo.get_transactions(
            user_id=user_id,
            page=page,
            limit=limit,
            symbol=symbol,
            transaction_type=transaction_type,
            from_date=from_date,
            to_date=to_date,
        )

    async def update_transaction(
        self,
        transaction_id: str,
        user_id: str,
        quantity: Decimal | None = None,
        price: Decimal | None = None,
        fee: Decimal | None = None,
        transaction_date: date | None = None,
    ) -> PortfolioTransaction:
        """Update a transaction with full re-validation of the symbol's history."""
        txn = await self.get_transaction(transaction_id, user_id)
        symbol = txn.symbol

        # Build updated transaction for validation
        updated_txn = PortfolioTransaction(
            id=txn.id,
            user_id=user_id,
            symbol=symbol,
            transaction_type=txn.transaction_type,
            quantity=quantity if quantity is not None else txn.quantity,
            price=price if price is not None else txn.price,
            fee=fee if fee is not None else txn.fee,
            transaction_date=transaction_date if transaction_date is not None else txn.transaction_date,
            created_at=txn.created_at,
            updated_at=datetime.utcnow(),
        )

        # Get other transactions for this symbol
        other_txns = await self.repo.get_user_transactions_for_symbol(
            user_id, symbol, exclude_transaction_id=transaction_id
        )

        # Validate the complete sequence
        try:
            validate_transaction_sequence(other_txns, updated_txn, exclude_txn_id=transaction_id)
        except ValueError as e:
            raise InvalidTransactionHistoryError(str(e))

        # Perform the update
        updated = await self.repo.update_transaction(
            transaction_id=transaction_id,
            user_id=user_id,
            quantity=quantity,
            price=price,
            fee=fee,
            transaction_date=transaction_date,
        )
        if not updated:
            raise NotFoundError("Transaction not found after update")
        return updated

    async def delete_transaction(self, transaction_id: str, user_id: str) -> None:
        """Delete a transaction after validating the resulting history."""
        txn = await self.get_transaction(transaction_id, user_id)
        symbol = txn.symbol

        # Get other transactions for this symbol
        other_txns = await self.repo.get_user_transactions_for_symbol(
            user_id, symbol, exclude_transaction_id=transaction_id
        )

        # Validate the sequence without this transaction
        try:
            validate_transaction_sequence(other_txns, exclude_txn_id=transaction_id)
        except ValueError as e:
            raise InvalidTransactionHistoryError(
                f"Deleting this transaction would create invalid history: {e}"
            )

        # Delete the transaction
        deleted = await self.repo.delete_transaction(transaction_id, user_id)
        if not deleted:
            raise NotFoundError("Transaction not found")

    # ── Portfolio Calculations ────────────────────────────────────────────────

    async def get_portfolio(self, user_id: str) -> dict:
        """Get complete portfolio with summary and holdings."""
        # Get all transactions for the user
        all_txns, _ = await self.repo.get_transactions(user_id, limit=10000)
        
        if not all_txns:
            return {
                "summary": {
                    "total_invested": Decimal("0"),
                    "current_value": Decimal("0"),
                    "total_pnl": Decimal("0"),
                    "total_pnl_percent": 0.0,
                    "today_pnl": Decimal("0"),
                },
                "holdings": [],
                "updated_at": datetime.utcnow(),
            }

        # Group by symbol
        txns_by_symbol: dict[str, list[PortfolioTransaction]] = defaultdict(list)
        for txn in all_txns:
            txns_by_symbol[txn.symbol].append(txn)

        # Calculate position for each symbol
        positions = {}
        for symbol, txns in txns_by_symbol.items():
            positions[symbol] = calculate_position(txns)

        # Get active symbols
        active_symbols = [s for s, p in positions.items() if p.is_active]

        # Fetch current prices for all active symbols
        current_prices = {}
        price_dates = {}
        if active_symbols:
            quotes = self.stock_service.get_quote_batch(active_symbols)
            for q in quotes:
                sym = q.get("symbol", "").upper()
                if sym and q.get("current") is not None:
                    current_prices[sym] = Decimal(str(q["current"]))
                    price_dates[sym] = datetime.utcnow()

        # Calculate portfolio summary and holdings
        summary, holdings = calculate_portfolio_summary(
            positions, current_prices, price_dates
        )

        # Enrich holdings with stock metadata
        stock_info = await self.repo.get_stock_info(list(holdings.keys()))
        for symbol, holding in holdings.items():
            stock = stock_info.get(symbol)
            if stock:
                holding["company_name"] = stock.name
                holding["sector"] = stock.sector

        return {
            "summary": summary,
            "holdings": list(holdings.values()),
            "updated_at": datetime.utcnow(),
        }

    async def get_holdings(self, user_id: str) -> list[dict]:
        """Get active holdings only."""
        portfolio = await self.get_portfolio(user_id)
        return portfolio["holdings"]

    async def get_holding_detail(self, user_id: str, symbol: str) -> dict:
        """Get detailed view of a single holding including transactions."""
        symbol = symbol.upper()

        # Get all transactions for this symbol
        txns = await self.repo.get_user_transactions_for_symbol(user_id, symbol)
        if not txns:
            raise NotFoundError(f"No transactions found for {symbol}")

        # Calculate position
        position = calculate_position(txns)

        # Get current price
        current_price = None
        price_updated_at = None
        quote = self.stock_service.get_quote(symbol)
        if quote and quote.get("current") is not None:
            current_price = Decimal(str(quote["current"]))
            price_updated_at = datetime.utcnow()

        # Get stock info
        stock_info = await self.repo.get_stock_info([symbol])
        stock = stock_info.get(symbol)

        # Get all portfolio for total value (for weight calculation)
        portfolio = await self.get_portfolio(user_id)
        total_portfolio_value = portfolio["summary"]["current_value"]

        # Build holding detail
        price_info = calculate_holding_from_position(
            position, current_price, price_updated_at, total_portfolio_value
        )

        # Convert transactions to response format
        txn_responses = []
        for t in txns:
            txn_responses.append({
                "id": t.id,
                "symbol": t.symbol,
                "transaction_type": t.transaction_type.value,
                "quantity": t.quantity,
                "price": t.price,
                "fee": t.fee,
                "transaction_date": t.transaction_date,
                "created_at": t.created_at,
                "updated_at": t.updated_at,
            })

        return {
            "symbol": symbol,
            "company_name": stock.name if stock else None,
            "sector": stock.sector if stock else None,
            "quantity": position.remaining_quantity,
            "average_cost": position.average_cost,
            "current_price": current_price,
            "invested_value": position.total_cost_basis,
            "market_value": price_info["market_value"],
            "unrealized_pnl": price_info["unrealized_pnl"],
            "unrealized_pnl_percent": price_info["unrealized_pnl_percent"],
            "realized_pnl": position.realized_pnl,
            "portfolio_weight": price_info["portfolio_weight"],
            "transactions": txn_responses,
            "price_updated_at": price_updated_at,
            "price_status": price_info["price_status"],
        }

    async def get_pnl(self, user_id: str) -> dict:
        """Get portfolio P&L breakdown."""
        portfolio = await self.get_portfolio(user_id)
        summary = portfolio["summary"]
        
        # Calculate realized P&L from all positions
        all_txns, _ = await self.repo.get_transactions(user_id, limit=10000)
        txns_by_symbol: dict[str, list[PortfolioTransaction]] = defaultdict(list)
        for txn in all_txns:
            txns_by_symbol[txn.symbol].append(txn)
        
        total_realized = Decimal("0")
        for symbol, txns in txns_by_symbol.items():
            pos = calculate_position(txns)
            total_realized += pos.realized_pnl
        
        return {
            "realized_pnl": total_realized,
            "unrealized_pnl": summary["total_pnl"] - total_realized,
            "total_pnl": summary["total_pnl"],
            "total_pnl_percent": summary["total_pnl_percent"],
            "today_pnl": summary["today_pnl"],
        }

    async def get_allocation(self, user_id: str) -> dict:
        """Get portfolio allocation by stock and sector."""
        portfolio = await self.get_portfolio(user_id)
        holdings = portfolio["holdings"]
        
        # Get stock info for sector mapping
        symbols = [h["symbol"] for h in holdings]
        stock_info = await self.repo.get_stock_info(symbols)
        
        return calculate_allocation({h["symbol"]: h for h in holdings}, stock_info)

    async def get_performance(
        self,
        user_id: str,
        period: Literal["1D", "1W", "1M", "3M", "6M", "1Y", "ALL"] = "1M",
    ) -> dict:
        """Get portfolio performance time series."""
        # For V1, return empty data as historical price data is not available
        # A full implementation would require storing daily portfolio snapshots
        # or having access to historical price data for all symbols
        
        period_days = {
            "1D": 1,
            "1W": 7,
            "1M": 30,
            "3M": 90,
            "6M": 180,
            "1Y": 365,
            "ALL": 3650,
        }
        
        days = period_days.get(period, 30)
        cutoff = date.today() - timedelta(days=days)
        
        # Get transactions after cutoff
        txns = await self.repo.get_transactions_after_date(user_id, cutoff)
        
        if not txns:
            return {"period": period, "data": []}
        
        # This is a placeholder - full implementation needs historical prices
        # For now, return current portfolio value as a single point
        portfolio = await self.get_portfolio(user_id)
        current_value = portfolio["summary"]["current_value"]
        
        return {
            "period": period,
            "data": [
                {
                    "date": date.today().isoformat(),
                    "value": current_value,
                }
            ],
        }

    # ── Helper Methods ────────────────────────────────────────────────────────

    async def _get_stock(self, symbol: str) -> Stock | None:
        """Get stock by symbol, using stock service cache first."""
        # Check stock service cache
        quote = self.stock_service.get_quote(symbol)
        if quote and quote.get("symbol"):
            # Stock exists in market data
            # Now get from DB for metadata
            stock_info = await self.repo.get_stock_info([symbol])
            return stock_info.get(symbol)
        
        # Fallback: check DB directly
        stock_info = await self.repo.get_stock_info([symbol])
        return stock_info.get(symbol)