"""Rule-based event classification for news articles.

Classifies articles into one of the predefined event types using
keyword matching.  Designed to be replaceable with a more sophisticated
classifier later.

Core event types (market-moving):
- earnings: Quarterly/annual results, profit, revenue, EPS
- dividend: Cash/stock dividends, bonus issues, rights issues
- sbp_monetary_policy: SBP policy rate, monetary policy, interest rate decisions
"""

import re

# ── Event type definitions with trigger patterns ──────────────────────────

_EVENT_RULES: list[tuple[str, list[str]]] = [
    ("earnings", [
        r"\bearnings?\b", r"\bprofit\b", r"\brevenue\b", r"\bloss\b",
        r"\bnet income\b", r"\bgross margin\b", r"\beps\b",
        r"\bquarterly result\b", r"\bannual result\b", r"\bhalf.?year",
        r"\bfinancial result\b", r"\bfinancial statement",
        r"\bsurprise\b", r"\bbeats?\b", r"\bmiss(es|ed)?\b",
        r"\b(above|below|ahead of|behind)\s+(expectations|estimate|forecast)",
        r"\bexceeded?\s+(expectations|estimate|forecast)", r"\bestimates?\b",
    ]),
    ("dividend", [
        r"\bdividend\b", r"\bfinal dividend\b", r"\binterim dividend\b",
        r"\bcash dividend\b", r"\bspecial dividend\b", r"\bbonus\b",
        r"\bright\b", r"\bissue\b",
    ]),
    ("sbp_monetary_policy", [
        r"\bmonetary policy\b", r"\bpolicy rate\b",
        r"\binterest rate\b", r"\bcash reserve\b", r"\bopen market\b",
        r"\brate cut\b", r"\brate hike\b", r"\brate hold\b",
        r"\bsbp\b.*\brate\b", r"\bbasis point\b",
    ]),
]

# Compile once at import time
_COMPILED_RULES: list[tuple[str, list[re.Pattern]]] = [
    (event_type, [re.compile(p, re.IGNORECASE) for p in patterns])
    for event_type, patterns in _EVENT_RULES
]


def classify_event(title: str, summary: str | None = None) -> str:
    """Classify a single article into an event type.

    Returns one of: 'earnings', 'dividend', 'sbp_monetary_policy', or 'other'.
    Priority is defined by the order in _EVENT_RULES.
    """
    text = f"{title} {summary or ''}"
    for event_type, patterns in _COMPILED_RULES:
        for pattern in patterns:
            if pattern.search(text):
                return event_type
    return "other"


def classify_articles(articles: list[dict]) -> list[dict]:
    """Classify a batch of articles. Adds 'event_type' to each dict."""
    for article in articles:
        article["event_type"] = classify_event(
            article.get("title", ""),
            article.get("summary"),
        )
    return articles
