"""API tests for auth endpoints."""

import pytest
from httpx import AsyncClient


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
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "new@test.com"

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

    async def test_signup_rate_limited(self, client: AsyncClient):
        """Test signup rate limiting - 5 requests per minute."""
        for i in range(5):
            resp = await client.post("/api/v1/auth/signup", json={
                "email": f"rate{i}@test.com",
                "password": "ValidPass123!",
            })
            assert resp.status_code in (201, 422)

        # 6th request should be rate limited
        resp = await client.post("/api/v1/auth/signup", json={
            "email": "rate6@test.com",
            "password": "ValidPass123!",
        })
        assert resp.status_code == 429


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

    async def test_login_rate_limited(self, client: AsyncClient, test_user):
        """Test login rate limiting - 5 requests per minute."""
        for i in range(5):
            resp = await client.post("/api/v1/auth/login", json={
                "email": test_user.email,
                "password": "wrongpassword",
            })
            assert resp.status_code == 401

        # 6th request should be rate limited
        resp = await client.post("/api/v1/auth/login", json={
            "email": test_user.email,
            "password": "wrongpassword",
        })
        assert resp.status_code == 429


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
        """Test refresh token reuse detection - should revoke all tokens and return 401."""
        # First refresh - should succeed
        resp1 = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token_fixture,
        })
        assert resp1.status_code == 200

        # Second refresh with OLD token - should fail with reuse detection
        resp2 = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token_fixture,
        })
        assert resp2.status_code == 401
        err_msg = str(resp2.json()).lower()
        assert "reused" in err_msg or "invalid" in err_msg

    async def test_refresh_stores_new_token_in_db(self, client: AsyncClient, refresh_token_fixture, db_session):
        """Test that refresh token rotation stores the new refresh token in DB."""
        from app.models.user import RefreshToken
        from app.core.security import decode_token
        from sqlalchemy import select

        resp1 = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token_fixture,
        })
        assert resp1.status_code == 200
        new_refresh_token = resp1.json()["refresh_token"]

        # Decode new token and verify it's stored in DB
        new_payload = decode_token(new_refresh_token)
        assert new_payload is not None
        jti = new_payload.get("jti")
        result = await db_session.execute(select(RefreshToken).where(RefreshToken.jti == jti))
        rt = result.scalars().first()
        assert rt is not None, "New refresh token must be stored in DB after rotation"
        assert rt.revoked is False

    async def test_refresh_rate_limited(self, client: AsyncClient, refresh_token_fixture):
        """Test refresh rate limiting - 10 requests per minute."""
        for i in range(10):
            resp = await client.post("/api/v1/auth/refresh", json={
                "refresh_token": refresh_token_fixture,
            })
            # First will succeed, rest will fail with 401 (token already used)
            if i == 0:
                assert resp.status_code == 200
            else:
                assert resp.status_code == 401


@pytest.mark.api
class TestAuthLogout:
    async def test_logout_rejects_invalid_refresh_token(self, client: AsyncClient, test_user):
        """Test that logout with invalid token returns 204 (silent success)."""
        resp = await client.post("/api/v1/auth/logout", json={
            "refresh_token": "invalid.token.here",
        })
        assert resp.status_code == 204

    async def test_logout_success(self, client: AsyncClient, refresh_token_fixture):
        resp = await client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token_fixture})
        assert resp.status_code == 204

    async def test_logout_revokes_refresh_token(self, client: AsyncClient, test_user):
        """Test that logout revokes the refresh token."""
        # Login to get tokens
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": test_user.email,
            "password": "TestPass123!",
        })
        assert login_resp.status_code == 200
        refresh_token = login_resp.json()["refresh_token"]
        access_token = login_resp.json()["access_token"]

        # Logout with the refresh token (authenticated)
        logout_resp = await client.post("/api/v1/auth/logout", headers={
            "Authorization": f"Bearer {access_token}"
        }, json={
            "refresh_token": refresh_token,
        })
        assert logout_resp.status_code == 204

        # Try to use the revoked refresh token
        refresh_resp = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token,
        })
        assert refresh_resp.status_code == 401

    async def test_logout_rate_limited(self, client: AsyncClient, test_user):
        """Test logout rate limiting."""
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": test_user.email,
            "password": "TestPass123!",
        })
        refresh_token = login_resp.json()["refresh_token"]

        for i in range(10):
            resp = await client.post("/api/v1/auth/logout", json={
                "refresh_token": refresh_token,
            })
            assert resp.status_code in (204, 401)  # 401 after first logout (token already revoked)

        # 11th request should be rate limited
        resp = await client.post("/api/v1/auth/logout", json={
            "refresh_token": refresh_token,
        })
        assert resp.status_code == 429


