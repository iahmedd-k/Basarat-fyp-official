"""Central, scheduled refresh of shared PSX market snapshots.

API handlers stay read-only. Celery owns upstream scrapes:
  - refresh_market_session: every ~60s during PSX open hours → Redis + live bus
  - refresh_market_cache: close/startup/weekly reference refresh
"""

from __future__ import annotations

import asyncio
import logging
import random
from uuid import uuid4

from app.celery_app import celery
from app.core.async_bridge import run_sync
from app.core.config import get_settings

log = logging.getLogger(__name__)

LOCK_KEY = "jobs:market-cache:lock"
CIRCUIT_KEY = "jobs:market-cache:circuit_open"
FAILURE_KEY = "jobs:market-cache:consecutive_failures"
USER_AGENT = "Mozilla/5.0 (compatible; BasaratMarketData/1.0; +market-data)"
ACCESS_DENIED_MARKERS = (
    "403",
    "429",
    "access denied",
    "too many requests",
    "rate limit",
    "blocked",
    "captcha",
    "cloudflare",
)


def _run_async(coro):
    """Drive a coroutine from this sync task via the shared process loop.

    Uses the single-loop bridge instead of `asyncio.run()` / `new_event_loop()`,
    which raised "Cannot run the event loop while another loop is running" and
    left async DB/Redis pools bound to a loop that was closed underneath them.
    """
    return run_sync(coro)


def _acquire_lock(ttl_seconds: int) -> tuple[str, object | None, str | None]:
    """Returns (status, client, token) where status is acquired|held|no_redis."""
    lock_token = uuid4().hex
    try:
        from app.core.redis import get_sync_redis_client

        client = get_sync_redis_client()
        if not client:
            return "no_redis", None, None
        if not client.set(LOCK_KEY, lock_token, nx=True, ex=ttl_seconds):
            return "held", client, None
        return "acquired", client, lock_token
    except Exception as exc:
        log.warning("Redis market refresh lock unavailable; continuing without lock: %s", exc)
        return "no_redis", None, None


def _release_lock(lock_client, lock_token: str | None) -> None:
    if not lock_client or not lock_token:
        return
    try:
        lock_client.eval(
            "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end",
            1,
            LOCK_KEY,
            lock_token,
        )
    except Exception:
        log.warning("Could not release market refresh lock", exc_info=True)


def _circuit_is_open(lock_client) -> bool:
    if not lock_client:
        try:
            from app.core.redis import get_sync_redis_client

            lock_client = get_sync_redis_client()
        except Exception:
            return False
    if not lock_client:
        return False
    try:
        return bool(lock_client.get(CIRCUIT_KEY))
    except Exception:
        return False


def _open_circuit(lock_client, reason: str) -> None:
    settings = get_settings()
    ttl = max(60, int(settings.MARKET_CIRCUIT_BREAKER_SECONDS))
    client = lock_client
    if not client:
        try:
            from app.core.redis import get_sync_redis_client

            client = get_sync_redis_client()
        except Exception:
            client = None
    if not client:
        log.warning("Circuit open requested (%s) but Redis unavailable", reason)
        return
    try:
        client.setex(CIRCUIT_KEY, ttl, reason[:200])
        log.warning("Opened market scrape circuit for %ss: %s", ttl, reason)
    except Exception as exc:
        log.warning("Failed to open market circuit: %s", exc)


