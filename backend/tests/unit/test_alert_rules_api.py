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
