"""Shared test fixtures for the Basarat test suite."""

import asyncio
from collections.abc import AsyncGenerator
from datetime import datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.stock import Stock
from app.models.user import User


# ---------------------------------------------------------------------------
# Async event-loop fixture (session-scoped so one loop for the whole suite)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# In-memory async SQLite engine + tables
# ---------------------------------------------------------------------------
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DB_URL, echo=False, future=True)
TestSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(scope="session", autouse=True)
def _dispose_engine_at_session_end():
    """Close the aiosqlite worker threads so the interpreter can exit on Windows."""
    yield
    import asyncio

    try:
        asyncio.get_event_loop().run_until_complete(engine.dispose())
    except RuntimeError:
        asyncio.run(engine.dispose())
        asyncio.run(asyncio.sleep(0))


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a clean async DB session, rolled back after each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session
        await session.rollback()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ---------------------------------------------------------------------------
# HTTPX async client wired to the FastAPI app
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Async test client with DB dependency overridden."""

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# User factory helpers
# ---------------------------------------------------------------------------
async def _create_user(
    db: AsyncSession,
    *,
    email: str | None = None,
    password: str = "TestPass123!",
    is_active: bool = True,
    is_admin: bool = False,
) -> User:
    email = email or f"{uuid4().hex[:8]}@test.com"
    user = User(
        email=email,
        username=email.split("@")[0],
        hashed_password=hash_password(password),
        full_name="Test User",
        is_active=is_active,
        is_admin=is_admin,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create and return a standard test user."""
    return await _create_user(db_session)


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Create and return an admin test user."""
    return await _create_user(db_session, is_admin=True, email="admin@test.com")


@pytest_asyncio.fixture
async def inactive_user(db_session: AsyncSession) -> User:
    """Create and return an inactive test user."""
    return await _create_user(db_session, is_active=False, email="inactive@test.com")


# ---------------------------------------------------------------------------
# Auth token fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def auth_headers(test_user: User) -> dict:
    """Return Authorization headers with a valid access token."""
    token = create_access_token({"sub": test_user.id})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(admin_user: User) -> dict:
    """Return Authorization headers for an admin user."""
    token = create_access_token({"sub": admin_user.id})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def expired_token_headers() -> dict:
    """Return headers with an expired token."""
    from datetime import timedelta
    token = create_access_token(
        {"sub": "fake-user-id"},
        expires_delta=timedelta(seconds=-1),
    )
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def refresh_token_fixture(test_user: User, db_session: AsyncSession) -> str:
    """Return a valid refresh token stored in the DB."""
    from datetime import timezone
    from app.core.security import create_refresh_token, decode_token
    from app.models.user import RefreshToken

    token = create_refresh_token({"sub": test_user.id})
    payload = decode_token(token)
    jti = payload.get("jti")
    exp = payload.get("exp")
    rt = RefreshToken(
        jti=jti,
        user_id=test_user.id,
        expires_at=datetime.fromtimestamp(exp, tz=timezone.utc),
    )
    db_session.add(rt)
    await db_session.flush()
    return token


# ---------------------------------------------------------------------------
# Mocked external service fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_market_data():
    """Sample market data matching pypsx_toolkit format."""
    return [
        {"symbol": "HBL", "sector": "Banking", "ldcp": 150.0, "open": 152.0,
         "high": 155.0, "low": 149.0, "current": 154.0, "change": 4.0,
         "change_pct": 2.67, "volume": 1000000},
        {"symbol": "OGDC", "sector": "Oil & Gas", "ldcp": 90.0, "open": 91.0,
         "high": 93.0, "low": 89.0, "current": 92.0, "change": 2.0,
         "change_pct": 2.22, "volume": 2000000},
        {"symbol": "LUCK", "sector": "Cement", "ldcp": 620.0, "open": 618.0,
         "high": 622.0, "low": 610.0, "current": 612.0, "change": -8.0,
         "change_pct": -1.29, "volume": 500000},
    ]


@pytest.fixture
def mock_indices_data():
    """Sample indices data."""
    import pandas as pd
    data = {
        "CURRENT": [42000.0, 15000.0, 8000.0],
        "CHANGE": [200.0, 50.0, -10.0],
        "PERCENTAGE_CHANGE": [0.48, 0.33, -0.12],
        "HIGH": [42200.0, 15100.0, 8050.0],
        "LOW": [41800.0, 14900.0, 7950.0],
    }
    return pd.DataFrame(data, index=["KSE100", "KSE30", "KMI30"])


@pytest.fixture
def mock_constituents_data():
    """Sample KSE-100 constituents data."""
    import pandas as pd
    data = {
        "NAME": ["Habib Bank", "OGDC", "Lucky Cement"],
        "LDCP": [150.0, 90.0, 620.0],
        "CURRENT": [154.0, 92.0, 612.0],
        "CHANGE": [4.0, 2.0, -8.0],
        "CHANGE %": [2.67, 2.22, -1.29],
        "IDX WTG %": [8.5, 7.2, 5.1],
        "IDX POINT": [12.5, 6.8, -3.2],
        "VOLUME": [1000000, 2000000, 500000],
        "FREEFLOAT (M)": [500.0, 800.0, 300.0],
        "MARKET CAP (M)": [5000.0, 8000.0, 3000.0],
    }
    return pd.DataFrame(data, index=["HBL", "OGDC", "LUCK"])


@pytest.fixture
def mock_stock_service():
    """Mock StockService that returns predictable data without external calls."""
    from unittest.mock import MagicMock
    service = MagicMock()

    def mock_get_quote(symbol):
        symbol = str(symbol).upper()
        quotes = {
            "HBL": {"symbol": "HBL", "name": "HBL", "sector": "Banking", "ldcp": 150.0, "open": 152.0,
                    "high": 155.0, "low": 149.0, "current": 154.0, "change": 4.0, "change_pct": 2.67, "volume": 1000000},
            "OGDC": {"symbol": "OGDC", "name": "OGDC", "sector": "Oil & Gas", "ldcp": 90.0, "open": 91.0,
                     "high": 93.0, "low": 89.0, "current": 92.0, "change": 2.0, "change_pct": 2.22, "volume": 2000000},
            "LUCK": {"symbol": "LUCK", "name": "LUCK", "sector": "Cement", "ldcp": 620.0, "open": 618.0,
                     "high": 622.0, "low": 610.0, "current": 612.0, "change": -8.0, "change_pct": -1.29, "volume": 500000},
        }
        return quotes.get(symbol, {"symbol": symbol, "name": symbol, "sector": "Unknown",
                                   "ldcp": 0.0, "open": 0.0, "high": 0.0, "low": 0.0,
                                   "current": 0.0, "change": 0.0, "change_pct": 0.0, "volume": 0})

    def mock_get_quote_batch(symbols):
        return [mock_get_quote(s) for s in symbols]

    def mock_get_overview(symbol):
        symbol = str(symbol).upper()
        return {
            "symbol": symbol, "name": symbol, "sector": "Banking" if symbol == "HBL" else "Oil & Gas" if symbol == "OGDC" else "Cement",
            "ltp": 154.0 if symbol == "HBL" else 92.0 if symbol == "OGDC" else 612.0,
            "ldcp": 150.0 if symbol == "HBL" else 90.0 if symbol == "OGDC" else 620.0,
            "change": 4.0 if symbol == "HBL" else 2.0 if symbol == "OGDC" else -8.0,
            "change_pct": 2.67 if symbol == "HBL" else 2.22 if symbol == "OGDC" else -1.29,
            "day_range": {"low": 149.0 if symbol == "HBL" else 89.0 if symbol == "OGDC" else 610.0,
                          "high": 155.0 if symbol == "HBL" else 93.0 if symbol == "OGDC" else 622.0},
            "volume": 1000000 if symbol == "HBL" else 2000000 if symbol == "OGDC" else 500000,
            "market_cap_m": 5000.0 if symbol == "HBL" else 8000.0 if symbol == "OGDC" else 3000.0,
            "market_cap": 5000.0 if symbol == "HBL" else 8000.0 if symbol == "OGDC" else 3000.0,
            "pe_ratio": 10.5,
            "year_change_pct": 15.0,
            "ytd_change_pct": 8.0,
        }

    def mock_get_price_history(symbol, range="1M"):
        return {"symbol": symbol.upper(), "range": range, "bars": [
            {"date": "2025-01-01", "open": 150.0, "high": 155.0, "low": 149.0, "close": 154.0, "volume": 1000000},
            {"date": "2025-01-02", "open": 154.0, "high": 156.0, "low": 152.0, "close": 155.0, "volume": 800000},
        ]}

    def mock_technical_indicators(symbol, indicators="RSI,MACD,BB,SMA,ADX", period=14):
        return {"symbol": symbol.upper(), "period": period, "indicators": {"RSI": [{"date": "2025-01-01", "value": 65.0}]}}

    def mock_get_fundamentals(symbol):
        return {"symbol": symbol.upper(), "metrics": [], "extras": {}}

    def mock_search_symbols(q, limit=10):
        q = (q or "").strip().upper()
        all_symbols = ["HBL", "OGDC", "LUCK", "UBL", "MCB", "ENGRO", "FFC", "SYS", "TRG", "AVN"]
        return [{"symbol": s, "name": s, "sector": "Banking"} for s in all_symbols if q in s][:limit]

    service.get_quote.side_effect = mock_get_quote
    service.get_quote_batch.side_effect = mock_get_quote_batch
    service.get_overview.side_effect = mock_get_overview
    service.get_price_history.side_effect = mock_get_price_history
    service.technical_indicators.side_effect = mock_technical_indicators
    service.get_fundamentals.side_effect = mock_get_fundamentals
    service.search_symbols.side_effect = mock_search_symbols

    return service


@pytest.fixture
def mock_market_service():
    """Mock MarketService that returns predictable data without external calls."""
    from unittest.mock import MagicMock
    import pandas as pd

    service = MagicMock()

    def mock_get_market_data():
        data = {
            "CURRENT": [42000.0, 15000.0, 8000.0],
            "CHANGE": [200.0, 50.0, -10.0],
            "PERCENTAGE_CHANGE": [0.48, 0.33, -0.12],
            "HIGH": [42200.0, 15100.0, 8050.0],
            "LOW": [41800.0, 14900.0, 7950.0],
        }
        return pd.DataFrame(data, index=["KSE100", "KSE30", "KMI30"])

    def mock_get_gainers(limit=10):
        return [{"symbol": "HBL", "name": "HBL", "sector": "Banking", "ldcp": 150.0, "open": 152.0,
                 "high": 155.0, "low": 149.0, "current": 154.0, "change": 4.0, "change_pct": 2.67, "volume": 1000000},
                {"symbol": "OGDC", "name": "OGDC", "sector": "Oil & Gas", "ldcp": 90.0, "open": 91.0,
                 "high": 93.0, "low": 89.0, "current": 92.0, "change": 2.0, "change_pct": 2.22, "volume": 2000000}]

    def mock_get_losers(limit=10):
        return [{"symbol": "LUCK", "name": "LUCK", "sector": "Cement", "ldcp": 620.0, "open": 618.0,
                 "high": 622.0, "low": 610.0, "current": 612.0, "change": -8.0, "change_pct": -1.29, "volume": 500000}]

    def mock_get_volume_spikes(limit=10):
        return [{"symbol": "HBL", "name": "HBL", "sector": "Banking", "ldcp": 150.0, "open": 152.0,
                 "high": 155.0, "low": 149.0, "current": 154.0, "change": 4.0, "change_pct": 2.67, "volume": 5000000}]

    service.get_market_data.side_effect = mock_get_market_data
    service.get_gainers.side_effect = mock_get_gainers
    service.get_losers.side_effect = mock_get_losers
    service.get_volume_spikes.side_effect = mock_get_volume_spikes

    return service


@pytest_asyncio.fixture(autouse=True)
async def seed_stocks(db_session: AsyncSession) -> list[Stock]:
    """Seed the test database with common stock symbols."""
    stocks = [
        Stock(id="stock-hbl", symbol="HBL", name="Habib Bank Limited", sector="Banking"),
        Stock(id="stock-ogdc", symbol="OGDC", name="Oil & Gas Development Company", sector="Oil & Gas"),
        Stock(id="stock-luck", symbol="LUCK", name="Lucky Cement", sector="Cement"),
        Stock(id="stock-ubl", symbol="UBL", name="United Bank Limited", sector="Banking"),
        Stock(id="stock-mcb", symbol="MCB", name="MCB Bank Limited", sector="Banking"),
    ]
    for stock in stocks:
        db_session.add(stock)
    await db_session.flush()
    for stock in stocks:
        await db_session.refresh(stock)
    return stocks


@pytest.fixture(autouse=True)
def override_services(mock_stock_service, mock_market_service):
    """Override StockService and MarketService dependencies with mocks."""
    from app.services.stock_service import StockService
    from app.services.market_service import MarketService
    from app.main import app

    def get_mock_stock_service():
        return mock_stock_service

    def get_mock_market_service():
        return mock_market_service

    app.dependency_overrides[StockService] = get_mock_stock_service
    app.dependency_overrides[MarketService] = get_mock_market_service

    yield

    app.dependency_overrides.pop(StockService, None)
    app.dependency_overrides.pop(MarketService, None)


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset rate limiter state between tests."""
    from app.core.rate_limiter import limiter
    limiter.reset()
    yield
