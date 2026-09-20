"""API tests for news endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.api
class TestNewsEndpoints:
    async def test_get_news(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/news", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    async def test_get_news_with_pagination(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/news?page=1&limit=5", headers=auth_headers)
        assert resp.status_code == 200

    async def test_get_news_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/news")
        assert resp.status_code in (401, 403)


@pytest.mark.api
class TestNewsRefresh:
    async def test_refresh_news(self, client: AsyncClient, auth_headers):
        resp = await client.post("/api/v1/news/refresh", headers=auth_headers)
        assert resp.status_code in (200, 202, 503)