@pytest.mark.api
class TestAuthChangePassword:
    async def test_change_password_success(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/auth/change-password",
            headers=auth_headers,
            json={
                "current_password": "TestPass123!",
                "new_password": "NewPass456!",
            },
        )
        assert resp.status_code == 204

    async def test_change_password_wrong_current(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/auth/change-password",
            headers=auth_headers,
            json={
                "current_password": "wrongpassword",
                "new_password": "NewPass456!",
            },
        )
        assert resp.status_code == 401

    async def test_change_password_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "a", "new_password": "b"},
        )
        assert resp.status_code in (401, 403)

    async def test_change_password_revokes_refresh_tokens(self, client: AsyncClient, test_user):
        """Test that password change revokes all refresh tokens."""
        # Login to get tokens
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": test_user.email,
            "password": "TestPass123!",
        })
        assert login_resp.status_code == 200
        refresh_token = login_resp.json()["refresh_token"]
        access_token = login_resp.json()["access_token"]

        # Change password
        headers = {"Authorization": f"Bearer {access_token}"}
        change_resp = await client.post(
            "/api/v1/auth/change-password",
            headers=headers,
            json={
                "current_password": "TestPass123!",
                "new_password": "NewPass456!",
            },
        )
        assert change_resp.status_code == 204

        # Try to use the old refresh token - should fail
        refresh_resp = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token,
        })
        assert refresh_resp.status_code == 401


@pytest.mark.api
class TestAuthForgotPassword:
    async def test_forgot_password_success(self, client: AsyncClient, test_user):
        resp = await client.post("/api/v1/auth/forgot-password", json={
            "email": test_user.email,
        })
        assert resp.status_code == 202
        assert "message" in resp.json()

    async def test_forgot_password_nonexistent_email(self, client: AsyncClient):
        """Test that forgot-password doesn't reveal if email exists (returns 202)."""
        resp = await client.post("/api/v1/auth/forgot-password", json={
            "email": "nonexistent@test.com",
        })
        assert resp.status_code == 202
        assert "message" in resp.json()

    async def test_forgot_password_invalid_email(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/forgot-password", json={
            "email": "not-an-email",
        })
        assert resp.status_code == 422

    async def test_forgot_password_rate_limited(self, client: AsyncClient):
        """Test forgot-password rate limiting - 3 requests per minute."""
        for i in range(3):
            resp = await client.post("/api/v1/auth/forgot-password", json={
                "email": f"rate{i}@test.com",
            })
            assert resp.status_code == 202

        # 4th request should be rate limited
        resp = await client.post("/api/v1/auth/forgot-password", json={
            "email": "rate4@test.com",
        })
        assert resp.status_code == 429


