import pytest
from httpx import AsyncClient


@pytest.mark.api
class TestETFEndpoints:
    async def test_list_etfs(self, client: AsyncClient):
        resp = await client.get("/api/v1/etfs")
        assert resp.status_code == 200
        data = resp.json()
        assert "etfs" in data
        assert data["total"] >= 1
        assert "shariah_count" in data
        assert "conventional_count" in data

    async def test_filter_shariah_etfs(self, client: AsyncClient):
        resp = await client.get("/api/v1/etfs?is_shariah_compliant=true")
        assert resp.status_code == 200
        data = resp.json()
        assert all(e["is_shariah_compliant"] is True for e in data["etfs"])

    async def test_get_etf_detail(self, client: AsyncClient):
        resp = await client.get("/api/v1/etfs/MIIETF")
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "MIIETF"
        assert "quote" in data
        assert data["quote"]["current_price"] > 0

    async def test_get_etf_history(self, client: AsyncClient):
        resp = await client.get("/api/v1/etfs/MIIETF/history?timeframe=1M")
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "MIIETF"
        assert data["count"] > 0
        assert len(data["history"]) > 0

    async def test_get_etf_performance(self, client: AsyncClient):
        resp = await client.get("/api/v1/etfs/MIIETF/performance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "MIIETF"
        assert "1M" in data["returns"]
        assert "benchmark_returns" in data


@pytest.mark.api
class TestIPOEndpoints:
    async def test_list_ipos(self, client: AsyncClient):
        resp = await client.get("/api/v1/ipos")
        assert resp.status_code == 200
        data = resp.json()
        assert "ipos" in data
        assert data["total"] >= 1
        assert "upcoming_count" in data
        assert "active_count" in data
        assert "listed_count" in data

    async def test_filter_listed_ipos(self, client: AsyncClient):
        resp = await client.get("/api/v1/ipos?status=LISTED")
        assert resp.status_code == 200
        data = resp.json()
        assert all(i["status"] == "LISTED" for i in data["ipos"])

    async def test_get_ipo_detail(self, client: AsyncClient):
        resp = await client.get("/api/v1/ipos/IPACO")
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "IPACO"
        assert data["status"] == "LISTED"

    async def test_get_ipo_calendar(self, client: AsyncClient):
        resp = await client.get("/api/v1/ipos/calendar")
        assert resp.status_code == 200
        data = resp.json()
        assert "upcoming_milestones" in data

    async def test_get_ipo_performance(self, client: AsyncClient):
        resp = await client.get("/api/v1/ipos/performance")
        assert resp.status_code == 200
        data = resp.json()
        assert "average_listing_day_gain_pct" in data
        assert len(data["recent_listings"]) > 0
