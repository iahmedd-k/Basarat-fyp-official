"""Risk API — VaR, CVaR, Monte Carlo, Stress Tests.

VaR/CVaR: Historical simulation (no distribution assumption).
Monte Carlo: GBM-based, runs async via Celery, poll for result.
Stress Tests: Pre-calibrated scenarios for PSX market.
"""

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import ServiceUnavailableError, NotFoundError
from app.db.session import get_db
from app.models.portfolio import Portfolio, PortfolioHolding
from app.models.stock import Stock
from app.models.user import User
from app.ml.serving.schemas import (
    MonteCarloRequest,
    MonteCarloResponse,
    RiskVaRResponse,
    StressTestResponse,
)

log = logging.getLogger(__name__)

router = APIRouter()


async def _get_holdings(db: AsyncSession, user_id: str) -> list:
    """Fetch portfolio holdings with symbol/sector for risk calculations."""
    result = await db.execute(
        select(Portfolio).where(Portfolio.user_id == user_id).limit(1)
    )
    portfolio = result.scalars().first()
    if not portfolio:
        return []

    q = (
        select(PortfolioHolding, Stock)
        .join(Stock, PortfolioHolding.stock_id == Stock.id)
        .where(PortfolioHolding.portfolio_id == portfolio.id)
    )
    result = await db.execute(q)
    rows = result.all()

    holdings = []
    for holding, stock in rows:
        holding.symbol = stock.symbol
        holding.sector = getattr(stock, "sector", "default") or "default"
        holdings.append(holding)
    return holdings


@router.get(
    "/risk/var",
    response_model=RiskVaRResponse,
    summary="Calculate portfolio Value at Risk (Historical Simulation)",
)
async def get_var(
    confidence: int = Query(95, ge=90, le=99),
    horizon: str = Query("1D", pattern="^(1D|1W|1M)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        from app.services.risk_service import calculate_var

        holdings = await _get_holdings(db, user.id)
        if not holdings:
            return RiskVaRResponse(
                confidence=confidence,
                horizon=horizon,
                var_value=None,
                cvar_value=None,
                method="historical_simulation",
                num_observations=0,
                annualized_volatility=None,
            )

        result = calculate_var(holdings, confidence=confidence, horizon=horizon)
        return RiskVaRResponse(
            confidence=result["confidence"],
            horizon=result["horizon"],
            var_value=result["var"],
            cvar_value=result["cvar"],
            method=result["method"],
            num_observations=result["num_observations"],
            annualized_volatility=result["annualized_volatility"],
        )
    except Exception as exc:
        log.exception("VaR calculation failed")
        raise ServiceUnavailableError(f"Failed to calculate VaR: {exc}")


@router.get(
    "/risk/cvar",
    response_model=RiskVaRResponse,
    summary="Calculate Conditional Value at Risk (Historical Simulation)",
)
async def get_cvar(
    confidence: int = Query(95, ge=90, le=99),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        from app.services.risk_service import calculate_var

        holdings = await _get_holdings(db, user.id)
        if not holdings:
            return RiskVaRResponse(
                confidence=confidence,
                horizon="1D",
                var_value=None,
                cvar_value=None,
                method="historical_simulation",
                num_observations=0,
                annualized_volatility=None,
            )

        result = calculate_var(holdings, confidence=confidence, horizon="1D")
        return RiskVaRResponse(
            confidence=result["confidence"],
            horizon=result["horizon"],
            var_value=result["var"],
            cvar_value=result["cvar"],
            method=result["method"],
            num_observations=result["num_observations"],
            annualized_volatility=result["annualized_volatility"],
        )
    except Exception as exc:
        log.exception("CVaR calculation failed")
        raise ServiceUnavailableError(f"Failed to calculate CVaR: {exc}")


@router.post(
    "/risk/monte-carlo",
    response_model=MonteCarloResponse,
    status_code=202,
    summary="Start async Monte Carlo simulation (GBM)",
)
async def run_monte_carlo(
    data: MonteCarloRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        holdings = await _get_holdings(db, user.id)
        if not holdings:
            raise NotFoundError("No portfolio holdings found for Monte Carlo simulation")

        from app.tasks.risk_tasks import run_monte_carlo_task

        symbols = [h.symbol for h in holdings]
        task = run_monte_carlo_task.delay(
            user_id=user.id,
            symbols=symbols,
            num_simulations=data.num_simulations,
            horizon_days=data.horizon_days,
        )

        return MonteCarloResponse(
            job_id=task.id,
            status="pending",
            num_simulations=data.num_simulations,
            horizon_days=data.horizon_days,
        )
    except NotFoundError:
        raise
    except Exception as exc:
        log.exception("Monte Carlo start failed")
        raise ServiceUnavailableError(f"Failed to start Monte Carlo: {exc}")


@router.get(
    "/risk/monte-carlo/{task_id}",
    response_model=dict,
    summary="Poll Monte Carlo simulation result",
)
async def get_monte_carlo_result(
    task_id: str,
    user: User = Depends(get_current_user),
):
    try:
        from celery.result import AsyncResult
        from app.tasks.risk_tasks import run_monte_carlo_task

        task_result = AsyncResult(task_id, app=run_monte_carlo_task.app)

        if task_result.state == "PENDING":
            return {"job_id": task_id, "status": "pending", "message": "Simulation is queued"}
        elif task_result.state == "FAILURE":
            return {
                "job_id": task_id,
                "status": "failed",
                "error": str(task_result.info),
            }
        elif task_result.state == "SUCCESS":
            result = task_result.result
            return {
                "job_id": task_id,
                "status": "completed",
                "num_simulations": result.get("num_simulations"),
                "horizon_days": result.get("horizon_days"),
                "params": result.get("params"),
                "percentiles": result.get("percentiles"),
                "stats": result.get("stats"),
                "paths_sample": result.get("paths_sample"),
                "completed_at": result.get("completed_at"),
            }
        else:
            return {"job_id": task_id, "status": task_result.state}

    except Exception as exc:
        log.exception("Monte Carlo result fetch failed")
        raise ServiceUnavailableError(f"Failed to fetch Monte Carlo result: {exc}")


@router.get(
    "/risk/stress-test",
    response_model=StressTestResponse,
    summary="Run stress test scenario on portfolio",
)
async def run_stress_test(
    scenario: str = Query(
        "2008_crash",
        pattern="^(2008_crash|pkr_devaluation|covid_crash|interest_rate_hike)$",
    ),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        from app.services.risk_service import run_stress_test as run_stress

        holdings = await _get_holdings(db, user.id)
        if not holdings:
            return StressTestResponse(
                scenario=scenario,
                name=scenario,
                description="No holdings",
                portfolio_impact=0,
                portfolio_impact_value=0,
                worst_case_loss=0,
                volatility_multiplier=1.0,
                recovery_days=0,
                current_value=0,
                stressed_value=0,
                holding_impacts=[],
            )

        result = run_stress(holdings, scenario)
        return StressTestResponse(**result)

    except Exception as exc:
        log.exception("Stress test failed")
        raise ServiceUnavailableError(f"Failed to run stress test: {exc}")
