"""API tests for market endpoints."""

from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from app.main import app
from app.services.market_service import MarketService


@pytest.fixture
def mock_market_service():
    """Provide a mock MarketService with all async methods stubbed."""
    mock = AsyncMock(spec=MarketService)
    return mock


@pytest.fixture
def override_market(mock_market_service):
    """Temporarily override MarketService dependency for the test."""
    app.dependency_overrides[MarketService] = lambda: mock_market_service
    yield mock_market_service
    app.dependency_overrides.pop(MarketService, None)


@pytest.mark.api
class TestMarketIndices:
    async def test_get_indices(self, client: AsyncClient, auth_headers, override_market):
        override_market.get_indices.return_value = [
            {"index": "KSE-100", "code": "KSE100", "current": 42000.0, "change": 200.0, "change_pct": 0.48, "high": 42200.0, "low": 41800.0},
            {"index": "KSE-30", "code": "KSE30", "current": 15000.0, "change": 50.0, "change_pct": 0.33, "high": 15100.0, "low": 14900.0},
            {"index": "KMI-30", "code": "KMI30", "current": 8000.0, "change": -10.0, "change_pct": -0.12, "high": 8050.0, "low": 7950.0},
        ]
        resp = await client.get("/api/v1/market/indices", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "indices" in data
        assert len(data["indices"]) == 3
        assert data["indices"][0]["code"] == "KSE100"

    async def test_get_kse100_constituents(self, client: AsyncClient, auth_headers, override_market):
        override_market.get_index_constituents.return_value = [
            {"symbol": "HBL", "name": "Habib Bank", "ldcp": 150.0, "current": 154.0, "change": 4.0, "change_pct": 2.67, "weight_pct": 10.0, "index_points": 50.0, "volume": 1000000, "freefloat_m": 500.0, "market_cap_m": 5000.0},
            {"symbol": "UBL", "name": "United Bank", "ldcp": 120.0, "current": 122.0, "change": 2.0, "change_pct": 1.67, "weight_pct": 8.0, "index_points": 30.0, "volume": 800000, "freefloat_m": 400.0, "market_cap_m": 4000.0},
            {"symbol": "MCB", "name": "MCB Bank", "ldcp": 90.0, "current": 91.0, "change": 1.0, "change_pct": 1.11, "weight_pct": 6.0, "index_points": 20.0, "volume": 600000, "freefloat_m": 300.0, "market_cap_m": 3000.0},
        ]
        resp = await client.get("/api/v1/market/indices/kse-100", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["index"] == "KSE-100"
        assert data["code"] == "KSE100"
        assert len(data["constituents"]) == 3

    async def test_get_kse30_constituents(self, client: AsyncClient, auth_headers, override_market):
        override_market.get_index_constituents.return_value = [
            {"symbol": "HBL", "name": "Habib Bank", "ldcp": 150.0, "current": 154.0, "change": 4.0, "change_pct": 2.67, "weight_pct": 10.0, "index_points": 50.0, "volume": 1000000, "freefloat_m": 500.0, "market_cap_m": 5000.0},
        ]
        resp = await client.get("/api/v1/market/indices/kse-30", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["code"] == "KSE30"

    async def test_get_kmi30_constituents(self, client: AsyncClient, auth_headers, override_market):
        override_market.get_index_constituents.return_value = [
            {"symbol": "Meezan", "name": "Meezan Bank", "ldcp": 200.0, "current": 205.0, "change": 5.0, "change_pct": 2.5, "weight_pct": 15.0, "index_points": 40.0, "volume": 500000, "freefloat_m": 250.0, "market_cap_m": 2500.0},
        ]
        resp = await client.get("/api/v1/market/indices/kmi-30", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == "KMI30"
        assert data["shariah_compliant"] is True

    async def test_indices_are_public(self, client: AsyncClient):
        resp = await client.get("/api/v1/market/indices")
        assert resp.status_code == 200


@pytest.mark.api
class TestMarketGainersLosers:
    async def test_get_gainers(self, client: AsyncClient, auth_headers, override_market):
        override_market.get_top_gainers.return_value = [
            {"symbol": "HBL", "sector": "Banking", "ldcp": 150.0, "open": 152.0, "high": 155.0, "low": 149.0, "current": 154.0, "change": 4.0, "change_pct": 2.67, "volume": 1000000},
        ]
        resp = await client.get("/api/v1/market/gainers", headers=auth_headers)
        assert resp.status_code == 200
        assert "gainers" in resp.json()

    async def test_get_gainers_with_limit(self, client: AsyncClient, auth_headers, override_market):
        override_market.get_top_gainers.return_value = [
            {"symbol": "HBL", "sector": "Banking", "ldcp": 150.0, "open": 152.0, "high": 155.0, "low": 149.0, "current": 154.0, "change": 4.0, "change_pct": 2.67, "volume": 1000000},
            {"symbol": "UBL", "sector": "Banking", "ldcp": 120.0, "open": 121.0, "high": 123.0, "low": 119.0, "current": 122.0, "change": 2.0, "change_pct": 1.67, "volume": 800000},
        ]
        resp = await client.get("/api/v1/market/gainers?limit=2", headers=auth_headers)
        assert resp.status_code == 200

    async def test_get_losers(self, client: AsyncClient, auth_headers, override_market):
        override_market.get_top_losers.return_value = [
            {"symbol": "LUCK", "sector": "Cement", "ldcp": 620.0, "open": 618.0, "high": 622.0, "low": 610.0, "current": 612.0, "change": -8.0, "change_pct": -1.29, "volume": 500000},
        ]
        resp = await client.get("/api/v1/market/losers", headers=auth_headers)
        assert resp.status_code == 200
        assert "losers" in resp.json()

    async def test_get_volume_spikes(self, client: AsyncClient, auth_headers, override_market):
        override_market.get_volume_spikes.return_value = [
            {"symbol": "OGDC", "sector": "Oil & Gas", "ldcp": 90.0, "open": 91.0, "high": 93.0, "low": 89.0, "current": 92.0, "change": 2.0, "change_pct": 2.22, "volume": 2000000},
        ]
        resp = await client.get("/api/v1/market/volume-spikes", headers=auth_headers)
        assert resp.status_code == 200
        assert "volume_spikes" in resp.json()

    async def test_gainers_limit_validation(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/market/gainers?limit=0", headers=auth_headers)
        assert resp.status_code == 422

    async def test_gainers_limit_max(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/market/gainers?limit=101", headers=auth_headers)
        assert resp.status_code == 422

    async def test_quotes_reject_invalid_sort_by(self, client: AsyncClient):
        resp = await client.get("/api/v1/market/quotes?sort_by=bogus")
        assert resp.status_code == 422

    async def test_quotes_reject_invalid_order(self, client: AsyncClient):
        resp = await client.get("/api/v1/market/quotes?order=sideways")
        assert resp.status_code == 422
