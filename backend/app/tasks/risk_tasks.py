"""Celery tasks for risk calculations.

Monte Carlo runs async (compute-heavy), result cached to disk.
Threshold-breach alerts hook into Module 9 (alert_service).
"""

import logging
import uuid
from datetime import datetime

from celery import shared_task

log = logging.getLogger(__name__)


def _get_sync_db():
    """Get a synchronous DB session for Celery tasks."""
    from app.db.base import get_sync_session_factory
    return get_sync_session_factory()()


def _get_user_holdings_sync(user_id: str, symbols: list[str] | None = None):
    """Get portfolio holdings synchronously with computed current_value and allocation_pct."""
    from app.models.portfolio import PortfolioTransaction, TransactionType
    from app.models.stock import Stock
    from sqlalchemy import select

    db = _get_sync_db()
    try:
        rows = db.execute(
            select(PortfolioTransaction, Stock)
            .join(Stock, PortfolioTransaction.symbol == Stock.symbol)
            .where(PortfolioTransaction.user_id == user_id)
            .order_by(PortfolioTransaction.transaction_date, PortfolioTransaction.created_at)
        ).all()

        from app.services.stock_service import StockService

        stock_service = StockService()
        filtered_rows = []
        positions: dict[str, float] = {}
        sectors: dict[str, str] = {}
        for transaction, stock in rows:
            quantity = float(transaction.quantity)
            positions[stock.symbol] = positions.get(stock.symbol, 0.0) + (quantity if transaction.transaction_type == TransactionType.BUY else -quantity)
            sectors[stock.symbol] = stock.sector or "default"
        filtered_rows = []
        for symbol, quantity in positions.items():
            if quantity <= 0 or (symbols and symbol not in symbols):
                continue
            filtered_rows.append((symbol, quantity))

        if not filtered_rows:
            return []

        stock_symbols = [symbol for symbol, _ in filtered_rows]
        quotes = stock_service.get_quote_batch(stock_symbols)
        quote_map = {sym: q for sym, q in zip(stock_symbols, quotes)}

        holdings = []
        total_value = 0.0
        from types import SimpleNamespace
        for symbol, quantity in filtered_rows:
            quote = quote_map.get(symbol)
            current_price = quote.get("current") if quote else None
            current_value = (float(current_price) * quantity) if current_price else 0.0
            holding = SimpleNamespace(symbol=symbol, sector=sectors[symbol], current_value=current_value, allocation_pct=0.0)
            total_value += current_value
            holdings.append(holding)

        for h in holdings:
            h.allocation_pct = round((h.current_value / total_value) * 100, 2) if total_value > 0 else 0.0

        return holdings
    finally:
        db.close()


