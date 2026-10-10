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

    def test_generic_words_not_falsely_tagged(self):
        alias_map = self._make_alias_map()
        # Add potentially dangerous generic terms
        alias_map["bank"] = "MEBL"
        alias_map["power"] = "HUBC"
        alias_map["systems"] = "SYS"
        alias_map["limited"] = "LUCK"

        # General sentence mentioning banks and power shouldn't match stop words
        result = tag_article("The commercial bank power generation update in Pakistan", alias_map)
        assert "MEBL" not in result
        assert "HUBC" not in result
        assert "LUCK" not in result


# ── Entity Context Extraction Tests ─────────────────────────────────────────


class TestEntityContextExtraction:
    def test_isolates_symbol_sentence_window(self):
        from app.services.sentiment_service import extract_entity_context

        article = (
            "OGDC announced record quarterly profit and new gas discovery in Sindh. "
            "The company will pay an interim dividend of Rs 5 per share. "
            "In other news, PPL suffered a steep revenue drop due to circular debt accumulation."
        )
        context_ogdc = extract_entity_context(article, symbol="OGDC")
        assert "OGDC announced record quarterly profit" in context_ogdc
        assert "interim dividend" in context_ogdc
        assert "PPL suffered a steep revenue drop" not in context_ogdc

    def test_isolates_second_entity_context(self):
        from app.services.sentiment_service import extract_entity_context

        article = (
            "OGDC announced record quarterly profit and new gas discovery in Sindh. "
            "Market dynamics remained mixed across energy exploration sectors. "
            "In other news, PPL suffered a steep revenue drop due to circular debt accumulation."
        )
        context_ppl = extract_entity_context(article, symbol="PPL")
        assert "PPL suffered a steep revenue drop" in context_ppl
        assert "OGDC announced record quarterly profit" not in context_ppl

    def test_heuristic_psx_lexicon(self):
        from app.services.sentiment_service import score_text

        pos_res = score_text("Company announced massive gas discovery and interim dividend payout")
        assert pos_res["label"] == "positive"
        assert pos_res["score"] > 0.15

        neg_res = score_text("Sector faces severe circular debt accumulation and super tax burden")
        assert neg_res["label"] == "negative"
        assert neg_res["score"] < -0.15


# ── Event Classification Tests ─────────────────────────────────────────────


