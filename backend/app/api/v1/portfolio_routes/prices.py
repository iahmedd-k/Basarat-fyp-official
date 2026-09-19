import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import BadRequestError, NotFoundError
from app.core.rate_limiter import limiter
from app.db.session import get_db
from app.models.user import User
from app.repository.portfolio_repository import PortfolioRepository
from app.schemas.portfolio import (
    BulkPriceRequest,
    BulkPriceResponse,
    ErrorResponse,
    PriceResponse,
)
from app.services.portfolio import PriceCacheService, PSXApiClient
from app.services.stock_service import StockService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/prices", tags=["prices"])


def get_repo(db: AsyncSession = Depends(get_db)) -> PortfolioRepository:
    return PortfolioRepository(db)


def get_psx_client(stock_service: StockService = Depends(StockService)) -> PSXApiClient:
    return PSXApiClient(stock_service)


def get_price_cache_service(
    db: AsyncSession = Depends(get_db),
    psx_client: PSXApiClient = Depends(get_psx_client),
    repo: PortfolioRepository = Depends(get_repo),
) -> PriceCacheService:
    return PriceCacheService(db, psx_client, repo)


@router.get(
    "/{symbol}",
    response_model=PriceResponse,
    summary="Get live price for a symbol (checks cache first, TTL ~30s)",
    responses={404: {"model": ErrorResponse}},
)
@limiter.limit("60/minute")
async def get_price(
    request: Request,
    symbol: str,
    user: User = Depends(get_current_user),
    price_cache: PriceCacheService = Depends(get_price_cache_service),
):
    price_data = await price_cache.get_price(symbol)
    return price_data


@router.post(
    "/bulk",
    response_model=BulkPriceResponse,
    summary="Get live prices for multiple symbols (used internally by portfolio summary)",
)
@limiter.limit("30/minute")
async def get_bulk_prices(
    request: Request,
    data: BulkPriceRequest,
    user: User = Depends(get_current_user),
    price_cache: PriceCacheService = Depends(get_price_cache_service),
):
    prices = await price_cache.get_bulk_prices(data.symbols)
    return {"prices": prices}