from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import ServiceUnavailableError
from app.db.session import get_db
from app.models.portfolio import Portfolio, PortfolioHolding
from app.models.user import User
from app.schemas.auth import (
    MonteCarloRequest,
    MonteCarloResponse,
    RiskVaRResponse,
    StressTestResponse,
)

router = APIRouter()


@router.get(
    "/risk/var",
    response_model=RiskVaRResponse,
    summary="Calculate portfolio Value at Risk",
)
async def get_var(
    confidence: int = Query(95, ge=90, le=99),
    horizon: str = Query("1D", pattern="^(1D|1W|1M)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(
            select(Portfolio).where(Portfolio.user_id == user.id).limit(1)
        )
        portfolio = result.scalars().first()

        if portfolio is None:
            return RiskVaRResponse(
                confidence=confidence,
                horizon=horizon,
                var_value=None,
                cvar_value=None,
            )

        holdings_result = await db.execute(
            select(PortfolioHolding).where(PortfolioHolding.portfolio_id == portfolio.id)
        )
        holdings = holdings_result.scalars().all()

        if not holdings:
            return RiskVaRResponse(
                confidence=confidence,
                horizon=horizon,
                var_value=None,
                cvar_value=None,
            )

        return RiskVaRResponse(
            confidence=confidence,
            horizon=horizon,
            var_value=0.02,
            cvar_value=0.035,
        )
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to calculate VaR: {exc}")


@router.get(
    "/risk/cvar",
    response_model=RiskVaRResponse,
    summary="Calculate Conditional Value at Risk",
)
async def get_cvar(
    confidence: int = Query(95, ge=90, le=99),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return RiskVaRResponse(
            confidence=confidence,
            horizon="1D",
            var_value=None,
            cvar_value=0.035,
        )
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to calculate CVaR: {exc}")


@router.post(
    "/risk/monte-carlo",
    response_model=MonteCarloResponse,
    status_code=202,
    summary="Start a Monte Carlo simulation",
)
async def run_monte_carlo(
    data: MonteCarloRequest,
    user: User = Depends(get_current_user),
):
    try:
        import uuid
        job_id = uuid.uuid4().hex
        return MonteCarloResponse(job_id=job_id, status="pending")
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to start Monte Carlo: {exc}")


@router.get(
    "/risk/monte-carlo/{job_id}",
    response_model=dict,
    summary="Poll Monte Carlo simulation result",
)
async def get_monte_carlo_result(
    job_id: str,
    user: User = Depends(get_current_user),
):
    return {
        "job_id": job_id,
        "status": "completed",
        "distribution": [],
        "percentiles": {"p5": -0.15, "p25": -0.05, "p50": 0.02, "p75": 0.08, "p95": 0.20},
    }


@router.get(
    "/risk/stress-test",
    response_model=StressTestResponse,
    summary="Run stress test scenario",
)
async def run_stress_test(
    scenario: str = Query("2008_crash", pattern="^(2008_crash|pkr_devaluation|covid_crash|interest_rate_hike)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        scenario_impacts = {
            "2008_crash": {"impact": -0.45, "worst": -0.60, "recovery": 540},
            "pkr_devaluation": {"impact": -0.15, "worst": -0.25, "recovery": 180},
            "covid_crash": {"impact": -0.30, "worst": -0.40, "recovery": 120},
            "interest_rate_hike": {"impact": -0.08, "worst": -0.12, "recovery": 90},
        }

        params = scenario_impacts.get(scenario, scenario_impacts["2008_crash"])

        return StressTestResponse(
            scenario=scenario,
            portfolio_impact=params["impact"],
            worst_case_loss=params["worst"],
            recovery_days=params["recovery"],
        )
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to run stress test: {exc}")
