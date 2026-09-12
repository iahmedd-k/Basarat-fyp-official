from fastapi import APIRouter, Depends, Query
from typing import Optional

from app.services.stock_service import StockService

router = APIRouter()


@router.get("/stocks/search", summary="Autocomplete stock search")
def search_stocks(
    q: str = Query(..., description="Search query (symbol prefix/substring)"),
    limit: int = Query(10, ge=1, le=50),
    service: StockService = Depends(StockService),
):
    return {"results": service.search_symbols(q, limit)}


@router.get("/stocks/{symbol}/overview", summary="Stock overview snapshot")
def get_stock_overview(
    symbol: str,
    service: StockService = Depends(StockService),
):
    return service.get_overview(symbol)


@router.get("/stocks/{symbol}/price-history", summary="Daily OHLCV price history")
def get_stock_price_history(
    symbol: str,
    range: str = Query("1M", pattern="^(1D|1W|1M|1Y)$"),
    service: StockService = Depends(StockService),
):
    return service.get_price_history(symbol, range)


@router.get("/stocks/{symbol}/technical-indicators", summary="Technical indicator series")
def get_stock_technical_indicators(
    symbol: str,
    indicators: str = Query("RSI,MACD,BB,SMA,ADX"),
    period: int = Query(14, ge=1, le=200),
    service: StockService = Depends(StockService),
):
    return service.technical_indicators(symbol, indicators, period)


@router.get("/stocks/{symbol}/fundamentals", summary="Company fundamentals")
def get_stock_fundamentals(
    symbol: str,
    service: StockService = Depends(StockService),
):
    return service.get_fundamentals(symbol)