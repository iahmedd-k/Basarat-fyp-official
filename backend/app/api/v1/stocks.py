import asyncio
import logging
import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.core.rate_limiter import limiter
from app.core.redis import cache_get, cache_set
from app.db.session import get_db
from app.models.stock import Stock, StockPrice
from app.schemas.stock import (
    FundamentalsResponse,
    PriceHistoryResponse,
    StockOverview,
    StockSearchResponse,
    TechnicalIndicatorsResponse,
)
from app.services.stock_service import StockService

log = logging.getLogger(__name__)

router = APIRouter()

_SYMBOL_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9]{1,9}$")
_COMPANY_NAME_CHARS = frozenset("&.,'()/-")


async def _resolve_stock_symbol(reference: str, db: AsyncSession) -> str:
    """Resolve a ticker directly, or an exact company/quote name on demand."""
    value = reference.strip()
    if _SYMBOL_PATTERN.fullmatch(value):
        return value.upper()

    valid_name = (
        bool(value)
        and len(value) <= 100
        and any(char.isalpha() for char in value)
        and all(
            char.isalnum() or char.isspace() or char in _COMPANY_NAME_CHARS
            for char in value
        )
    )
    if not valid_name:
        raise HTTPException(
            status_code=422,
            detail="Enter a stock symbol or exact company name up to 100 characters.",
        )

    normalized_name = " ".join(value.split()).casefold()
    try:
        result = await db.execute(
            select(Stock.symbol)
            .where(
                Stock.is_active.is_(True),
                func.lower(func.trim(Stock.name)) == normalized_name,
            )
            .limit(2)
        )
        matches = {str(symbol).upper() for symbol in result.scalars().all()}
    except Exception as exc:
        log.exception("Stock name lookup failed for %r", value)
        raise ServiceUnavailableError("Stock name lookup temporarily unavailable") from exc

    if not matches:
        for cache_key in ("market:quotes", "market:quotes:last_known"):
            quotes = await cache_get(cache_key)
            if not isinstance(quotes, list):
                continue
            matches = {
                str(quote.get("symbol") or "").strip().upper()
                for quote in quotes
                if isinstance(quote, dict)
                and " ".join(str(quote.get("name") or "").split()).casefold() == normalized_name
                and str(quote.get("symbol") or "").strip()
            }
            if matches:
                break

    if len(matches) == 1:
        return matches.pop()
    if len(matches) > 1:
        raise NotFoundError(f"Company name '{value}' matches multiple stocks; use its ticker symbol.")
    raise NotFoundError(f"No stock found for ticker or exact company name '{value}'.")


