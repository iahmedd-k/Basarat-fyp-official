import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import NotFoundError
from app.core.rate_limiter import limiter
from app.db.session import get_db
from app.models.user import User
from app.repository.portfolio_repository import PortfolioRepository
from app.schemas.portfolio import (
    ErrorResponse,
    HoldingDetailResponse,
    PortfolioSummaryResponse,
)
from app.services.portfolio import ValuationEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/portfolio", tags=["portfolio-summary"])


def get_repo(db: AsyncSession = Depends(get_db)) -> PortfolioRepository:
    return PortfolioRepository(db)


def get_valuation_engine(
    db: AsyncSession = Depends(get_db),
    repo: PortfolioRepository = Depends(get_repo),
) -> ValuationEngine:
    # PriceCacheService will be created inside ValuationEngine
    return ValuationEngine(db, repo=repo)


@router.get(
    "/summary",
    response_model=PortfolioSummaryResponse,
    summary="Get portfolio summary with live valuations and P&L",
    responses={404: {"model": ErrorResponse}},
)
@limiter.limit("30/minute")
async def get_portfolio_summary(
    request: Request,
    user: User = Depends(get_current_user),
    valuation: ValuationEngine = Depends(get_valuation_engine),
):
    summary = await valuation.compute_portfolio_summary(user.id)
    return summary


@router.get(
    "/holdings/{symbol}",
    response_model=HoldingDetailResponse,
    summary="Get detailed holding info for a single symbol",
    responses={404: {"model": ErrorResponse}},
)
@limiter.limit("30/minute")
async def get_holding_detail(
    request: Request,
    symbol: str,
    user: User = Depends(get_current_user),
    valuation: ValuationEngine = Depends(get_valuation_engine),
):
    holding = await valuation.compute_holding_detail(user.id, symbol)
    if not holding:
        raise NotFoundError(f"Holding for '{symbol}' not found.")
    return holding