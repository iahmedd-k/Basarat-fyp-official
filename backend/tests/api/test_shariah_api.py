"""API tests for Shariah screening endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shariah import ShariahScreening


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
    async def test_purification(self, client: AsyncClient, auth_headers):
        resp = await client.get(
            "/api/v1/shariah/OGDC/purification?holding_qty=100&holding_value=15000.0",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "OGDC"
        assert data["holding_qty"] == 100
        assert data["holding_value"] == 15000.0
        assert data["purification_amount"] > 0
        assert data["purification_rate"] > 0
        assert "notes" in data

    async def test_purification_is_public(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/shariah/OGDC/purification?holding_qty=100&holding_value=15000.0",
        )
        assert resp.status_code == 200

    async def test_purification_unknown_symbol_has_no_default_rate(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/shariah/ZZZ999/purification?holding_qty=100&holding_value=15000.0",
        )
        assert resp.status_code == 404

    async def test_purification_invalid_qty(self, client: AsyncClient, auth_headers):
        resp = await client.get(
            "/api/v1/shariah/OGDC/purification?holding_qty=0&holding_value=15000.0",
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_purification_invalid_value(self, client: AsyncClient, auth_headers):
        resp = await client.get(
            "/api/v1/shariah/OGDC/purification?holding_qty=100&holding_value=-100",
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
