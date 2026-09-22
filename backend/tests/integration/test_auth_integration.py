"""Integration tests — full auth flow with real DB session."""

import hashlib
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import EmailVerificationToken, User
from app.services.auth_service import _hash_code


async def _verify_user_in_db(db: AsyncSession, user_id: str) -> None:
    """Helper: mark a user as verified directly in DB."""
    user = await db.get(User, user_id)
    user.is_verified = True
    await db.flush()


async def _signup_and_verify(client: AsyncClient, db_session: AsyncSession, email: str, password: str, full_name: str | None = None) -> dict:
    """Signup, insert OTP in DB, verify via API, return tokens."""
    resp = await client.post("/api/v1/auth/signup", json={
        "email": email, "password": password, "full_name": full_name,
    })
    assert resp.status_code == 201

    result = await db_session.execute(select(User).where(User.email == email))
    user = result.scalars().first()
    assert user is not None

    code = "123456"
    verification_token = EmailVerificationToken(
        token_hash=_hash_code(code),
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    db_session.add(verification_token)
    await db_session.flush()

    verify_resp = await client.post("/api/v1/auth/verify-email", json={
        "email": email, "code": code,
    })
    assert verify_resp.status_code == 200
    return verify_resp.json()


@pytest.mark.integration
class TestAuthFlowIntegration:
    async def test_signup_login_refresh_cycle(self, client: AsyncClient, db_session: AsyncSession):
        tokens = await _signup_and_verify(client, db_session, "flow@test.com", "SecurePass1!", "Flow Test")
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        login_resp = await client.post("/api/v1/auth/login", json={
            "email": "flow@test.com", "password": "SecurePass1!",
        })
        assert login_resp.status_code == 200

        refresh_resp = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": tokens["refresh_token"],
        })
        assert refresh_resp.status_code == 200

        profile_resp = await client.get(
            "/api/v1/users/me",
            headers=headers,
        )
        assert profile_resp.status_code == 200
        assert profile_resp.json()["email"] == "flow@test.com"

    async def test_change_password_flow(self, client: AsyncClient, db_session: AsyncSession):
        tokens = await _signup_and_verify(client, db_session, "changepw@test.com", "OldPass123!")
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        change_resp = await client.post(
            "/api/v1/auth/change-password",
            headers=headers,
            json={"current_password": "OldPass123!", "new_password": "NewPass456!"},
        )
        assert change_resp.status_code == 204

        login_resp = await client.post("/api/v1/auth/login", json={
            "email": "changepw@test.com", "password": "NewPass456!",
        })
        assert login_resp.status_code == 200

    async def test_inactive_user_cannot_login(self, client: AsyncClient, inactive_user):
        resp = await client.post("/api/v1/auth/login", json={
            "email": inactive_user.email, "password": "TestPass123!",
        })
        assert resp.status_code == 401


@pytest.mark.integration
class TestUserIntegration:
    async def test_get_and_update_profile(self, client: AsyncClient, auth_headers):
        get_resp = await client.get("/api/v1/users/me", headers=auth_headers)
        assert get_resp.status_code == 200

        update_resp = await client.patch(
            "/api/v1/users/me", headers=auth_headers,
            json={"full_name": "Updated Name"},
        )
        assert update_resp.status_code == 200

    async def test_update_risk_profile(self, client: AsyncClient, auth_headers):
        resp = await client.patch(
            "/api/v1/users/me/risk-profile", headers=auth_headers,
            json={"risk_tolerance": "aggressive"},
        )
        assert resp.status_code == 200

    async def test_update_notification_preferences(self, client: AsyncClient, auth_headers):
        resp = await client.patch(
            "/api/v1/users/me/notification-preferences", headers=auth_headers,
            json={"channels": ["push", "email"], "categories": ["portfolio", "alerts"]},
        )
        assert resp.status_code == 200
