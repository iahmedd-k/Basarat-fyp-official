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