@pytest.mark.api
class TestAuthResetPassword:
    async def test_reset_password_success(self, client: AsyncClient, test_user, db_session):
        """Test successful password reset with valid token."""
        from app.services.auth_service import AuthService
        from app.core.security import hash_password
        import hashlib
        import secrets
        from datetime import datetime, timedelta, timezone
        from app.models.user import PasswordResetToken

        # Create a reset token directly in DB
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        reset_token = PasswordResetToken(
            token_hash=token_hash,
            user_id=test_user.id,
            expires_at=expires_at,
        )
        db_session.add(reset_token)
        await db_session.flush()

        # Use the token to reset password
        resp = await client.post("/api/v1/auth/reset-password", json={
            "token": raw_token,
            "new_password": "NewResetPass123!",
        })
        assert resp.status_code == 204

        # Verify new password works
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": test_user.email,
            "password": "NewResetPass123!",
        })
        assert login_resp.status_code == 200

    async def test_reset_password_invalid_token(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/reset-password", json={
            "token": "invalid-token",
            "new_password": "NewPass123!",
        })
        assert resp.status_code == 422

    async def test_reset_password_expired_token(self, client: AsyncClient, test_user, db_session):
        """Test that expired reset token is rejected."""
        from app.models.user import PasswordResetToken
        import hashlib
        import secrets
        from datetime import datetime, timedelta, timezone

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) - timedelta(hours=1)  # Expired

        reset_token = PasswordResetToken(
            token_hash=token_hash,
            user_id=test_user.id,
            expires_at=expires_at,
        )
        db_session.add(reset_token)
        await db_session.flush()

        resp = await client.post("/api/v1/auth/reset-password", json={
            "token": raw_token,
            "new_password": "NewPass123!",
        })
        assert resp.status_code == 422

    async def test_reset_password_reused_token(self, client: AsyncClient, test_user, db_session):
        """Test that a reset token can only be used once."""
        from app.models.user import PasswordResetToken
        import hashlib
        import secrets
        from datetime import datetime, timedelta, timezone

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        reset_token = PasswordResetToken(
            token_hash=token_hash,
            user_id=test_user.id,
            expires_at=expires_at,
        )
        db_session.add(reset_token)
        await db_session.flush()

        # First use - should succeed
        resp1 = await client.post("/api/v1/auth/reset-password", json={
            "token": raw_token,
            "new_password": "NewPass123!",
        })
        assert resp1.status_code == 204

        # Second use - should fail
        resp2 = await client.post("/api/v1/auth/reset-password", json={
            "token": raw_token,
            "new_password": "AnotherPass123!",
        })
        assert resp2.status_code == 422

    async def test_reset_password_rate_limited(self, client: AsyncClient):
        """Test reset-password rate limiting - 3 requests per minute."""
        for i in range(3):
            resp = await client.post("/api/v1/auth/reset-password", json={
                "token": f"token{i}",
                "new_password": "NewPass123!",
            })
            assert resp.status_code == 422  # Invalid tokens but not rate limited yet

        # 4th request should be rate limited
        resp = await client.post("/api/v1/auth/reset-password", json={
            "token": "token4",
            "new_password": "NewPass123!",
        })
        assert resp.status_code == 429


@pytest.mark.regression
class TestAuthRouteRegression:
    async def test_single_reset_password_route_registered(self):
        """Guard against duplicate route registration (SEC-001 regression)."""
        from app.main import app

        reset_routes = [
            route for route in app.routes
            if hasattr(route, "path") and route.path == "/api/v1/auth/reset-password"
        ]
        assert len(reset_routes) == 1, (
            f"Expected exactly 1 route for POST /api/v1/auth/reset-password, "
            f"found {len(reset_routes)}. SEC-001 regression detected."
        )

    async def test_signup_response_shape(self, client: AsyncClient):
        """Assert signup success response matches expected schema (SEC-002 regression)."""
        resp = await client.post("/api/v1/auth/signup", json={
            "email": "shape@test.com",
            "password": "ShapeTest123!",
        })
        assert resp.status_code == 201
        data = resp.json()

        assert set(data.keys()) == {"access_token", "refresh_token", "token_type", "user"}
        assert isinstance(data["access_token"], str)
        assert isinstance(data["refresh_token"], str)
        assert data["token_type"] == "bearer"

        user = data["user"]
        assert set(user.keys()) == {"id", "email", "username", "full_name"}
        assert isinstance(user["id"], str)
        assert isinstance(user["email"], str)
        assert isinstance(user["username"], str)
        assert "is_admin" not in user
