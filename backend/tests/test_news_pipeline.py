"""Tests for the news pipeline components.

Uses mock data — no live website requests.
"""

import hashlib
from datetime import datetime, timezone

from app.services.news_pipeline.dedup import (
    compute_content_hash,
    normalise_url,
    normalise_title,
    is_duplicate,
)
from app.services.news_pipeline.event_classifier import classify_event, classify_articles
from app.services.news_pipeline.impact_scorer import compute_impact_score, score_articles
from app.services.news_pipeline.symbol_tagger import tag_article


# ── Deduplication Tests ────────────────────────────────────────────────────


class TestNormaliseUrl:
    def test_strips_query_and_fragment(self):
        url = "https://example.com/path?a=1&b=2#section"
        assert normalise_url(url) == "https://example.com/path"

    def test_lowercases_scheme_and_host(self):
        url = "HTTP://EXAMPLE.COM/Path"
        assert normalise_url(url) == "http://example.com/Path"

    def test_strips_trailing_slash(self):
        url = "https://example.com/path/"
        assert normalise_url(url) == "https://example.com/path"


class TestNormaliseTitle:
    def test_lowercases_and_strips(self):
        assert normalise_title("  Hello World  ") == "hello world"

    def test_collapses_whitespace(self):
        assert normalise_title("hello   world") == "hello world"

    def test_strips_punctuation(self):
        assert normalise_title("PSX: Market rises!") == "psx market rises"


class TestContentHash:
    def test_same_input_same_hash(self):
        h1 = compute_content_hash("Test Title", "https://example.com/article")
        h2 = compute_content_hash("Test Title", "https://example.com/article")
        assert h1 == h2

    def test_different_input_different_hash(self):
        h1 = compute_content_hash("Title A", "https://example.com/a")
        h2 = compute_content_hash("Title B", "https://example.com/b")
        assert h1 != h2

    def test_is_deterministic(self):
        h = compute_content_hash("Test", "https://x.com")
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex


class TestIsDuplicate:
    def test_not_duplicate_empty_set(self):
        assert not is_duplicate("abc123", set())

    def test_duplicate_in_set(self):
        assert is_duplicate("abc123", {"abc123", "def456"})


# ── Symbol Tagging Tests ───────────────────────────────────────────────────


class TestSymbolTagger:
    def _make_alias_map(self):
        return {
            "ogdc": "OGDC",
            "oil and gas development": "OGDC",
            "engro fertilizers": "EFERT",
            "efert": "EFERT",
            "UBL": "UBL",
            "united bank": "UBL",
            "k electric": "KEL",
            "k-electric": "KEL",
            "hub power": "HUBC",
            "hubco": "HUBC",
        }

    def test_single_symbol_match(self):
        alias_map = self._make_alias_map()
        result = tag_article("OGDC announces quarterly earnings", alias_map)
        assert "OGDC" in result

    def test_multiple_symbols(self):
        alias_map = self._make_alias_map()
        result = tag_article("OGDC and EFERT both reported strong earnings", alias_map)
        assert "OGDC" in result
        assert "EFERT" in result

    def test_no_match(self):
        alias_map = self._make_alias_map()
        result = tag_article("Global markets rally on tech stocks", alias_map)
        assert result == []

    def test_case_insensitive(self):
        alias_map = self._make_alias_map()
        result = tag_article("ogdc reports profit", alias_map)
        assert "OGDC" in result

    def test_alias_match(self):
        alias_map = self._make_alias_map()
        result = tag_article("Oil and Gas Development Company reports results", alias_map)
        assert "OGDC" in result


# ── Event Classification Tests ─────────────────────────────────────────────


class TestEventClassifier:
    def test_earnings(self):
        assert classify_event("OGDC reports quarterly earnings") == "earnings"

    def test_dividend(self):
        assert classify_event("UBL declares final dividend of Rs10") == "dividend"

    def test_interest_rate(self):
        # "SBP holds policy rate at 22%" matches monetary_policy first (more specific)
        assert classify_event("SBP holds policy rate at 22%") == "monetary_policy"

    def test_interest_rate_pure(self):
        # Pure interest rate language without SBP/monetary policy keywords
        assert classify_event("Rate cut expected next quarter") == "interest_rate"

    def test_monetary_policy(self):
        assert classify_event("Monetary policy decision announced") == "monetary_policy"

    def test_acquisition(self):
        assert classify_event("Company A acquires Company B") == "acquisition"

    def test_regulatory(self):
        assert classify_event("SECP issues new compliance notice") == "regulatory_action"

    def test_other(self):
        assert classify_event("Random news about weather") == "other"

    def test_batch_classification(self):
        articles = [
            {"title": "OGDC earnings beat estimates", "summary": None},
            {"title": "UBL dividend announced", "summary": None},
            {"title": "Random article", "summary": None},
        ]
        result = classify_articles(articles)
        assert result[0]["event_type"] == "earnings"
        assert result[1]["event_type"] == "dividend"
        assert result[2]["event_type"] == "other"


