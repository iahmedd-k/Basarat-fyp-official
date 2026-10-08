from typing import Optional
from fastapi import APIRouter, Query
import logging

from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.core.redis import cache_get
from app.db.session import db_session
from app.schemas.etf import (
    ETFResponse,
    ETFListResponse,
    ETFHistoryResponse,
    ETFPerformanceResponse,
)
from app.services.etf_service import ETFService

router = APIRouter(prefix="/etfs", tags=["ETFs"])
log = logging.getLogger(__name__)


@router.get(
    "",
    response_model=ETFListResponse,
    summary="List all active PSX ETFs (Public)",
    description="Retrieve all active Exchange Traded Funds on PSX with live quotes, daily change %, volume, and benchmark indices.",
)
async def list_etfs(
    category: Optional[str] = Query(None, description="Filter by category (e.g. Islamic Equity ETF, Sector Equity ETF)"),
    is_shariah_compliant: Optional[bool] = Query(None, description="Filter by Shariah compliance"),
    q: Optional[str] = Query(None, description="Search by symbol, fund name, or benchmark"),
    search: Optional[str] = Query(None, description="Alias for search query"),
):
    try:
        search_query = q or search
        cache_key = f"etf:list:v1:{category}:{is_shariah_compliant}:{search_query}"
        cached = await cache_get(cache_key)
        if cached:
            return ETFListResponse(**cached)
        async with db_session() as db:
            return await ETFService(db).get_etfs(
                category=category,
                is_shariah_compliant=is_shariah_compliant,
                search=search_query,
            )
    except Exception as exc:
        log.exception("Error listing ETFs: %s", exc)
        raise ServiceUnavailableError("Failed to retrieve ETFs.")


@router.get(
    "/{symbol}",
    response_model=ETFResponse,
    summary="Get single ETF overview & live quote (Public)",
    description="Retrieve detailed ETF directory metadata, fund manager details, and live bid/ask/price quotes.",
)
async def get_etf_detail(
    symbol: str,
):
    try:
        clean_sym = symbol.strip().upper()
        cache_key = f"etf:detail:v1:{clean_sym}"
        cached = await cache_get(cache_key)
        if cached:
            return ETFResponse(**cached)
        async with db_session() as db:
            return await ETFService(db).get_etf_by_symbol(clean_sym)
    except NotFoundError:
        raise
    except Exception as exc:
        log.exception("Error getting ETF %s: %s", symbol, exc)
        raise ServiceUnavailableError(f"Failed to retrieve ETF {symbol}.")


@router.get(
    "/{symbol}/history",
    response_model=ETFHistoryResponse,
    summary="Get ETF historical OHLCV prices (Public)",
    description="Retrieve historical timeseries data for interactive chart rendering (timeframe: 1M, 3M, 1Y).",
)
async def get_etf_history(
    symbol: str,
    timeframe: str = Query("1M", description="History timeframe: 1M, 3M, 1Y"),
):
    try:
        clean_sym = symbol.strip().upper()
        clean_tf = timeframe.strip().upper()
        cache_key = f"etf:hist:v1:{clean_sym}:{clean_tf}"
        cached = await cache_get(cache_key)
        if cached:
            return ETFHistoryResponse(**cached)
        async with db_session() as db:
            return await ETFService(db).get_history(clean_sym, timeframe=clean_tf)
    except NotFoundError:
        raise
    except Exception as exc:
        log.exception("Error getting ETF history for %s: %s", symbol, exc)
        raise ServiceUnavailableError(f"Failed to retrieve history for ETF {symbol}.")


@router.get(
    "/{symbol}/performance",
    response_model=ETFPerformanceResponse,
    summary="Get ETF performance vs benchmark (Public)",
    description="Multi-period return statistics (1D, 1W, 1M, 3M, 1Y, YTD) compared against the underlying benchmark index.",
)
async def get_etf_performance(
    symbol: str,
):
    try:
        clean_sym = symbol.strip().upper()
        cache_key = f"etf:perf:v1:{clean_sym}"
        cached = await cache_get(cache_key)
        if cached:
            return ETFPerformanceResponse(**cached)
        async with db_session() as db:
            return await ETFService(db).get_performance(clean_sym)
    except NotFoundError:
        raise
    except Exception as exc:
        log.exception("Error getting ETF performance for %s: %s", symbol, exc)
        raise ServiceUnavailableError(f"Failed to retrieve performance for ETF {symbol}.")
