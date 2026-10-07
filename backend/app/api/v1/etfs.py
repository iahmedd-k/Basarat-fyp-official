from typing import Optional
from fastapi import APIRouter, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.db.session import get_db
from app.schemas.etf import (
    ETFResponse,
    ETFListResponse,
    ETFHistoryResponse,
    ETFPerformanceResponse,
)
from app.services.etf_service import ETFService

router = APIRouter(prefix="/etfs", tags=["ETFs"])
log = logging.getLogger(__name__)


def _get_service(db: AsyncSession = Depends(get_db)) -> ETFService:
    return ETFService(db)


from app.core.redis import cache_get, cache_set


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
    service: ETFService = Depends(_get_service),
):
    try:
        search_query = q or search
        cache_key = f"etfs:list:{category or 'all'}:{is_shariah_compliant}:{search_query or 'all'}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return ETFListResponse(**cached)

        res = await service.get_etfs(
            category=category,
            is_shariah_compliant=is_shariah_compliant,
            search=search_query,
        )
        await cache_set(cache_key, res.model_dump(mode="json"), ttl_seconds=120)
        return res
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
    service: ETFService = Depends(_get_service),
):
    try:
        clean_sym = symbol.strip().upper()
        cache_key = f"etf:detail:{clean_sym}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return ETFResponse(**cached)

        res = await service.get_etf_by_symbol(clean_sym)
        await cache_set(cache_key, res.model_dump(mode="json"), ttl_seconds=120)
        return res
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
    service: ETFService = Depends(_get_service),
):
    try:
        clean_sym = symbol.strip().upper()
        clean_tf = timeframe.strip().upper()
        cache_key = f"etf:history:{clean_sym}:{clean_tf}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return ETFHistoryResponse(**cached)

        res = await service.get_history(clean_sym, timeframe=clean_tf)
        await cache_set(cache_key, res.model_dump(mode="json"), ttl_seconds=300)
        return res
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
    service: ETFService = Depends(_get_service),
):
    try:
        clean_sym = symbol.strip().upper()
        cache_key = f"etf:perf:{clean_sym}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return ETFPerformanceResponse(**cached)

        res = await service.get_performance(clean_sym)
        await cache_set(cache_key, res.model_dump(mode="json"), ttl_seconds=300)
        return res
    except NotFoundError:
        raise
    except Exception as exc:
        log.exception("Error getting ETF performance for %s: %s", symbol, exc)
        raise ServiceUnavailableError(f"Failed to retrieve performance for ETF {symbol}.")
