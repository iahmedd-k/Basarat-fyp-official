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

    Runs the FinBERT pipeline on news data,
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
                    text("SELECT DISTINCT symbol FROM stocks LIMIT 50")
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


@shared_task(
    name="app.tasks.sentiment_tasks.rescore_failed_sentiment",
    bind=True,
    max_retries=1,
    acks_late=True,
)
def rescore_failed_sentiment_task(self, limit: int = 50):
    """Retry scoring articles that previously failed FinBERT.

    Runs hourly. Fetches articles with sentiment_status='failed',
    retries FinBERT up to 3 times, updates on success.
    """
    from app.services.sentiment_service import score_text
    from app.models.news import NewsArticle
    from sqlalchemy import select
    from app.db.session import async_session_factory

    log.info("Rescore failed sentiment task started")

    async def _run():
        async with async_session_factory() as db:
            result = await db.execute(
                select(NewsArticle)
                .where(
                    NewsArticle.sentiment_status == "failed",
                    NewsArticle.source_type == "news",
                )
                .limit(limit)
            )
            articles = result.scalars().all()

            if not articles:
                log.info("No failed sentiment articles to rescore")
                return {"status": "completed", "retried": 0, "succeeded": 0}

            retried = 0
            succeeded = 0

            for article in articles:
                text = f"{article.title}. {article.summary or ''}"
                text = text[:1500]

                for attempt in range(3):
                    try:
                        sentiment = score_text(text)
                        if sentiment and sentiment.get("score") is not None:
                            score = sentiment["score"]
                            label = sentiment["label"]
                            min_conf = 0.6
                            if abs(score) < min_conf:
                                label = "neutral"
                                score = 0.0

                            article.sentiment_label = label
                            article.sentiment_score = round(score, 4)
                            article.sentiment_method = "finbert"
                            article.sentiment_status = "ok"
                            await db.flush()
                            succeeded += 1
                            break
                    except Exception:
                        if attempt == 2:
                            raise
                        import asyncio
                        await asyncio.sleep(2 ** attempt)

                retried += 1

            await db.commit()
            return {"status": "completed", "retried": retried, "succeeded": succeeded}

    try:
        return _run_async(_run())
    except Exception as exc:
        log.exception("Rescore failed sentiment task failed")
        raise self.retry(exc=exc, countdown=300)


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