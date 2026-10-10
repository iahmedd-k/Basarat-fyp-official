"""Publish the daily KSE-100 recommendation snapshot after sentiment runs."""

import json
import logging
from datetime import date, datetime

from celery.exceptions import SoftTimeLimitExceeded

from app.celery_app import celery

log = logging.getLogger(__name__)


@celery.task(
    name="app.tasks.recommendation_cache.refresh_recommendations",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def refresh_recommendations_task(self):
    """Recompute recommendations for all active symbols and cache to Redis.

    Celery Beat runs this once after the daily OHLCV, feature, forecast and
    sentiment jobs. API list routes read this shared cache and only reweight
    its stored source scores per user.
    """
    log.info("[RECOMMEND] Refreshing recommendation cache")

    try:
        from app.core.redis import set_dataset_status_sync

        set_dataset_status_sync("recommendations", "pending")
        from app.services.recommendation_service import (
            RecommendationEngine,
            save_recommendations_cache,
        )
        from app.data.scraper.symbol_universe import get_active_symbols
        from app.core.redis import get_sync_redis_client

        engine = RecommendationEngine()
        recommendations = engine.get_all_recommendations(
            risk_tolerance="moderate",
            weights=None,  # use defaults
        )

        expected_symbols = {
            str(entry["symbol"]).strip().upper()
            for entry in get_active_symbols()
            if entry.get("symbol")
        }
        actual_symbols = [
            str(item.get("symbol") or "").strip().upper()
            for item in recommendations
        ]
        if (
            not expected_symbols
            or len(actual_symbols) != len(set(actual_symbols))
            or set(actual_symbols) != expected_symbols
        ):
            missing = sorted(expected_symbols - set(actual_symbols))
            unexpected = sorted(set(actual_symbols) - expected_symbols)
            raise RuntimeError(
                "Recommendation snapshot is incomplete or has duplicate symbols "
                f"(expected={len(expected_symbols)}, actual={len(actual_symbols)}, "
                f"missing={missing[:10]}, unexpected={unexpected[:10]})"
            )
        for item in recommendations:
            data_as_of = item.get("data_as_of")
            if not data_as_of:
                raise RuntimeError(
                    f"Recommendation for {item['symbol']} has no source data date"
                )
            date.fromisoformat(str(data_as_of)[:10])

        started_at = datetime.utcnow()
        save_recommendations_cache(recommendations)

        redis = get_sync_redis_client()
        if redis is None:
            raise RuntimeError("Redis is unavailable; recommendation snapshot was not warmed")
        redis.ping()
        raw_snapshot = redis.get("recommendations:default:v5")
        if raw_snapshot is None:
            raise RuntimeError("Recommendation snapshot was not written to Redis")
        published = json.loads(raw_snapshot)
        published_at = datetime.fromisoformat(published["timestamp"])
        published_symbols = {
            str(item.get("symbol") or "").strip().upper()
            for item in published.get("recommendations", [])
            if isinstance(item, dict)
        }
        if (
            published_at < started_at
            or published.get("cache_version") != 5
            or published.get("count") != len(expected_symbols)
            or published_symbols != expected_symbols
        ):
            raise RuntimeError("Redis still contains an older or incomplete recommendation snapshot")

        set_dataset_status_sync("recommendations", "success")

        for pattern in (
            "rec:list:v3:*",
            "rec:detail:v3:*",
            "rec:targetstop:v3:*",
        ):
            cursor = 0
            while True:
                cursor, keys = redis.scan(cursor, match=pattern, count=500)
                if keys:
                    redis.delete(*keys)
                if cursor == 0:
                    break

        # Summary stats
        buy_count = sum(1 for r in recommendations if r.get("signal") == "buy")
        sell_count = sum(1 for r in recommendations if r.get("signal") == "sell")
        hold_count = sum(1 for r in recommendations if r.get("signal") == "hold")

        log.info("[RECOMMEND] Cache refreshed: %d symbols (BUY=%d, SELL=%d, HOLD=%d)",
                 len(recommendations), buy_count, sell_count, hold_count)

        return {
            "status": "success",
            "count": len(recommendations),
            "buy": buy_count,
            "sell": sell_count,
            "hold": hold_count,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except SoftTimeLimitExceeded:
        log.error("[RECOMMEND] Task timed out")
        raise self.retry(countdown=600)
    except Exception as exc:
        log.exception("[RECOMMEND] Failed to refresh recommendations")
        raise self.retry(exc=exc)
