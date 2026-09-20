"""Explainable impact scoring (0-100).

Deterministic formula using weighted signals.  NOT a trading prediction.

Signals:
  1. Source weight       (0-30): official sources score higher
  2. Event type weight   (0-25): earnings/dividend > general news
  3. Symbol specificity  (0-20): company-specific > market-wide
  4. Sentiment strength  (0-15): stronger sentiment → higher impact
  5. Recency weight      (0-10): newer articles score higher
"""

from datetime import datetime, timezone


# ── Source weights (0-30) ──────────────────────────────────────────────────
_SOURCE_WEIGHTS: dict[str, int] = {
    "PSX": 30,
    "SECP": 28,
    "SBP": 28,
    "Business Recorder": 20,
    "Dawn Business": 18,
}

# ── Event type weights (0-25) ─────────────────────────────────────────────
_EVENT_WEIGHTS: dict[str, int] = {
    "earnings": 25,
    "dividend": 24,
    "acquisition": 23,
    "merger": 22,
    "regulatory_action": 20,
    "interest_rate": 20,
    "monetary_policy": 20,
    "contract": 18,
    "circular_debt": 18,
    "block_order": 20,
    "management_change": 17,
    "litigation": 15,
    "oil_price": 14,
    "currency": 14,
    "imf": 14,
    "expansion": 13,
    "other": 5,
}


def _source_weight(source: str | None) -> int:
    return _SOURCE_WEIGHTS.get(source or "", 10)


def _event_weight(event_type: str | None) -> int:
    return _EVENT_WEIGHTS.get(event_type or "other", 5)


def _symbol_weight(symbols: list[str]) -> int:
    """Company-specific articles score higher.  Max 20."""
    n = len(symbols)
    if n == 0:
        return 5  # market-wide
    if n == 1:
        return 20  # single-company focus
    if n <= 3:
        return 17
    return 14  # affects many companies


def _sentiment_weight(sentiment_score: float | None) -> int:
    """Stronger absolute sentiment → higher impact.  Max 15."""
    if sentiment_score is None:
        return 5
    abs_score = abs(float(sentiment_score))
    if abs_score >= 0.8:
        return 15
    if abs_score >= 0.5:
        return 12
    if abs_score >= 0.2:
        return 8
    return 5


def _recency_weight(published_at: datetime | None) -> int:
    """Newer articles score higher.  Max 10."""
    if published_at is None:
        return 5
    now = datetime.now(timezone.utc)
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    age_hours = max((now - published_at).total_seconds() / 3600, 0)
    if age_hours <= 6:
        return 10
    if age_hours <= 24:
        return 8
    if age_hours <= 72:
        return 6
    return 4


def compute_impact_score(
    source: str | None,
    event_type: str | None,
    symbols: list[str],
    sentiment_score: float | None,
    published_at: datetime | None,
) -> int:
    """Compute deterministic impact score (0-100).

    Formula: source + event + symbol specificity + sentiment + recency
    """
    score = (
        _source_weight(source)
        + _event_weight(event_type)
        + _symbol_weight(symbols)
        + _sentiment_weight(sentiment_score)
        + _recency_weight(published_at)
    )
    return min(max(score, 0), 100)


def score_articles(articles: list[dict]) -> list[dict]:
    """Score a batch of articles. Adds 'impact_score' to each dict."""
    for article in articles:
        article["impact_score"] = compute_impact_score(
            source=article.get("source"),
            event_type=article.get("event_type"),
            symbols=article.get("symbols", []),
            sentiment_score=article.get("sentiment_score"),
            published_at=article.get("published_at"),
        )
    return articles
