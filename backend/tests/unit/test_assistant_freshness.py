"""Unit tests for assistant live-intent / freshness helpers."""

from app.services.assistant_freshness import (
    wants_live_numbers,
    wants_live_portfolio,
    is_fresh_enough,
    cache_age_seconds,
)


def test_wants_live_numbers_price_queries():
    assert wants_live_numbers("What is the current price of OGDC?")
    assert wants_live_numbers("OGDC LTP today")
    assert wants_live_numbers("Show me top gainers")
    assert wants_live_numbers("How is the market today?")
    assert wants_live_numbers("live quote for HBL")


def test_wants_live_numbers_false_for_education():
    assert not wants_live_numbers("What is RSI?")
    assert not wants_live_numbers("Explain diversification")
    assert not wants_live_numbers("How do I create a portfolio?")


def test_wants_live_portfolio():
    assert wants_live_portfolio("What is my portfolio P&L today?")
    assert wants_live_portfolio("Show my live portfolio value")
    assert not wants_live_portfolio("How do I create a portfolio?")


def test_freshness_helpers():
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    fresh = (now - timedelta(seconds=30)).isoformat()
    stale = (now - timedelta(seconds=600)).isoformat()
    assert is_fresh_enough(fresh, 60)
    assert not is_fresh_enough(stale, 60)
    assert cache_age_seconds(None) is None
    assert cache_age_seconds(fresh) < 120
