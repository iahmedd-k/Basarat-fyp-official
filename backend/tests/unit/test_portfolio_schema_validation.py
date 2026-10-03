import pytest
from pydantic import ValidationError

from app.schemas.portfolio import (
    CompletedTradeCreate,
    TransactionCreate,
    TransactionUpdate,
)


def test_transaction_create_rejects_invalid_decimal():
    with pytest.raises(ValidationError):
        TransactionCreate(
            symbol="OGDC",
            transaction_type="BUY",
            quantity="not-a-number",
            price="230",
            transaction_date="2026-10-02",
        )


def test_completed_trade_rejects_invalid_decimal():
    with pytest.raises(ValidationError):
        CompletedTradeCreate(
            symbol="OGDC",
            quantity="100",
            buy_price="not-a-number",
            buy_date="2026-09-01",
            sell_price="250",
            sell_date="2026-09-15",
        )


def test_transaction_update_rejects_invalid_decimal():
    with pytest.raises(ValidationError):
        TransactionUpdate(price="not-a-number")
