"""Route checks using an isolated test account and deterministic synthetic prices."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from httpx import AsyncClient


@pytest.fixture
def synthetic_prices(monkeypatch):
    from app.services import risk_service
    dates = pd.date_range("2025-01-01", periods=280, freq="B")
    t = np.arange(len(dates), dtype=float)
    # Deterministic non-constant series with a shared cycle and distinct movement.
    hbl = 100 * np.exp(.0002 * t + .012 * np.sin(t / 3) + .004 * np.sin(t / 13))
    ogdc = 80 * np.exp(.0001 * t + .009 * np.sin(t / 3 + .2) + .006 * np.cos(t / 9))
    monkeypatch.setattr(risk_service, "_get_price_pivot", lambda: pd.DataFrame({"HBL": hbl, "OGDC": ogdc}, index=dates))


@pytest.mark.api
async def _seed_database_portfolio(db_session, test_user, monkeypatch):
    from app.models.portfolio import PortfolioTransaction, TransactionType
    from app.services.stock_service import StockService
    db_session.add_all([
        PortfolioTransaction(user_id=test_user.id, symbol="HBL", transaction_type=TransactionType.BUY, quantity=Decimal("400"), price=Decimal("140"), fee=Decimal("0"), transaction_date=date(2025, 1, 2)),
        PortfolioTransaction(user_id=test_user.id, symbol="OGDC", transaction_type=TransactionType.BUY, quantity=Decimal("500"), price=Decimal("75"), fee=Decimal("0"), transaction_date=date(2025, 1, 2)),
    ])
    await db_session.flush()
    monkeypatch.setattr(StockService, "get_quote_batch", lambda self, symbols: [{"symbol": "HBL", "current": 150.0}, {"symbol": "OGDC", "current": 80.0}])


@pytest.mark.api
async def test_seeded_portfolio_var_and_stress_routes(client: AsyncClient, auth_headers, test_user, db_session, monkeypatch, synthetic_prices):
    await _seed_database_portfolio(db_session, test_user, monkeypatch)

    var_resp = await client.get("/api/v1/risk/var?confidence=95&horizon=1W", headers=auth_headers)
    assert var_resp.status_code == 200, var_resp.text
    var = var_resp.json()
    assert var["status"] == "available"
    assert var["num_observations"] == 275
    assert var["portfolio_value"] == 100000
    assert var["var_value"] < 0 and var["cvar_value"] <= var["var_value"]
    assert set(var["symbols_used"]) == {"HBL", "OGDC"}
    assert var["var_loss_amount"] > 0 and var["currency"] == "PKR"

    stress_resp = await client.get("/api/v1/risk/stress-test?scenario=2008_crash", headers=auth_headers)
    assert stress_resp.status_code == 200, stress_resp.text
    stress = stress_resp.json()
    assert stress["status"] == "available"
    assert stress["current_value"] == 100000
    impact_by_symbol = {item["symbol"]: item for item in stress["holding_impacts"]}
    assert impact_by_symbol["HBL"]["shock_pct"] == -55.0  # Banking alias recognized
    assert stress["worst_case_loss_value"] < 0
    assert "illustrative" in stress["method"]


@pytest.mark.api
async def test_seeded_portfolio_monte_carlo_start_and_poll(client: AsyncClient, auth_headers, test_user, db_session, monkeypatch, synthetic_prices):
    from app.core import task_runner
    from app.services.risk_service import run_monte_carlo_simulation

    await _seed_database_portfolio(db_session, test_user, monkeypatch)
    seeded_holdings = [SimpleNamespace(symbol="HBL", sector="Banking", current_value=60000.0, allocation_pct=60.0), SimpleNamespace(symbol="OGDC", sector="Oil & Gas", current_value=40000.0, allocation_pct=40.0)]
    # Preserve the real dispatcher/task calculation; only poll storage is stubbed to
    # supply its result synchronously, as a completed worker would.
    calculated = run_monte_carlo_simulation(seeded_holdings, num_simulations=1200, horizon_days=10, seed=0)
    calculated.update(user_id=test_user.id, completed_at="2026-09-24T00:00:00Z")
    monkeypatch.setattr(task_runner, "dispatch_task", lambda *a, **k: SimpleNamespace(id="seeded-mc-job"))
    monkeypatch.setattr(task_runner, "get_local_job_result", lambda job_id: ("SUCCESS", calculated, None))
    start = await client.post("/api/v1/risk/monte-carlo", headers=auth_headers, json={"num_simulations": 1200, "horizon_days": 10, "seed": 0})
    assert start.status_code == 202, start.text
    assert start.json()["job_id"] == "seeded-mc-job"
    # route imports get_local_job_result directly; patch its module attribute.
    poll = await client.get("/api/v1/risk/monte-carlo/seeded-mc-job", headers=auth_headers)
    assert poll.status_code == 200, poll.text
    result = poll.json()
    assert result["status"] == "completed"
    assert result["method"] == "correlated_multivariate_gbm"
    assert result["portfolio_value"] == 100000
    assert result["tail_estimate_reliable"] is True
    assert len(result["paths_sample"][0]) == 11


def test_risk_response_handles_zero_value_and_unavailable_symbols(monkeypatch):
    from app.ml.serving.schemas import StressTestResponse
    from app.services import risk_service

    zero_stress = risk_service.run_stress_test(
        [SimpleNamespace(symbol="HBL", sector="Banking", current_value=0)], "2008_crash"
    )
    assert StressTestResponse(**zero_stress).status == "no_holdings"

    prices = np.linspace(100, 120, 80)
    monkeypatch.setattr(risk_service, "_get_price_pivot", lambda: pd.DataFrame({"HBL": prices}, index=pd.date_range("2025-01-01", periods=80)))
    result = risk_service.calculate_var(
        [SimpleNamespace(symbol="HBL", current_value=60000, allocation_pct=60), SimpleNamespace(symbol="MISSING", current_value=40000, allocation_pct=40)],
        confidence=95,
        horizon="1D",
    )
    assert result["status"] == "partial"
    assert result["symbols_excluded"] == ["MISSING"]
    assert result["covered_portfolio_value"] == 60000
