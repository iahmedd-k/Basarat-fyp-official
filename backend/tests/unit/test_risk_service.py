"""Unit tests for Risk Service, VaR, Monte Carlo, and Stress Testing."""

from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
import pandas as pd
import pytest

from app.services.risk_service import (
    calculate_var,
    run_monte_carlo_simulation,
    run_stress_test,
    _normalize_sector,
)


class TestRiskCalculations:
    def _make_mock_price_pivot(self):
        dates = pd.date_range("2025-01-01", periods=120, freq="B")
        rng = np.random.default_rng(42)
        p_ogdc = 100 * np.exp(np.cumsum(rng.normal(0.0005, 0.015, 120)))
        p_engro = 250 * np.exp(np.cumsum(rng.normal(0.0003, 0.012, 120)))
        p_hbl = 120 * np.exp(np.cumsum(rng.normal(-0.0002, 0.018, 120)))

        df = pd.DataFrame({
            "OGDC": p_ogdc,
            "ENGRO": p_engro,
            "HBL": p_hbl,
        }, index=dates)
        return df

    def test_var_and_cvar_positive_holdings(self):
        pivot = self._make_mock_price_pivot()
        holdings = [
            SimpleNamespace(symbol="OGDC", sector="Oil & Gas Exploration", current_value=100000.0, allocation_pct=50.0),
            SimpleNamespace(symbol="ENGRO", sector="Fertilizer", current_value=100000.0, allocation_pct=50.0),
        ]

        with patch("app.services.risk_service._get_price_pivot", return_value=pivot):
            res_95 = calculate_var(holdings, confidence=95, horizon="1D")
            assert res_95["status"] == "available"
            assert res_95["var"] is not None
            assert res_95["cvar"] is not None
            assert res_95["var"] < 0  # VaR return is negative quantile
            assert res_95["cvar"] <= res_95["var"]  # CVaR is in deeper tail
            assert res_95["var_loss_amount"] > 0
            assert res_95["portfolio_value"] == 200000.0

    def test_var_empty_holdings(self):
        res = calculate_var([], confidence=95, horizon="1D")
        assert res["status"] == "no_holdings"
        assert res["var"] is None
        assert res["portfolio_value"] == 0.0

    def test_monte_carlo_simulation_shrinkage_and_reproducibility(self):
        pivot = self._make_mock_price_pivot()
        holdings = [
            SimpleNamespace(symbol="OGDC", sector="Oil & Gas Exploration", current_value=50000.0, allocation_pct=50.0),
            SimpleNamespace(symbol="ENGRO", sector="Fertilizer", current_value=50000.0, allocation_pct=50.0),
        ]

        with patch("app.services.risk_service._get_price_pivot", return_value=pivot):
            res1 = run_monte_carlo_simulation(holdings, num_simulations=500, horizon_days=30, seed=123)
            res2 = run_monte_carlo_simulation(holdings, num_simulations=500, horizon_days=30, seed=123)

            assert res1["status"] == "completed"
            assert res1["num_simulations"] == 500
            assert res1["horizon_days"] == 30
            # Reproducibility via seed
            assert res1["percentiles"]["p50"] == res2["percentiles"]["p50"]
            assert res1["stats"]["mean_return"] == res2["stats"]["mean_return"]
            assert "p1" in res1["percentiles"]
            assert "p99" in res1["percentiles"]
            assert len(res1["paths_sample"]) <= 50

    def test_stress_test_expanded_sectors(self):
        holdings = [
            SimpleNamespace(symbol="INDU", sector="Automobile Assembler", current_value=100000.0),
            SimpleNamespace(symbol="EPCL", sector="Chemical", current_value=100000.0),
            SimpleNamespace(symbol="NESTLE", sector="Food & Personal Care Products", current_value=100000.0),
        ]

        res = run_stress_test(holdings, scenario="pkr_devaluation")
        assert res["status"] == "available"
        assert res["scenario"] == "pkr_devaluation"
        assert len(res["holding_impacts"]) == 3
        # Auto is -35% under PKR devaluation
        auto_impact = next(h for h in res["holding_impacts"] if h["symbol"] == "INDU")
        assert auto_impact["shock_pct"] == -35.0

        # Food is -5% under PKR devaluation (defensive pricing power)
        food_impact = next(h for h in res["holding_impacts"] if h["symbol"] == "NESTLE")
        assert food_impact["shock_pct"] == -5.0

    def test_normalize_sector_coverage(self):
        assert _normalize_sector("Automobile Assembler") == "auto"
        assert _normalize_sector("Chemicals & Synthetics") == "chemical"
        assert _normalize_sector("Food and Personal Care") == "food"
        assert _normalize_sector("Engineering & Cables") == "engineering"
        assert _normalize_sector("Life Insurance") == "insurance"
        assert _normalize_sector("Refinery Limited") == "refinery"
        assert _normalize_sector("Commercial Banks") == "bank"
