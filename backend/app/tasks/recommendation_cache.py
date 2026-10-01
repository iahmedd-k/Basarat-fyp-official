"""Publish the daily KSE-100 recommendation snapshot after sentiment runs."""

import logging
from datetime import datetime, date

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

        # Persist the daily shared recommendation output; Redis remains only a
        # rebuildable read cache. Keep valid fields and skip empty results.
        from sqlalchemy import select
        from app.db.base import get_sync_session_factory
        from app.models.stock import Stock, StockDailyAnalysis
        from app.tasks.stock_data_pipeline import _clean
        session = get_sync_session_factory()()
        try:
            stocks = {
                row.symbol: row.id
                for row in session.execute(select(Stock)).scalars().all()
            }
            as_of = date.today()
            for item in recommendations:
                symbol = str(item.get("symbol", "")).upper()
                stock_id = stocks.get(symbol)
                payload = _clean(item)
                if not stock_id or not payload:
                    continue
                row = session.execute(select(StockDailyAnalysis).where(
                    StockDailyAnalysis.stock_id == stock_id,
                    StockDailyAnalysis.as_of_date == as_of,
                )).scalar_one_or_none()
                if row is None:
                    row = StockDailyAnalysis(stock_id=stock_id, as_of_date=as_of)
                    session.add(row)
                row.recommendation_json = payload
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

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
