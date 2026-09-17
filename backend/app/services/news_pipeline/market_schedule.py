"""Market-aware scheduling — determines whether news ingestion should run.

Uses Asia/Karachi (UTC+5) timezone exclusively.
All times are configurable via Settings.

Window logic:
  MARKET:      09:30 - 15:30 PKT  (ingest every 30 min)
  POST-MARKET: 15:30 - 17:00 PKT  (ingest every 60 min)
  CLOSED:      17:00 - 09:30 PKT  (no ingestion)

Weekends (Saturday/Sunday) are always CLOSED.
"""

import logging
from datetime import datetime, time, timedelta, timezone

from app.core.config import get_settings

log = logging.getLogger(__name__)

PKT = timezone(timedelta(hours=5))


def _now_pkt() -> datetime:
    return datetime.now(PKT)


def _market_open_time() -> time:
    s = get_settings()
    return time(s.MARKET_OPEN_HOUR, s.MARKET_OPEN_MINUTE)


def _market_close_time() -> time:
    s = get_settings()
    return time(s.MARKET_CLOSE_HOUR, s.MARKET_CLOSE_MINUTE)


def _post_market_close_time() -> time:
    s = get_settings()
    return time(s.POST_MARKET_CLOSE_HOUR, s.POST_MARKET_CLOSE_MINUTE)


def is_weekend() -> bool:
    """Saturday (5) or Sunday (6)."""
    return _now_pkt().weekday() >= 5


def is_market_hours() -> bool:
    """True if current PKT time is within PSX market session (09:30-15:30)."""
    if is_weekend():
        return False
    now = _now_pkt().time()
    return _market_open_time() <= now < _market_close_time()


def is_post_market() -> bool:
    """True if current PKT time is in the post-market window (15:30-17:00)."""
    if is_weekend():
        return False
    now = _now_pkt().time()
    return _market_close_time() <= now < _post_market_close_time()


def is_ingestion_allowed() -> bool:
    """True if ingestion should run now (market hours or post-market)."""
    return is_market_hours() or is_post_market()


def get_ingestion_interval() -> int:
    """Return the appropriate ingestion interval in seconds for the current window."""
    if is_market_hours():
        return get_settings().NEWS_INGESTION_INTERVAL_MARKET
    if is_post_market():
        return get_settings().NEWS_INGESTION_INTERVAL_POST_MARKET
    return 0  # no ingestion outside active windows


def next_ingestion_window() -> datetime | None:
    """Return the PKT datetime of the next ingestion window start, or None if unknown."""
    now = _now_pkt()
    today_open = now.replace(
        hour=get_settings().MARKET_OPEN_HOUR,
        minute=get_settings().MARKET_OPEN_MINUTE,
        second=0, microsecond=0,
    )
    today_close = now.replace(
        hour=get_settings().POST_MARKET_CLOSE_HOUR,
        minute=get_settings().POST_MARKET_CLOSE_MINUTE,
        second=0, microsecond=0,
    )

    if is_weekend():
        # Next Monday at market open
        days_until_monday = 7 - now.weekday()
        return today_open + timedelta(days=days_until_monday)

    now_time = now.time()
    market_open = _market_open_time()
    post_market_close = _post_market_close_time()

    if now_time < market_open:
        return today_open
    if now_time >= post_market_close:
        # After post-market today → next trading day at market open
        if now.weekday() == 4:  # Friday
            return today_open + timedelta(days=3)  # Monday
        return today_open + timedelta(days=1)

    return None  # currently in an active window


def market_status() -> dict:
    """Return a summary of current market/ingestion status."""
    now = _now_pkt()
    status = "closed"
    if is_market_hours():
        status = "market_hours"
    elif is_post_market():
        status = "post_market"

    return {
        "timezone": "Asia/Karachi",
        "current_time_pkt": now.isoformat(),
        "status": status,
        "is_weekend": is_weekend(),
        "ingestion_allowed": is_ingestion_allowed(),
        "next_window": next_ingestion_window().isoformat() if next_ingestion_window() else None,
    }
