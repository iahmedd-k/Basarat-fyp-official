import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.repository.portfolio_repository import PortfolioRepository
from app.services.portfolio.price_cache_service import PriceCacheService

logger = logging.getLogger(__name__)


class ValuationEngine:
    """Computes portfolio valuation, P&L, and holdings from transactions."""

    def __init__(
        self,
        db: AsyncSession,
        price_cache_service: Optional[PriceCacheService] = None,
        repo: Optional[PortfolioRepository] = None,
    ):
        self.db = db
        self.repo = repo or PortfolioRepository(db)
        self.price_cache = price_cache_service or PriceCacheService(db)

    async def compute_portfolio_summary(self, user_id: str) -> dict:
        """
        Compute full portfolio summary:
        - Group transactions by symbol
        - Compute average cost basis (average-cost method)
        - Fetch live prices
        - Calculate per-symbol and total valuation
        """
        holdings = await self.repo.get_user_holdings(user_id)

        if not holdings:
            return self._empty_summary()

        # Get live prices for all symbols
        symbols = [h["symbol"] for h in holdings]
        price_data = await self.price_cache.get_bulk_prices(symbols)

        # Compute per-holding details
        holding_details = []
        total_invested = Decimal("0")
        total_current_value = Decimal("0")
        total_day_change = Decimal("0")

        for h in holdings:
            symbol = h["symbol"]
            quantity = h["quantity"]
            avg_cost = Decimal(str(h["avg_cost"]))
            invested_value = Decimal(str(h["invested_value"]))

            price_info = price_data.get(symbol, {})
            current_price = Decimal(str(price_info.get("current_price", avg_cost)))
            change_percent = Decimal(str(price_info.get("change_percent", 0)))
            market_status = price_info.get("market_status", "CLOSED")

            current_value = current_price * quantity
            unrealized_pnl = current_value - invested_value
            unrealized_pnl_percent = (
                (unrealized_pnl / invested_value * 100) if invested_value > 0 else Decimal("0")
            )

            # Day change: approximate from change_percent * invested_value
            day_change = invested_value * (change_percent / 100)

            total_invested += invested_value
            total_current_value += current_value
            total_day_change += day_change

            weight = (
                (current_value / total_current_value * 100) if total_current_value > 0 else Decimal("0")
            )

            holding_details.append({
                "symbol": symbol,
                "quantity": quantity,
                "avg_cost": float(round(avg_cost, 2)),
                "invested_value": float(round(invested_value, 2)),
                "current_price": float(round(current_price, 2)),
                "current_value": float(round(current_value, 2)),
                "unrealized_pnl": float(round(unrealized_pnl, 2)),
                "unrealized_pnl_percent": float(round(unrealized_pnl_percent, 2)),
                "day_change_percent": float(round(change_percent, 2)),
                "weight_in_portfolio": float(round(weight, 2)),
                "market_status": market_status,
            })

        total_unrealized_pnl = total_current_value - total_invested
        total_unrealized_pnl_percent = (
            (total_unrealized_pnl / total_invested * 100) if total_invested > 0 else Decimal("0")
        )
        day_change_percent = (
            (total_day_change / total_invested * 100) if total_invested > 0 else Decimal("0")
        )

        return {
            "total_invested": float(round(total_invested, 2)),
            "total_current_value": float(round(total_current_value, 2)),
            "total_unrealized_pnl": float(round(total_unrealized_pnl, 2)),
            "total_unrealized_pnl_percent": float(round(total_unrealized_pnl_percent, 2)),
            "day_change": float(round(total_day_change, 2)),
            "day_change_percent": float(round(day_change_percent, 2)),
            "holdings": holding_details,
            "generated_at": datetime.utcnow(),
        }

    async def compute_holding_detail(self, user_id: str, symbol: str) -> Optional[dict]:
        """Compute detailed holding info for a single symbol."""
        holding = await self.repo.get_holding_by_symbol(user_id, symbol)

        if not holding:
            return None

        # Get live price
        price_info = await self.price_cache.get_price(symbol)
        current_price = Decimal(str(price_info.get("current_price", holding["avg_cost"])))
        change_percent = Decimal(str(price_info.get("change_percent", 0)))
        market_status = price_info.get("market_status", "CLOSED")

        quantity = holding["quantity"]
        avg_cost = Decimal(str(holding["avg_cost"]))
        invested_value = avg_cost * quantity
        current_value = current_price * quantity
        unrealized_pnl = current_value - invested_value
        unrealized_pnl_percent = (
            (unrealized_pnl / invested_value * 100) if invested_value > 0 else Decimal("0")
        )

        # Format transactions
        transactions = []
        for txn in holding["transactions"]:
            transactions.append({
                "id": txn.id,
                "type": txn.type.value,
                "quantity": txn.quantity,
                "price": float(txn.price),
                "fees": float(txn.fees),
                "transaction_date": txn.transaction_date,
            })

        return {
            "symbol": symbol.upper(),
            "quantity": quantity,
            "avg_cost": float(round(avg_cost, 2)),
            "current_price": float(round(current_price, 2)),
            "unrealized_pnl": float(round(unrealized_pnl, 2)),
            "unrealized_pnl_percent": float(round(unrealized_pnl_percent, 2)),
            "transactions": transactions,
            "price_history_ref": f"/api/prices/{symbol.upper()}/history",
        }

    async def validate_sell_quantity(self, user_id: str, symbol: str, sell_quantity: int) -> tuple[bool, str]:
        """Validate that user has enough shares to sell."""
        net_quantity = await self.repo.get_net_quantity(user_id, symbol)
        if sell_quantity > net_quantity:
            return False, f"Cannot sell {sell_quantity} shares, only {net_quantity} held."
        return True, ""

    def _empty_summary(self) -> dict:
        return {
            "total_invested": 0.0,
            "total_current_value": 0.0,
            "total_unrealized_pnl": 0.0,
            "total_unrealized_pnl_percent": 0.0,
            "day_change": 0.0,
            "day_change_percent": 0.0,
            "holdings": [],
            "generated_at": datetime.utcnow(),
        }