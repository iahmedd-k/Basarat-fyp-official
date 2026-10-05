"""Comprehensive unit tests for Community scale & re-architecture modules."""

import pytest
import time
from datetime import datetime, timedelta, timezone

from app.core.id_generator import generate_time_id, extract_timestamp_from_id
from app.services.cashtag_service import CashtagService
from app.services.feed_cache_service import FeedCacheService
from app.services.trending_service import TrendingService
from app.schemas.community import (
    CommunityPostCreate,
    CommunityPostResponse,
    CommunityPostDetailResponse,
    CommunityUnifiedProfileResponse,
    PostType,
    PostStatus,
)


class TestIdGenerator:
    def test_generate_time_id_format(self):
        id1 = generate_time_id()
        assert isinstance(id1, str)
        assert len(id1) == 32
        # Check version 7 nibble
        assert id1[12] == "7"

    def test_generate_time_id_monotonicity(self):
        ids = [generate_time_id() for _ in range(100)]
        sorted_ids = sorted(ids)
        assert ids == sorted_ids, "Generated time IDs must be monotonically increasing"

    def test_extract_timestamp(self):
        t0 = time.time()
        time_id = generate_time_id()
        extracted = extract_timestamp_from_id(time_id)
        assert extracted is not None
        assert abs(extracted - t0) < 1.0


class TestCashtagService:
    def test_extract_cashtags(self):
        content = "Looking at $OGDC, $PPL and #HBL today! Also $50 is not a ticker."
        tags = CashtagService.extract_cashtags(content)
        assert "OGDC" in tags
        assert "PPL" in tags
        assert "HBL" in tags
        assert "50" not in tags
        assert len(tags) <= 5

    def test_extract_cashtags_dedupe_and_case(self):
        content = "Bullish on $ogdc and $OGDC! Also $ogdc again."
        tags = CashtagService.extract_cashtags(content)
        assert tags == ["OGDC"]


class TestFeedCacheService:
    def test_l1_cache_get_set(self):
        FeedCacheService.set_l1("test:key:1", {"data": 123}, ttl_seconds=2.0)
        hit = FeedCacheService.get_l1("test:key:1")
        assert hit == {"data": 123}

    def test_l1_cache_invalidation(self):
        FeedCacheService.set_l1("test:key:2", {"data": 456}, ttl_seconds=2.0)
        FeedCacheService.invalidate_l1("test:key:2")
        assert FeedCacheService.get_l1("test:key:2") is None

    def test_jitter(self):
        base = 3600
        jittered = FeedCacheService._jitter(base)
        assert jittered >= base
        assert jittered <= base + int(base * 0.15) + 5


class TestTrendingService:
    def test_rank_score_decay(self):
        now = datetime.now(timezone.utc)
        recent_post_score = TrendingService.calculate_post_rank_score(
            like_count=50, comment_count=10, view_count=200, bookmark_count=5,
            created_at=now - timedelta(minutes=15)
        )
        old_post_score = TrendingService.calculate_post_rank_score(
            like_count=50, comment_count=10, view_count=200, bookmark_count=5,
            created_at=now - timedelta(days=3)
        )
        assert recent_post_score > old_post_score, "Recent posts must outrank older posts with identical engagement"

    def test_rank_score_engagement_weight(self):
        now = datetime.now(timezone.utc)
        high_eng = TrendingService.calculate_post_rank_score(
            like_count=100, comment_count=50, view_count=1000, bookmark_count=20,
            created_at=now - timedelta(hours=2)
        )
        low_eng = TrendingService.calculate_post_rank_score(
            like_count=1, comment_count=0, view_count=10, bookmark_count=0,
            created_at=now - timedelta(hours=2)
        )
        assert high_eng > low_eng


class TestCommunitySchemas:
    def test_post_response_cleaning(self):
        now = datetime.now(timezone.utc)
        resp = CommunityPostResponse(
            id="018d0000000070008000000000000001",
            author_id="user_123",
            author_username="trader_alpha",
            author_full_name="Alpha Trader",
            author_avatar_url="https://img.com/a.png",
            post_type=PostType.STOCK,
            stock_symbol="OGDC",
            stock_name="Oil & Gas Development Co",
            tickers=["OGDC", "PPL"],
            price_at_post=142.50,
            content="Breakout confirmed on high volume",
            like_count=15,
            comment_count=3,
            view_count=120,
            bookmark_count=5,
            liked_by_me=True,
            bookmarked_by_me=True,
            created_at=now,
            updated_at=now,
        )
        assert resp.liked_by_me is True
        assert resp.bookmarked_by_me is True
        assert resp.tickers == ["OGDC", "PPL"]
        assert resp.price_at_post == 142.50
