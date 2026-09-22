"""API tests for auth endpoints."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import EmailVerificationToken, PasswordResetToken, User
from app.services.auth_service import _hash_code


@pytest.mark.api
class TestAuthSignup:
    async def test_signup_success(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/signup", json={
            "email": "new@test.com",
            "password": "ValidPass123!",
            "full_name": "New User",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "message" in data

    async def test_signup_duplicate_email(self, client: AsyncClient, test_user):
        resp = await client.post("/api/v1/auth/signup", json={
            "email": test_user.email,
            "password": "ValidPass123!",
        })
        assert resp.status_code == 409

    async def test_signup_invalid_email(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/signup", json={
            "email": "not-an-email",
            "password": "ValidPass123!",
        })
        assert resp.status_code == 422

    async def test_signup_short_password(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/signup", json={
            "email": "a@b.com",
            "password": "ab",
        })
        assert resp.status_code == 422


@pytest.mark.api
class TestAuthVerifyEmail:
    async def test_verify_email_success(self, client: AsyncClient, db_session: AsyncSession):
        user = User(
            email="verify@test.com",
            username="verify",
            hashed_password=hash_password("ValidPass123!"),
            is_verified=False,
        )
        db_session.add(user)
        await db_session.flush()

        code = "123456"
        verification_token = EmailVerificationToken(
            token_hash=_hash_code(code),
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        db_session.add(verification_token)
        await db_session.flush()

        resp = await client.post("/api/v1/auth/verify-email", json={
            "email": "verify@test.com",
            "code": code,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_verify_email_wrong_code(self, client: AsyncClient, db_session: AsyncSession):
        user = User(
            email="wrong@test.com",
            username="wrong",
            hashed_password=hash_password("ValidPass123!"),
            is_verified=False,
        )
        db_session.add(user)
        await db_session.flush()

        verification_token = EmailVerificationToken(
            token_hash=_hash_code("111111"),
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        db_session.add(verification_token)
        await db_session.flush()

        resp = await client.post("/api/v1/auth/verify-email", json={
            "email": "wrong@test.com",
            "code": "999999",
        })
        assert resp.status_code == 400

    async def test_verify_email_expired_code(self, client: AsyncClient, db_session: AsyncSession):
        user = User(
            email="expired@test.com",
            username="expired",
            hashed_password=hash_password("ValidPass123!"),
            is_verified=False,
        )
        db_session.add(user)
        await db_session.flush()

        code = "123456"
        verification_token = EmailVerificationToken(
            token_hash=_hash_code(code),
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        db_session.add(verification_token)
        await db_session.flush()

        resp = await client.post("/api/v1/auth/verify-email", json={
            "email": "expired@test.com",
            "code": code,
        })
        assert resp.status_code == 400

    async def test_verify_already_verified(self, client: AsyncClient, test_user):
        resp = await client.post("/api/v1/auth/verify-email", json={
            "email": test_user.email,
            "code": "123456",
        })
        assert resp.status_code == 400


@pytest.mark.api
class TestAuthResendVerification:
    async def test_resend_verification_success(self, client: AsyncClient, db_session: AsyncSession):
        user = User(
            email="resend@test.com",
            username="resend",
            hashed_password=hash_password("ValidPass123!"),
            is_verified=False,
        )
        db_session.add(user)
        await db_session.flush()

        resp = await client.post("/api/v1/auth/resend-verification", json={
            "email": "resend@test.com",
        })
        assert resp.status_code == 202

    async def test_resend_verification_nonexistent_email(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/resend-verification", json={
            "email": "nonexistent@test.com",
        })
        assert resp.status_code == 202

    async def test_resend_verification_already_verified(self, client: AsyncClient, test_user):
        resp = await client.post("/api/v1/auth/resend-verification", json={
            "email": test_user.email,
        })
        assert resp.status_code == 202


@pytest.mark.api
class TestAuthLogin:
    async def test_login_success(self, client: AsyncClient, test_user):
        resp = await client.post("/api/v1/auth/login", json={
            "email": test_user.email,
            "password": "TestPass123!",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_login_unverified_email(self, client: AsyncClient, db_session: AsyncSession):
        user = User(
            email="unverified@test.com",
            username="unverified",
            hashed_password=hash_password("TestPass123!"),
            is_verified=False,
        )
        db_session.add(user)
        await db_session.flush()

        resp = await client.post("/api/v1/auth/login", json={
            "email": "unverified@test.com",
            "password": "TestPass123!",
        })
        assert resp.status_code == 401

    async def test_login_wrong_password(self, client: AsyncClient, test_user):
        resp = await client.post("/api/v1/auth/login", json={
            "email": test_user.email,
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    async def test_login_nonexistent_user(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/login", json={
            "email": "nobody@test.com",
            "password": "password123",
        })
        assert resp.status_code == 401


@pytest.mark.api
class TestAuthRefresh:
    async def test_refresh_success(self, client: AsyncClient, refresh_token_fixture):
        resp = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token_fixture,
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_refresh_invalid_token(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": "invalid.token.here",
        })
        assert resp.status_code == 401

    async def test_refresh_reuse_detection(self, client: AsyncClient, refresh_token_fixture):
        resp1 = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token_fixture,
        })
        assert resp1.status_code == 200

        resp2 = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token_fixture,
        })
        assert resp2.status_code == 401


@pytest.mark.api
class TestAuthLogout:
    async def test_logout_rejects_invalid_refresh_token(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/logout", json={
            "refresh_token": "invalid.token.here",
        })
        assert resp.status_code == 204

    async def test_logout_success(self, client: AsyncClient, refresh_token_fixture):
        resp = await client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token_fixture})
        assert resp.status_code == 204


@pytest.mark.api
class TestAuthChangePassword:
    async def test_change_password_success(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/auth/change-password",
            headers=auth_headers,
            json={"current_password": "TestPass123!", "new_password": "NewPass456!"},
        )
        assert resp.status_code == 204

    async def test_change_password_wrong_current(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/auth/change-password",
            headers=auth_headers,
            json={"current_password": "wrongpassword", "new_password": "NewPass456!"},
        )
        assert resp.status_code == 401


@pytest.mark.api
class TestAuthForgotPassword:
    async def test_forgot_password_success(self, client: AsyncClient, test_user):
        resp = await client.post("/api/v1/auth/forgot-password", json={
            "email": test_user.email,
        })
        assert resp.status_code == 202

    async def test_forgot_password_nonexistent_email(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/forgot-password", json={
            "email": "nonexistent@test.com",
        })
        assert resp.status_code == 202


@pytest.mark.api
class TestAuthResetPassword:
    async def test_reset_password_success(self, client: AsyncClient, test_user, db_session):
        code = "654321"
        reset_token = PasswordResetToken(
            token_hash=_hash_code(code),
            user_id=test_user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=1),
        )
        db_session.add(reset_token)
        await db_session.flush()

        resp = await client.post("/api/v1/auth/reset-password", json={
            "email": test_user.email,
            "code": code,
            "new_password": "NewResetPass123!",
        })
        assert resp.status_code == 204

        login_resp = await client.post("/api/v1/auth/login", json={
            "email": test_user.email,
            "password": "NewResetPass123!",
        })
        assert login_resp.status_code == 200

    async def test_reset_password_wrong_code(self, client: AsyncClient, test_user, db_session):
        reset_token = PasswordResetToken(
            token_hash=_hash_code("111111"),
            user_id=test_user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=1),
        )
        db_session.add(reset_token)
        await db_session.flush()

        resp = await client.post("/api/v1/auth/reset-password", json={
            "email": test_user.email,
            "code": "999999",
            "new_password": "NewPass123!",
        })
        assert resp.status_code == 400

    async def test_reset_password_expired_code(self, client: AsyncClient, test_user, db_session):
        code = "123456"
        reset_token = PasswordResetToken(
            token_hash=_hash_code(code),
            user_id=test_user.id,
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        db_session.add(reset_token)
        await db_session.flush()

        resp = await client.post("/api/v1/auth/reset-password", json={
            "email": test_user.email,
            "code": code,
            "new_password": "NewPass123!",
        })
        assert resp.status_code == 400

    async def test_reset_password_reused_code(self, client: AsyncClient, test_user, db_session):
        code = "123456"
        reset_token = PasswordResetToken(
            token_hash=_hash_code(code),
            user_id=test_user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=1),
        )
        db_session.add(reset_token)
        await db_session.flush()

        resp1 = await client.post("/api/v1/auth/reset-password", json={
            "email": test_user.email,
            "code": code,
            "new_password": "NewPass123!",
        })
        assert resp1.status_code == 204

        resp2 = await client.post("/api/v1/auth/reset-password", json={
            "email": test_user.email,
            "code": code,
            "new_password": "AnotherPass123!",
        })
        assert resp2.status_code == 400


@pytest.mark.regression
class TestAuthRouteRegression:
    async def test_signup_response_shape(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/signup", json={
            "email": "shape@test.com",
            "password": "ShapeTest123!",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert set(data.keys()) == {"message"}
        assert isinstance(data["message"], str)