class TestEventClassifier:
    def test_earnings(self):
        assert classify_event("OGDC reports quarterly earnings") == "earnings"

    def test_dividend(self):
        assert classify_event("UBL declares final dividend of Rs10") == "dividend"

    def test_interest_rate(self):
        assert classify_event("SBP holds policy rate at 22%") == "sbp_monetary_policy"

    def test_interest_rate_pure(self):
        assert classify_event("Rate cut expected next quarter") == "sbp_monetary_policy"

    def test_monetary_policy(self):
        assert classify_event("Monetary policy decision announced") == "sbp_monetary_policy"

    def test_earnings_surprise_beat(self):
        assert classify_event("OGDC beats earnings estimates") == "earnings"

    def test_earnings_surprise_miss(self):
        assert classify_event("LUCK misses profit expectations") == "earnings"

    def test_interest_rate_decision(self):
        assert classify_event("SBP raises interest rate by 100bps") == "sbp_monetary_policy"

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

    def test_circular_debt_impact_weight(self):
        score = compute_impact_score(
            source="Business Recorder",
            event_type="circular_debt",
            symbols=[],
            sentiment_score=0.5,
            published_at=datetime.now(timezone.utc),
        )
        score_other = compute_impact_score(
            source="Business Recorder",
            event_type="other",
            symbols=[],
            sentiment_score=0.5,
            published_at=datetime.now(timezone.utc),
        )
        assert score > score_other  # circular_debt must not fall back to default weight

    def test_block_order_impact_weight(self):
        score = compute_impact_score(
            source="Business Recorder",
            event_type="block_order",
            symbols=["OGDC"],
            sentiment_score=0.6,
            published_at=datetime.now(timezone.utc),
        )
        assert score >= 20 + 18 + 20 + 12 + 10 - 0  # source+event+symbol+sentiment+recency floor


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

    async def test_is_weekendSaturday(self):
        from app.services.news_pipeline import market_schedule
        from datetime import time as dt_time
        # Patch _now_pkt to return a Saturday at 10:00 PKT
        from unittest.mock import patch
        fake_now = datetime(2026, 9, 19, 10, 0, 0, tzinfo=market_schedule.PKT)  # Saturday
        with patch.object(market_schedule, "_now_pkt", return_value=fake_now):
            assert await market_schedule.is_weekend() is True
            assert await market_schedule.is_market_hours() is False
            assert await market_schedule.is_ingestion_allowed() is False

    async def test_is_weekendSunday(self):
        from app.services.news_pipeline import market_schedule
        from unittest.mock import patch
        fake_now = datetime(2026, 9, 20, 10, 0, 0, tzinfo=market_schedule.PKT)  # Sunday
        with patch.object(market_schedule, "_now_pkt", return_value=fake_now):
            assert await market_schedule.is_weekend() is True
            assert await market_schedule.is_ingestion_allowed() is False

    async def test_market_hours_weekday(self):
        from app.services.news_pipeline import market_schedule
        from unittest.mock import patch
        # Wednesday 10:00 PKT — inside market hours
        fake_now = datetime(2026, 9, 16, 10, 0, 0, tzinfo=market_schedule.PKT)
        with patch.object(market_schedule, "_now_pkt", return_value=fake_now):
            assert await market_schedule.is_weekend() is False
            assert await market_schedule.is_market_hours() is True
            assert await market_schedule.is_post_market() is False
            assert await market_schedule.is_ingestion_allowed() is True

    async def test_post_market_weekday(self):
        from app.services.news_pipeline import market_schedule
        from unittest.mock import patch
        # Wednesday 16:00 PKT — post-market
        fake_now = datetime(2026, 9, 16, 16, 0, 0, tzinfo=market_schedule.PKT)
        with patch.object(market_schedule, "_now_pkt", return_value=fake_now):
            assert await market_schedule.is_market_hours() is False
            assert await market_schedule.is_post_market() is True
            assert await market_schedule.is_ingestion_allowed() is True

    async def test_closed_after_post_market(self):
        from app.services.news_pipeline import market_schedule
        from unittest.mock import patch
        # Wednesday 18:00 PKT — after post-market
        fake_now = datetime(2026, 9, 16, 18, 0, 0, tzinfo=market_schedule.PKT)
        with patch.object(market_schedule, "_now_pkt", return_value=fake_now):
            assert await market_schedule.is_market_hours() is False
            assert await market_schedule.is_post_market() is False
            assert await market_schedule.is_ingestion_allowed() is False

    async def test_closed_before_market_open(self):
        from app.services.news_pipeline import market_schedule
        from unittest.mock import patch
        # Wednesday 08:00 PKT — before market
        fake_now = datetime(2026, 9, 16, 8, 0, 0, tzinfo=market_schedule.PKT)
        with patch.object(market_schedule, "_now_pkt", return_value=fake_now):
            assert await market_schedule.is_market_hours() is False
            assert await market_schedule.is_ingestion_allowed() is False

    async def test_ingestion_interval_market(self):
        from app.services.news_pipeline import market_schedule
        from unittest.mock import patch
        fake_now = datetime(2026, 9, 16, 10, 0, 0, tzinfo=market_schedule.PKT)
        with patch.object(market_schedule, "_now_pkt", return_value=fake_now):
            assert await market_schedule.get_ingestion_interval() == 1800  # 30 min

    async def test_ingestion_interval_post_market(self):
        from app.services.news_pipeline import market_schedule
        from unittest.mock import patch
        fake_now = datetime(2026, 9, 16, 16, 0, 0, tzinfo=market_schedule.PKT)
        with patch.object(market_schedule, "_now_pkt", return_value=fake_now):
            assert await market_schedule.get_ingestion_interval() == 3600  # 60 min

    async def test_ingestion_interval_closed(self):
        from app.services.news_pipeline import market_schedule
        from unittest.mock import patch
        fake_now = datetime(2026, 9, 16, 18, 0, 0, tzinfo=market_schedule.PKT)
        with patch.object(market_schedule, "_now_pkt", return_value=fake_now):
            assert await market_schedule.get_ingestion_interval() == 0

    async def test_next_window_before_open(self):
        from app.services.news_pipeline import market_schedule
        from unittest.mock import patch
        # Wednesday 08:00 PKT — next window is today at 09:30
        fake_now = datetime(2026, 9, 16, 8, 0, 0, tzinfo=market_schedule.PKT)
        with patch.object(market_schedule, "_now_pkt", return_value=fake_now):
            nxt = await market_schedule.next_ingestion_window()
            assert nxt is not None
            assert nxt.hour == 9
            assert nxt.minute == 15

    async def test_next_window_after_post_market(self):
        from app.services.news_pipeline import market_schedule
        from unittest.mock import patch
        # Wednesday 18:00 PKT — next window is tomorrow at 09:30
        fake_now = datetime(2026, 9, 16, 18, 0, 0, tzinfo=market_schedule.PKT)
        with patch.object(market_schedule, "_now_pkt", return_value=fake_now):
            nxt = await market_schedule.next_ingestion_window()
            assert nxt is not None
            assert nxt.day == 17  # Thursday

    async def test_next_window_friday_after_post_market(self):
        from app.services.news_pipeline import market_schedule
        from unittest.mock import patch
        # Friday 18:00 PKT — next window is Monday
        fake_now = datetime(2026, 9, 18, 18, 0, 0, tzinfo=market_schedule.PKT)
        with patch.object(market_schedule, "_now_pkt", return_value=fake_now):
            nxt = await market_schedule.next_ingestion_window()
            assert nxt is not None
            assert nxt.weekday() == 0  # Monday

    async def test_market_status_structure(self):
        from app.services.news_pipeline.market_schedule import market_status
        status = await market_status()
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
