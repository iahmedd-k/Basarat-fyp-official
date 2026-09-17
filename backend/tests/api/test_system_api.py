"""API tests for system and health endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.api
class TestSystemEndpoints:
    async def test_ready(self, client: AsyncClient):
        resp = await client.get("/api/v1/ready")
        assert resp.status_code == 200

    async def test_root(self, client: AsyncClient):
        resp = await client.get("/api/v1/")
        assert resp.status_code == 200


@pytest.mark.api
class TestHealthEndpoint:
    async def test_health(self, client: AsyncClient):
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
