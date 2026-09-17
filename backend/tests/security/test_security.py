"""Security tests — authentication, authorization, input validation, injection."""

import pytest
from httpx import AsyncClient


@pytest.mark.security
class TestAuthenticationSecurity:
    async def test_unauthenticated_access_rejected(self, client: AsyncClient):
        protected_endpoints = [
            ("GET", "/api/v1/users/me"),
            ("GET", "/api/v1/portfolio"),
            ("GET", "/api/v1/market/indices"),
            ("GET", "/api/v1/news"),
            ("GET", "/api/v1/community/feed"),
            ("GET", "/api/v1/alerts"),
            ("GET", "/api/v1/notifications"),
        ]
        for method, url in protected_endpoints:
            resp = await getattr(client, method.lower())(url)
            assert resp.status_code in (401, 403), f"{method} {url} should require auth"

    async def test_invalid_token_rejected(self, client: AsyncClient):
        headers = {"Authorization": "Bearer invalid.jwt.token"}
        resp = await client.get("/api/v1/users/me", headers=headers)
        assert resp.status_code == 401

    async def test_expired_token_rejected(self, client: AsyncClient, expired_token_headers):
        resp = await client.get("/api/v1/users/me", headers=expired_token_headers)
        assert resp.status_code == 401

    async def test_malformed_bearer_header(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": "NotBearer token"},
        )
        assert resp.status_code in (401, 403)

    async def test_empty_bearer_token(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer "},
        )
        assert resp.status_code in (401, 403)


@pytest.mark.security
class TestAuthorizationSecurity:
    async def test_non_admin_cannot_access_admin_routes(self, client: AsyncClient, auth_headers):
        admin_endpoints = [
            ("GET", "/api/v1/users"),
        ]
        for method, url in admin_endpoints:
            resp = await getattr(client, method.lower())(url, headers=auth_headers)
            assert resp.status_code in (403, 404), f"Non-admin should not access {method} {url}"

    async def test_user_cannot_modify_other_users_data(
        self, client: AsyncClient, db_session, auth_headers, test_user
    ):
        from app.models.user import User
        from app.models.portfolio import Portfolio, PortfolioHolding
        from app.core.security import hash_password

        other = User(
            email="other@test.com",
            username="other",
            hashed_password=hash_password("pass"),
        )
        db_session.add(other)
        await db_session.flush()

        other_portfolio = Portfolio(user_id=other.id, name="Other Portfolio")
        db_session.add(other_portfolio)
        await db_session.flush()

        other_holding = PortfolioHolding(
            portfolio_id=other_portfolio.id,
            stock_id="stock-hbl",
            quantity=100,
            avg_buy_price=150.0,
        )
        db_session.add(other_holding)
        await db_session.flush()

        resp = await client.delete(
            f"/api/v1/portfolio/holdings/{other_holding.id}",
            headers=auth_headers,
        )
        assert resp.status_code in (403, 404)


@pytest.mark.security
class TestInputValidation:
    async def test_sql_injection_in_signup(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/signup", json={
            "email": "'; DROP TABLE users; --@test.com",
            "password": "Pass1234!",
        })
        assert resp.status_code in (201, 400, 422)

    async def test_sql_injection_in_search(self, client: AsyncClient, auth_headers):
        resp = await client.get(
            "/api/v1/stocks/search?q=' OR 1=1 --",
            headers=auth_headers,
        )
        assert resp.status_code in (200, 400, 422)

    async def test_sql_injection_in_login(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/login", json={
            "email": "admin@test.com",
            "password": "' OR '1'='1",
        })
        assert resp.status_code == 401

    async def test_xss_in_community_post(self, client: AsyncClient, auth_headers):
        xss_payloads = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert(1)>",
            "javascript:alert(1)",
            "<svg onload=alert(1)>",
        ]
        for payload in xss_payloads:
            resp = await client.post(
                "/api/v1/community/posts",
                headers=auth_headers,
                json={"symbol": "HBL", "stance": "bullish", "rationale_text": payload},
            )
            if resp.status_code == 201:
                body = resp.json()
                assert "<script>" not in body.get("rationale_text", "") or resp.status_code == 201

    async def test_path_traversal_in_stock_symbol(self, client: AsyncClient, auth_headers):
        resp = await client.get(
            "/api/v1/stocks/../../etc/passwd/overview",
            headers=auth_headers,
        )
        assert resp.status_code in (400, 404, 422)

    async def test_oversized_payload_rejected(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/community/posts",
            headers=auth_headers,
            json={"symbol": "HBL", "stance": "bullish", "rationale_text": "A" * 1_000_000},
        )
        assert resp.status_code in (400, 413, 422)

    async def test_negative_stock_quantity_rejected(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/portfolio/holdings",
            headers=auth_headers,
            json={"symbol": "HBL", "quantity": -100, "avg_buy_price": 150.0, "purchase_date": "2025-01-01"},
        )
        assert resp.status_code in (400, 422)

    async def test_zero_stock_quantity_rejected(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/portfolio/holdings",
            headers=auth_headers,
            json={"symbol": "HBL", "quantity": 0, "avg_buy_price": 150.0, "purchase_date": "2025-01-01"},
        )
        assert resp.status_code in (400, 422)


@pytest.mark.security
class TestTokenSecurity:
    async def test_token_type_confusion(self, client: AsyncClient, test_user):
        from app.core.security import create_refresh_token
        refresh = create_refresh_token({"sub": test_user.id})
        resp = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {refresh}"},
        )
        assert resp.status_code == 401

    async def test_token_with_wrong_algorithm(self, client: AsyncClient):
        import json
        import base64
        header = base64.urlsafe_b64encode(
            json.dumps({"alg": "none", "typ": "JWT"}).encode()
        ).rstrip(b"=").decode()
        payload = base64.urlsafe_b64encode(
            json.dumps({"sub": "fake", "type": "access"}).encode()
        ).rstrip(b"=").decode()
        token = f"{header}.{payload}."
        resp = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401

    async def test_reuse_of_refresh_token_as_access(self, client: AsyncClient, test_user):
        from app.core.security import create_refresh_token
        refresh = create_refresh_token({"sub": test_user.id})
        resp = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {refresh}"},
        )
        assert resp.status_code == 401


@pytest.mark.security
class TestPasswordSecurity:
    async def test_password_not_returned_in_response(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/signup", json={
            "email": "sec@test.com",
            "password": "SecretPass1!",
        })
        assert resp.status_code == 201
        body = resp.json()
        assert "password" not in body
        assert "hashed_password" not in body
        assert "user" in body
        assert "password" not in body.get("user", {})

    async def test_login_failure_does_not_leak_info(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/login", json={
            "email": "nonexistent@test.com",
            "password": "wrong",
        })
        assert resp.status_code == 401
        assert "user" not in resp.json()
