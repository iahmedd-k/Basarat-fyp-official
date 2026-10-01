"""Single-event-loop bridge for synchronous callers (Celery tasks, sync services).

The scraper tasks previously called `asyncio.run()` / `asyncio.new_event_loop()`
directly. That fails with:

    RuntimeError: Cannot run the event loop while another loop is running

whenever a coroutine is driven from a context that already has a running loop,
and it also churned a fresh loop per call, which left SQLAlchemy and Redis async
pools bound to a loop that was then closed underneath them.

This module owns exactly one long-lived event loop per process, running on one
daemon thread. Every coroutine is submitted to it with
`run_coroutine_threadsafe`, so:

  * loops can never nest,
  * async clients stay bound to the same loop for the life of the process,
  * sync callers simply block on the future.
"""

from __future__ import annotations

import asyncio
import atexit
import logging
import threading
from typing import Any, Coroutine

log = logging.getLogger(__name__)

_lock = threading.Lock()
_loop: asyncio.AbstractEventLoop | None = None
_thread: threading.Thread | None = None
_ready = threading.Event()


def _serve(loop: asyncio.AbstractEventLoop) -> None:
    asyncio.set_event_loop(loop)
    loop.call_soon(_ready.set)
    try:
        loop.run_forever()
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception:
            log.debug("async generator shutdown failed", exc_info=True)


def get_loop() -> asyncio.AbstractEventLoop:
    """Return the process-wide bridge loop, starting it on first use."""
    global _loop, _thread
    with _lock:
        if _loop is not None and not _loop.is_closed():
            return _loop
        loop = asyncio.new_event_loop()
        thread = threading.Thread(
            target=_serve, args=(loop,), name="basarat-async-bridge", daemon=True
        )
        thread.start()
        _loop, _thread = loop, thread
    if not _ready.wait(timeout=10):
        raise RuntimeError("async bridge loop failed to start within 10s")
    return loop


def run_sync(coro: Coroutine[Any, Any, Any], timeout: float | None = None) -> Any:
    """Run `coro` on the shared bridge loop and block for its result.

    Safe to call from sync Celery tasks and from sync request handlers. It must
    not be called from inside the bridge loop's own thread.
    """
    if threading.current_thread() is _thread:
        coro.close()
        raise RuntimeError(
            "run_sync() cannot be called from the async bridge thread; "
            "await the coroutine directly instead"
        )
    loop = get_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=timeout)


def close(timeout: float = 5.0) -> None:
    """Stop the bridge loop. Safe to call more than once."""
    global _loop, _thread
    with _lock:
        loop, thread = _loop, _thread
        _loop, _thread = None, None
    if loop is None:
        return
    try:
        loop.call_soon_threadsafe(loop.stop)
        if thread is not None:
            thread.join(timeout=timeout)
    except Exception:
        log.debug("async bridge shutdown error", exc_info=True)
    finally:
        if not loop.is_closed():
            try:
                loop.close()
            except Exception:
                log.debug("async bridge close error", exc_info=True)


atexit.register(close)
