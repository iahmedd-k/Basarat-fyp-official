import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import AppError, ServiceUnavailableError
from app.core.rate_limiter import limiter
from app.db.session import get_db
from app.models.user import User
from app.repository.portfolio_repository import PortfolioRepository
from app.schemas.portfolio import (
    AllocationResponse,
    HoldingCreate,
    HoldingResponse,
    HoldingUpdate,
    PnLSummary,
    PortfolioResponse,
    RiskMetricsResponse,
)
from app.services.portfolio_service import PortfolioService
from app.services.stock_service import StockService

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_service(
    db: AsyncSession = Depends(get_db),
    stock_service: StockService = Depends(StockService),
) -> PortfolioService:
    repo = PortfolioRepository(db)
    return PortfolioService(portfolio_repo=repo, stock_service=stock_service)


@router.get(
    "/portfolio",
    response_model=PortfolioResponse,
    summary="Get portfolio holdings and total value",
)
@limiter.limit("30/minute")
async def get_portfolio(
    request: Request,
    user: User = Depends(get_current_user),
    service: PortfolioService = Depends(_get_service),
):
    try:
        return await service.get_portfolio(user.id)
    except AppError:
        raise
    except Exception:
        logger.exception("Failed to fetch portfolio")
        raise ServiceUnavailableError("Portfolio temporarily unavailable.")


@router.post(
    "/portfolio/holdings",
    response_model=HoldingResponse,
    status_code=201,
    summary="Add a new holding to portfolio",
)
@limiter.limit("10/minute")
async def add_holding(
    request: Request,
    data: HoldingCreate,
    user: User = Depends(get_current_user),
    service: PortfolioService = Depends(_get_service),
):
    try:
        return await service.add_holding(user.id, data)
    except AppError:
        raise
    except Exception:
        logger.exception("Failed to add holding")
        raise ServiceUnavailableError("Failed to add holding.")


@router.patch(
    "/portfolio/holdings/{holding_id}",
    response_model=HoldingResponse,
    summary="Update an existing holding",
)
@limiter.limit("10/minute")
async def update_holding(
    request: Request,
    holding_id: str,
    data: HoldingUpdate,
    user: User = Depends(get_current_user),
    service: PortfolioService = Depends(_get_service),
):
    try:
        return await service.update_holding(user.id, holding_id, data)
    except AppError:
        raise
    except Exception:
        logger.exception("Failed to update holding")
        raise ServiceUnavailableError("Failed to update holding.")


@router.delete(
    "/portfolio/holdings/{holding_id}",
    status_code=204,
    summary="Delete a holding from portfolio",
)
@limiter.limit("10/minute")
async def delete_holding(
    request: Request,
    holding_id: str,
    user: User = Depends(get_current_user),
    service: PortfolioService = Depends(_get_service),
):
    try:
        await service.delete_holding(user.id, holding_id)
    except AppError:
        raise
    except Exception:
        logger.exception("Failed to delete holding")
        raise ServiceUnavailableError("Failed to delete holding.")


@router.get(
    "/portfolio/pnl",
    response_model=PnLSummary,
    summary="Get unrealized P&L summary",
)
@limiter.limit("30/minute")
async def get_pnl(
    request: Request,
    user: User = Depends(get_current_user),
    service: PortfolioService = Depends(_get_service),
):
    try:
        return await service.get_pnl(user.id)
    except AppError:
        raise
    except Exception:
        logger.exception("Failed to fetch P&L")
        raise ServiceUnavailableError("Failed to fetch P&L.")


@router.get(
    "/portfolio/allocation",
    response_model=AllocationResponse,
    summary="Get sector allocation breakdown",
)
@limiter.limit("30/minute")
async def get_allocation(
    request: Request,
    user: User = Depends(get_current_user),
    service: PortfolioService = Depends(_get_service),
):
    try:
        return await service.get_allocation(user.id)
    except AppError:
        raise
    except Exception:
        logger.exception("Failed to fetch allocation")
        raise ServiceUnavailableError("Failed to fetch allocation.")


@router.get(
    "/portfolio/risk-metrics",
    response_model=RiskMetricsResponse,
    summary="Get portfolio risk metrics (VaR, Sharpe, max drawdown)",
)
@limiter.limit("5/minute")
async def get_risk_metrics(
    request: Request,
    user: User = Depends(get_current_user),
    service: PortfolioService = Depends(_get_service),
):
    try:
        return await service.get_risk_metrics(user.id)
    except AppError:
        raise
    except Exception:
        logger.exception("Failed to fetch risk metrics")
        raise ServiceUnavailableError("Failed to fetch risk metrics.")
