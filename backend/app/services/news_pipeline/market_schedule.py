"""Market-aware scheduling — determines whether news ingestion should run.

Uses Asia/Karachi (UTC+5) timezone exclusively.
All times are configurable via Settings and market_hours_config table.

Window logic:
  MARKET:      09:15 - 15:30 PKT  (ingest every 30 min)
  FRIDAY:      09:00 - 12:00 and 14:30 - 16:30 PKT (through midday break)
  POST-MARKET: 15:30 - 17:00 PKT  (ingest every 60 min, configurable)
  CLOSED:      outside above windows + weekends + holidays

Ramadan schedule (configurable override):
  Mon-Thu: 09:00 - 13:30
  Fri: 09:00 - 12:30
"""

import json
import logging
import time as time_module
from contextlib import asynccontextmanager
from datetime import datetime, time, timedelta, timezone
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import select, text as sa_text

from app.core.config import get_settings
from app.cache.redis_client import redis_client
from app.db.session import async_session_factory
from app.models.news import MarketHoursConfig

log = logging.getLogger(__name__)

PKT = timezone(timedelta(hours=5))

# In-memory cache for config
_config_cache: Optional[dict] = None
_config_cache_time: float = 0
_CONFIG_CACHE_TTL = 300  # 5 minutes

_LOCK_KEY = "news:ingestion:lock"
_LOCK_TTL = 900  # 15 minutes


def _now_pkt() -> datetime:
    return datetime.now(PKT)


async def _load_market_config() -> dict:
    """Load market hours config from DB with caching."""
    global _config_cache, _config_cache_time
    now = time_module.time()
    if _config_cache and (now - _config_cache_time) < _CONFIG_CACHE_TTL:
        return _config_cache

    try:
        async with async_session_factory() as db:
            result = await db.execute(
                select(MarketHoursConfig).where(MarketHoursConfig.is_active == True)
            )
            configs = result.scalars().all()

        default = _default_config()
        config = {
            "weekly": default["weekly"],
            "holidays": default["holidays"],
            "overrides": default["overrides"],
        }
        for cfg in configs:
            if cfg.name == "default_weekly" and cfg.config_json:
                config["weekly"] = cfg.config_json
            elif cfg.name == "holidays" and cfg.config_json:
                config["holidays"] = cfg.config_json
            elif cfg.name == "overrides" and cfg.config_json:
                config["overrides"] = cfg.config_json

        if not config.get("weekly"):
            config["weekly"] = default["weekly"]

        _config_cache = config
        _config_cache_time = now
        return config
    except Exception as exc:
        log.warning("Failed to load market config, using defaults: %s", exc)
        return _default_config()


def _default_config() -> dict:
    """Default PSX market hours (2024/2025 schedule)."""
    return {
        "weekly": {
            "monday": {"open": "09:15", "close": "15:30"},
            "tuesday": {"open": "09:15", "close": "15:30"},
            "wednesday": {"open": "09:15", "close": "15:30"},
            "thursday": {"open": "09:15", "close": "15:30"},
            "friday": {"open": "09:00", "close": "16:30", "break": {"start": "12:00", "end": "14:30"}},
            "saturday": None,
            "sunday": None,
        },
        "holidays": [],
        "overrides": [],
    }


def _parse_time(time_str: str) -> time:
    """Parse HH:MM string to time object."""
    return datetime.strptime(time_str, "%H:%M").time()


async def _get_day_schedule(day_name: str) -> Optional[dict]:
    """Get schedule for a specific day, checking overrides first."""
    config = await _load_market_config()

    # Check overrides (date-specific)
    today_str = _now_pkt().date().isoformat()
    for override in config.get("overrides", []):
        if override.get("date") == today_str:
            return override.get("schedule")

    # Check weekly schedule
    return config.get("weekly", {}).get(day_name.lower())


async def is_holiday() -> bool:
    """Check if today is a holiday."""
    config = await _load_market_config()
    today_str = _now_pkt().date().isoformat()
    return today_str in config.get("holidays", [])


async def is_weekend() -> bool:
    """Saturday (5) or Sunday (6)."""
    return _now_pkt().weekday() >= 5


async def is_market_hours() -> bool:
    """True if current PKT time is within PSX market session."""
    if await is_weekend() or await is_holiday():
        return False

    now = _now_pkt()
    day_name = now.strftime("%A").lower()
    schedule = await _get_day_schedule(day_name)

    if not schedule:
        return False

    now_time = now.time()
    open_time = _parse_time(schedule["open"])
    close_time = _parse_time(schedule["close"])

    # Check if in midday break (Friday)
    if "break" in schedule:
        break_start = _parse_time(schedule["break"]["start"])
        break_end = _parse_time(schedule["break"]["end"])
        if break_start <= now_time < break_end:
            return False  # In break period

    return open_time <= now_time < close_time


