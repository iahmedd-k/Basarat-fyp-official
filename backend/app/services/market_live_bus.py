"""Redis pub/sub bridge: Celery workers publish; API processes fan-out to WebSockets.

WebSocket connections live in uvicorn processes. Celery cannot touch them directly.
This bus is the scalable cross-process transport for live board updates.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional

from app.core.config import get_settings

log = logging.getLogger(__name__)

_listener_task: Optional[asyncio.Task] = None
_listener_stop: Optional[asyncio.Event] = None


def live_channel() -> str:
    return get_settings().MARKET_LIVE_PUBSUB_CHANNEL


def publish_board_update_sync(
    quotes: list[dict],
    *,
    as_of: str | None = None,
    is_stale: bool = False,
    source: str = "session_refresh",
) -> bool:
    """Publish a board snapshot from a Celery worker (sync Redis)."""
    if not quotes:
        return False
    client = None
    try:
        from app.core.redis import get_sync_redis_client

        client = get_sync_redis_client()
        if not client:
            log.warning("Live bus publish skipped: Redis unavailable")
            return False
        payload = {
            "type": "board_update",
            "as_of": as_of,
            "is_stale": is_stale,
            "source": source,
            "count": len(quotes),
            "quotes": quotes,
        }
        receivers = client.publish(live_channel(), json.dumps(payload, default=str))
        log.info(
            "Published board_update (%d quotes) to %s; redis receivers=%s",
            len(quotes),
            live_channel(),
            receivers,
        )
        return True
    except Exception as exc:
        log.warning("Live bus publish failed: %s", exc)
        return False


async def _dispatch_board_message(raw: str) -> None:
    from app.services.websocket_manager import ws_manager

    try:
        message = json.loads(raw)
    except Exception:
        log.warning("Ignoring non-JSON live bus message")
        return

    if message.get("type") != "board_update":
        return

    quotes = message.get("quotes") or []
    if not isinstance(quotes, list) or not quotes:
        return

    delivered = await ws_manager.broadcast_board_update(
        quotes,
        as_of=message.get("as_of"),
        is_stale=bool(message.get("is_stale", False)),
        source=str(message.get("source") or "session_refresh"),
    )
    log.debug("WS board_update delivered to %d clients", delivered)


async def _listen_loop(stop_event: asyncio.Event) -> None:
    """Long-running Redis subscriber bound to the API event loop."""
    settings = get_settings()
    channel = live_channel()
    backoff = 1.0

    while not stop_event.is_set():
        pubsub = None
        client = None
        try:
            import redis.asyncio as aioredis

            if not getattr(settings, "REDIS_ENABLED", True):
                await asyncio.wait_for(stop_event.wait(), timeout=30.0)
                continue

            client = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2.0,
                socket_timeout=None,
            )
            pubsub = client.pubsub()
            await pubsub.subscribe(channel)
            log.info("Market live bus subscribed to Redis channel %s", channel)
            backoff = 1.0

            while not stop_event.is_set():
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                )
                if message and message.get("type") == "message":
                    data = message.get("data")
                    if isinstance(data, bytes):
                        data = data.decode("utf-8", errors="replace")
                    if isinstance(data, str):
                        await _dispatch_board_message(data)
                else:
                    await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("Market live bus listener error: %s (retry in %.1fs)", exc, backoff)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=backoff)
            except asyncio.TimeoutError:
                pass
            backoff = min(backoff * 2, 30.0)
        finally:
            if pubsub is not None:
                try:
                    await pubsub.unsubscribe(channel)
                    await pubsub.aclose()
                except Exception:
                    pass
            if client is not None:
                try:
                    await client.aclose()
                except Exception:
                    pass


async def start_live_bus_listener() -> None:
    """Start the API-side Redis → WebSocket fan-out (idempotent)."""
    global _listener_task, _listener_stop
    if _listener_task and not _listener_task.done():
        return
    _listener_stop = asyncio.Event()
    _listener_task = asyncio.create_task(
        _listen_loop(_listener_stop),
        name="market-live-bus-listener",
    )
    log.info("Market live bus listener started")


async def stop_live_bus_listener() -> None:
    """Stop the listener cleanly on API shutdown."""
    global _listener_task, _listener_stop
    if _listener_stop is not None:
        _listener_stop.set()
    if _listener_task is not None:
        _listener_task.cancel()
        try:
            await _listener_task
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
    _listener_task = None
    _listener_stop = None
    log.info("Market live bus listener stopped")
