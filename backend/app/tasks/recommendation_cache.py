"""Recommendation Cache — Celery task to precompute recommendations on schedule.

Runs periodically (every 4 hours) to precompute recommendations for all
active symbols. The API reads from the cache instead of computing on every
request, since the underlying data (features, live market data) is expensive.
"""

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
    """Recompute recommendations for all active symbols and cache to disk.

    This task runs every 4 hours via Celery Beat. The API endpoints
    read from the cache, not from live computation.
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
