"""Celery tasks for risk calculations.

Monte Carlo runs async (compute-heavy), result cached to disk.
Threshold-breach alerts hook into Module 9 (alert_service).
"""

import asyncio
import logging
import uuid
from datetime import datetime

from celery import shared_task

log = logging.getLogger(__name__)


def _get_sync_db():
    """Get a synchronous DB session for Celery tasks."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.config import settings

    engine = create_engine(settings.DATABASE_URL_SYNC)
    Session = sessionmaker(bind=engine)
    return Session()


def _get_user_holdings_sync(user_id: str, symbols: list[str] | None = None):
    """Get portfolio holdings synchronously."""
    from app.models.portfolio import Portfolio, PortfolioHolding
    from app.models.stock import Stock
    from sqlalchemy import select

    db = _get_sync_db()
    try:
        result = db.execute(
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
        result = db.execute(q)
        rows = result.all()

        holdings = []
        for holding, stock in rows:
            if symbols and stock.symbol not in symbols:
                continue
            # Attach symbol and sector to holding for risk calculations
            holding.symbol = stock.symbol
            holding.sector = getattr(stock, "sector", "default") or "default"
            holdings.append(holding)
        return holdings
    finally:
        db.close()


@shared_task(
    name="app.tasks.risk_tasks.run_monte_carlo",
    bind=True,
    max_retries=2,
    acks_late=True,
)
def run_monte_carlo_task(
    self,
    user_id: str,
    symbols: list[str] | None = None,
    num_simulations: int = 1000,
    horizon_days: int = 30,
    seed: int | None = None,
):
    """Run Monte Carlo simulation async via Celery.

    Args:
        user_id: owning user
        symbols: stock symbols to include (None = full portfolio)
        num_simulations: number of MC paths (100-10000)
        horizon_days: forecast horizon (1-365)
        seed: optional random seed

    Returns:
        {job_id, status, num_simulations, horizon_days, percentiles, stats}
    """
    from app.services.risk_service import (
        run_monte_carlo_simulation,
        save_monte_carlo_result,
    )

    job_id = uuid.uuid4().hex
    log.info("Monte Carlo task started: job=%s user=%s sims=%d horizon=%d",
             job_id, user_id, num_simulations, horizon_days)

    try:
        holdings = _get_user_holdings_sync(user_id, symbols)

        if not holdings:
            result = {
                "job_id": job_id,
                "status": "completed",
                "message": "No holdings found",
                "num_simulations": num_simulations,
                "horizon_days": horizon_days,
                "percentiles": {},
                "stats": {},
                "distribution": [],
                "paths_sample": [],
                "completed_at": datetime.utcnow().isoformat(),
            }
            save_monte_carlo_result(job_id, result)
            return result

        result = run_monte_carlo_simulation(
            holdings=holdings,
            num_simulations=num_simulations,
            horizon_days=horizon_days,
            seed=seed,
        )

        result["job_id"] = job_id
        result["completed_at"] = datetime.utcnow().isoformat()
        save_monte_carlo_result(job_id, result)

        log.info("Monte Carlo task completed: job=%s", job_id)
        return result

    except Exception as exc:
        log.exception("Monte Carlo task failed: job=%s", job_id)
        result = {
            "job_id": job_id,
            "status": "failed",
            "error": str(exc),
            "completed_at": datetime.utcnow().isoformat(),
        }
        try:
            save_monte_carlo_result(job_id, result)
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=60)


@shared_task(
    name="app.tasks.risk_tasks.check_threshold_breaches",
    bind=True,
    max_retries=1,
)
def check_threshold_breaches_task(self, user_id: str):
    """Check portfolio for risk threshold breaches → trigger Module 9 alerts.

    Thresholds:
      - VaR(95%) > 3% of portfolio value
      - CVaR(95%) > 5% of portfolio value
      - Single-stock weight > 30%
    """
    from app.services.risk_service import calculate_var

    log.info("Threshold breach check: user=%s", user_id)

    try:
        holdings = _get_user_holdings_sync(user_id)
        if not holdings:
            return {"status": "no_holdings", "breaches": []}

        breaches = []

        # VaR check
        var_result = calculate_var(holdings, confidence=95, horizon="1D")
        if var_result["var"] is not None and abs(var_result["var"]) > 0.03:
            breaches.append({
                "type": "var_breach",
                "severity": "high",
                "message": f"VaR(95%) = {abs(var_result['var'])*100:.2f}% exceeds 3% threshold",
                "value": var_result["var"],
                "threshold": -0.03,
            })

        # CVaR check
        if var_result["cvar"] is not None and abs(var_result["cvar"]) > 0.05:
            breaches.append({
                "type": "cvar_breach",
                "severity": "critical",
                "message": f"CVaR(95%) = {abs(var_result['cvar'])*100:.2f}% exceeds 5% threshold",
                "value": var_result["cvar"],
                "threshold": -0.05,
            })

        # Concentration check
        for h in holdings:
            weight = float(h.allocation_pct or 0) / 100.0
            if weight > 0.30:
                breaches.append({
                    "type": "concentration_breach",
                    "severity": "medium",
                    "message": f"{h.symbol} weight = {weight*100:.1f}% exceeds 30% limit",
                    "symbol": h.symbol,
                    "value": weight,
                    "threshold": 0.30,
                })

        # Create alerts via Module 9 (async, so use event loop)
        if breaches:
            try:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(_send_alerts(user_id, breaches))
                loop.close()
                log.info("Threshold alerts sent: user=%s count=%d", user_id, len(breaches))
            except Exception as alert_exc:
                log.exception("Failed to send threshold alerts: user=%s", user_id)

        return {
            "status": "checked",
            "breaches": breaches,
            "checked_at": datetime.utcnow().isoformat(),
        }

    except Exception as exc:
        log.exception("Threshold breach check failed: user=%s", user_id)
        raise self.retry(exc=exc, countdown=120)


async def _send_alerts(user_id: str, breaches: list[dict]):
    """Send threshold breach alerts via AlertService (Module 9)."""
    from app.db.session import async_session_factory
    from app.models.alert import Alert
    from uuid import uuid4

    async with async_session_factory() as db:
        for b in breaches:
            alert = Alert(
                id=uuid4().hex,
                user_id=user_id,
                title=f"[{b['severity'].upper()}] {b['type'].replace('_', ' ').title()}",
                message=b["message"],
            )
            db.add(alert)
        await db.commit()
