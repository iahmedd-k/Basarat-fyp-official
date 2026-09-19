"""End-to-end tests — complete user journeys through the API."""

import pytest
from httpx import AsyncClient


@pytest.mark.e2e
class TestNewUserJourney:
    """Simulate a new user's first session on the platform."""

    async def test_complete_onboarding_journey(self, client: AsyncClient):
        signup = await client.post("/api/v1/auth/signup", json={
            "email": "newinvestor@test.com",
            "password": "Invest123!",
            "full_name": "New Investor",
        })
        assert signup.status_code == 201
        token = signup.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        profile = await client.get("/api/v1/users/me", headers=headers)
        assert profile.status_code == 200
        assert profile.json()["email"] == "newinvestor@test.com"

        risk = await client.patch(
            "/api/v1/users/me/risk-profile",
            headers=headers,
            json={"risk_tolerance": "moderate"},
        )
        assert risk.status_code == 200

        search = await client.get(
            "/api/v1/stocks/search?q=HBL",
            headers=headers,
        )
        assert search.status_code == 200

        indices = await client.get("/api/v1/market/indices", headers=headers)
        assert indices.status_code == 200

        gainers = await client.get("/api/v1/market/gainers?limit=5", headers=headers)
        assert gainers.status_code == 200

        news = await client.get("/api/v1/news?limit=10", headers=headers)
        assert news.status_code == 200


@pytest.mark.e2e
class TestPortfolioManagementJourney:
    """Simulate a user building and managing their portfolio."""

    async def test_portfolio_lifecycle(self, client: AsyncClient):
        signup = await client.post("/api/v1/auth/signup", json={
            "email": "portfolio@test.com",
            "password": "Port123!",
        })
        token = signup.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        holdings_to_add = [
            {"symbol": "HBL", "quantity": 100, "avg_buy_price": 150.0, "purchase_date": "2025-01-01"},
            {"symbol": "OGDC", "quantity": 200, "avg_buy_price": 90.0, "purchase_date": "2025-01-01"},
            {"symbol": "LUCK", "quantity": 50, "avg_buy_price": 620.0, "purchase_date": "2025-01-01"},
        ]

        holding_ids = []
        for h in holdings_to_add:
            resp = await client.post(
                "/api/v1/portfolio/holdings",
                headers=headers,
                json=h,
            )
            assert resp.status_code == 201
            holding_ids.append(resp.json()["id"])

        portfolio = await client.get("/api/v1/portfolio", headers=headers)
        assert portfolio.status_code == 200
        assert len(portfolio.json()["holdings"]) == 3

        pnl = await client.get("/api/v1/portfolio/pnl", headers=headers)
        assert pnl.status_code == 200

        allocation = await client.get("/api/v1/portfolio/allocation", headers=headers)
        assert allocation.status_code == 200

        await client.patch(
            f"/api/v1/portfolio/holdings/{holding_ids[0]}",
            headers=headers,
            json={"quantity": 150},
        )

        await client.delete(
            f"/api/v1/portfolio/holdings/{holding_ids[2]}",
            headers=headers,
        )

        final = await client.get("/api/v1/portfolio", headers=headers)
        assert len(final.json()["holdings"]) == 2


@pytest.mark.e2e
class TestAlertManagementJourney:
    """Simulate a user setting up and managing alerts."""

    async def test_alert_lifecycle(self, client: AsyncClient):
        signup = await client.post("/api/v1/auth/signup", json={
            "email": "alertuser@test.com",
            "password": "Alert123!",
        })
        token = signup.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        rule_resp = await client.post(
            "/api/v1/alerts/rules",
            headers=headers,
            json={"condition": "price_above", "threshold": 200.0},
        )
        assert rule_resp.status_code == 201
        rule_id = rule_resp.json()["id"]

        rules = await client.get("/api/v1/alerts/rules", headers=headers)
        assert rules.status_code == 200
        assert any(r["id"] == rule_id for r in rules.json()["rules"])

        await client.patch(
            f"/api/v1/alerts/rules/{rule_id}",
            headers=headers,
            json={"threshold": 250.0},
        )

        alerts = await client.get("/api/v1/alerts", headers=headers)
        assert alerts.status_code == 200


@pytest.mark.e2e
class TestCommunityJourney:
    """Simulate a user engaging with the community."""

    async def test_community_engagement(self, client: AsyncClient):
        signup = await client.post("/api/v1/auth/signup", json={
            "email": "community@test.com",
            "password": "Comm123!",
        })
        token = signup.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        post_resp = await client.post(
            "/api/v1/community/posts",
            headers=headers,
            json={"content": "What do you think about HBL at 150?", "symbols": ["HBL"]},
        )
        assert post_resp.status_code == 201
        post_id = post_resp.json()["id"]

        comment_resp = await client.post(
            f"/api/v1/community/posts/{post_id}/comments",
            headers=headers,
            json={"content": "Strong buy signal!"},
        )
        assert comment_resp.status_code == 201

        like_resp = await client.post(
            f"/api/v1/community/posts/{post_id}/like",
            headers=headers,
        )
        assert like_resp.status_code == 200
        assert like_resp.json()["likedByMe"] is True

        feed = await client.get("/api/v1/community/feed", headers=headers)
        assert feed.status_code == 200

        comments = await client.get(
            f"/api/v1/community/posts/{post_id}/comments",
            headers=headers,
        )
        assert comments.status_code == 200
        assert len(comments.json()["items"]) == 1

        share = await client.post(
            f"/api/v1/community/posts/{post_id}/share",
            headers=headers,
        )
        assert share.status_code == 201
        short_code = share.json()["shortCode"]

        resolve = await client.get(f"/api/v1/community/share/{short_code}")
        assert resolve.status_code == 200
        assert resolve.json()["postId"] == post_id


@pytest.mark.e2e
class TestResearchJourney:
    """Simulate a user researching a stock before investing."""

    async def test_stock_research_flow(self, client: AsyncClient):
        signup = await client.post("/api/v1/auth/signup", json={
            "email": "researcher@test.com",
            "password": "Research1!",
        })
        token = signup.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        overview = await client.get("/api/v1/stocks/HBL/overview", headers=headers)
        assert overview.status_code in (200, 404)

        news = await client.get("/api/v1/news?limit=5", headers=headers)
        assert news.status_code == 200

        sentiment = await client.get("/api/v1/sentiment/HBL", headers=headers)
        assert sentiment.status_code in (200, 503)

        kse100 = await client.get("/api/v1/market/indices/kse-100", headers=headers)
        assert kse100.status_code == 200
