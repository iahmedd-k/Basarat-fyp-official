"""Celery tasks for sentiment aggregation.

Scheduled job: runs daily to refresh per-stock and market sentiment.
Uses 7-day rolling window with decay-weighted averaging.
"""

import asyncio
import logging
from datetime import datetime

from celery import shared_task

log = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine from sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@shared_task(
    name="app.tasks.sentiment_tasks.aggregate_sentiment",
    bind=True,
    max_retries=2,
    acks_late=True,
)
def aggregate_sentiment_task(self, symbols: list[str] | None = None):
    """Aggregate sentiment for all (or specified) symbols.

    Runs the FinBERT pipeline on news + community data,
    computes 7-day decay-weighted scores, and caches to disk.
    """
    from app.services.sentiment_service import (
        compute_stock_sentiment,
        compute_market_sentiment,
    )
    from app.db.session import async_session_factory

    log.info("Sentiment aggregation started: symbols=%s", symbols or "all")

    async def _run():
        async with async_session_factory() as db:
            if not symbols:
                from sqlalchemy import text
                result = await db.execute(
                    text("SELECT DISTINCT symbol FROM post_stock_tags LIMIT 50")
                )
                symbols_to_process = [row[0] for row in result.fetchall()]
            else:
                symbols_to_process = [s.upper() for s in symbols]

            processed = 0
            errors = []

            for sym in symbols_to_process:
                try:
                    await compute_stock_sentiment(db, sym, days=7)
                    processed += 1
                except Exception as exc:
                    errors.append({"symbol": sym, "error": str(exc)})
                    log.warning("Sentiment failed for %s: %s", sym, exc)

            try:
                await compute_market_sentiment(db)
            except Exception as exc:
                errors.append({"symbol": "MARKET", "error": str(exc)})
                log.warning("Market sentiment failed: %s", exc)

            return {
                "status": "completed",
                "processed": processed,
                "errors": errors,
                "completed_at": datetime.utcnow().isoformat(),
            }

    try:
        result = _run_async(_run())
        log.info("Sentiment aggregation completed: processed=%d", result["processed"])
        return result
    except Exception as exc:
        log.exception("Sentiment aggregation task failed")
        raise self.retry(exc=exc, countdown=120)


@shared_task(
    name="app.tasks.sentiment_tasks.refresh_single_stock",
    bind=True,
    max_retries=1,
)
def refresh_stock_sentiment_task(self, symbol: str):
    """Refresh sentiment for a single stock (on-demand)."""
    from app.services.sentiment_service import compute_stock_sentiment
    from app.db.session import async_session_factory

    async def _run():
        async with async_session_factory() as db:
            return await compute_stock_sentiment(db, symbol, days=7)

    try:
        return _run_async(_run())
    except Exception as exc:
        log.exception("Sentiment refresh failed for %s", symbol)
        raise self.retry(exc=exc, countdown=60)
