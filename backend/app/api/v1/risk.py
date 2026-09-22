"""Risk API — VaR/CVaR, Monte Carlo, Stress Tests.

VaR/CVaR: Historical simulation (no distribution assumption).
Monte Carlo: GBM-based, runs async via Celery, poll for result.
Stress Tests: Pre-calibrated scenarios for PSX market.
"""

import asyncio
import logging
from dataclasses import dataclass

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import AppError, NotFoundError, ServiceUnavailableError
from app.core.rate_limiter import limiter
from app.db.session import get_db
from app.models.portfolio import PortfolioTransaction, TransactionType
from app.models.stock import Stock
from app.models.user import User
from app.repository.portfolio_repository import PortfolioRepository
from app.ml.serving.schemas import (
    MonteCarloRequest,
    MonteCarloResponse,
    MonteCarloResultResponse,
    RiskVaRResponse,
    StressTestResponse,
)

log = logging.getLogger(__name__)

router = APIRouter()


@dataclass
class HoldingInfo:
    symbol: str
    sector: str
    current_value: float
    allocation_pct: float


async def _get_holdings(db: AsyncSession, user_id: str) -> list[HoldingInfo]:
    """Fetch portfolio holdings with symbol/sector/value for risk calculations.

    Computes current_value from quantity * live price and allocation_pct
    from each holding's share of total portfolio value.
    """
    from app.services.portfolio_service import PortfolioService
    from app.repository.portfolio_repository import PortfolioRepository

    portfolio_service = PortfolioService(db, repo=PortfolioRepository(db))
    holdings = await portfolio_service.get_holdings(user_id)

    if not holdings:
        return []

    holdings_info: list[HoldingInfo] = []
    for h in holdings:
        if isinstance(h, dict):
            symbol = h.get("symbol", "")
            sector = h.get("sector") or "default"
            current_value = float(h.get("market_value") or h.get("current_value") or 0)
        else:
            symbol = getattr(h, "symbol", "")
            sector = getattr(h, "sector", None) or "default"
            current_value = float(getattr(h, "market_value", None) or getattr(h, "current_value", 0) or 0)
        holdings_info.append(
            HoldingInfo(
                symbol=symbol,
                sector=sector,
                current_value=current_value,
                allocation_pct=0.0,
            )
        )

    total_value = sum(h.current_value for h in holdings_info)
    if total_value > 0:
        for h in holdings_info:
            h.allocation_pct = round((h.current_value / total_value) * 100, 2)

    return holdings_info


@router.get(
    "/risk/var",
    response_model=RiskVaRResponse,
    summary="Calculate portfolio Value at Risk and CVaR (Historical Simulation)",
)
@limiter.limit("10/minute")
async def get_var(
    request: Request,
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

        result = await asyncio.to_thread(
            calculate_var, holdings, confidence=confidence, horizon=horizon
        )
        return RiskVaRResponse(
            confidence=result["confidence"],
            horizon=result["horizon"],
            var_value=result["var"],
            cvar_value=result["cvar"],
            method=result["method"],
            num_observations=result["num_observations"],
            annualized_volatility=result["annualized_volatility"],
        )
    except AppError:
        raise
    except Exception:
        log.exception("VaR calculation failed")
        raise ServiceUnavailableError("VaR calculation temporarily unavailable.")


@router.post(
    "/risk/monte-carlo",
    response_model=MonteCarloResponse,
    status_code=202,
    summary="Start async Monte Carlo simulation (GBM)",
)
@limiter.limit("3/minute")
async def run_monte_carlo(
    request: Request,
    data: MonteCarloRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        holdings = await _get_holdings(db, user.id)
        if not holdings:
            raise NotFoundError("No portfolio holdings found for Monte Carlo simulation.")

        from app.tasks.risk_tasks import run_monte_carlo_task
        from app.core.task_runner import dispatch_task
        import uuid

        symbols = [h.symbol for h in holdings]
        task_future = dispatch_task(
            run_monte_carlo_task,
            user_id=user.id,
            symbols=symbols,
            num_simulations=data.num_simulations,
            horizon_days=data.horizon_days,
        )
        task_id = getattr(task_future, "id", uuid.uuid4().hex)

        return MonteCarloResponse(
            job_id=str(task_id),
            status="pending",
            num_simulations=data.num_simulations,
            horizon_days=data.horizon_days,
        )
    except AppError:
        raise
    except Exception:
        log.exception("Monte Carlo start failed")
        raise ServiceUnavailableError("Monte Carlo simulation temporarily unavailable.")


@router.get(
    "/risk/monte-carlo/{task_id}",
    response_model=MonteCarloResultResponse,
    summary="Poll Monte Carlo simulation result",
)
@limiter.limit("30/minute")
async def get_monte_carlo_result(
    request: Request,
    task_id: str,
    user: User = Depends(get_current_user),
):
    try:
        from app.core.task_runner import get_local_job_result

        local_result = get_local_job_result(task_id)
        if local_result is not None:
            state, result, error = local_result
        else:
            from celery.result import AsyncResult
            from app.tasks.risk_tasks import run_monte_carlo_task
            task_result = AsyncResult(task_id, app=run_monte_carlo_task.app)
            state, result, error = task_result.state, task_result.result, None

        if state == "PENDING":
            return MonteCarloResultResponse(
                job_id=task_id, status="pending",
            )
        elif state == "FAILURE":
            log.warning("Monte Carlo task failed: task_id=%s user=%s", task_id, user.id)
            return MonteCarloResultResponse(
                job_id=task_id, status="failed",
                error="Simulation failed. Please try again.",
            )
        elif state == "SUCCESS":
            result_owner = result.get("user_id")
            if not result_owner or result_owner != user.id:
                raise NotFoundError("Task not found.")

            return MonteCarloResultResponse(
                job_id=task_id,
                status="completed",
                num_simulations=result.get("num_simulations"),
                horizon_days=result.get("horizon_days"),
                params=result.get("params"),
                percentiles=result.get("percentiles"),
                stats=result.get("stats"),
                paths_sample=result.get("paths_sample"),
                completed_at=result.get("completed_at"),
            )
        else:
            return MonteCarloResultResponse(
                job_id=task_id, status=state,
            )
    except AppError:
        raise
    except Exception:
        log.exception("Monte Carlo result fetch failed")
        raise ServiceUnavailableError("Monte Carlo result temporarily unavailable.")


@router.get(
    "/risk/stress-test",
    response_model=StressTestResponse,
    summary="Run stress test scenario on portfolio",
)
@limiter.limit("10/minute")
async def run_stress_test(
    request: Request,
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

        result = await asyncio.to_thread(run_stress, holdings, scenario)
        return StressTestResponse(**result)
    except Exception:
        log.exception("Stress test failed")
        raise ServiceUnavailableError("Stress test temporarily unavailable.")
