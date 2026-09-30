"""Live price quote endpoints (formerly undeclared portfolio_routes/prices)."""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import NotFoundError
from app.core.rate_limiter import limiter
from app.db.session import get_db
from app.models.user import User
from app.services.portfolio.price_cache_service import PriceCacheService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/prices", tags=["Prices"])


class PriceResponse(BaseModel):
    symbol: str
    ldcp: float = 0.0
    current_price: float = 0.0
    change: float = 0.0
    change_percent: float = 0.0
    volume: int = 0
    market_status: str = "CLOSED"
    last_updated: datetime | str | None = None
    stale: bool = False
    available: bool = True


class BulkPriceRequest(BaseModel):
    symbols: list[str] = Field(..., min_length=1, max_length=100)

    @field_validator("symbols")
    @classmethod
    def _normalize(cls, values: list[str]) -> list[str]:
        cleaned = [str(v).strip().upper() for v in values if v and str(v).strip()]
        if not cleaned:
            raise ValueError("At least one symbol is required")
        # Preserve order, drop duplicates
        seen: set[str] = set()
        out: list[str] = []
        for sym in cleaned:
            if sym not in seen:
                seen.add(sym)
                out.append(sym)
        return out


class BulkPriceResponse(BaseModel):
    prices: dict[str, PriceResponse]


def get_price_cache_service(db: AsyncSession = Depends(get_db)) -> PriceCacheService:
    return PriceCacheService(db=db)


@router.get(
    "/{symbol}",
    response_model=PriceResponse,
    summary="Get live price for a symbol (Redis cache TTL ~30s)",
)
@limiter.limit("60/minute")
async def get_price(
    request: Request,
    symbol: str,
    user: User = Depends(get_current_user),
    price_cache: PriceCacheService = Depends(get_price_cache_service),
):
    data = await price_cache.get_price(symbol)
    if not data.get("available") and float(data.get("current_price") or 0) <= 0:
        raise NotFoundError(f"No price data available for '{symbol.upper()}'.")
    return PriceResponse(**data)


@router.post(
    "/bulk",
    response_model=BulkPriceResponse,
    summary="Get live prices for multiple symbols",
)
@limiter.limit("30/minute")
async def get_bulk_prices(
    request: Request,
    data: BulkPriceRequest = Body(...),
    user: User = Depends(get_current_user),
    price_cache: PriceCacheService = Depends(get_price_cache_service),
):
    raw: dict[str, Any] = await price_cache.get_bulk_prices(data.symbols)
    prices = {sym: PriceResponse(**payload) for sym, payload in raw.items()}
    return BulkPriceResponse(prices=prices)
