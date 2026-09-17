"""API tests for risk endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.api
class TestRiskVaR:
    async def test_var_empty_portfolio(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/risk/var", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["confidence"] == 95
        assert data["horizon"] == "1D"
        assert data["var_value"] is None
        assert data["cvar_value"] is None
        assert data["num_observations"] == 0

    async def test_var_custom_params(self, client: AsyncClient, auth_headers):
        resp = await client.get(
            "/api/v1/risk/var?confidence=99&horizon=1W", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["confidence"] == 99
        assert data["horizon"] == "1W"

    async def test_var_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/risk/var")
        assert resp.status_code in (401, 403)

    async def test_var_invalid_confidence(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/risk/var?confidence=50", headers=auth_headers)
        assert resp.status_code == 422

    async def test_var_invalid_horizon(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/risk/var?horizon=1Y", headers=auth_headers)
        assert resp.status_code == 422


@pytest.mark.api
class TestRiskMonteCarlo:
    async def test_monte_carlo_empty_portfolio(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/risk/monte-carlo",
            headers=auth_headers,
            json={"num_simulations": 100, "horizon_days": 10},
        )
        assert resp.status_code == 404

    async def test_monte_carlo_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/risk/monte-carlo",
            json={"num_simulations": 100, "horizon_days": 10},
        )
        assert resp.status_code in (401, 403)

    async def test_monte_carlo_invalid_simulations(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/risk/monte-carlo",
            headers=auth_headers,
            json={"num_simulations": 10, "horizon_days": 10},
        )
        assert resp.status_code == 422

    async def test_monte_carlo_invalid_horizon(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/risk/monte-carlo",
            headers=auth_headers,
            json={"num_simulations": 100, "horizon_days": 400},
        )
        assert resp.status_code == 422


@pytest.mark.api
class TestRiskMonteCarloPoll:
    async def test_poll_nonexistent_task(self, client: AsyncClient, auth_headers):
        resp = await client.get(
            "/api/v1/risk/monte-carlo/nonexistent-task-id", headers=auth_headers
        )
        assert resp.status_code in (200, 503)

    async def test_poll_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/risk/monte-carlo/some-task-id")
        assert resp.status_code in (401, 403)


@pytest.mark.api
class TestRiskStressTest:
    async def test_stress_test_empty_portfolio(self, client: AsyncClient, auth_headers):
        resp = await client.get(
            "/api/v1/risk/stress-test?scenario=2008_crash", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["scenario"] == "2008_crash"
        assert data["portfolio_impact"] == 0
        assert data["holding_impacts"] == []

    async def test_stress_test_all_scenarios(self, client: AsyncClient, auth_headers):
        for scenario in ["2008_crash", "pkr_devaluation", "covid_crash", "interest_rate_hike"]:
            resp = await client.get(
                f"/api/v1/risk/stress-test?scenario={scenario}", headers=auth_headers
            )
            assert resp.status_code == 200
            assert resp.json()["scenario"] == scenario

    async def test_stress_test_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/risk/stress-test?scenario=2008_crash")
        assert resp.status_code in (401, 403)

    async def test_stress_test_invalid_scenario(self, client: AsyncClient, auth_headers):
        resp = await client.get(
            "/api/v1/risk/stress-test?scenario=alien_invasion", headers=auth_headers
        )
        assert resp.status_code == 422

    async def test_stress_test_default_scenario(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/risk/stress-test", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["scenario"] == "2008_crash"