async def is_post_market() -> bool:
    """True if current PKT time is in the post-market window."""
    if await is_weekend() or await is_holiday():
        return False

    now = _now_pkt()
    day_name = now.strftime("%A").lower()
    schedule = await _get_day_schedule(day_name)

    if not schedule:
        return False

    now_time = now.time()
    close_time = _parse_time(schedule["close"])
    settings = get_settings()
    post_market_end = time(settings.POST_MARKET_CLOSE_HOUR, settings.POST_MARKET_CLOSE_MINUTE)

    return close_time <= now_time < post_market_end


async def is_ingestion_allowed() -> bool:
    """True if ingestion should run now (market hours or post-market)."""
    settings = get_settings()
    if not getattr(settings, "NEWS_MARKET_GATING_ENABLED", True):
        return True  # Gating disabled - always allow
    return await is_market_hours() or await is_post_market()


async def get_ingestion_interval() -> int:
    """Return the appropriate ingestion interval in seconds for the current window."""
    if await is_market_hours():
        return get_settings().NEWS_INGESTION_INTERVAL_MARKET
    if await is_post_market():
        return get_settings().NEWS_INGESTION_INTERVAL_POST_MARKET
    return 0


async def next_ingestion_window() -> Optional[datetime]:
    """Return the PKT datetime of the next ingestion window start."""
    if await is_market_hours() or await is_post_market():
        return None  # Currently in a window

    now = _now_pkt()
    settings = get_settings()

    # Check upcoming days for the next valid window
    for days_ahead in range(0, 10):  # Look ahead up to 10 days
        check_date = now + timedelta(days=days_ahead)
        day_name = check_date.strftime("%A").lower()

        # Skip weekends
        if check_date.weekday() >= 5:
            continue

        # Check holidays
        if check_date.date().isoformat() in (await _load_market_config()).get("holidays", []):
            continue

        schedule = await _get_day_schedule(day_name)
        if not schedule:
            continue

        open_time = _parse_time(schedule["open"])
        next_open = check_date.replace(
            hour=open_time.hour,
            minute=open_time.minute,
            second=0, microsecond=0,
        )

        if next_open > now:
            return next_open

        # Handle midday break resumption on the same day (e.g. Friday 12:00-14:30)
        if "break" in schedule and days_ahead == 0:
            break_end = _parse_time(schedule["break"]["end"])
            break_resume = check_date.replace(
                hour=break_end.hour,
                minute=break_end.minute,
                second=0, microsecond=0,
            )
            if break_resume > now:
                return break_resume

    return None


async def market_status() -> dict:
    """Return a summary of current market/ingestion status."""
    now = _now_pkt()
    in_market = await is_market_hours()
    in_post = await is_post_market()
    is_wknd = await is_weekend()
    is_hol = await is_holiday()

    if in_market:
        status = "market_hours"
    elif in_post:
        status = "post_market"
    else:
        status = "closed"

    next_win = await next_ingestion_window()

    return {
        "timezone": "Asia/Karachi",
        "current_time_pkt": now.isoformat(),
        "status": status,
        "is_weekend": is_wknd,
        "is_holiday": is_hol,
        "ingestion_allowed": await is_ingestion_allowed(),
        "gating_enabled": getattr(get_settings(), "NEWS_MARKET_GATING_ENABLED", True),
        "within_run_window": in_market or in_post,
        "session_label": status,
        "next_scheduled_run_at": next_win.isoformat() if next_win else None,
    }


# ── Single-flight lock ────────────────────────────────────────────────────

_LOCK_KEY = "news:ingestion:lock"
_LOCK_TTL = 900  # 15 minutes


@asynccontextmanager
async def ingestion_lock():
    """Context manager for single-flight ingestion lock using Redis.

    Usage:
        with ingestion_lock() as acquired:
            if not acquired:
                return  # Another run is active
            run_pipeline()

    If Redis is unavailable, falls back to DB advisory lock.
    """
    acquired = False
    try:
        # Try Redis first
        if redis_client:
            acquired = redis_client.set(_LOCK_KEY, "1", nx=True, ex=_LOCK_TTL)
        else:
            acquired = False
    except Exception:
        acquired = False

    # Fallback to DB advisory lock
    if not acquired:
        try:
            async with async_session_factory() as db:
                result = await db.execute(
                    sa.text("SELECT pg_try_advisory_xact_lock(:lock_id)"),
                    {"lock_id": 123456789}  # Fixed lock ID for news ingestion
                )
                acquired = result.scalar()
        except Exception:
            acquired = False

    try:
        yield acquired
    finally:
        if acquired:
            try:
                if redis_client:
                    redis_client.delete(_LOCK_KEY)
            except Exception:
                pass