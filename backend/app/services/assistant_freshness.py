"""Assistant data freshness helpers and live-number intent detection."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional


_LIVE_NUMBER_RE = re.compile(
    r"\b("
    r"today|live|now|current|currently|latest|realtime|real[\s-]?time|"
    r"ltp|quote|price|prices|change\s*%?|volume|"
    r"gainers?|losers?|top\s+gainer|top\s+loser|"
    r"how\s+is\s+(?:the\s+)?market|market\s+today|"
    r"what(?:'s| is)\s+(?:the\s+)?(?:price|quote)|"
    r"trading\s+at|closing\s+price|open(?:ing)?\s+price"
    r")\b",
    re.IGNORECASE,
)

_LIVE_PORTFOLIO_RE = re.compile(
    r"\b("
    r"(?:live|current|today(?:'s)?)\s+(?:portfolio|pnl|p&l|holdings?)|"
    r"portfolio\s+(?:now|today|live)|"
    r"(?:my\s+)?(?:pnl|p&l)\s+(?:now|today)"
    r")\b",
    re.IGNORECASE,
)


def wants_live_numbers(message: str) -> bool:
    """True when the user is asking for current market/price figures."""
    if not message:
        return False
    return bool(_LIVE_NUMBER_RE.search(message))


def wants_live_portfolio(message: str) -> bool:
    """True when the user wants fresh portfolio valuation numbers."""
    if not message:
        return False
    return bool(_LIVE_PORTFOLIO_RE.search(message)) or (
        wants_live_numbers(message)
        and bool(re.search(r"\b(?:my\s+)?(?:portfolio|holdings?|pnl|p&l)\b", message, re.I))
    )


def cache_age_seconds(fetched_at: Optional[str]) -> Optional[float]:
    """Return age in seconds for an ISO timestamp, or None if unknown."""
    if not fetched_at:
        return None
    try:
        stamp = datetime.fromisoformat(str(fetched_at).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds()
    except (TypeError, ValueError):
        return None


def is_fresh_enough(fetched_at: Optional[str], max_age_seconds: float) -> bool:
    age = cache_age_seconds(fetched_at)
    if age is None:
        return False
    return age <= max_age_seconds
