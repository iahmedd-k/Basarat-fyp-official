"""Publish the daily KSE-100 recommendation snapshot after sentiment runs."""

import logging
from datetime import datetime

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
        from app.services.recommendation_service import (
            RecommendationEngine,
            save_recommendations_cache,
        )

        engine = RecommendationEngine()
        recommendations = engine.get_all_recommendations(
            risk_tolerance="moderate",
            weights=None,  # use defaults
        )

        save_recommendations_cache(recommendations)

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
