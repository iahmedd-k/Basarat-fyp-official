"""End-to-end tests — complete user journeys through the API."""

import hashlib
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import EmailVerificationToken, User
from app.services.auth_service import _hash_code


async def _signup_and_verify(client: AsyncClient, db_session: AsyncSession, email: str, password: str, full_name: str | None = None) -> dict:
    """Signup, verify with OTP, login, return tokens."""
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


@pytest.mark.e2e
class TestNewUserJourney:
    async def test_complete_onboarding_journey(self, client: AsyncClient, db_session: AsyncSession):
        tokens = await _signup_and_verify(client, db_session, "newinvestor@test.com", "Invest123!", "New Investor")
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        profile = await client.get("/api/v1/users/me", headers=headers)
        assert profile.status_code == 200

        search = await client.get("/api/v1/stocks/search?q=HBL", headers=headers)
        assert search.status_code == 200

        news = await client.get("/api/v1/news?limit=10", headers=headers)
        assert news.status_code == 200


@pytest.mark.e2e
class TestPortfolioManagementJourney:
    async def test_portfolio_lifecycle(self, client: AsyncClient, db_session: AsyncSession):
        tokens = await _signup_and_verify(client, db_session, "portfolio@test.com", "Port123!")
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        portfolio = await client.get("/api/v1/portfolio", headers=headers)
        assert portfolio.status_code == 200


@pytest.mark.e2e
class TestAlertManagementJourney:
    async def test_alert_lifecycle(self, client: AsyncClient, db_session: AsyncSession):
        tokens = await _signup_and_verify(client, db_session, "alertuser@test.com", "Alert123!")
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        rules = await client.get("/api/v1/alerts/rules", headers=headers)
        assert rules.status_code == 200


@pytest.mark.e2e
class TestResearchJourney:
    async def test_stock_research_flow(self, client: AsyncClient, db_session: AsyncSession):
        tokens = await _signup_and_verify(client, db_session, "researcher@test.com", "Research1!")
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        news = await client.get("/api/v1/news?limit=5", headers=headers)
        assert news.status_code == 200
