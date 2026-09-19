"""Integration tests — full auth flow with real DB session."""

import pytest
from httpx import AsyncClient


@pytest.mark.integration
class TestAuthFlowIntegration:
    async def test_signup_login_refresh_cycle(self, client: AsyncClient):
        signup_resp = await client.post("/api/v1/auth/signup", json={
            "email": "flow@test.com",
            "password": "SecurePass1!",
            "full_name": "Flow Test",
        })
        assert signup_resp.status_code == 201
        tokens = signup_resp.json()

        login_resp = await client.post("/api/v1/auth/login", json={
            "email": "flow@test.com",
            "password": "SecurePass1!",
        })
        assert login_resp.status_code == 200

        refresh_resp = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": tokens["refresh_token"],
        })
        assert refresh_resp.status_code == 200
        new_tokens = refresh_resp.json()
        assert new_tokens["access_token"] != tokens["access_token"]

        profile_resp = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {new_tokens['access_token']}"},
        )
        assert profile_resp.status_code == 200
        assert profile_resp.json()["email"] == "flow@test.com"

    async def test_change_password_flow(self, client: AsyncClient):
        signup = await client.post("/api/v1/auth/signup", json={
            "email": "changepw@test.com",
            "password": "OldPass123!",
        })
        token = signup.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        change_resp = await client.post(
            "/api/v1/auth/change-password",
            headers=headers,
            json={
                "current_password": "OldPass123!",
                "new_password": "NewPass456!",
            },
        )
        assert change_resp.status_code == 204

        login_resp = await client.post("/api/v1/auth/login", json={
            "email": "changepw@test.com",
            "password": "NewPass456!",
        })
        assert login_resp.status_code == 200

    async def test_inactive_user_cannot_login(self, client: AsyncClient, inactive_user):
        resp = await client.post("/api/v1/auth/login", json={
            "email": inactive_user.email,
            "password": "TestPass123!",
        })
        assert resp.status_code == 401


@pytest.mark.integration
class TestUserIntegration:
    async def test_get_and_update_profile(self, client: AsyncClient, auth_headers):
        get_resp = await client.get("/api/v1/users/me", headers=auth_headers)
        assert get_resp.status_code == 200
        assert get_resp.json()["full_name"] == "Test User"

        update_resp = await client.patch(
            "/api/v1/users/me",
            headers=auth_headers,
            json={"full_name": "Updated Name"},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["full_name"] == "Updated Name"

    async def test_update_risk_profile(self, client: AsyncClient, auth_headers):
        resp = await client.patch(
            "/api/v1/users/me/risk-profile",
            headers=auth_headers,
            json={"risk_tolerance": "aggressive"},
        )
        assert resp.status_code == 200

    async def test_update_notification_preferences(self, client: AsyncClient, auth_headers):
        resp = await client.patch(
            "/api/v1/users/me/notification-preferences",
            headers=auth_headers,
            json={"channels": ["push", "email"], "categories": ["portfolio", "alerts"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["channels"] == ["push", "email"]
        assert data["categories"] == ["portfolio", "alerts"]

    async def test_update_notification_preferences_partial(self, client: AsyncClient, auth_headers):
        resp = await client.patch(
            "/api/v1/users/me/notification-preferences",
            headers=auth_headers,
            json={"channels": ["push"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["channels"] == ["push"]

    async def test_update_notification_preferences_requires_auth(self, client: AsyncClient):
        resp = await client.patch(
            "/api/v1/users/me/notification-preferences",
            json={"channels": ["push"]},
        )
        assert resp.status_code in (401, 403)


@pytest.mark.integration
class TestPortfolioIntegration:
    async def test_full_portfolio_lifecycle(self, client: AsyncClient, auth_headers):
        create_resp = await client.post(
            "/api/v1/portfolio/holdings",
            headers=auth_headers,
            json={"symbol": "HBL", "quantity": 100, "avg_buy_price": 150.0, "purchase_date": "2025-01-01"},
        )
        assert create_resp.status_code in (201, 503)
        holding_id = create_resp.json()["id"]

        portfolio_resp = await client.get("/api/v1/portfolio", headers=auth_headers)
        assert portfolio_resp.status_code == 200
        holdings = portfolio_resp.json()["holdings"]
        assert any(h["id"] == holding_id for h in holdings)

        update_resp = await client.patch(
            f"/api/v1/portfolio/holdings/{holding_id}",
            headers=auth_headers,
            json={"quantity": 200},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["quantity"] == 200

        delete_resp = await client.delete(
            f"/api/v1/portfolio/holdings/{holding_id}",
            headers=auth_headers,
        )
        assert delete_resp.status_code == 204

        final_resp = await client.get("/api/v1/portfolio", headers=auth_headers)
        holdings = final_resp.json()["holdings"]
        assert not any(h["id"] == holding_id for h in holdings)


@pytest.mark.integration
class TestAlertIntegration:
    async def test_full_alert_rule_lifecycle(self, client: AsyncClient, auth_headers):
        create_resp = await client.post(
            "/api/v1/alerts/rules",
            headers=auth_headers,
            json={"condition": "price_above", "threshold": 200.0},
        )
        assert create_resp.status_code == 201
        rule_id = create_resp.json()["id"]

        update_resp = await client.patch(
            f"/api/v1/alerts/rules/{rule_id}",
            headers=auth_headers,
            json={"threshold": 250.0, "is_active": False},
        )
        assert update_resp.status_code == 200

        delete_resp = await client.delete(
            f"/api/v1/alerts/rules/{rule_id}",
            headers=auth_headers,
        )
        assert delete_resp.status_code == 204


@pytest.mark.integration
class TestCommunityIntegration:
    async def test_post_comment_like_flow(self, client: AsyncClient, auth_headers):
        post_resp = await client.post(
            "/api/v1/community/posts",
            headers=auth_headers,
            json={"content": "Integration test post about HBL", "symbols": ["HBL"]},
        )
        assert post_resp.status_code == 201
        post_id = post_resp.json()["id"]

        comment_resp = await client.post(
            f"/api/v1/community/posts/{post_id}/comments",
            headers=auth_headers,
            json={"content": "Test comment"},
        )
        assert comment_resp.status_code == 201

        like_resp = await client.post(
            f"/api/v1/community/posts/{post_id}/like",
            headers=auth_headers,
        )
        assert like_resp.status_code == 200
        assert like_resp.json()["likedByMe"] is True

        feed_resp = await client.get("/api/v1/community/feed", headers=auth_headers)
        assert feed_resp.status_code == 200
        assert any(p["id"] == post_id for p in feed_resp.json()["items"])
