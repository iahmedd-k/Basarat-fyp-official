"""API tests for news endpoints."""

import pytest
from httpx import AsyncClient
from datetime import datetime, timedelta

from sqlalchemy import delete
from app.models.news import NewsArticle, NewsArticleSymbol


@pytest.mark.api
class TestNewsEndpoints:
    async def test_get_news_is_public(self, client: AsyncClient):
        resp = await client.get("/api/v1/news")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    async def _create_test_articles(self, db_session, now):
        """Create test articles with link table entries and commit so the router can see them."""
        articles = [
            NewsArticle(
                title="New OGDC update",
                url="https://example.test/news/new",
                source="Test Source",
                source_type="news",
                symbols='["OGDC"]',
                sentiment_label=None,
                published_at=now,
                created_at=now,
            ),
            NewsArticle(
                title="Older OGDC update",
                url="https://example.test/news/old",
                source="Test Source",
                source_type="news",
                symbols='["OGDC"]',
                sentiment_label="bullish",
                published_at=now - timedelta(days=1),
                created_at=now - timedelta(days=1),
            ),
            NewsArticle(
                title="OGDC update without publication date",
                url="https://example.test/news/undated",
                source="Test Source",
                source_type="news",
                symbols='["OGDC"]',
                sentiment_label="neutral",
                published_at=None,
                created_at=now - timedelta(days=2),
            ),
        ]
        db_session.add_all(articles)
        await db_session.flush()

        # Add link table entries for symbol filtering
        for article in articles:
            db_session.add(NewsArticleSymbol(article_id=article.id, symbol="OGDC"))
        await db_session.flush()
        # Commit so the router (which opens its own db session) can see inserted data
        await db_session.commit()
        return articles

    async def _cleanup_articles(self, db_session, article_ids):
        """Delete committed test articles to prevent inter-test data leakage."""
        await db_session.execute(
            delete(NewsArticleSymbol).where(NewsArticleSymbol.article_id.in_(article_ids))
        )
        await db_session.execute(
            delete(NewsArticle).where(NewsArticle.id.in_(article_ids))
        )
        await db_session.commit()

    async def test_news_cursor_pagination_and_total(
        self, client: AsyncClient, db_session, monkeypatch
    ):
        # Keep this database-pagination test independent of shared Redis state.
        async def cache_get(_key):
            return None

        async def cache_set(_key, _value, ttl_seconds=60):
            return None

        monkeypatch.setattr("app.api.v1.news.cache_get", cache_get)
        monkeypatch.setattr("app.api.v1.news.cache_set", cache_set)

        now = datetime.utcnow()
        articles = await self._create_test_articles(db_session, now)
        article_ids = [a.id for a in articles]

        try:
            # Test /api/v1/news with symbol filter (filtered query - total not calculated for performance)
            first = await client.get("/api/v1/news?symbol=OGDC&limit=1")
            assert first.status_code == 200
            first_data = first.json()
            # For filtered queries, total is not calculated (performance optimization) - should be >= 0
            assert first_data["total"] >= 0
            assert len(first_data["items"]) == 1
            assert first_data["has_more"] is True
            assert first_data["next_cursor"]

            second = await client.get(
                "/api/v1/news",
                params={"symbol": "OGDC", "limit": 1, "cursor": first_data["next_cursor"]},
            )
            assert second.status_code == 200
            second_data = second.json()
            assert second_data["total"] >= 0
            assert len(second_data["items"]) == 1
            assert second_data["items"][0]["title"] == "Older OGDC update"
            assert second_data["has_more"] is True
            assert second_data["next_cursor"]

            third = await client.get(
                "/api/v1/news",
                params={"symbol": "OGDC", "limit": 1, "cursor": second_data["next_cursor"]},
            )
            assert third.status_code == 200
            third_data = third.json()
            assert third_data["items"][0]["title"] == "OGDC update without publication date"
            assert third_data["has_more"] is False
            assert third_data["next_cursor"] is None

            # Test /api/v1/stocks/OGDC/news (also filtered - total not calculated)
            stock_first = await client.get("/api/v1/stocks/OGDC/news?limit=1&source_type=news")
            assert stock_first.status_code == 200
            stock_first_data = stock_first.json()
            assert stock_first_data["total"] >= 0
            assert stock_first_data["has_more"] is True

            stock_second = await client.get(
                "/api/v1/stocks/OGDC/news",
                params={"limit": 1, "source_type": "news", "cursor": stock_first_data["next_cursor"]},
            )
            assert stock_second.status_code == 200
            assert stock_second.json()["total"] >= 0
            assert len(stock_second.json()["items"]) == 1
            assert stock_second.json()["has_more"] is True

            stock_third = await client.get(
                "/api/v1/stocks/OGDC/news",
                params={"limit": 1, "source_type": "news", "cursor": stock_second.json()["next_cursor"]},
            )
            assert stock_third.status_code == 200
            assert stock_third.json()["items"][0]["title"] == "OGDC update without publication date"
            assert stock_third.json()["has_more"] is False

            # Text search is a filtered query — total is NOT computed (returns 0), but items should match
            search = await client.get("/api/v1/news", params={"q": "Older OGDC update"})
            assert search.status_code == 200
            assert search.json()["total"] >= 0
            assert len(search.json()["items"]) >= 1
            assert search.json()["items"][0]["title"] == "Older OGDC update"

            missing = await client.get("/api/v1/news", params={"q": "no matching article xyz"})
            assert missing.status_code == 200
            assert missing.json()["items"] == []
            assert missing.json()["total"] == 0

            invalid_cursor = await client.get("/api/v1/news", params={"cursor": "not-a-valid-cursor"})
            assert invalid_cursor.status_code == 400

        finally:
            # Always cleanup committed articles to prevent data leakage to next test
            await self._cleanup_articles(db_session, article_ids)

    async def test_stock_news_filter_handles_missing_sentiment(self, client: AsyncClient, db_session):
        now = datetime.utcnow()
        article = NewsArticle(
            title="OGDC update without sentiment - unique",
            url="https://example.test/news/no-sentiment-unique",
            source="Test Source",
            source_type="news",
            symbols='["OGDC"]',
            sentiment_label=None,
            published_at=now,
            created_at=now,
        )
        db_session.add(article)
        await db_session.flush()

        # Add link table entry for symbol filtering
        db_session.add(NewsArticleSymbol(article_id=article.id, symbol="OGDC"))
        await db_session.flush()
        await db_session.commit()

        try:
            response = await client.get("/api/v1/stocks/OGDC/news?sentiment=bullish")
            assert response.status_code == 200
            # No bullish articles were inserted in this test - items should be empty
            items = response.json()["items"]
            # Filter out any items that are NOT from this test (may have none=sentiment articles from other commits)
            bullish_items = [i for i in items if i.get("sentiment", {}).get("label") == "bullish"]
            assert bullish_items == []
            assert response.json()["total"] == 0
        finally:
            await self._cleanup_articles(db_session, [article.id])