# ── Impact Score Tests ─────────────────────────────────────────────────────


class TestImpactScorer:
    def test_high_impact_official_source(self):
        score = compute_impact_score(
            source="PSX",
            event_type="earnings",
            symbols=["OGDC"],
            sentiment_score=0.9,
            published_at=datetime.now(timezone.utc),
        )
        assert score >= 70

    def test_low_impact_general_news(self):
        score = compute_impact_score(
            source="Dawn Business",
            event_type="other",
            symbols=[],
            sentiment_score=0.1,
            published_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        assert score <= 40

    def test_score_clamped_to_100(self):
        score = compute_impact_score(
            source="PSX",
            event_type="earnings",
            symbols=["OGDC", "PPL", "ENGRO"],
            sentiment_score=0.99,
            published_at=datetime.now(timezone.utc),
        )
        assert score <= 100

    def test_score_non_negative(self):
        score = compute_impact_score(
            source="Unknown",
            event_type="other",
            symbols=[],
            sentiment_score=None,
            published_at=None,
        )
        assert score >= 0

    def test_batch_scoring(self):
        articles = [
            {"source": "PSX", "event_type": "earnings", "symbols": ["OGDC"],
             "sentiment_score": 0.9, "published_at": datetime.now(timezone.utc)},
        ]
        result = score_articles(articles)
        assert "impact_score" in result[0]
        assert isinstance(result[0]["impact_score"], int)


# ── Multiple-Symbol Article Tests ──────────────────────────────────────────


class TestMultipleSymbolArticles:
    def test_article_affecting_multiple_companies(self):
        from app.services.news_pipeline.symbol_tagger import tag_article
        alias_map = {
            "ogdc": "OGDC",
            "ppl": "PPL",
            "mar": "MAR",
        }
        text = "Oil prices impact OGDC, PPL and MAR differently"
        result = tag_article(text, alias_map)
        assert len(result) >= 2


# ── Market Schedule Tests ──────────────────────────────────────────────────


class TestMarketSchedule:
    """Test market-hours logic using mocked times."""

    def test_is_weekendSaturday(self):
        from app.services.news_pipeline import market_schedule
        from datetime import time as dt_time
        # Patch _now_pkt to return a Saturday at 10:00 PKT
        from unittest.mock import patch
        fake_now = datetime(2026, 9, 19, 10, 0, 0, tzinfo=market_schedule.PKT)  # Saturday
        with patch.object(market_schedule, "_now_pkt", return_value=fake_now):
            assert market_schedule.is_weekend() is True
            assert market_schedule.is_market_hours() is False
            assert market_schedule.is_ingestion_allowed() is False

    def test_is_weekendSunday(self):
        from app.services.news_pipeline import market_schedule
        from unittest.mock import patch
        fake_now = datetime(2026, 9, 20, 10, 0, 0, tzinfo=market_schedule.PKT)  # Sunday
        with patch.object(market_schedule, "_now_pkt", return_value=fake_now):
            assert market_schedule.is_weekend() is True
            assert market_schedule.is_ingestion_allowed() is False

    def test_market_hours_weekday(self):
        from app.services.news_pipeline import market_schedule
        from unittest.mock import patch
        # Wednesday 10:00 PKT — inside market hours
        fake_now = datetime(2026, 9, 16, 10, 0, 0, tzinfo=market_schedule.PKT)
        with patch.object(market_schedule, "_now_pkt", return_value=fake_now):
            assert market_schedule.is_weekend() is False
            assert market_schedule.is_market_hours() is True
            assert market_schedule.is_post_market() is False
            assert market_schedule.is_ingestion_allowed() is True

    def test_post_market_weekday(self):
        from app.services.news_pipeline import market_schedule
        from unittest.mock import patch
        # Wednesday 16:00 PKT — post-market
        fake_now = datetime(2026, 9, 16, 16, 0, 0, tzinfo=market_schedule.PKT)
        with patch.object(market_schedule, "_now_pkt", return_value=fake_now):
            assert market_schedule.is_market_hours() is False
            assert market_schedule.is_post_market() is True
            assert market_schedule.is_ingestion_allowed() is True

    def test_closed_after_post_market(self):
        from app.services.news_pipeline import market_schedule
        from unittest.mock import patch
        # Wednesday 18:00 PKT — after post-market
        fake_now = datetime(2026, 9, 16, 18, 0, 0, tzinfo=market_schedule.PKT)
        with patch.object(market_schedule, "_now_pkt", return_value=fake_now):
            assert market_schedule.is_market_hours() is False
            assert market_schedule.is_post_market() is False
            assert market_schedule.is_ingestion_allowed() is False

    def test_closed_before_market_open(self):
        from app.services.news_pipeline import market_schedule
        from unittest.mock import patch
        # Wednesday 08:00 PKT — before market
        fake_now = datetime(2026, 9, 16, 8, 0, 0, tzinfo=market_schedule.PKT)
        with patch.object(market_schedule, "_now_pkt", return_value=fake_now):
            assert market_schedule.is_market_hours() is False
            assert market_schedule.is_ingestion_allowed() is False

    def test_ingestion_interval_market(self):
        from app.services.news_pipeline import market_schedule
        from unittest.mock import patch
        fake_now = datetime(2026, 9, 16, 10, 0, 0, tzinfo=market_schedule.PKT)
        with patch.object(market_schedule, "_now_pkt", return_value=fake_now):
            assert market_schedule.get_ingestion_interval() == 1800  # 30 min

    def test_ingestion_interval_post_market(self):
        from app.services.news_pipeline import market_schedule
        from unittest.mock import patch
        fake_now = datetime(2026, 9, 16, 16, 0, 0, tzinfo=market_schedule.PKT)
        with patch.object(market_schedule, "_now_pkt", return_value=fake_now):
            assert market_schedule.get_ingestion_interval() == 3600  # 60 min

    def test_ingestion_interval_closed(self):
        from app.services.news_pipeline import market_schedule
        from unittest.mock import patch
        fake_now = datetime(2026, 9, 16, 18, 0, 0, tzinfo=market_schedule.PKT)
        with patch.object(market_schedule, "_now_pkt", return_value=fake_now):
            assert market_schedule.get_ingestion_interval() == 0

    def test_next_window_before_open(self):
        from app.services.news_pipeline import market_schedule
        from unittest.mock import patch
        # Wednesday 08:00 PKT — next window is today at 09:30
        fake_now = datetime(2026, 9, 16, 8, 0, 0, tzinfo=market_schedule.PKT)
        with patch.object(market_schedule, "_now_pkt", return_value=fake_now):
            nxt = market_schedule.next_ingestion_window()
            assert nxt is not None
            assert nxt.hour == 9
            assert nxt.minute == 30

    def test_next_window_after_post_market(self):
        from app.services.news_pipeline import market_schedule
        from unittest.mock import patch
        # Wednesday 18:00 PKT — next window is tomorrow at 09:30
        fake_now = datetime(2026, 9, 16, 18, 0, 0, tzinfo=market_schedule.PKT)
        with patch.object(market_schedule, "_now_pkt", return_value=fake_now):
            nxt = market_schedule.next_ingestion_window()
            assert nxt is not None
            assert nxt.day == 17  # Thursday

    def test_next_window_friday_after_post_market(self):
        from app.services.news_pipeline import market_schedule
        from unittest.mock import patch
        # Friday 18:00 PKT — next window is Monday
        fake_now = datetime(2026, 9, 18, 18, 0, 0, tzinfo=market_schedule.PKT)
        with patch.object(market_schedule, "_now_pkt", return_value=fake_now):
            nxt = market_schedule.next_ingestion_window()
            assert nxt is not None
            assert nxt.weekday() == 0  # Monday

    def test_market_status_structure(self):
        from app.services.news_pipeline.market_schedule import market_status
        status = market_status()
        assert "timezone" in status
        assert status["timezone"] == "Asia/Karachi"
        assert "current_time_pkt" in status
        assert "status" in status
        assert status["status"] in ("market_hours", "post_market", "closed")


# ── Ingestion State Tests ──────────────────────────────────────────────────


class TestIngestionState:
    def test_set_and_get_last_ingestion_time(self):
        from app.services.news_pipeline import ingestion_state
        from datetime import datetime, timezone
        test_time = datetime(2026, 9, 16, 10, 30, 0, tzinfo=timezone.utc)
        ingestion_state.set_last_ingestion_time(test_time)
        result = ingestion_state.get_last_ingestion_time()
        assert result is not None
        assert result.hour == 10
        assert result.minute == 30

    def test_increment_run_count(self):
        from app.services.news_pipeline import ingestion_state
        before = ingestion_state._load_state().get("total_runs", 0)
        ingestion_state.increment_run_count()
        after = ingestion_state._load_state().get("total_runs", 0)
        assert after == before + 1