@router.get(
    "/stocks/search",
    response_model=StockSearchResponse,
    summary="Autocomplete stock search",
)
@limiter.limit("60/minute")
async def search_stocks(
    request: Request,
    q: str = Query(..., min_length=1, max_length=50, description="Search query (symbol prefix/substring or company name)"),
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    service: StockService = Depends(StockService),
):
    clean_q = q.strip()
    if not clean_q:
        return {"results": []}

    cache_key = f"stocks:search:{clean_q.lower()}:{limit}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached

    # 1. Database-first search (matches symbol prefix, substring, or full company name)
    try:
        stmt = (
            select(Stock)
            .where(
                Stock.is_active == True,
                or_(
                    Stock.symbol.ilike(f"{clean_q}%"),
                    Stock.symbol.ilike(f"%{clean_q}%"),
                    Stock.name.ilike(f"%{clean_q}%"),
                ),
            )
            .order_by(
                case(
                    (Stock.symbol.ilike(f"{clean_q}%"), 1),
                    (Stock.symbol.ilike(f"%{clean_q}%"), 2),
                    else_=3,
                )
            )
            .limit(limit)
        )
        db_results = (await db.execute(stmt)).scalars().all()
        if db_results:
            results = {
                "results": [
                    {
                        "symbol": s.symbol,
                        "name": s.name or s.symbol,
                        "sector": s.sector,
                    }
                    for s in db_results
                ]
            }
            await cache_set(cache_key, results, ttl_seconds=300)
            return results
    except Exception as exc:
        log.debug("Database stock search error, falling back to cache: %s", exc)

    # 2. Seamless fallback to Redis / PSX market cache
    try:
        results = await asyncio.to_thread(service.search_symbols, clean_q, limit)
        response_obj = {"results": results}
        await cache_set(cache_key, response_obj, ttl_seconds=300)
        return response_obj
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
    symbol: str = Path(..., description="PSX ticker or exact company/quote name"),
    db: AsyncSession = Depends(get_db),
    service: StockService = Depends(StockService),
):
    symbol = await _resolve_stock_symbol(symbol, db)
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
    symbol: str = Path(..., description="PSX ticker or exact company/quote name"),
    range: str = Query("1M", pattern="^(1D|1W|1M|1Y)$"),
    db: AsyncSession = Depends(get_db),
    service: StockService = Depends(StockService),
):
    symbol = await _resolve_stock_symbol(symbol, db)
    try:
        data = await asyncio.to_thread(service.get_price_history, symbol, range)
        if not data.get("bars"):
            _, lookback = StockService.RANGE_MAP.get(
                range.upper(), StockService.RANGE_MAP["1M"]
            )
            result = await db.execute(
                select(
                    StockPrice.date.label("date"),
                    StockPrice.open.label("open"),
                    StockPrice.high.label("high"),
                    StockPrice.low.label("low"),
                    StockPrice.close.label("close"),
                    StockPrice.volume.label("volume"),
                )
                .join(Stock, StockPrice.stock_id == Stock.id)
                .where(Stock.symbol == symbol)
                .order_by(StockPrice.date.desc())
                .limit(400)
            )
            stored_rows = result.all()
            if stored_rows:
                latest_date = stored_rows[0].date
                cutoff = latest_date - lookback
                selected_rows = [
                    row for row in reversed(stored_rows) if row.date >= cutoff
                ]
                if not selected_rows:
                    selected_rows = (
                        list(reversed(stored_rows))[-1:]
                        if range == "1D"
                        else list(reversed(stored_rows))[-5:]
                    )

                as_of_date = latest_date
                age_days = max(0, (date.today() - as_of_date).days)
                data = {
                    "symbol": symbol,
                    "range": range,
                    "bars": [
                        {
                            "date": row.date.isoformat(),
                            "open": float(row.open) if row.open is not None else None,
                            "high": float(row.high) if row.high is not None else None,
                            "low": float(row.low) if row.low is not None else None,
                            "close": float(row.close) if row.close is not None else None,
                            "volume": int(row.volume or 0),
                        }
                        for row in selected_rows
                    ],
                    "as_of_date": as_of_date.isoformat(),
                    "data_age_days": age_days,
                    "is_stale": age_days > 3,
                }
            else:
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
    summary="Technical indicator series with overall signal summary",
)
@router.get(
    "/stocks/{symbol}/technicals",
    response_model=TechnicalIndicatorsResponse,
    summary="Technical indicator series with overall signal summary (alias)",
    include_in_schema=True,
)
@limiter.limit("20/minute")
async def get_stock_technical_indicators(
    request: Request,
    symbol: str = Path(..., description="PSX ticker or exact company/quote name"),
    indicators: str = Query("RSI,MACD,BB,SMA,ADX", description="Comma-separated indicators (RSI, MACD, BB, SMA, ADX)"),
    period: int = Query(14, ge=1, le=200, description="Calculation window period"),
    limit: int = Query(30, ge=1, le=365, description="Number of historical indicator data points to return (default: 30 bars / ~1 month)"),
    db: AsyncSession = Depends(get_db),
    service: StockService = Depends(StockService),
):
    symbol = await _resolve_stock_symbol(symbol, db)
    try:
        data = await asyncio.to_thread(
            service.technical_indicators, symbol, indicators, period, limit
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
    symbol: str = Path(..., description="PSX ticker or exact company/quote name"),
    db: AsyncSession = Depends(get_db),
    service: StockService = Depends(StockService),
):
    symbol = await _resolve_stock_symbol(symbol, db)
    try:
        data = await asyncio.to_thread(service.get_fundamentals, symbol)
        return data
    except ServiceUnavailableError:
        raise
    except Exception:
        raise ServiceUnavailableError("Fundamentals data temporarily unavailable")