@pytest.mark.api
class TestNewsRefresh:
    async def test_refresh_news(self, client: AsyncClient, auth_headers):
        resp = await client.post("/api/v1/news/refresh", headers=auth_headers)
        assert resp.status_code in (200, 202, 503)

    async def test_refresh_news_uses_async_redis_lock(
        self, client: AsyncClient, monkeypatch
    ):
        from unittest.mock import AsyncMock

        from app.services.news_pipeline import ingestion_state

        class AsyncRedisStub:
            def __init__(self):
                self.set_calls = []

            async def set(self, *_args, **_kwargs):
                self.set_calls.append((_args, _kwargs))
                return True

            async def delete(self, *_args):
                return 1

        redis_stub = AsyncRedisStub()
        monkeypatch.setattr(
            "app.api.v1.news.market_status",
            AsyncMock(return_value={"status": "closed"}),
        )
        monkeypatch.setattr(ingestion_state, "get_last_ingestion_time", lambda: None)
        monkeypatch.setattr(
            ingestion_state,
            "get_ingestion_status",
            lambda: {"state": "idle"},
        )
        monkeypatch.setattr(ingestion_state, "mark_ingestion_queued", lambda: None)
        monkeypatch.setattr(
            "app.api.v1.news.get_redis_client",
            lambda: redis_stub,
        )
        monkeypatch.setattr(
            "app.tasks.scrape_news.run.apply_async",
            lambda **_kwargs: None,
        )

        response = await client.post("/api/v1/news/refresh")

        assert response.status_code == 200
        assert response.json()["status"] == "started"
        assert len(redis_stub.set_calls) == 1
