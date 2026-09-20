"""API tests for user profile and investment profile preferences."""

import pytest
from httpx import AsyncClient

from app.schemas.auth import InvestmentHorizon, RiskTolerance, SectorPreference


@pytest.mark.api
class TestUsersInvestmentProfile:
    async def test_get_investment_profile_options(self, client: AsyncClient):
        resp = await client.get("/api/v1/users/investment-profile/options")
        assert resp.status_code == 200
        data = resp.json()
        assert "risk_tolerances" in data
        assert "investment_horizons" in data
        assert "sectors" in data
        assert data["risk_tolerances"] == ["conservative", "moderate", "aggressive"]
        assert data["investment_horizons"] == ["short_term", "medium_term", "long_term"]
        assert "Commercial Banks" in data["sectors"]
        assert "All Sectors" in data["sectors"]

    async def test_get_risk_profile_sectors_alias(self, client: AsyncClient):
        resp = await client.get("/api/v1/users/risk-profile/sectors")
        assert resp.status_code == 200
        data = resp.json()
        assert "sectors" in data

    async def test_unified_profile_post_and_get(self, client: AsyncClient, auth_headers):
        payload = {
            "full_name": "Investment Trader",
            "risk_tolerance": RiskTolerance.AGGRESSIVE.value,
            "investment_horizon": InvestmentHorizon.LONG_TERM.value,
            "sector_preferences": [SectorPreference.TECHNOLOGY.value, SectorPreference.COMMERCIAL_BANKS.value],
        }
        resp = await client.post("/api/v1/users/me", headers=auth_headers, json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["full_name"] == "Investment Trader"
        assert data["risk_tolerance"] == "aggressive"
        assert data["investment_horizon"] == "long_term"
        assert data["sector_preferences"] == ["Technology", "Commercial Banks"]

        # Check that GET /users/me and GET /users/me/investment-profile return the same
        me_resp = await client.get("/api/v1/users/me", headers=auth_headers)
        assert me_resp.status_code == 200
        me_data = me_resp.json()
        assert me_data["full_name"] == "Investment Trader"
        assert me_data["risk_tolerance"] == "aggressive"

        inv_resp = await client.get("/api/v1/users/me/investment-profile", headers=auth_headers)
        assert inv_resp.status_code == 200
        assert inv_resp.json()["full_name"] == "Investment Trader"

    async def test_update_investment_profile_patch_success(self, client: AsyncClient, auth_headers):
        payload = {
            "risk_tolerance": RiskTolerance.CONSERVATIVE.value,
            "investment_horizon": InvestmentHorizon.SHORT_TERM.value,
            "sector_preferences": [SectorPreference.ALL_SECTORS.value],
        }
        resp = await client.patch("/api/v1/users/me/investment-profile", headers=auth_headers, json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["risk_tolerance"] == "conservative"
        assert data["investment_horizon"] == "short_term"
        assert data["sector_preferences"] == ["All Sectors"]

    async def test_update_risk_profile_invalid_tolerance(self, client: AsyncClient, auth_headers):
        payload = {
            "risk_tolerance": "super_high_risk",
        }
        resp = await client.patch("/api/v1/users/me", headers=auth_headers, json=payload)
        assert resp.status_code == 422

    async def test_update_risk_profile_invalid_horizon(self, client: AsyncClient, auth_headers):
        payload = {
            "investment_horizon": "infinity",
        }
        resp = await client.patch("/api/v1/users/me", headers=auth_headers, json=payload)
        assert resp.status_code == 422

    async def test_update_risk_profile_invalid_sector(self, client: AsyncClient, auth_headers):
        payload = {
            "sector_preferences": ["NonExistentSector123"],
        }
        resp = await client.patch("/api/v1/users/me", headers=auth_headers, json=payload)
        assert resp.status_code == 422

    async def test_update_risk_profile_all_sectors_conflict(self, client: AsyncClient, auth_headers):
        payload = {
            "sector_preferences": ["All Sectors", "Technology"],
        }
        resp = await client.patch("/api/v1/users/me", headers=auth_headers, json=payload)
        assert resp.status_code == 422
