"""API tests for system and health endpoints."""

import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock


@pytest.mark.api
class TestSystemEndpoints:
    async def test_ready_healthy(self, client: AsyncClient):
        with patch("app.services.health_service.HealthService.check_health", new_callable=AsyncMock) as mock_health:
            mock_health.return_value = {"status": "healthy", "components": {}}
            resp = await client.get("/api/v1/ready")
            assert resp.status_code == 200

    async def test_ready_unhealthy(self, client: AsyncClient):
        with patch("app.services.health_service.HealthService.check_health", new_callable=AsyncMock) as mock_health:
            mock_health.return_value = {"status": "unhealthy", "components": {"database": "disconnected"}}
            resp = await client.get("/api/v1/ready")
            assert resp.status_code == 503

    async def test_root(self, client: AsyncClient):
        resp = await client.get("/api/v1/")
        assert resp.status_code == 200
        data = resp.json()
        assert "message" in data

    async def test_root_top_level(self, client: AsyncClient):
        resp = await client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert "message" in data


@pytest.mark.api
class TestHealthEndpoint:
    async def test_health_liveness(self, client: AsyncClient):
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    async def test_health_ready_healthy(self, client: AsyncClient):
        with patch("app.services.health_service.HealthService.check_health", new_callable=AsyncMock) as mock_health:
            mock_health.return_value = {"status": "healthy", "components": {}}
            resp = await client.get("/api/v1/health/ready")
            assert resp.status_code == 200

    async def test_health_ready_unhealthy(self, client: AsyncClient):
        with patch("app.services.health_service.HealthService.check_health", new_callable=AsyncMock) as mock_health:
            mock_health.return_value = {"status": "unhealthy", "components": {"database": "disconnected"}}
            resp = await client.get("/api/v1/health/ready")
            assert resp.status_code == 503
