"""API tests for Shariah screening endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shariah import ShariahScreening
from app.services.shariah_service import ShariahService


@pytest.fixture(autouse=True)
def source_backed_kmi_fixture(monkeypatch):
    """Make the external index source deterministic without static service fallbacks."""
    from app.services.market_service import MarketService

    rows = [{"symbol": symbol, "name": symbol, "current": 100 + i}
            for i, symbol in enumerate(["OGDC"] + [f"T{i:02d}" for i in range(29)])]

    async def get_index_constituents(self, index_code):
        return rows if index_code == "KMI30" else []

    monkeypatch.setattr(MarketService, "get_index_constituents", get_index_constituents)
    monkeypatch.setattr(
        MarketService,
        "constituents_freshness",
        classmethod(lambda cls, index_code: {"as_of": "2026-09-25T08:00:00+00:00", "is_stale": False}),
    )


@pytest.mark.api
class TestShariahScreening:
    async def test_screening_unknown_stock(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/shariah/UNKNOWNXYZ", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "UNKNOWNXYZ"
        assert data["screening_available"] is False
        assert data["is_shariah_compliant"] is None

    async def test_screening_kmi30_compliant(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/shariah/OGDC", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "OGDC"
        assert data["is_shariah_compliant"] is True
        assert data["screening_method"] is not None

    async def test_screening_non_compliant(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/shariah/HBL", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "HBL"
        assert data["is_shariah_compliant"] is False

    async def test_screening_is_public(self, client: AsyncClient):
        resp = await client.get("/api/v1/shariah/OGDC")
        assert resp.status_code == 200
        assert resp.json()["screening_available"] is True

    async def test_screening_rejects_invalid_symbol(self, client: AsyncClient):
        resp = await client.get("/api/v1/shariah/!!!")
        assert resp.status_code == 422

    async def test_screening_uppercases_symbol(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/shariah/ogdc", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["symbol"] == "OGDC"


@pytest.mark.api
class TestShariahCriteria:
    async def test_criteria_ogdc_pass(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/shariah/OGDC/criteria", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "OGDC"
        assert len(data["criteria"]) >= 2
        names = [c["name"] for c in data["criteria"]]
        assert "Debt to Total Assets Ratio" in names
        assert "Non-Permissible / Interest Income Ratio" in names

    async def test_criteria_hbl_fail(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/shariah/HBL/criteria", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "HBL"
        assert data["is_shariah_compliant"] is False
        debt_criterion = next(c for c in data["criteria"] if c["name"] == "Debt to Total Assets Ratio")
        assert debt_criterion["value"] is None
        assert debt_criterion["passed"] is None

    async def test_criteria_is_public(self, client: AsyncClient):
        resp = await client.get("/api/v1/shariah/OGDC/criteria")
        assert resp.status_code == 200

    async def test_criteria_for_unknown_symbol_is_unavailable(self, client: AsyncClient):
        resp = await client.get("/api/v1/shariah/ZZZ999/criteria")
        assert resp.status_code == 200
        data = resp.json()
        assert data["screening_available"] is False
        assert data["is_shariah_compliant"] is None
        assert all(item["value"] is None and item["passed"] is None for item in data["criteria"])


@pytest.mark.api
class TestShariahPurification:
    def test_calculation_applies_verified_rate_to_dividend_income(self):
        service = ShariahService(None)
        amount, rate = service.calculate_purification(
            dividend_income=15000.0, symbol="OGDC", rate=0.012
        )
        assert rate == 0.012
        assert amount == 180.0

    async def test_purification_requires_verified_rate_when_psx_does_not_publish_one(self, client: AsyncClient, auth_headers):
        resp = await client.get(
            "/api/v1/shariah/MEBL/purification?dividend_income=15000.0",
            headers=auth_headers,
        )
        assert resp.status_code == 422
        assert "verified purification rate" in resp.json()["error"]["message"].lower()

    async def test_purification_is_public_and_uses_dated_psx_rate(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/shariah/OGDC/purification?dividend_income=15000.0",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["purification_rate"] == 0.0662
        assert data["purification_amount"] == 993.0
        assert data["data_as_of"].startswith("2025-12-31")
        assert data["data_is_stale"] is True
        assert data["source_url"].startswith("https://dps.psx.com.pk/")
        assert data["rate_is_provisional"] is True

    async def test_purification_requires_dividend_income(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/shariah/OGDC/purification?holding_value=15000.0",
        )
        assert resp.status_code == 422

    async def test_purification_unknown_symbol_has_no_default_rate(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/shariah/ZZZ999/purification?dividend_income=15000.0",
        )
        assert resp.status_code == 404

    async def test_purification_rejects_non_compliant_symbol(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/shariah/HBL/purification?dividend_income=15000.0",
        )
        assert resp.status_code == 422

    async def test_purification_invalid_qty(self, client: AsyncClient, auth_headers):
        resp = await client.get(
            "/api/v1/shariah/OGDC/purification?dividend_income=-1",
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_purification_invalid_value(self, client: AsyncClient, auth_headers):
        resp = await client.get(
            "/api/v1/shariah/OGDC/purification?dividend_income=0",
            headers=auth_headers,
        )
        assert resp.status_code == 422


@pytest.mark.api
class TestShariahKMI30:
    async def test_kmi30(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/shariah/kmi30", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["index"] == "KMI-30"
        assert len(data["constituents"]) > 0
        first = data["constituents"][0]
        assert "symbol" in first

    async def test_kmi30_is_public(self, client: AsyncClient):
        resp = await client.get("/api/v1/shariah/kmi30")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_constituents"] == 30
        assert data["as_of"].startswith("2025-12-31")
        assert data["effective_from"].startswith("2026-05-25")

    async def test_kmi30_source_snapshot_has_expected_rows_and_ratios(self, client: AsyncClient):
        resp = await client.get("/api/v1/shariah/kmi30")
        rows = {row["symbol"]: row for row in resp.json()["constituents"]}
        assert len(rows) == 30
        assert rows["OGDC"]["interest_income_ratio"] == 0.0662
        assert rows["OGDC"]["purification_rate_provisional"] is True
        assert rows["MEBL"]["interest_income_ratio"] is None
        assert rows["MEBL"]["purification_rate_provisional"] is False
        assert rows["FFC"]["purification_rate_provisional"] is False
        assert rows["SYS"]["purification_rate_provisional"] is False
