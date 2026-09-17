import asyncio
import re

from fastapi import APIRouter, Depends, Path, Query, Request

from app.core.authorization import get_current_user
from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.core.rate_limiter import limiter
from app.schemas.stock import (
    FundamentalsResponse,
    PriceHistoryResponse,
    StockOverview,
    StockSearchResponse,
    TechnicalIndicatorsResponse,
)
from app.services.stock_service import StockService

router = APIRouter()

_SYMBOL_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9]{1,9}$")


def _validate_symbol(symbol: str) -> str:
    """Normalize and validate a PSX stock symbol.

    Raises ValueError if the symbol doesn't match expected format.
    """
    symbol = symbol.strip().upper()
    if not _SYMBOL_PATTERN.match(symbol):
        raise ValueError(
            f"Invalid stock symbol '{symbol}'. "
            "Symbols must be 2-10 alphanumeric characters starting with a letter."
        )
    return symbol


@router.get(
    "/stocks/search",
    response_model=StockSearchResponse,
    summary="Autocomplete stock search",
)
@limiter.limit("60/minute")
async def search_stocks(
    request: Request,
    q: str = Query(..., min_length=1, max_length=50, description="Search query (symbol prefix/substring)"),
    limit: int = Query(10, ge=1, le=100),
    service: StockService = Depends(StockService),
    _user=Depends(get_current_user),
):
    try:
        results = await asyncio.to_thread(service.search_symbols, q, limit)
        return {"results": results}
    except Exception:
        raise ServiceUnavailableError("Stock search temporarily unavailable")


@router.get(
    "/stocks/{symbol}/overview",
    response_model=StockOverview,
    summary="Stock overview snapshot",
)
@limiter.limit("30/minute")
async def get_stock_overview(
    request: Request,
    symbol: str = Path(..., description="PSX stock symbol (e.g. HBL, OGDC)"),
    service: StockService = Depends(StockService),
    _user=Depends(get_current_user),
):
    try:
        symbol = _validate_symbol(symbol)
    except ValueError as exc:
        raise ServiceUnavailableError(str(exc))
    try:
        overview = await asyncio.to_thread(service.get_overview, symbol)
        if overview.get("message") == "no data":
            raise NotFoundError(f"Stock '{symbol}' not found or no data available")
        return overview
    except NotFoundError:
        raise
    except ServiceUnavailableError:
        raise
    except Exception:
        raise ServiceUnavailableError("Stock overview temporarily unavailable")


@router.get(
    "/stocks/{symbol}/price-history",
    response_model=PriceHistoryResponse,
    summary="Daily OHLCV price history",
)
@limiter.limit("30/minute")
async def get_stock_price_history(
    request: Request,
    symbol: str = Path(..., description="PSX stock symbol (e.g. HBL, OGDC)"),
    range: str = Query("1M", pattern="^(1D|1W|1M|1Y)$"),
    service: StockService = Depends(StockService),
    _user=Depends(get_current_user),
):
    try:
        symbol = _validate_symbol(symbol)
    except ValueError as exc:
        raise ServiceUnavailableError(str(exc))
    try:
        data = await asyncio.to_thread(service.get_price_history, symbol, range)
        if not data.get("bars"):
            raise NotFoundError(f"No price history available for '{symbol}'")
        return data
    except NotFoundError:
        raise
    except ServiceUnavailableError:
        raise
    except Exception:
        raise ServiceUnavailableError("Price history temporarily unavailable")


@router.get(
    "/stocks/{symbol}/technical-indicators",
    response_model=TechnicalIndicatorsResponse,
    summary="Technical indicator series",
)
@limiter.limit("20/minute")
async def get_stock_technical_indicators(
    request: Request,
    symbol: str = Path(..., description="PSX stock symbol (e.g. HBL, OGDC)"),
    indicators: str = Query("RSI,MACD,BB,SMA,ADX"),
    period: int = Query(14, ge=1, le=200),
    service: StockService = Depends(StockService),
    _user=Depends(get_current_user),
):
    try:
        symbol = _validate_symbol(symbol)
    except ValueError as exc:
        raise ServiceUnavailableError(str(exc))
    try:
        data = await asyncio.to_thread(
            service.technical_indicators, symbol, indicators, period
        )
        if not data.get("indicators"):
            raise NotFoundError(f"No indicator data available for '{symbol}'")
        return data
    except NotFoundError:
        raise
    except ServiceUnavailableError:
        raise
    except Exception:
        raise ServiceUnavailableError("Technical indicators temporarily unavailable")


@router.get(
    "/stocks/{symbol}/fundamentals",
    response_model=FundamentalsResponse,
    summary="Company fundamentals",
)
@limiter.limit("20/minute")
async def get_stock_fundamentals(
    request: Request,
    symbol: str = Path(..., description="PSX stock symbol (e.g. HBL, OGDC)"),
    service: StockService = Depends(StockService),
    _user=Depends(get_current_user),
):
    try:
        symbol = _validate_symbol(symbol)
    except ValueError as exc:
        raise ServiceUnavailableError(str(exc))
    try:
        data = await asyncio.to_thread(service.get_fundamentals, symbol)
        return data
    except ServiceUnavailableError:
        raise
    except Exception:
        raise ServiceUnavailableError("Fundamentals data temporarily unavailable")
