"""Celery task: market-aware news ingestion.

Runs every 30 minutes via celery beat, but only actually scrapes
when within PSX market hours or the post-market window.

During market hours (09:30-15:30 PKT):  every 30 min
Post-market (15:30-17:00 PKT):          every 60 min
After 17:00 PKT / weekends:             no ingestion

Manual trigger via POST /news/refresh uses the SAME pipeline.
"""

import asyncio
import logging
from datetime import datetime, timezone

from celery import shared_task

log = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        # Async connections cannot safely be reused by the next Celery task's
        # fresh event loop. Dispose the worker-local pool before closing this loop.
        from app.db.base import engine
        try:
            loop.run_until_complete(engine.dispose())
        except Exception:
            log.exception("Failed to dispose async database connections")
        finally:
            loop.close()


@shared_task(
    name="app.tasks.scrape_news.run",
    bind=True,
    max_retries=1,
    acks_late=True,
)
def run(self, force: bool = False, limit_per_source: int = 50):
    """Run the news ingestion pipeline if market schedule allows it.

    Args:
        force: If True, bypass market-hours check (used by POST /news/refresh).
        limit_per_source: Max articles to fetch per source adapter.
    """
    from app.services.news_pipeline.market_schedule import is_ingestion_allowed, market_status
    from app.services.news_pipeline.ingestion_state import get_last_ingestion_time
    from app.core.config import get_settings

    status = _run_async(market_status())
    log.info("News ingestion task triggered: force=%s, market_status=%s", force, status["status"])

    # ── Check 1: Market schedule gate ────────────────────────────────────
    if not force and not _run_async(is_ingestion_allowed()):
        log.info("Outside market hours and post-market window — skipping ingestion")
        return {
            "status": "skipped",
            "reason": "outside_market_hours",
            "market_status": status,
        }

    # ── Check 2: Cooldown — avoid overlapping runs ───────────────────────
    from app.services.news_pipeline.ingestion_state import set_last_ingestion_time
    last_run = get_last_ingestion_time()
    cooldown = get_settings().NEWS_REFRESH_COOLDOWN
    now = datetime.now(timezone.utc)

    if last_run and not force:
        elapsed = (now - last_run).total_seconds()
        if elapsed < cooldown:
            remaining = int(cooldown - elapsed)
            log.info("Cooldown active — %ds remaining, skipping", remaining)
            return {
                "status": "skipped",
                "reason": "cooldown_active",
                "seconds_remaining": remaining,
                "market_status": status,
            }

    # ── Run the pipeline ─────────────────────────────────────────────────
    from app.services.news_pipeline.pipeline import run_pipeline
    from app.db.session import async_session_factory

    async def _execute():
        async with async_session_factory() as db:
            result = await run_pipeline(db, limit_per_source=limit_per_source)
            return result

    try:
        pipeline_result = _run_async(_execute())

        log.info(
            "News ingestion complete: fetched=%d, inserted=%d, dedup_skipped=%d, errors=%d",
            pipeline_result.total_fetched,
            pipeline_result.total_inserted,
            pipeline_result.total_skipped_duplicate,
            pipeline_result.errors,
        )

        # Extract events from newly ingested news
        if pipeline_result.total_inserted > 0:
            async def _extract_events():
                from app.services.event_service import extract_events_from_news
                async with async_session_factory() as db:
                    return await extract_events_from_news(db)

            events_created = _run_async(_extract_events())
            pipeline_result.events_created = events_created
            log.info("Events extracted from news: %d", events_created)

        return {
            "status": "completed",
            "total_fetched": pipeline_result.total_fetched,
            "total_inserted": pipeline_result.total_inserted,
            "total_dedup_skipped": pipeline_result.total_skipped_duplicate,
            "events_created": pipeline_result.events_created,
            "errors": pipeline_result.errors,
            "completed_at": pipeline_result.completed_at,
            "market_status": status,
        }

    except Exception as exc:
        log.exception("News ingestion task failed")
        raise self.retry(exc=exc, countdown=120)
