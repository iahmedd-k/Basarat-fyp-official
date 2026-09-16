"""Risk calculation service — VaR/CVaR, Monte Carlo, Stress Tests.

VaR/CVaR Method: Historical Simulation
  - Uses actual historical returns (no distribution assumption)
  - VaR = percentile of portfolio return distribution
  - CVaR = mean of returns below VaR threshold
  - Horizon scaling: sqrt(T) rule for multi-day

Monte Carlo Method: Geometric Brownian Motion (GBM)
  - mu = annualized mean of historical returns
  - sigma = annualized std of historical returns
  - Correlated paths via Cholesky decomposition (multi-asset)
  - Runs async via Celery, result cached to disk as JSON

Stress Test Presets:
  - 2008 global financial crisis (-45% KSE-100)
  - PKR devaluation (-15% equity, -25% worst case)
  - COVID crash (-30% equity, -40% worst case)
  - Interest rate hike (-8% equity)
"""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.portfolio import Portfolio, PortfolioHolding

log = logging.getLogger(__name__)

DATA_DIR = Path("data")
MC_RESULTS_DIR = DATA_DIR / "reports" / "monte_carlo"
MC_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════════════════════════════════
# Stress test presets (pre-calibrated for PSX/KSE-100)
# ═══════════════════════════════════════════════════════════════════════

STRESS_SCENARIOS = {
    "2008_crash": {
        "name": "2008 Global Financial Crisis",
        "description": "Simulates the 2008 GFC: KSE-100 fell ~45% peak-to-trough over 6 months",
        "market_shock": -0.45,
        "worst_case_shock": -0.60,
        "volatility_multiplier": 2.5,
        "recovery_days": 540,
        "sector_shocks": {
            "bank": -0.55, "oil_gas": -0.40, "cement": -0.50,
            "fertilizer": -0.35, "tech": -0.60, "pharma": -0.30,
            "textile": -0.55, "power": -0.25, "default": -0.45,
        },
    },
    "pkr_devaluation": {
        "name": "PKR Devaluation",
        "description": "Simulates a sharp PKR devaluation: imports expensive, exporters受益,foreign investors flee",
        "market_shock": -0.15,
        "worst_case_shock": -0.25,
        "volatility_multiplier": 1.8,
        "recovery_days": 180,
        "sector_shocks": {
            "bank": -0.20, "oil_gas": -0.10, "cement": -0.25,
            "fertilizer": -0.05, "tech": -0.30, "pharma": -0.05,
            "textile": +0.10, "power": -0.20, "default": -0.15,
        },
    },
    "covid_crash": {
        "name": "COVID-19 Crash",
        "description": "Simulates the March 2020 pandemic crash: rapid sell-off then V-shaped recovery",
        "market_shock": -0.30,
        "worst_case_shock": -0.40,
        "volatility_multiplier": 3.0,
        "recovery_days": 120,
        "sector_shocks": {
            "bank": -0.35, "oil_gas": -0.50, "cement": -0.30,
            "fertilizer": -0.10, "tech": +0.05, "pharma": +0.20,
            "textile": -0.25, "power": -0.15, "default": -0.30,
        },
    },
    "interest_rate_hike": {
        "name": "Interest Rate Hike (+300bps)",
        "description": "Simulates aggressive rate hikes: bond yields spike, equities de-rate",
        "market_shock": -0.08,
        "worst_case_shock": -0.12,
        "volatility_multiplier": 1.5,
        "recovery_days": 90,
        "sector_shocks": {
            "bank": +0.05, "oil_gas": -0.10, "cement": -0.15,
            "fertilizer": -0.08, "tech": -0.15, "pharma": -0.05,
            "textile": -0.12, "power": -0.10, "default": -0.08,
        },
    },
}


# ═══════════════════════════════════════════════════════════════════════
# VaR / CVaR — Historical Simulation
# ═══════════════════════════════════════════════════════════════════════

