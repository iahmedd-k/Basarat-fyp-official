"""Celery tasks for evaluating alert rules and watchlist target prices."""

import logging
from datetime import datetime, timedelta
from uuid import uuid4

from app.celery_app import celery
from app.core.config import get_settings

log = logging.getLogger(__name__)


def _get_sync_session():
    from app.db.base import get_sync_session_factory
    return get_sync_session_factory()()


def _is_in_cooldown(
    session,
    redis_client,
    cooldown_key: str,
    rule_id: str | None = None,
    user_id: str | None = None,
    title_pattern: str | None = None,
    ttl_seconds: int = 1800,
) -> bool:
    """Check if an alert is on cooldown via Redis with DB fallback to prevent duplicate spam."""
    if redis_client:
        try:
            # set(key, "1", nx=True, ex=ttl_seconds) returns True if newly set, False/None if already exists
            is_new = redis_client.set(cooldown_key, "1", nx=True, ex=ttl_seconds)
            if not is_new:
                return True
            return False
        except Exception as exc:
            log.warning("Redis cooldown check failed for %s: %s", cooldown_key, exc)

    # Fallback to DB check: ensure no alert was created for this rule/target within cooldown window
    if session:
        try:
            from app.models.alert import Alert
            from sqlalchemy import select
            cutoff = datetime.utcnow() - timedelta(seconds=ttl_seconds)
            if rule_id:
                existing = session.execute(
                    select(Alert.id).where(Alert.rule_id == rule_id, Alert.created_at >= cutoff).limit(1)
                ).scalar()
                if existing:
                    return True
            elif user_id and title_pattern:
                existing = session.execute(
                    select(Alert.id).where(
                        Alert.user_id == user_id,
                        Alert.title.like(f"%{title_pattern}%"),
                        Alert.created_at >= cutoff,
                    ).limit(1)
                ).scalar()
                if existing:
                    return True
        except Exception as exc:
            log.warning("DB fallback cooldown check failed: %s", exc)

    return False


