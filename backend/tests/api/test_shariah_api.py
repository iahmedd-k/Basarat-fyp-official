"""API tests for Shariah screening endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shariah import ShariahScreening


@pytest.mark.api
class TestShariahScreening:
    async def test_screening_not_found(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/shariah/NONEXISTENT", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "NONEXISTENT"
        assert data["is_shariah_compliant"] is False
        assert data["overall_score"] is None

    async def test_screening_found(self, client: AsyncClient, auth_headers, db_session: AsyncSession):
        screening = ShariahScreening(
            stock_id="stock-hbl",
            is_shariah_compliant=True,
            debt_ratio=0.25,
            interest_income_ratio=0.03,
            screening_method="AAOIFI",
        )
        db_session.add(screening)
        await db_session.flush()

        resp = await client.get("/api/v1/shariah/HBL", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "HBL"
        assert data["is_shariah_compliant"] is True
        assert data["screening_method"] == "AAOIFI"
        assert data["screened_at"] is not None

    async def test_screening_not_compliant(self, client: AsyncClient, auth_headers, db_session: AsyncSession):
        screening = ShariahScreening(
            stock_id="stock-hbl",
            is_shariah_compliant=False,
            debt_ratio=0.45,
            interest_income_ratio=0.08,
            screening_method="AAOIFI",
        )
        db_session.add(screening)
        await db_session.flush()

        resp = await client.get("/api/v1/shariah/HBL", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_shariah_compliant"] is False

    async def test_screening_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/shariah/HBL")
        assert resp.status_code in (401, 403)

    async def test_screening_uppercases_symbol(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/shariah/hbl", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["symbol"] == "HBL"


@pytest.mark.api
class TestShariahCriteria:
    async def test_criteria_not_found(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/shariah/NONEXISTENT/criteria", headers=auth_headers)
        assert resp.status_code == 404

    async def test_criteria_pass(self, client: AsyncClient, auth_headers, db_session: AsyncSession):
        screening = ShariahScreening(
            stock_id="stock-hbl",
            is_shariah_compliant=True,
            debt_ratio=0.25,
            interest_income_ratio=0.03,
        )
        db_session.add(screening)
        await db_session.flush()

        resp = await client.get("/api/v1/shariah/HBL/criteria", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "HBL"
        assert len(data["criteria"]) == 2

        debt = data["criteria"][0]
        assert debt["name"] == "Debt Ratio"
        assert debt["threshold"] == 0.33
        assert debt["value"] == 0.25
        assert debt["passed"] is True

        interest = data["criteria"][1]
        assert interest["name"] == "Interest Income Ratio"
        assert interest["threshold"] == 0.05
        assert interest["value"] == 0.03
        assert interest["passed"] is True

    async def test_criteria_fail(self, client: AsyncClient, auth_headers, db_session: AsyncSession):
        screening = ShariahScreening(
            stock_id="stock-hbl",
            is_shariah_compliant=False,
            debt_ratio=0.45,
            interest_income_ratio=0.08,
        )
        db_session.add(screening)
        await db_session.flush()

        resp = await client.get("/api/v1/shariah/HBL/criteria", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["criteria"][0]["passed"] is False
        assert data["criteria"][1]["passed"] is False

    async def test_criteria_no_screening(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/shariah/HBL/criteria", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["criteria"][0]["value"] is None
        assert data["criteria"][0]["passed"] is False

    async def test_criteria_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/shariah/HBL/criteria")
        assert resp.status_code in (401, 403)


@pytest.mark.api
class TestShariahPurification:
    async def test_purification(self, client: AsyncClient, auth_headers):
        resp = await client.get(
            "/api/v1/shariah/HBL/purification?holding_qty=100&holding_value=15000.0",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "HBL"
        assert data["holding_qty"] == 100
        assert data["holding_value"] == 15000.0
        assert data["purification_amount"] == 375.0
        assert data["purification_rate"] == 0.025

    async def test_purification_requires_auth(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/shariah/HBL/purification?holding_qty=100&holding_value=15000.0",
        )
        assert resp.status_code in (401, 403)

    async def test_purification_invalid_qty(self, client: AsyncClient, auth_headers):
        resp = await client.get(
            "/api/v1/shariah/HBL/purification?holding_qty=0&holding_value=15000.0",
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_purification_invalid_value(self, client: AsyncClient, auth_headers):
        resp = await client.get(
            "/api/v1/shariah/HBL/purification?holding_qty=100&holding_value=-100",
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
        assert data["constituents"] == []

    async def test_kmi30_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/shariah/kmi30")
        assert resp.status_code in (401, 403)