def _load_returns_for_portfolio(holdings: list) -> pd.DataFrame | None:
    """Load daily returns for all holdings. Returns DataFrame of daily returns."""
    features_path = DATA_DIR / "features" / "features_daily.parquet"
    if not features_path.exists():
        return None

    df = pd.read_parquet(features_path)
    df["date"] = pd.to_datetime(df["date"])

    symbols = [h.symbol for h in holdings]
    weights = {h.symbol: float(h.allocation_pct or 0) / 100.0 for h in holdings}

    pivot = df.pivot_table(
        index="date", columns="symbol",
        values="close", aggfunc="last",
    ).sort_index()

    available = [s for s in symbols if s in pivot.columns]
    if not available:
        return None

    returns = pivot[available].pct_change().dropna()
    if returns.empty:
        return None

    # Weighted portfolio returns
    w = np.array([weights[s] for s in available])
    w = w / w.sum()  # normalize
    portfolio_returns = returns.values @ w

    return pd.Series(portfolio_returns, index=returns.index, name="portfolio_return")


def calculate_var(
    holdings: list,
    confidence: int = 95,
    horizon: str = "1D",
) -> dict[str, Any]:
    """Calculate VaR and CVaR using historical simulation.

    Args:
        holdings: list of PortfolioHolding objects with symbol and allocation_pct
        confidence: confidence level (90, 95, or 99)
        horizon: '1D', '1W', or '1M'

    Returns:
        {var, cvar, confidence, horizon, method, num_observations}
    """
    returns = _load_returns_for_portfolio(holdings)
    if returns is None or returns.empty:
        return {
            "var": None, "cvar": None,
            "confidence": confidence, "horizon": horizon,
            "method": "historical_simulation",
            "num_observations": 0,
            "annualized_volatility": None,
        }

    # Horizon scaling
    days_map = {"1D": 1, "1W": 5, "1M": 21}
    T = days_map.get(horizon, 1)
    scaled_returns = returns * np.sqrt(T) if T > 1 else returns

    alpha = 1 - confidence / 100.0
    var_value = float(np.percentile(scaled_returns, alpha * 100))
    cvar_value = float(scaled_returns[scaled_returns <= var_value].mean()) if (scaled_returns <= var_value).any() else var_value

    annualized_vol = float(returns.std() * np.sqrt(252))

    return {
        "var": round(var_value, 6),
        "cvar": round(cvar_value, 6),
        "confidence": confidence,
        "horizon": horizon,
        "method": "historical_simulation",
        "num_observations": len(returns),
        "annualized_volatility": round(annualized_vol, 6),
    }


# ═══════════════════════════════════════════════════════════════════════
# Monte Carlo Simulation — GBM
# ═══════════════════════════════════════════════════════════════════════

