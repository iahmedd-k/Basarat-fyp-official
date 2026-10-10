"""Performance and regression tests — response time and throughput baselines."""

import asyncio
import time

import pytest
from httpx import AsyncClient


@pytest.mark.performance
class TestResponseTime:
    """Ensure key endpoints respond within acceptable time limits."""

    MAX_RESPONSE_MS = 2000

    async def _measure(self, client, method, url, **kwargs):
        start = time.perf_counter()
        resp = await getattr(client, method)(url, **kwargs)
        elapsed_ms = (time.perf_counter() - start) * 1000
        return resp, elapsed_ms

    async def test_health_response_time(self, client: AsyncClient):
        resp, ms = await self._measure(client, "get", "/api/v1/health")
        assert resp.status_code == 200
        assert ms < self.MAX_RESPONSE_MS, f"Health endpoint took {ms:.0f}ms"

    async def test_signup_response_time(self, client: AsyncClient):
        resp, ms = await self._measure(
            client, "post", "/api/v1/auth/signup",
            json={"email": f"perf{time.time()}@test.com", "password": "PerfPass1!"},
        )
        assert resp.status_code == 201
        assert ms < self.MAX_RESPONSE_MS, f"Signup took {ms:.0f}ms"

    async def test_market_indices_response_time(self, client: AsyncClient, auth_headers, mock_market_service, override_services):
        mock_market_service.get_indices.return_value = [
            {"index": "KSE-100", "code": "KSE100", "current": 42000.0, "change": 200.0, "change_pct": 0.48, "high": 42200.0, "low": 41800.0},
        ]
        resp, ms = await self._measure(
            client, "get", "/api/v1/market/indices", headers=auth_headers,
        )
        assert resp.status_code == 200
        assert ms < self.MAX_RESPONSE_MS


@pytest.mark.performance
class TestConcurrency:
    """Test that endpoints handle concurrent requests."""

    async def test_concurrent_signups(self, client: AsyncClient):
        async def signup(i):
            return await client.post("/api/v1/auth/signup", json={
                "email": f"conc{i}_{time.time()}@test.com",
                "password": "ConcPass1!",
            })

        results = await asyncio.gather(*[signup(i) for i in range(5)])
        statuses = [r.status_code for r in results]
        assert all(s == 201 for s in statuses)

    async def test_concurrent_reads(self, client: AsyncClient, auth_headers):
        async def read():
            return await client.get("/api/v1/news", headers=auth_headers)

        results = await asyncio.gather(*[read() for _ in range(20)])
        statuses = [r.status_code for r in results]
        assert all(s == 200 for s in statuses)


@pytest.mark.regression
class TestRegression:
    """Ensure previously fixed bugs don't resurface."""

    async def test_empty_email_returns_422(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/signup", json={
            "email": "", "password": "Pass1234!",
        })
        assert resp.status_code == 422

    async def test_sql_injection_in_search(self, client: AsyncClient, auth_headers):
        resp = await client.get(
            "/api/v1/stocks/search?q='; DROP TABLE users; --",
            headers=auth_headers,
        )
        assert resp.status_code in (200, 400, 422)

    async def test_xss_in_post_content(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/community/posts",
            headers=auth_headers,
            json={"content": "<script>alert('xss')</script>", "symbols": ["HBL"]},
        )
        assert resp.status_code in (201, 422)

    async def test_large_payload_rejected(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/community/posts",
            headers=auth_headers,
            json={"content": "x" * 100000, "symbols": ["HBL"]},
        )
        assert resp.status_code in (400, 413, 422)

    async def test_negative_quantity_rejected(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/portfolio/transactions",
            headers=auth_headers,
            json={
                "symbol": "HBL",
                "transaction_type": "buy",
                "quantity": -10,
                "price": 150.0,
                "transaction_date": "2025-01-01T00:00:00Z",
            },
        )
        assert resp.status_code in (400, 422)

    async def test_limit_param_boundary(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/market/gainers?limit=100", headers=auth_headers)
        assert resp.status_code in (200, 503)

        resp = await client.get("/api/v1/market/gainers?limit=101", headers=auth_headers)
        assert resp.status_code == 422

        resp = await client.get("/api/v1/market/gainers?limit=0", headers=auth_headers)
        assert resp.status_code == 422
