"""Unit tests for Alert Rules Stock Resolution and Helpers."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.alerts import _resolve_stock
from app.core.exceptions import NotFoundError
from app.models.stock import Stock


def test_resolve_stock_by_id_found():
    async def _test():
        db = AsyncMock(spec=AsyncSession)
        mock_stock = Stock(id="stock-123", symbol="SYS", name="Systems Limited")
        db.get.return_value = mock_stock

        res = await _resolve_stock(db, stock_id="stock-123")
        assert res == mock_stock
        db.get.assert_awaited_once_with(Stock, "stock-123")

    asyncio.run(_test())


def test_resolve_stock_by_id_not_found():
    async def _test():
        db = AsyncMock(spec=AsyncSession)
        db.get.return_value = None

        with pytest.raises(NotFoundError, match="Stock with id 'fake-id' not found."):
            await _resolve_stock(db, stock_id="fake-id")

    asyncio.run(_test())


def test_resolve_stock_by_symbol_found():
    async def _test():
        db = AsyncMock(spec=AsyncSession)
        mock_stock = Stock(id="stock-456", symbol="OGDC", name="Oil and Gas Development Co")

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_stock
        db.execute.return_value = mock_result

        res = await _resolve_stock(db, symbol="ogdc")
        assert res == mock_stock
        assert db.execute.called

    asyncio.run(_test())


def test_resolve_stock_by_symbol_not_found():
    async def _test():
        db = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        db.execute.return_value = mock_result

        with pytest.raises(NotFoundError, match="Stock with symbol 'UNKNOWN' not found."):
            await _resolve_stock(db, symbol="UNKNOWN")

    asyncio.run(_test())


def test_resolve_stock_by_name_found():
    async def _test():
        db = AsyncMock(spec=AsyncSession)
        mock_stock = Stock(id="stock-789", symbol="LUCK", name="Lucky Cement")

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_stock
        db.execute.return_value = mock_result

        res = await _resolve_stock(db, stock_name="Lucky")
        assert res == mock_stock
        assert db.execute.called

    asyncio.run(_test())


def test_resolve_stock_none_provided():
    async def _test():
        db = AsyncMock(spec=AsyncSession)
        res = await _resolve_stock(db)
        assert res is None

    asyncio.run(_test())


def test_quick_alert_rule_creation_both_directions():
    from app.api.v1.alerts import create_quick_alert_rule
    from app.models.user import User
    from app.schemas.auth import QuickAlertRuleCreate

    async def _test():
        db = AsyncMock(spec=AsyncSession)
        mock_user = User(id="user-999")
        mock_stock = Stock(id="stock-pso", symbol="PSO", name="Pakistan State Oil")

        mock_stock_res = MagicMock()
        mock_stock_res.scalars.return_value.first.return_value = mock_stock

        # Mock DB execute responses
        mock_price_res = MagicMock()
        mock_price_res.scalar.return_value = 250.0  # Base price Rs. 250.00

        def _execute_side_effect(stmt, *args, **kwargs):
            stmt_str = str(stmt)
            if "stocks" in stmt_str:
                return mock_stock_res
            if "stock_prices" in stmt_str:
                return mock_price_res
            return MagicMock()

        db.execute = AsyncMock(side_effect=_execute_side_effect)

        data = QuickAlertRuleCreate(symbol="PSO", percent_threshold=3.0, direction="both")
        res = await create_quick_alert_rule(data=data, user=mock_user, db=db)

        assert res.symbol == "PSO"
        assert res.base_price == 250.0
        assert res.percent_threshold == 3.0
        assert len(res.rules) == 2
        # Upper threshold: 250 * 1.03 = 257.50
        assert res.rules[0].condition == "price_above"
        assert res.rules[0].threshold == 257.50
        # Lower threshold: 250 * 0.97 = 242.50
        assert res.rules[1].condition == "price_below"
        assert res.rules[1].threshold == 242.50

    asyncio.run(_test())


def test_check_stock_alerts():
    from app.api.v1.alerts import check_stock_alerts
    from app.models.user import User
    from app.models.alert import AlertRule

    async def _test():
        db = AsyncMock(spec=AsyncSession)
        mock_user = User(id="user-999")
        mock_stock = Stock(id="stock-pso", symbol="PSO", name="Pakistan State Oil")
        mock_rule = AlertRule(
            id="rule-1",
            user_id="user-999",
            stock_id="stock-pso",
            condition="price_above",
            threshold=257.50,
            is_active=True,
        )

        mock_res = MagicMock()
        mock_res.all.return_value = [(mock_rule, mock_stock)]
        db.execute = AsyncMock(return_value=mock_res)

        res = await check_stock_alerts(symbol="PSO", user=mock_user, db=db)
        assert res.symbol == "PSO"
        assert res.has_active_alert is True
        assert len(res.rules) == 1
        assert res.rules[0].threshold == 257.50

    asyncio.run(_test())