@shared_task(
    name="app.tasks.risk_tasks.run_monte_carlo",
    bind=True,
    max_retries=2,
    acks_late=True,
    soft_time_limit=120,
    time_limit=180,
)
def run_monte_carlo_task(
    self,
    user_id: str,
    symbols: list[str] | None = None,
    holdings_snapshot: list[dict] | None = None,
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

    job_id = (self.request.id if getattr(self, "request", None) and self.request.id else None) or uuid.uuid4().hex
    log.info("Monte Carlo task started: job=%s user=%s sims=%d horizon=%d",
             job_id, user_id, num_simulations, horizon_days)

    try:
        if holdings_snapshot is not None:
            from types import SimpleNamespace
            holdings = [SimpleNamespace(**item) for item in holdings_snapshot]
        else:
            holdings = _get_user_holdings_sync(user_id, symbols)

        if not holdings:
            result = {
                "job_id": job_id,
                "status": "error",
                "user_id": user_id,
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
        result["user_id"] = user_id
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
def check_threshold_breaches_task(self, user_id: str, risk_tolerance: str | None = None):
    """Check portfolio for risk threshold breaches calibrated by user risk tolerance.

    Calibrated Thresholds:
      - Conservative: VaR > 2.5%, CVaR > 4.0%, Concentration > 20%
      - Moderate:     VaR > 3.5%, CVaR > 5.5%, Concentration > 30%
      - Aggressive:   VaR > 5.0%, CVaR > 7.5%, Concentration > 45%
    """
    from app.services.risk_service import calculate_var

    log.info("Threshold breach check: user=%s risk_tolerance=%s", user_id, risk_tolerance)

    profile_limits = {
        "conservative": {"var": 0.025, "cvar": 0.040, "conc": 0.20},
        "moderate": {"var": 0.035, "cvar": 0.055, "conc": 0.30},
        "aggressive": {"var": 0.050, "cvar": 0.075, "conc": 0.45},
    }
    limits = profile_limits.get(str(risk_tolerance).lower(), profile_limits["moderate"])

    try:
        holdings = _get_user_holdings_sync(user_id)
        if not holdings:
            return {"status": "no_holdings", "breaches": []}

        breaches = []

        # VaR check
        var_result = calculate_var(holdings, confidence=95, horizon="1D")
        if var_result["var"] is not None and abs(var_result["var"]) > limits["var"]:
            breaches.append({
                "type": "var_breach",
                "severity": "high",
                "message": f"VaR(95%) = {abs(var_result['var'])*100:.2f}% exceeds {limits['var']*100:.1f}% threshold",
                "value": var_result["var"],
                "threshold": -limits["var"],
            })

        # CVaR check
        if var_result["cvar"] is not None and abs(var_result["cvar"]) > limits["cvar"]:
            breaches.append({
                "type": "cvar_breach",
                "severity": "critical",
                "message": f"CVaR(95%) = {abs(var_result['cvar'])*100:.2f}% exceeds {limits['cvar']*100:.1f}% threshold",
                "value": var_result["cvar"],
                "threshold": -limits["cvar"],
            })

        # Concentration check
        for h in holdings:
            weight = float(h.allocation_pct or 0) / 100.0
            if weight > limits["conc"]:
                breaches.append({
                    "type": "concentration_breach",
                    "severity": "medium",
                    "message": f"{h.symbol} weight = {weight*100:.1f}% exceeds {limits['conc']*100:.0f}% limit",
                    "symbol": h.symbol,
                    "value": weight,
                    "threshold": limits["conc"],
                })

        # Create alerts via Module 9 (sync DB)
        if breaches:
            try:
                _send_alerts_sync(user_id, breaches)
                log.info("Threshold alerts sent: user=%s count=%d", user_id, len(breaches))
            except Exception:
                log.exception("Failed to send threshold alerts: user=%s", user_id)

        return {
            "status": "checked",
            "breaches": breaches,
            "checked_at": datetime.utcnow().isoformat(),
        }

    except Exception as exc:
        log.exception("Threshold breach check failed: user=%s", user_id)
        raise self.retry(exc=exc, countdown=120)


def _send_alerts_sync(user_id: str, breaches: list[dict]):
    """Send threshold breach alerts via sync DB session (Module 9)."""
    from uuid import uuid4
    from app.models.alert import Alert

    db = _get_sync_db()
    try:
        for b in breaches:
            alert = Alert(
                id=uuid4().hex,
                user_id=user_id,
                title=f"[{b['severity'].upper()}] {b['type'].replace('_', ' ').title()}",
                message=b["message"],
            )
            db.add(alert)
        db.commit()
        from app.tasks.push_notifications import send_to_user
        from app.core.task_runner import dispatch_task
        for breach in breaches:
            dispatch_task(
                send_to_user,
                user_id,
                f"Basarat risk alert: {breach['severity'].upper()}",
                breach["message"],
                {"type": breach["type"], "severity": breach["severity"]},
            )
    finally:
        db.close()


@shared_task(
    name="app.tasks.risk_tasks.check_all_portfolios_risk_breaches",
    bind=True,
    max_retries=1,
    acks_late=True,
)
def check_all_portfolios_risk_breaches(self):
    """Check risk threshold breaches across all users with active portfolio holdings."""
    from app.models.portfolio import PortfolioTransaction
    from sqlalchemy import select

    db = _get_sync_db()
    try:
        user_ids = list(db.scalars(
            select(PortfolioTransaction.user_id).distinct()
        ))
        log.info("Checking risk breaches for %d portfolio owners", len(user_ids))
        results = {}
        for uid in user_ids:
            try:
                res = check_threshold_breaches_task(uid)
                results[uid] = len(res.get("breaches", []))
            except Exception as e:
                log.warning("Risk breach check failed for user %s: %s", uid, e)
        return {"status": "completed", "evaluated_users": len(user_ids), "breach_summary": results}
    finally:
        db.close()