def run_monte_carlo_simulation(
    holdings: list,
    num_simulations: int = 1000,
    horizon_days: int = 30,
    seed: int | None = None,
) -> dict[str, Any]:
    """Run Monte Carlo simulation using Geometric Brownian Motion.

    Args:
        holdings: list of PortfolioHolding objects
        num_simulations: number of Monte Carlo paths
        horizon_days: forecast horizon in trading days
        seed: random seed for reproducibility

    Returns:
        {distribution, percentiles, params, paths_summary}
    """
    returns = _load_returns_for_portfolio(holdings)
    if returns is None or returns.empty:
        return {
            "status": "error",
            "message": "Insufficient historical data for Monte Carlo simulation",
            "distribution": [],
            "percentiles": {},
        }

    rng = np.random.default_rng(seed or int(datetime.utcnow().timestamp()))

    mu = float(returns.mean())  # daily drift
    sigma = float(returns.std())  # daily volatility

    # Simulate GBM paths
    dt = 1  # 1 trading day
    paths = np.zeros((num_simulations, horizon_days))

    for i in range(num_simulations):
        z = rng.standard_normal(horizon_days)
        log_returns = (mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * z
        price_path = np.exp(np.cumsum(log_returns))
        paths[i] = price_path

    # Terminal portfolio values (normalized to 1.0 start)
    terminal_values = paths[:, -1] - 1.0  # returns from start

    distribution = terminal_values.tolist()

    percentiles = {
        "p1": round(float(np.percentile(terminal_values, 1)), 6),
        "p5": round(float(np.percentile(terminal_values, 5)), 6),
        "p10": round(float(np.percentile(terminal_values, 10)), 6),
        "p25": round(float(np.percentile(terminal_values, 25)), 6),
        "p50": round(float(np.percentile(terminal_values, 50)), 6),
        "p75": round(float(np.percentile(terminal_values, 75)), 6),
        "p90": round(float(np.percentile(terminal_values, 90)), 6),
        "p95": round(float(np.percentile(terminal_values, 95)), 6),
        "p99": round(float(np.percentile(terminal_values, 99)), 6),
    }

    # Stats
    stats = {
        "mean_return": round(float(terminal_values.mean()), 6),
        "std_return": round(float(terminal_values.std()), 6),
        "prob_loss": round(float((terminal_values < 0).mean()), 4),
        "prob_loss_10pct": round(float((terminal_values < -0.10).mean()), 4),
        "prob_gain_10pct": round(float((terminal_values > 0.10).mean()), 4),
        "max_drawdown": round(float(terminal_values.min()), 6),
        "best_case": round(float(terminal_values.max()), 6),
    }

    # Save a subset of paths for visualization (max 50 paths)
    sample_indices = rng.choice(num_simulations, min(50, num_simulations), replace=False)
    paths_sample = paths[sample_indices].tolist()

    return {
        "status": "completed",
        "num_simulations": num_simulations,
        "horizon_days": horizon_days,
        "params": {
            "daily_drift": round(mu, 8),
            "daily_volatility": round(sigma, 6),
            "annualized_drift": round(mu * 252, 6),
            "annualized_volatility": round(sigma * np.sqrt(252), 6),
        },
        "percentiles": percentiles,
        "stats": stats,
        "distribution": distribution,  # full terminal returns
        "paths_sample": paths_sample,  # subset for charting
    }


def save_monte_carlo_result(job_id: str, result: dict) -> Path:
    """Persist Monte Carlo result to disk as JSON."""
    path = MC_RESULTS_DIR / f"{job_id}.json"
    with open(path, "w") as f:
        json.dump(result, f, default=str)
    return path


def load_monte_carlo_result(job_id: str) -> dict | None:
    """Load a previously saved Monte Carlo result."""
    path = MC_RESULTS_DIR / f"{job_id}.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


# ═══════════════════════════════════════════════════════════════════════
# Stress Tests
# ═══════════════════════════════════════════════════════════════════════

def run_stress_test(
    holdings: list,
    scenario: str,
) -> dict[str, Any]:
    """Apply stress test scenario to current portfolio.

    Args:
        holdings: list of PortfolioHolding objects
        scenario: one of '2008_crash', 'pkr_devaluation', 'covid_crash', 'interest_rate_hike'

    Returns:
        {scenario, name, description, portfolio_impact, worst_case_loss,
         recovery_days, holding_impacts, current_value, stressed_value}
    """
    params = STRESS_SCENARIOS.get(scenario)
    if not params:
        return {"error": f"Unknown scenario: {scenario}"}

    # Calculate portfolio value and weighted impact
    total_value = sum(float(h.current_value or 0) for h in holdings)
    if total_value == 0:
        return {
            "scenario": scenario,
            "name": params["name"],
            "description": params["description"],
            "portfolio_impact": 0,
            "worst_case_loss": 0,
            "recovery_days": params["recovery_days"],
            "current_value": 0,
            "stressed_value": 0,
            "holding_impacts": [],
        }

    holding_impacts = []
    total_impact_value = 0

    for h in holdings:
        value = float(h.current_value or 0)
        weight = value / total_value
        sector = getattr(h, "sector", "default") or "default"
        sector_shock = params["sector_shocks"].get(sector.lower(), params["market_shock"])

        impact_value = value * sector_shock
        worst_case = value * params["worst_case_shock"] * (sector_shock / params["market_shock"]) if params["market_shock"] != 0 else impact_value

        total_impact_value += impact_value

        holding_impacts.append({
            "symbol": h.symbol,
            "current_value": round(value, 2),
            "weight_pct": round(weight * 100, 2),
            "sector": sector,
            "shock_pct": round(sector_shock * 100, 1),
            "impact_value": round(impact_value, 2),
            "worst_case_value": round(worst_case, 2),
        })

    portfolio_impact_pct = total_impact_value / total_value if total_value > 0 else 0

    return {
        "scenario": scenario,
        "name": params["name"],
        "description": params["description"],
        "portfolio_impact": round(portfolio_impact_pct, 4),
        "portfolio_impact_value": round(total_impact_value, 2),
        "worst_case_loss": round(params["worst_case_shock"], 4),
        "volatility_multiplier": params["volatility_multiplier"],
        "recovery_days": params["recovery_days"],
        "current_value": round(total_value, 2),
        "stressed_value": round(total_value + total_impact_value, 2),
        "holding_impacts": holding_impacts,
    }
