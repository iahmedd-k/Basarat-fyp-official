"""Portfolio Calculation Service

This module contains all financial calculations for the portfolio module.
Uses Decimal for all financial calculations to ensure precision.

Methodology:
- Average cost method (weighted average) for BUY transactions
- FIFO-like realized P/L for SELL transactions using current average cost
- All calculations use Decimal for precision
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

from app.models.portfolio import PortfolioTransaction, TransactionType
from app.models.stock import Stock


@dataclass
class Position:
    """Represents a single stock position derived from transaction history."""
    symbol: str
    total_bought: Decimal
    total_sold: Decimal
    remaining_quantity: Decimal
    total_cost_basis: Decimal
    average_cost: Decimal
    realized_pnl: Decimal
    transactions: list[PortfolioTransaction]

    @property
    def is_active(self) -> bool:
        return self.remaining_quantity > 0


def _round_decimal(value: Decimal, places: int = 4) -> Decimal:
    """Round Decimal to specified decimal places."""
    if value.is_nan() or value.is_infinite():
        return Decimal("0")
    quantize_exp = Decimal("0.1") ** places
    return value.quantize(quantize_exp, rounding=ROUND_HALF_UP)


def calculate_position(transactions: list[PortfolioTransaction]) -> Position:
    """
    Calculate a position from a list of transactions for a single symbol.
    
    Uses average cost method:
    - BUY: new_avg_cost = (old_cost + buy_qty * buy_price + fee) / (old_qty + buy_qty)
    - SELL: realized_pnl = sell_qty * (sell_price - avg_cost) - fee
    
    Args:
        transactions: List of transactions for a single symbol, ordered by date then created_at
        
    Returns:
        Position dataclass with all calculated fields
    """
    total_bought = Decimal("0")
    total_sold = Decimal("0")
    total_cost_basis = Decimal("0")
    realized_pnl = Decimal("0")
    average_cost = Decimal("0")

    def _sort_key(t):
        t_date = t.transaction_date
        if isinstance(t_date, datetime):
            t_date = t_date.date()
        created = t.created_at
        created_ts = created.timestamp() if (created is not None and hasattr(created, 'timestamp')) else 0.0
        type_order = 0 if t.transaction_type == TransactionType.BUY else 1
        return (t_date or date.min, type_order, created_ts)

    sorted_txns = sorted(transactions, key=_sort_key)

    for txn in sorted_txns:
        qty = txn.quantity
        price = txn.price
        fee = txn.fee or Decimal("0")

        if txn.transaction_type == TransactionType.BUY:
            # New total cost = old cost + (qty * price) + fee
            total_cost_basis += qty * price + fee
            total_bought += qty
            # Recalculate average cost
            if total_bought > 0:
                average_cost = total_cost_basis / total_bought

        elif txn.transaction_type == TransactionType.SELL:
            if total_bought - total_sold < qty:
                raise ValueError(
                    f"Insufficient holdings for SELL: "
                    f"available={total_bought - total_sold}, requested={qty}"
                )
            
            # Cost of sold shares at current average cost
            cost_of_sold = average_cost * qty
            # Proceeds from sale
            sell_proceeds = qty * price - fee
            # Realized P/L
            realized_pnl += sell_proceeds - cost_of_sold
            
            total_sold += qty
            total_cost_basis -= cost_of_sold
            
            remaining = total_bought - total_sold
            if remaining > 0:
                average_cost = total_cost_basis / remaining
            else:
                average_cost = Decimal("0")
                total_cost_basis = Decimal("0")

    remaining_quantity = total_bought - total_sold

    return Position(
        symbol=transactions[0].symbol if transactions else "",
        total_bought=total_bought,
        total_sold=total_sold,
        remaining_quantity=_round_decimal(remaining_quantity),
        total_cost_basis=_round_decimal(total_cost_basis),
        average_cost=_round_decimal(average_cost, 4),
        realized_pnl=_round_decimal(realized_pnl),
        transactions=transactions,
    )


def validate_transaction_sequence(
    transactions: list[PortfolioTransaction],
    new_txn: PortfolioTransaction | None = None,
    exclude_txn_id: str | None = None,
) -> list[PortfolioTransaction]:
    """
    Validate that a transaction sequence never creates negative holdings.
    
    Args:
        transactions: Existing transactions for the symbol
        new_txn: Optional new transaction to test
        exclude_txn_id: Optional transaction ID to exclude (for updates/deletes)
        
    Returns:
        Validated and sorted list of all transactions
        
    Raises:
        ValueError: If sequence would create negative holdings
    """
    all_txns = [t for t in transactions if exclude_txn_id is None or t.id != exclude_txn_id]
    if new_txn:
        all_txns.append(new_txn)
    
    def _sort_key(t):
        t_date = t.transaction_date
        if isinstance(t_date, datetime):
            t_date = t_date.date()
        created = t.created_at
        created_ts = created.timestamp() if (created is not None and hasattr(created, 'timestamp')) else 0.0
        # BUY (0) before SELL (1) on the same date
        type_order = 0 if t.transaction_type == TransactionType.BUY else 1
        return (t_date or date.min, type_order, created_ts)

    all_txns.sort(key=_sort_key)
    
    running_qty = Decimal("0")
    for txn in all_txns:
        if txn.transaction_type == TransactionType.BUY:
            running_qty += txn.quantity
        else:  # SELL
            if running_qty < txn.quantity:
                raise ValueError(
                    f"Transaction {txn.id} would create negative holdings: "
                    f"available={running_qty}, selling={txn.quantity}"
                )
            running_qty -= txn.quantity
    
    return all_txns


def calculate_holding_from_position(
    position: Position,
    current_price: Decimal | None,
    price_updated_at: datetime | None,
    total_portfolio_value: Decimal,
) -> dict:
    """Convert a Position to a holding dictionary for API response."""
    invested_value = position.total_cost_basis
    
    if current_price is not None and position.is_active:
        market_value = _round_decimal(position.remaining_quantity * current_price)
        unrealized_pnl = _round_decimal(market_value - invested_value)
        if invested_value > 0:
            unrealized_pnl_pct = float(_round_decimal(
                (unrealized_pnl / invested_value) * 100, 2
            ))
        else:
            unrealized_pnl_pct = 0.0
        
        portfolio_weight = 0.0
        if total_portfolio_value > 0:
            portfolio_weight = float(_round_decimal(
                (market_value / total_portfolio_value) * 100, 2
            ))
        
        return {
            "market_value": market_value,
            "unrealized_pnl": unrealized_pnl,
            "unrealized_pnl_percent": unrealized_pnl_pct,
            "portfolio_weight": portfolio_weight,
            "price_status": "AVAILABLE",
        }
    else:
        return {
            "market_value": None,
            "unrealized_pnl": None,
            "unrealized_pnl_percent": None,
            "portfolio_weight": None,
            "price_status": "UNAVAILABLE",
        }


def calculate_portfolio_summary(
    positions: dict[str, Position],
    current_prices: dict[str, Decimal | None],
    price_dates: dict[str, datetime | None],
) -> tuple[dict, dict]:
    """
    Calculate portfolio summary and holdings with current prices.
    
    Returns:
        Tuple of (summary_dict, holdings_dict)
    """
    total_invested = Decimal("0")
    total_current_value = Decimal("0")
    total_realized_pnl = Decimal("0")
    total_unrealized_pnl = Decimal("0")
    
    active_positions = {
        symbol: pos for symbol, pos in positions.items() if pos.is_active
    }
    
    # First pass: calculate total portfolio value
    for symbol, position in active_positions.items():
        total_invested += position.total_cost_basis
        total_realized_pnl += position.realized_pnl
        
        current_price = current_prices.get(symbol)
        if current_price is not None:
            total_current_value += position.remaining_quantity * current_price
        else:
            # If no price available, use cost basis as fallback for total value
            total_current_value += position.total_cost_basis
    
    # Second pass: calculate holdings
    holdings = {}
    for symbol, position in active_positions.items():
        current_price = current_prices.get(symbol)
        price_updated_at = price_dates.get(symbol)
        
        invested_value = position.total_cost_basis
        
        price_info = calculate_holding_from_position(
            position, current_price, price_updated_at, total_current_value
        )
        
        if current_price is not None:
            total_unrealized_pnl += price_info["unrealized_pnl"] or Decimal("0")
        
        holdings[symbol] = {
            "symbol": symbol,
            "quantity": position.remaining_quantity,
            "average_cost": position.average_cost,
            "invested_value": invested_value,
            "realized_pnl": position.realized_pnl,
            "current_price": current_price,
            "price_updated_at": price_updated_at,
            **price_info,
        }
    
    total_pnl = total_realized_pnl + total_unrealized_pnl
    total_pnl_pct = 0.0
    if total_invested > 0:
        total_pnl_pct = float(_round_decimal((total_pnl / total_invested) * 100, 2))
    
    # Today's P&L would require previous day's prices - simplified for now
    today_pnl = Decimal("0")
    
    summary = {
        "total_invested": _round_decimal(total_invested),
        "current_value": _round_decimal(total_current_value),
        "total_pnl": _round_decimal(total_pnl),
        "total_pnl_percent": total_pnl_pct,
        "today_pnl": _round_decimal(today_pnl),
    }
    
    return summary, holdings


def calculate_allocation(
    holdings: dict[str, dict],
    stock_info: dict[str, Stock],
) -> dict[str, list[dict]]:
    """Calculate allocation by stock and by sector."""
    by_stock = []
    by_sector_dict = defaultdict(lambda: {"market_value": Decimal("0")})
    
    for symbol, holding in holdings.items():
        market_value = holding.get("market_value")
        if market_value is None:
            continue
            
        # By stock
        by_stock.append({
            "symbol": symbol,
            "market_value": market_value,
            "percentage": holding.get("portfolio_weight", 0),
        })
        
        # By sector
        stock = stock_info.get(symbol)
        sector = stock.sector if stock and stock.sector else "Unknown"
        by_sector_dict[sector]["market_value"] += market_value
    
    total_value = sum(h.get("market_value", Decimal("0")) for h in holdings.values() if h.get("market_value") is not None)
    
    by_sector = []
    for sector, data in by_sector_dict.items():
        pct = 0.0
        if total_value > 0:
            pct = float(_round_decimal((data["market_value"] / total_value) * 100, 2))
        by_sector.append({
            "sector": sector,
            "market_value": data["market_value"],
            "percentage": pct,
        })
    
    # Sort by market value descending
    by_stock.sort(key=lambda x: x["market_value"], reverse=True)
    by_sector.sort(key=lambda x: x["market_value"], reverse=True)
    
    return {
        "by_stock": by_stock,
        "by_sector": by_sector,
    }


def calculate_performance_time_series(
    transactions: list[PortfolioTransaction],
    historical_prices: dict[str, dict[date, Decimal]],
    period: str = "1M",
) -> list[dict]:
    """Value open positions at each available historical price date.

    The result is a market-value chart (not a time-weighted return): cash paid
    for purchases and cash received for sales are intentionally excluded.
    This makes the chart honest for a holdings screen and avoids inventing a
    return series when deposits/withdrawals are not modelled.
    """
    if not transactions or not historical_prices:
        return []
    all_dates = sorted({price_date for prices in historical_prices.values() for price_date in prices})
    points: list[dict] = []
    for point_date in all_dates:
        value = Decimal("0")
        quantities: dict[str, Decimal] = {}
        for transaction in transactions:
            if transaction.transaction_date > point_date:
                continue
            direction = Decimal("1") if transaction.transaction_type == TransactionType.BUY else Decimal("-1")
            quantities[transaction.symbol] = quantities.get(transaction.symbol, Decimal("0")) + direction * transaction.quantity
        for symbol, quantity in quantities.items():
            if quantity <= 0:
                continue
            prices = historical_prices.get(symbol, {})
            available_dates = [d for d in prices if d <= point_date]
            if available_dates:
                value += quantity * prices[max(available_dates)]
        points.append({"date": point_date.isoformat(), "value": _round_decimal(value, 2)})
    return points


# Portfolio-specific domain errors
class PortfolioError(Exception):
    """Base portfolio error."""
    pass


class InsufficientHoldingError(PortfolioError):
    """Raised when user tries to sell more than they own."""
    pass


class InvalidTransactionHistoryError(PortfolioError):
    """Raised when transaction sequence would be invalid."""
    pass


class SymbolNotFoundError(PortfolioError):
    """Raised when symbol doesn't exist in stock universe."""
    pass


class PriceUnavailableError(PortfolioError):
    """Raised when current price cannot be fetched."""
    pass