def _looks_like_access_denied(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(marker in text for marker in ACCESS_DENIED_MARKERS)


def _failure_count() -> int:
    """Consecutive failed session refreshes recorded in Redis."""
    try:
        from app.core.redis import get_sync_redis_client

        client = get_sync_redis_client()
        if not client:
            return 0
        return int(client.get(FAILURE_KEY) or 0)
    except Exception:
        return 0


def _record_failure() -> None:
    try:
        from app.core.redis import get_sync_redis_client

        client = get_sync_redis_client()
        if not client:
            return
        count = int(client.incr(FAILURE_KEY) or 1)
        # Expire on its own so a clean session eventually clears the counter.
        client.expire(FAILURE_KEY, 86400)
        log.warning("Recorded market scrape failure #%d", count)
    except Exception as exc:
        log.debug("Could not record scrape failure: %s", exc)


def _clear_failures() -> None:
    try:
        from app.core.redis import get_sync_redis_client

        client = get_sync_redis_client()
        if client:
            client.delete(FAILURE_KEY)
    except Exception as exc:
        log.debug("Could not clear scrape failure counter: %s", exc)


async def _refresh_quotes_and_optional_reference(
    *,
    refresh_reference: bool,
    refresh_constituents: bool,
    publish_live: bool,
    source: str,
) -> dict:
    from app.services.market_service import MarketService

    service = MarketService()
    results: dict = {"quotes": 0, "indices": 0, "constituents": {}, "published": False}
    quotes = await service.get_market_data(force_refresh=True, read_only=False)
    results["quotes"] = len(quotes)

    if refresh_reference:
        indices = await service.get_indices(force_refresh=True, read_only=False)
        results["indices"] = len(indices)

    if refresh_constituents:
        for code in ("KSE100", "KSE30", "KMI30"):
            values = await service.get_index_constituents(
                code, force_refresh=True, read_only=False
            )
            results["constituents"][code] = len(values)
        # Persist the membership we just scraped so the on-disk symbol universe
        # tracks the live index instead of freezing at image build time.
        try:
            results["universe_symbols"] = await asyncio.to_thread(
                MarketService.persist_symbol_universe
            )
        except Exception as exc:
            log.warning("Could not persist symbol universe: %s", exc)
            results["universe_symbols"] = 0
        try:
            from app.services.assistant_context_cache import warm_assistant_universe

            universe = await warm_assistant_universe(force_refresh_constituents=False)
            results["assistant_universe"] = universe.get("symbol_count", 0)
        except Exception as exc:
            log.warning("Assistant universe warm failed: %s", exc)
            results["assistant_universe"] = 0

    if publish_live and quotes:
        freshness = await asyncio.to_thread(service.quote_freshness)
        from app.services.market_live_bus import publish_board_update_sync

        results["published"] = publish_board_update_sync(
            quotes,
            as_of=freshness.get("as_of"),
            is_stale=bool(freshness.get("is_stale", False)),
            source=source,
        )
    return results


@celery.task(
    name="app.tasks.refresh_market_cache.refresh_market_cache",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    acks_late=True,
)
def refresh_market_cache(self, refresh_reference: bool = False, refresh_constituents: bool = False):
    """Full/reference refresh (startup, close snapshot, weekly constituents)."""
    status, lock_client, lock_token = _acquire_lock(ttl_seconds=900)
    if status == "held":
        log.info("Skipping market refresh; another worker holds the refresh lock")
        return {"status": "skipped", "reason": "already_running"}

    if _circuit_is_open(lock_client):
        _release_lock(lock_client, lock_token)
        return {"status": "skipped", "reason": "circuit_open"}

    try:
        result = _run_async(
            _refresh_quotes_and_optional_reference(
                refresh_reference=refresh_reference,
                refresh_constituents=refresh_constituents,
                publish_live=True,
                source="market_cache_refresh",
            )
        )
        log.info("PSX market cache refresh completed: %s", result)
        if result.get("quotes", 0) > 0:
            _clear_failures()
        return {"status": "completed", **result}
    except Exception as exc:
        if _looks_like_access_denied(exc):
            _open_circuit(lock_client, str(exc))
            return {"status": "circuit_open", "error": str(exc)}
        log.exception("PSX market cache refresh failed")
        raise self.retry(exc=exc)
    finally:
        _release_lock(lock_client, lock_token)


@celery.task(
    name="app.tasks.refresh_market_cache.refresh_market_session",
    bind=True,
    max_retries=1,
    default_retry_delay=30,
    acks_late=True,
    soft_time_limit=180,
    time_limit=240,
)
def refresh_market_session(self):
    """Intraday shared snapshot: scrape once, cache, publish to all WS clients via Redis bus."""
    settings = get_settings()
    if not settings.MARKET_SESSION_REFRESH_ENABLED:
        return {"status": "skipped", "reason": "disabled"}

    # Randomised jitter, applied BEFORE the lock is taken. Sleeping while holding
    # the refresh lock would idle the single worker and stall every other task.
    # A wide jitter also breaks the fixed-interval request fingerprint that PSX
    # uses to detect and block scrapers.
    jitter_span = max(0.0, float(getattr(settings, "MARKET_SESSION_REFRESH_JITTER_SECONDS", 0) or 0))
    if jitter_span:
        import time as _time

        delay = random.uniform(0.0, jitter_span)
        log.debug("Session refresh jitter delay %.1fs", delay)
        _time.sleep(delay)

    from app.services.news_pipeline.market_schedule import is_market_hours, market_status

    status_info = _run_async(market_status())
    if not _run_async(is_market_hours()):
        return {
            "status": "skipped",
            "reason": "market_closed",
            "market_status": status_info.get("status"),
        }

    if _circuit_is_open(None):
        return {"status": "skipped", "reason": "circuit_open"}

    # Back off entirely once the scraper has failed repeatedly. Continuing to
    # hammer PSX while blocked only extends the block.
    failures = _failure_count()
    threshold = max(1, int(getattr(settings, "MARKET_SCRAPE_FAILURE_THRESHOLD", 3) or 3))
    if failures >= threshold:
        log.error(
            "Skipping session refresh: %d consecutive failures (threshold %d); scraper is backed off",
            failures, threshold,
        )
        return {"status": "skipped", "reason": "failure_backoff", "consecutive_failures": failures}

    lock_ttl = max(45, int(settings.MARKET_SESSION_REFRESH_SECONDS) + 15)
    lock_status, lock_client, lock_token = _acquire_lock(ttl_seconds=lock_ttl)
    if lock_status == "held":
        return {"status": "skipped", "reason": "already_running"}

    try:
        result = _run_async(
            _refresh_quotes_and_optional_reference(
                refresh_reference=False,
                refresh_constituents=False,
                publish_live=True,
                source="session_refresh",
            )
        )
        if result.get("quotes", 0) == 0:
            _record_failure()
            log.warning("Session refresh returned 0 quotes; keeping last_known cache")
            return {"status": "empty", **result, "market_status": status_info.get("status")}
        _clear_failures()
        log.info("PSX session market refresh completed: %s", result)
        return {"status": "completed", **result, "market_status": status_info.get("status")}
    except Exception as exc:
        _record_failure()
        if _looks_like_access_denied(exc):
            _open_circuit(lock_client, str(exc))
            return {"status": "circuit_open", "error": str(exc)}
        log.exception("PSX session market refresh failed")
        raise self.retry(exc=exc)
    finally:
        _release_lock(lock_client, lock_token)
