"""API tests for news endpoints."""

import pytest
from httpx import AsyncClient
from datetime import datetime, timedelta, timezone

from app.models.news import NewsArticle


@pytest.mark.api
class TestNewsEndpoints:
    async def test_get_news_is_public(self, client: AsyncClient):
        resp = await client.get("/api/v1/news")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    async def test_news_cursor_pagination_and_total(self, client: AsyncClient, db_session):
        now = datetime.now(timezone.utc)
        db_session.add_all([
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
        ])
        await db_session.flush()

        first = await client.get("/api/v1/news?symbol=OGDC&limit=1")
        assert first.status_code == 200
        first_data = first.json()
        assert first_data["total"] == 2
        assert len(first_data["items"]) == 1
        assert first_data["has_more"] is True
        assert first_data["next_cursor"]

        second = await client.get(
            "/api/v1/news",
            params={"symbol": "OGDC", "limit": 1, "cursor": first_data["next_cursor"]},
        )
        assert second.status_code == 200
        second_data = second.json()
        assert second_data["total"] == 2
        assert len(second_data["items"]) == 1
        assert second_data["items"][0]["title"] == "Older OGDC update"
        assert second_data["has_more"] is False
        assert second_data["next_cursor"] is None

        stock_first = await client.get("/api/v1/stocks/OGDC/news?limit=1&source_type=news")
        assert stock_first.status_code == 200
        stock_first_data = stock_first.json()
        assert stock_first_data["total"] == 2
        assert stock_first_data["has_more"] is True

        stock_second = await client.get(
            "/api/v1/stocks/OGDC/news",
            params={"limit": 1, "source_type": "news", "cursor": stock_first_data["next_cursor"]},
        )
        assert stock_second.status_code == 200
        assert stock_second.json()["total"] == 2
        assert len(stock_second.json()["items"]) == 1
        assert stock_second.json()["has_more"] is False

        search = await client.get("/api/v1/news", params={"q": "Older OGDC update"})
        assert search.status_code == 200
        assert search.json()["total"] == 1
        assert search.json()["items"][0]["title"] == "Older OGDC update"

        missing = await client.get("/api/v1/news", params={"q": "no matching article"})
        assert missing.status_code == 200
        assert missing.json()["items"] == []
        assert missing.json()["total"] == 0

        invalid_cursor = await client.get("/api/v1/news", params={"cursor": "not-a-valid-cursor"})
        assert invalid_cursor.status_code == 400

    async def test_stock_news_filter_handles_missing_sentiment(self, client: AsyncClient, db_session):
        now = datetime.now(timezone.utc)
        db_session.add(NewsArticle(
            title="OGDC update without sentiment",
            url="https://example.test/news/no-sentiment",
            source="Test Source",
            source_type="news",
            symbols='["OGDC"]',
            sentiment_label=None,
            published_at=now,
            created_at=now,
        ))
        await db_session.flush()

        response = await client.get("/api/v1/stocks/OGDC/news?sentiment=bullish")
        assert response.status_code == 200
        assert response.json()["items"] == []
        assert response.json()["total"] == 0


@pytest.mark.api
class TestNewsRefresh:
    async def test_refresh_news(self, client: AsyncClient, auth_headers):
        resp = await client.post("/api/v1/news/refresh", headers=auth_headers)
        assert resp.status_code in (200, 202, 503)
