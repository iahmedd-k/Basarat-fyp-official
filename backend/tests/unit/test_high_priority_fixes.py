"""Focused regression tests for High-priority production gap fixes."""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.authorization import get_current_user
from app.core.exceptions import UnauthorizedError
from app.core.security import create_access_token, decode_token
from app.models.portfolio import PortfolioTransaction, TransactionType
from app.models.user import User
from app.services.portfolio_calculation import calculate_position


@pytest.mark.asyncio
async def test_access_token_includes_token_version_claim():
    token = create_access_token({"sub": "user-1", "tv": 3})
    payload = decode_token(token)
    assert payload is not None
    assert payload["type"] == "access"
    assert payload["tv"] == 3
    assert payload["sub"] == "user-1"


@pytest.mark.asyncio
async def test_get_current_user_rejects_stale_token_version():
    mock_user = MagicMock(spec=User)
    mock_user.is_active = True
    mock_user.token_version = 5
    mock_db = AsyncMock()
    mock_db.get.return_value = mock_user

    with pytest.raises(UnauthorizedError):
        await get_current_user(
            payload={"sub": "u1", "type": "access", "tv": 4},
            db=mock_db,
        )


@pytest.mark.asyncio
async def test_get_current_user_accepts_matching_token_version():
    mock_user = MagicMock(spec=User)
    mock_user.is_active = True
    mock_user.token_version = 5
    mock_db = AsyncMock()
    mock_db.get.return_value = mock_user

    result = await get_current_user(
        payload={"sub": "u1", "type": "access", "tv": 5},
        db=mock_db,
    )
    assert result is mock_user


def test_portfolio_avg_cost_after_partial_sell_then_buy():
    tx_a = PortfolioTransaction(
        id="a",
        user_id="u1",
        symbol="SYS",
        transaction_type=TransactionType.BUY,
        quantity=Decimal("100"),
        price=Decimal("10.00"),
        fee=Decimal("0"),
        transaction_date=date(2026, 1, 1),
    )
    tx_b = PortfolioTransaction(
        id="b",
        user_id="u1",
        symbol="SYS",
        transaction_type=TransactionType.SELL,
        quantity=Decimal("50"),
        price=Decimal("12.00"),
        fee=Decimal("0"),
        transaction_date=date(2026, 1, 2),
    )
    tx_c = PortfolioTransaction(
        id="c",
        user_id="u1",
        symbol="SYS",
        transaction_type=TransactionType.BUY,
        quantity=Decimal("50"),
        price=Decimal("20.00"),
        fee=Decimal("0"),
        transaction_date=date(2026, 1, 3),
    )
    pos = calculate_position([tx_a, tx_b, tx_c])
    assert pos.remaining_quantity == Decimal("100.0000")
    assert pos.average_cost == Decimal("15.0000")


@pytest.mark.asyncio
async def test_ws_alerts_auth_rejects_inactive_user():
    from app.api.v1.ws import _resolve_active_user_id_from_access_token

    token = create_access_token({"sub": "dead-user", "tv": 0})
    inactive = MagicMock(spec=User)
    inactive.is_active = False
    inactive.token_version = 0
    inactive.id = "dead-user"

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=inactive)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch("app.api.v1.ws.async_session_factory", return_value=mock_session):
        resolved = await _resolve_active_user_id_from_access_token(token)
    assert resolved is None


@pytest.mark.asyncio
async def test_ws_alerts_auth_accepts_active_user():
    from app.api.v1.ws import _resolve_active_user_id_from_access_token

    token = create_access_token({"sub": "live-user", "tv": 0})
    active = MagicMock(spec=User)
    active.is_active = True
    active.token_version = 0
    active.id = "live-user"

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=active)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch("app.api.v1.ws.async_session_factory", return_value=mock_session):
        resolved = await _resolve_active_user_id_from_access_token(token)
    assert resolved == "live-user"


def test_news_refresh_requires_current_user_dependency():
    import inspect
    from app.api.v1.news import refresh_news
    from app.core.authorization import get_current_user

    params = inspect.signature(refresh_news).parameters
    assert "user" in params
    dep = params["user"].default
    assert dep.dependency is get_current_user


def test_devices_register_looks_up_fcm_globally():
    import inspect
    from app.api.v1 import devices as devices_mod

    src = inspect.getsource(devices_mod.register_device)
    assert "Device.fcm_token == data.fcm_token" in src
    # Must reassign ownership globally (not scoped only to current user)
    assert "existing.user_id = user.id" in src


def test_admin_etf_ipo_crud_methods_exist():
    assert hasattr(ETFService := __import__("app.services.etf_service", fromlist=["ETFService"]).ETFService, "create_etf")
    assert hasattr(ETFService, "update_etf")
    assert hasattr(ETFService, "delete_etf")
    IPOService = __import__("app.services.ipo_service", fromlist=["IPOService"]).IPOService
    assert hasattr(IPOService, "create_ipo")
    assert hasattr(IPOService, "update_ipo")
    assert hasattr(IPOService, "delete_ipo")
