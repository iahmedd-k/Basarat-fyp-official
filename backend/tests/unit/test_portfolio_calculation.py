from datetime import date, timedelta
from decimal import Decimal
from time import perf_counter
from uuid import uuid4

from app.models.portfolio import PortfolioTransaction, TransactionType
from app.services.portfolio_calculation import calculate_performance_time_series


def _transaction(
    symbol: str,
    transaction_type: TransactionType,
    quantity: str,
    transaction_date: date,
) -> PortfolioTransaction:
    return PortfolioTransaction(
        id=uuid4().hex,
        user_id="test-user",
        symbol=symbol,
        transaction_type=transaction_type,
        quantity=Decimal(quantity),
        price=Decimal("1"),
        fee=Decimal("0"),
        transaction_date=transaction_date,
    )


def test_performance_time_series_values_at_each_price_date():
    start = date(2026, 1, 1)
    transactions = [
        _transaction("A", TransactionType.SELL, "3", start + timedelta(days=2)),
        _transaction("B", TransactionType.BUY, "5", start + timedelta(days=1)),
        _transaction("A", TransactionType.BUY, "10", start),
    ]
    prices = {
        "A": {
            start: Decimal("2"),
            start + timedelta(days=1): Decimal("3"),
            start + timedelta(days=3): Decimal("4"),
        },
        "B": {
            start + timedelta(days=1): Decimal("10"),
            start + timedelta(days=2): Decimal("11"),
        },
    }

    result = calculate_performance_time_series(transactions, prices)

    assert result == [
        {"date": "2026-01-01", "value": Decimal("20.00")},
        {"date": "2026-01-02", "value": Decimal("80.00")},
        {"date": "2026-01-03", "value": Decimal("76.00")},
        {"date": "2026-01-04", "value": Decimal("83.00")},
    ]


def test_performance_time_series_stays_under_one_second_for_year_of_history():
    start = date(2025, 1, 1)
    symbols = [f"S{index}" for index in range(6)]
    transactions = [
        _transaction(
            symbols[index % len(symbols)],
            TransactionType.BUY,
            "1",
            start + timedelta(days=index % 250),
        )
        for index in range(5_000)
    ]
    prices = {
        symbol: {
            start + timedelta(days=day): Decimal("100")
            for day in range(365)
        }
        for symbol in symbols
    }

    started = perf_counter()
    result = calculate_performance_time_series(transactions, prices, "1Y")
    elapsed = perf_counter() - started

    assert len(result) == 365
    assert result[-1]["value"] == Decimal("500000.00")
    assert elapsed < 1.0, f"Historical valuation took {elapsed:.3f}s"


def test_calculate_position_multi_cycle_reentry():
    """Verify that after selling 100% of holdings, a new buy recalculates average cost without dilution."""
    from app.services.portfolio_calculation import calculate_position
    
    t1 = PortfolioTransaction(
        id=uuid4().hex, user_id="u1", symbol="SYS",
        transaction_type=TransactionType.BUY, quantity=Decimal("100"),
        price=Decimal("100.0"), fee=Decimal("0"), transaction_date=date(2026, 1, 1),
    )
    t2 = PortfolioTransaction(
        id=uuid4().hex, user_id="u1", symbol="SYS",
        transaction_type=TransactionType.SELL, quantity=Decimal("100"),
        price=Decimal("120.0"), fee=Decimal("0"), transaction_date=date(2026, 1, 5),
    )
    t3 = PortfolioTransaction(
        id=uuid4().hex, user_id="u1", symbol="SYS",
        transaction_type=TransactionType.BUY, quantity=Decimal("50"),
        price=Decimal("200.0"), fee=Decimal("0"), transaction_date=date(2026, 1, 10),
    )

    pos = calculate_position([t1, t2, t3])
    assert pos.remaining_quantity == Decimal("50.0000")
    assert pos.average_cost == Decimal("200.0000")
    assert pos.total_cost_basis == Decimal("10000.0000")
    assert pos.realized_pnl == Decimal("2000.0000")


def test_calculate_position_partial_sell_then_buy():
    """Verify weighted average cost when partially sold then bought at higher price."""
    from app.services.portfolio_calculation import calculate_position

    t1 = PortfolioTransaction(
        id=uuid4().hex, user_id="u1", symbol="OGDC",
        transaction_type=TransactionType.BUY, quantity=Decimal("100"),
        price=Decimal("100.0"), fee=Decimal("0"), transaction_date=date(2026, 1, 1),
    )
    t2 = PortfolioTransaction(
        id=uuid4().hex, user_id="u1", symbol="OGDC",
        transaction_type=TransactionType.SELL, quantity=Decimal("50"),
        price=Decimal("120.0"), fee=Decimal("0"), transaction_date=date(2026, 1, 5),
    )
    t3 = PortfolioTransaction(
        id=uuid4().hex, user_id="u1", symbol="OGDC",
        transaction_type=TransactionType.BUY, quantity=Decimal("50"),
        price=Decimal("200.0"), fee=Decimal("0"), transaction_date=date(2026, 1, 10),
    )

    pos = calculate_position([t1, t2, t3])
    # Remaining: 50 @ 100 + 50 @ 200 = 100 shares with cost basis 15,000 -> avg cost 150
    assert pos.remaining_quantity == Decimal("100.0000")
    assert pos.average_cost == Decimal("150.0000")
    assert pos.total_cost_basis == Decimal("15000.0000")
    assert pos.realized_pnl == Decimal("1000.0000")


def test_calculate_allocation_zero_division_guard():
    """Verify calculate_allocation handles empty or zero market value gracefully."""
    from app.services.portfolio_calculation import calculate_allocation

    empty_res = calculate_allocation({})
    assert empty_res["by_stock"] == []
    assert empty_res["by_sector"] == []

    zero_holding = {
        "OGDC": {
            "symbol": "OGDC",
            "market_value": Decimal("0"),
            "portfolio_weight": 0.0,
            "sector": "Oil & Gas",
        }
    }
    zero_res = calculate_allocation(zero_holding)
    assert len(zero_res["by_stock"]) == 1
    assert zero_res["by_stock"][0]["percentage"] == 0.0
