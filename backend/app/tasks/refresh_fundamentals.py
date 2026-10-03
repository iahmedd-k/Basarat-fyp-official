"""Paced daily refresh of persisted KSE-100 fundamentals."""

from __future__ import annotations

import logging
import multiprocessing
import random
import time
from datetime import datetime, timezone
from uuid import uuid4

from app.celery_app import celery
from app.core.config import get_settings
from app.core.redis import cache_set_sync
from app.data.scraper.symbol_universe import get_active_symbols

log = logging.getLogger(__name__)

_LOCK_KEY = "jobs:fundamentals-refresh:lock"


def _acquire_lock(ttl_seconds: int = 21600):
    from app.core.redis import get_sync_redis_client

    client = get_sync_redis_client()
    if client is None:
        return None, None
    token = uuid4().hex
    if not client.set(_LOCK_KEY, token, nx=True, ex=ttl_seconds):
        return client, None
    return client, token


def _release_lock(client, token):
    if client is None or token is None:
        return
    try:
        client.eval(
            "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end",
            1,
            _LOCK_KEY,
            token,
        )
    except Exception:
        log.warning("Could not release fundamentals refresh lock", exc_info=True)


def _persist_snapshot(session, symbol: str, payload: dict, run_id: str, now: datetime) -> None:
    from sqlalchemy import select

    from app.models.fundamentals import StockFundamentals
    from app.models.stock import Stock

    row = session.execute(
        select(StockFundamentals).where(StockFundamentals.symbol == symbol)
    ).scalar_one_or_none()
    stock = session.execute(select(Stock).where(Stock.symbol == symbol)).scalar_one_or_none()
    if row is None:
        row = StockFundamentals(symbol=symbol)
        session.add(row)
    row.stock_id = stock.id if stock else None
    row.payload = payload
    row.data_status = payload.get("data_status", "partial")
    source_as_of_date = payload.get("source_as_of_date")
    row.source_as_of_date = str(source_as_of_date or now.date().isoformat())
    row.fetched_at = now
    row.last_successful_at = now
    row.refresh_run_id = run_id
    row.payload_version = 1
    row.last_error = None
    session.flush()


def _fetch_symbol_worker(symbol: str, result_queue) -> None:
    try:
        from app.services.stock_service import StockService

        payload = StockService()._fetch_fundamentals_upstream(
            symbol,
            allow_synthetic=False,
            force_refresh=True,
        )
        result_queue.put(("success", payload))
    except Exception as exc:
        result_queue.put(("error", f"{type(exc).__name__}: {exc}"))


def _fetch_symbol_with_timeout(symbol: str, timeout_seconds: float) -> dict:
    """Run an upstream fetch in a killable process with a hard deadline."""
    context = multiprocessing.get_context("spawn")
    result_queue = context.Queue()
    process = context.Process(
        target=_fetch_symbol_worker,
        args=(symbol, result_queue),
        name=f"fundamentals-fetch-{symbol}",
    )
    process.start()
    try:
        process.join(timeout=max(0.1, timeout_seconds))
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
            raise TimeoutError(
                f"Fundamentals source timed out for {symbol} after {timeout_seconds:.1f}s"
            )
        if result_queue.empty():
            raise RuntimeError(
                f"Fundamentals source exited without a result for {symbol} "
                f"(exit_code={process.exitcode})"
            )
        status, value = result_queue.get()
        if status == "error":
            raise RuntimeError(value)
        if not isinstance(value, dict):
            raise RuntimeError(f"Fundamentals source returned invalid data for {symbol}")
        return value
    finally:
        if process.is_alive():
            process.terminate()
        process.join(timeout=5)
        result_queue.cancel_join_thread()
        result_queue.close()


@celery.task(
    name="app.tasks.refresh_fundamentals.refresh_fundamentals",
    bind=True,
    max_retries=0,
    acks_late=True,
    soft_time_limit=21600,
    time_limit=22200,
)
def refresh_fundamentals(self, symbols: list[str] | None = None):
    """Refresh KSE-100 fundamentals one symbol at a time.

    The deliberately long inter-symbol pause protects the shared/cloud IP.
    A source failure never replaces the previous valid database snapshot.
    """
    settings = get_settings()
    if not settings.FUNDAMENTALS_REFRESH_ENABLED:
        return {"status": "skipped", "reason": "disabled"}

    lock_client, lock_token = _acquire_lock()
    if lock_client is None:
        log.error("Redis is unavailable; refusing to run uncoordinated fundamentals refresh")
        return {"status": "blocked", "reason": "redis_unavailable"}
    if lock_client is not None and lock_token is None:
        return {"status": "skipped", "reason": "already_running"}

    from app.db.base import get_sync_session_factory
    from app.models.fundamentals import FundamentalsRefreshRun

    configured = symbols or [item["symbol"] for item in get_active_symbols()]
    configured = sorted({str(symbol).strip().upper() for symbol in configured if symbol})
    run_id = uuid4().hex
    started = datetime.now(timezone.utc)
    session_factory = get_sync_session_factory()
    session = session_factory()
    run = FundamentalsRefreshRun(
        id=run_id,
        started_at=started,
        expected_count=len(configured),
        status="running",
    )
    session.add(run)
    session.commit()

    result = {
        "status": "completed",
        "run_id": run_id,
        "expected": len(configured),
        "success": 0,
        "failed": 0,
        "timed_out": 0,
        "rate_limited": False,
    }
    try:
        for index, symbol in enumerate(configured):
            if index:
                delay = max(0.0, float(settings.FUNDAMENTALS_REQUEST_DELAY_SECONDS))
                jitter = random.uniform(0.0, max(0.0, float(settings.FUNDAMENTALS_REQUEST_JITTER_SECONDS)))
                log.info("Waiting %.1fs before fundamentals symbol %s", delay + jitter, symbol)
                time.sleep(delay + jitter)
            try:
                started_symbol = time.monotonic()
                payload = _fetch_symbol_with_timeout(
                    symbol,
                    float(settings.FUNDAMENTALS_SYMBOL_TIMEOUT_SECONDS),
                )
                if not isinstance(payload, dict) or payload.get("data_status") == "unavailable":
                    raise RuntimeError("No valid fundamentals payload returned")
                now = datetime.now(timezone.utc)
                _persist_snapshot(session, symbol, payload, run_id, now)
                session.commit()
                cache_set_sync(
                    f"fund:v21:{symbol}",
                    payload,
                    int(settings.FUNDAMENTALS_REDIS_TTL_SECONDS),
                )
                result["success"] += 1
                log.info(
                    "Fundamentals refreshed for %s in %.1fs",
                    symbol,
                    time.monotonic() - started_symbol,
                )
            except Exception as exc:
                session.rollback()
                result["failed"] += 1
                log.warning("Fundamentals refresh failed for %s: %s", symbol, exc)
                if isinstance(exc, TimeoutError):
                    result["timed_out"] += 1
                    log.error("Skipping timed-out symbol and continuing refresh")
                if "403" in str(exc) or "429" in str(exc):
                    result["rate_limited"] = True
                    log.error("Stopping fundamentals refresh after source rate limit")
                    break

        run.status = "completed" if result["failed"] == 0 else "partial"
        run.success_count = result["success"]
        run.failed_count = result["failed"]
        run.finished_at = datetime.now(timezone.utc)
        session.commit()
        result["status"] = run.status
        return result
    except Exception as exc:
        session.rollback()
        run.status = "failed"
        run.error = str(exc)[:2000]
        run.finished_at = datetime.now(timezone.utc)
        session.commit()
        raise
    finally:
        session.close()
        _release_lock(lock_client, lock_token)
