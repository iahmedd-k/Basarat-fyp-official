"""API tests for user profile and investment profile preferences."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.models.user import User
from app.schemas.auth import InvestmentHorizon, RiskTolerance, SectorPreference
from app.services.email_service import EmailService


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

    async def test_profile_updates_name_and_phone_and_returns_username(
        self, client: AsyncClient, auth_headers, test_user: User
    ):
        response = await client.patch(
            "/api/v1/users/me",
            headers=auth_headers,
            json={"full_name": "  Ada   O'Neil ", "phone": "+1 (415) 555-0132"},
        )

        assert response.status_code == 200
        assert response.json()["full_name"] == "Ada O'Neil"
        assert response.json()["phone"] == "+14155550132"
        assert response.json()["username"] == test_user.username

    async def test_profile_rejects_invalid_name_and_phone(self, client: AsyncClient, auth_headers):
        invalid_name = await client.patch(
            "/api/v1/users/me",
            headers=auth_headers,
            json={"full_name": "Ada 123"},
        )
        invalid_phone = await client.patch(
            "/api/v1/users/me",
            headers=auth_headers,
            json={"phone": "not-a-phone"},
        )

        assert invalid_name.status_code == 422
        assert invalid_phone.status_code == 422

    async def test_email_change_only_updates_after_verification(
        self, client: AsyncClient, auth_headers, test_user: User, monkeypatch
    ):
        sent_codes: list[str] = []

        async def capture_code(recipient: str, code: str):
            assert recipient == "new-address@example.com"
            sent_codes.append(code)
            return {"status": "sent"}

        with patch.object(EmailService, "send_email_change_code", new_callable=AsyncMock, side_effect=capture_code):
            request_response = await client.post(
                "/api/v1/users/me/email-change",
                headers=auth_headers,
                json={"email": "new-address@example.com"},
            )
        assert request_response.status_code == 200
        assert sent_codes
        assert test_user.email != "new-address@example.com"

        verify_response = await client.post(
            "/api/v1/users/me/email-change/verify",
            headers=auth_headers,
            json={"code": sent_codes[0]},
        )
        assert verify_response.status_code == 200
        assert verify_response.json()["email"] == "new-address@example.com"
        assert verify_response.json()["username"] == test_user.username

    async def test_email_change_rejects_invalid_code(self, client: AsyncClient, auth_headers):
        response = await client.post(
            "/api/v1/users/me/email-change/verify",
            headers=auth_headers,
            json={"code": "000000"},
        )
        assert response.status_code == 400

    async def test_avatar_upload_updates_profile_url(
        self, client: AsyncClient, auth_headers, monkeypatch
    ):
        from app.api.v1.users import cloudinary_service

        upload_mock = AsyncMock(
            return_value=(
                "https://res.cloudinary.com/example/image/upload/profile-images/avatar.png",
                "profile-images/user/avatar",
            )
        )
        monkeypatch.setattr(cloudinary_service, "upload_image", upload_mock)
        response = await client.post(
            "/api/v1/users/me/avatar",
            headers=auth_headers,
            files={"image": ("avatar.png", b"png-content", "image/png")},
        )

        assert response.status_code == 200
        assert response.json()["avatar_url"].startswith("https://res.cloudinary.com/")
        upload_mock.assert_awaited_once()
        assert upload_mock.await_args.kwargs["folder"].startswith("profile-images/")

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