@celery.task(
    name="app.tasks.alert_tasks.evaluate_alert_rules",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    acks_late=True,
)
def evaluate_alert_rules_task(self):
    """Evaluate active alert rules and watchlist target prices against current market quotes."""
    log.info("Starting alert rules and watchlist target price evaluation")

    # Only evaluate during PSX session — quotes are refreshed then; off-hours would re-fire on stale LTPs.
    try:
        import asyncio
        from app.services.news_pipeline.market_schedule import is_market_hours

        loop = asyncio.new_event_loop()
        try:
            open_now = loop.run_until_complete(is_market_hours())
        finally:
            loop.close()
        if not open_now:
            log.info("Skipping alert evaluation; market is closed")
            return {"status": "skipped", "reason": "market_closed", "triggered": 0}
    except Exception as exc:
        log.warning("Market-hours gate failed for alerts; continuing: %s", exc)

    from sqlalchemy import select
    from app.core.redis import get_sync_redis_client
    from app.core.task_runner import dispatch_task
    from app.models.alert import Alert, AlertRule
    from app.models.stock import Stock
    from app.models.watchlist import Watchlist, WatchlistItem
    from app.services.stock_service import StockService
    from app.tasks.push_notifications import send_to_user

    redis_client = None
    try:
        redis_client = get_sync_redis_client()
    except Exception as exc:
        log.warning("Sync Redis client unavailable for alert evaluation: %s", exc)

    session = _get_sync_session()
    stock_service = StockService()
    triggered_count = 0

    try:
        # 1. Fetch active AlertRules
        rules_stmt = (
            select(AlertRule, Stock)
            .outerjoin(Stock, AlertRule.stock_id == Stock.id)
            .where(AlertRule.is_active.is_(True))
        )
        rules_rows = session.execute(rules_stmt).all()

        # 2. Fetch Watchlist items with target_price
        watchlist_stmt = (
            select(WatchlistItem, Watchlist)
            .join(Watchlist, WatchlistItem.watchlist_id == Watchlist.id)
            .where(WatchlistItem.target_price.is_not(None))
        )
        watchlist_rows = session.execute(watchlist_stmt).all()

        # 3. Collect unique symbols to quote
        symbols_set = set()
        for rule, stock in rules_rows:
            if stock and stock.symbol:
                symbols_set.add(stock.symbol.upper())

        for item, _ in watchlist_rows:
            if item.symbol:
                symbols_set.add(item.symbol.upper())

        symbols_list = list(symbols_set)
        quotes_map = {}
        if symbols_list:
            raw_quotes = stock_service.get_quote_batch(symbols_list)
            for q in raw_quotes:
                if isinstance(q, dict) and q.get("symbol"):
                    quotes_map[q["symbol"].upper()] = q

        # 4. Evaluate AlertRules
        for rule, stock in rules_rows:
            if not stock or not stock.symbol:
                continue

            sym = stock.symbol.upper()
            quote = quotes_map.get(sym)
            if not quote or quote.get("current") is None:
                continue

            current_price = float(quote.get("current") or 0.0)
            change_pct = float(quote.get("change_pct") or 0.0)
            threshold = float(rule.threshold or 0.0)
            cond = str(rule.condition).lower().strip()

            matched = False
            trigger_reason = ""

            if cond in ("price_above", "above", "target_price_above", "gte"):
                if current_price >= threshold and threshold > 0:
                    matched = True
                    trigger_reason = f"{sym} reached PKR {current_price:.2f} (above target {threshold:.2f})"
            elif cond in ("price_below", "below", "target_price_below", "lte"):
                if current_price <= threshold and threshold > 0:
                    matched = True
                    trigger_reason = f"{sym} dropped to PKR {current_price:.2f} (below limit {threshold:.2f})"
            elif cond in ("pct_change_up", "change_pct_above", "gain_above"):
                target_gain = abs(threshold)
                if change_pct >= target_gain:
                    matched = True
                    trigger_reason = f"{sym} is up {change_pct:+.2f}% (exceeding +{target_gain:.2f}%)"
            elif cond in ("pct_change_down", "change_pct_below", "loss_below"):
                target_loss = -abs(threshold)
                if change_pct <= target_loss:
                    matched = True
                    trigger_reason = f"{sym} is down {change_pct:+.2f}% (exceeding {target_loss:.2f}%)"

            if matched:
                cooldown_key = f"alert:cooldown:rule:{rule.id}"
                if not _is_in_cooldown(session, redis_client, cooldown_key, rule_id=rule.id, ttl_seconds=1800):
                    alert = Alert(
                        id=uuid4().hex,
                        user_id=rule.user_id,
                        rule_id=rule.id,
                        title=f"Price Alert: {sym}",
                        message=trigger_reason,
                    )
                    session.add(alert)
                    session.flush()

                    dispatch_task(
                        send_to_user,
                        rule.user_id,
                        f"Price Alert: {sym}",
                        trigger_reason,
                        {
                            "type": "price_alert",
                            "symbol": sym,
                            "rule_id": rule.id,
                            "price": str(current_price),
                        },
                    )
                    triggered_count += 1
                    log.info("AlertRule triggered: rule_id=%s user_id=%s symbol=%s", rule.id, rule.user_id, sym)

        # 5. Evaluate Watchlist Target Prices
        for item, watchlist in watchlist_rows:
            sym = item.symbol.upper()
            quote = quotes_map.get(sym)
            if not quote or quote.get("current") is None:
                continue

            current_price = float(quote.get("current") or 0.0)
            target_price = float(item.target_price or 0.0)

            if target_price > 0 and current_price >= target_price:
                cooldown_key = f"alert:cooldown:watchlist:{item.id}"
                if not _is_in_cooldown(
                    session,
                    redis_client,
                    cooldown_key,
                    user_id=watchlist.user_id,
                    title_pattern=f"Watchlist Target: {sym}",
                    ttl_seconds=3600,
                ):
                    message = f"{sym} reached your target price of PKR {target_price:.2f} (Current: PKR {current_price:.2f})"
                    alert = Alert(
                        id=uuid4().hex,
                        user_id=watchlist.user_id,
                        rule_id=None,
                        title=f"Watchlist Target: {sym}",
                        message=message,
                    )
                    session.add(alert)
                    session.flush()

                    dispatch_task(
                        send_to_user,
                        watchlist.user_id,
                        f"Watchlist Target: {sym}",
                        message,
                        {
                            "type": "watchlist_target",
                            "symbol": sym,
                            "item_id": item.id,
                            "price": str(current_price),
                        },
                    )
                    triggered_count += 1
                    log.info("Watchlist target reached: item_id=%s user_id=%s symbol=%s", item.id, watchlist.user_id, sym)

        session.commit()
        return {
            "status": "success",
            "evaluated_rules": len(rules_rows),
            "evaluated_watchlist_items": len(watchlist_rows),
            "triggered_alerts": triggered_count,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as exc:
        session.rollback()
        log.exception("Alert evaluation task failed")
        raise self.retry(exc=exc)
    finally:
        session.close()
