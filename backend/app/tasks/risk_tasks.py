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
    """Send threshold breach alerts via sync DB session with 24h deduplication (Industry Standard)."""
    from datetime import datetime, timedelta
    from uuid import uuid4
    from sqlalchemy import select
    from app.models.alert import Alert
    from app.core.redis import get_sync_redis_client
    from app.tasks.push_notifications import send_to_user
    from app.core.task_runner import dispatch_task

    redis_client = None
    try:
        redis_client = get_sync_redis_client()
    except Exception as exc:
        log.warning("Sync Redis client unavailable for risk breach alert deduplication: %s", exc)

    db = _get_sync_db()
    alerts_to_send = []
    try:
        cutoff_24h = datetime.utcnow() - timedelta(hours=24)
        for b in breaches:
            breach_type = str(b.get("type", "unknown"))
            sym = str(b.get("symbol", "")).upper()
            title = f"[{b['severity'].upper()}] {breach_type.replace('_', ' ').title()}"

            # 1. Redis Cooldown (24 hours / 86400s)
            cooldown_key = f"alert:cooldown:risk:{user_id}:{breach_type}"
            if sym:
                cooldown_key += f":{sym}"

            in_cooldown = False
            if redis_client:
                try:
                    is_new = redis_client.set(cooldown_key, "1", nx=True, ex=86400)
                    if not is_new:
                        in_cooldown = True
                except Exception as exc:
                    log.warning("Redis risk cooldown check failed for %s: %s", cooldown_key, exc)

            # 2. DB fallback deduplication: check if identical breach alert was created in last 24h
            if not in_cooldown:
                existing = db.execute(
                    select(Alert.id).where(
                        Alert.user_id == user_id,
                        Alert.title == title,
                        Alert.created_at >= cutoff_24h,
                    ).limit(1)
                ).scalar()
                if existing:
                    in_cooldown = True

            if in_cooldown:
                log.info("Risk alert suppressed by 24h cooldown: user=%s type=%s sym=%s", user_id, breach_type, sym)
                continue

            alert = Alert(
                id=uuid4().hex,
                user_id=user_id,
                title=title,
                message=b["message"],
            )
            db.add(alert)
            alerts_to_send.append((b, title))

        if alerts_to_send:
            db.commit()
            for breach, title in alerts_to_send:
                dispatch_task(
                    send_to_user,
                    user_id,
                    f"Basarat risk alert: {breach['severity'].upper()}",
                    breach["message"],
                    {
                        "type": "risk_alert",
                        "risk_type": breach["type"],
                        "severity": breach["severity"],
                        "symbol": breach.get("symbol", ""),
                    },
                )
    except Exception as exc:
        db.rollback()
        log.exception("Error in _send_alerts_sync: %s", exc)
        raise
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
