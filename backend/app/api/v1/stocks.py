from fastapi import APIRouter, Depends, Query

from app.core.authorization import get_current_user
from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.schemas.stock import (
    FundamentalsResponse,
    PriceHistoryResponse,
    StockOverview,
    StockSearchResponse,
    TechnicalIndicatorsResponse,
)
from app.services.stock_service import StockService

router = APIRouter()


@router.get(
    "/stocks/search",
    response_model=StockSearchResponse,
    summary="Autocomplete stock search",
)
async def search_stocks(
    q: str = Query(..., description="Search query (symbol prefix/substring)"),
    limit: int = Query(10, ge=1, le=50),
    service: StockService = Depends(StockService),
    _user=Depends(get_current_user),
):
    try:
        results = service.search_symbols(q, limit)
        return {"results": results}
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to search stocks: {exc}")


@router.get(
    "/stocks/{symbol}/overview",
    response_model=StockOverview,
    summary="Stock overview snapshot",
)
async def get_stock_overview(
    symbol: str,
    service: StockService = Depends(StockService),
    _user=Depends(get_current_user),
):
    try:
        overview = service.get_overview(symbol)
        if overview.get("message") == "no data":
            raise NotFoundError(f"Stock '{symbol}' not found or no data available")
        return overview
    except NotFoundError:
        raise
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to fetch overview for '{symbol}': {exc}")


@router.get(
    "/stocks/{symbol}/price-history",
    response_model=PriceHistoryResponse,
    summary="Daily OHLCV price history",
)
async def get_stock_price_history(
    symbol: str,
    range: str = Query("1M", pattern="^(1D|1W|1M|1Y)$"),
    service: StockService = Depends(StockService),
    _user=Depends(get_current_user),
):
    try:
        data = service.get_price_history(symbol, range)
        if not data.get("bars"):
            raise NotFoundError(f"No price history available for '{symbol}'")
        return data
    except NotFoundError:
        raise
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to fetch price history for '{symbol}': {exc}")


@router.get(
    "/stocks/{symbol}/technical-indicators",
    response_model=TechnicalIndicatorsResponse,
    summary="Technical indicator series",
)
async def get_stock_technical_indicators(
    symbol: str,
    indicators: str = Query("RSI,MACD,BB,SMA,ADX"),
    period: int = Query(14, ge=1, le=200),
    service: StockService = Depends(StockService),
    _user=Depends(get_current_user),
):
    try:
        data = service.technical_indicators(symbol, indicators, period)
        if not data.get("indicators"):
            raise NotFoundError(f"No indicator data available for '{symbol}'")
        return data
    except NotFoundError:
        raise
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to fetch indicators for '{symbol}': {exc}")


@router.get(
    "/stocks/{symbol}/fundamentals",
    response_model=FundamentalsResponse,
    summary="Company fundamentals",
)
async def get_stock_fundamentals(
    symbol: str,
    service: StockService = Depends(StockService),
    _user=Depends(get_current_user),
):
    try:
        data = service.get_fundamentals(symbol)
        return data
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to fetch fundamentals for '{symbol}': {exc}")
