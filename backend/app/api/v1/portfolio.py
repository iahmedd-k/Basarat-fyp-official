from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import ServiceUnavailableError
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

router = APIRouter()


def _get_service(db: AsyncSession = Depends(get_db)) -> PortfolioService:
    repo = PortfolioRepository(db)
    stocks = StockService()
    return PortfolioService(portfolio_repo=repo, stock_service=stocks)


@router.get(
    "/portfolio",
    response_model=PortfolioResponse,
    summary="Get portfolio holdings and total value",
)
async def get_portfolio(
    user: User = Depends(get_current_user),
    service: PortfolioService = Depends(_get_service),
):
    try:
        return await service.get_portfolio(user.id)
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to fetch portfolio: {exc}")


@router.post(
    "/portfolio/holdings",
    response_model=HoldingResponse,
    status_code=201,
    summary="Add a new holding to portfolio",
)
async def add_holding(
    data: HoldingCreate,
    user: User = Depends(get_current_user),
    service: PortfolioService = Depends(_get_service),
):
    try:
        return await service.add_holding(user.id, data)
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to add holding: {exc}")


@router.patch(
    "/portfolio/holdings/{holding_id}",
    response_model=HoldingResponse,
    summary="Update an existing holding",
)
async def update_holding(
    holding_id: str,
    data: HoldingUpdate,
    user: User = Depends(get_current_user),
    service: PortfolioService = Depends(_get_service),
):
    try:
        return await service.update_holding(user.id, holding_id, data)
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to update holding: {exc}")


@router.delete(
    "/portfolio/holdings/{holding_id}",
    status_code=204,
    summary="Delete a holding from portfolio",
)
async def delete_holding(
    holding_id: str,
    user: User = Depends(get_current_user),
    service: PortfolioService = Depends(_get_service),
):
    try:
        await service.delete_holding(user.id, holding_id)
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to delete holding: {exc}")


@router.get(
    "/portfolio/pnl",
    response_model=PnLSummary,
    summary="Get unrealized P&L summary",
)
async def get_pnl(
    user: User = Depends(get_current_user),
    service: PortfolioService = Depends(_get_service),
):
    try:
        return await service.get_pnl(user.id)
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to fetch P&L: {exc}")


@router.get(
    "/portfolio/allocation",
    response_model=AllocationResponse,
    summary="Get sector allocation breakdown",
)
async def get_allocation(
    user: User = Depends(get_current_user),
    service: PortfolioService = Depends(_get_service),
):
    try:
        return await service.get_allocation(user.id)
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to fetch allocation: {exc}")


@router.get(
    "/portfolio/risk-metrics",
    response_model=RiskMetricsResponse,
    summary="Get portfolio risk metrics (VaR, Sharpe, max drawdown)",
)
async def get_risk_metrics(
    user: User = Depends(get_current_user),
    service: PortfolioService = Depends(_get_service),
):
    try:
        return await service.get_risk_metrics(user.id)
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to fetch risk metrics: {exc}")
