"""Portfolio risk calculations.

Historical VaR uses overlapping, compounded holding-period returns. Monte Carlo
uses a correlated multivariate GBM as an explicitly simplified scenario model.
The stress presets are illustrative shocks, not calibrated or replayed historical
events; they must not be presented as forecasts.
"""

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)
DATA_DIR = Path("data")
MC_RESULTS_DIR = DATA_DIR / "reports" / "monte_carlo"
MC_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

STRESS_SCENARIOS = {
    "2008_crash": {"name": "Illustrative broad market crash", "description": "Illustrative one-step sector shocks; not a reconstruction of 2008.", "market_shock": -.45, "worst_case_shock": -.60, "volatility_multiplier": 2.5, "recovery_days": 540, "sector_shocks": {"bank": -.55, "oil_gas": -.40, "cement": -.50, "fertilizer": -.35, "tech": -.60, "pharma": -.30, "textile": -.55, "power": -.25}},
    "pkr_devaluation": {"name": "Illustrative PKR devaluation", "description": "Illustrative sector shocks; not an empirically calibrated forecast.", "market_shock": -.15, "worst_case_shock": -.25, "volatility_multiplier": 1.8, "recovery_days": 180, "sector_shocks": {"bank": -.20, "oil_gas": -.10, "cement": -.25, "fertilizer": -.05, "tech": -.30, "pharma": -.05, "textile": .10, "power": -.20}},
    "covid_crash": {"name": "Illustrative pandemic sell-off", "description": "Illustrative one-step shocks; not a replay of March 2020.", "market_shock": -.30, "worst_case_shock": -.40, "volatility_multiplier": 3.0, "recovery_days": 120, "sector_shocks": {"bank": -.35, "oil_gas": -.50, "cement": -.30, "fertilizer": -.10, "tech": .05, "pharma": .20, "textile": -.25, "power": -.15}},
    "interest_rate_hike": {"name": "Illustrative interest rate shock", "description": "Illustrative sector shocks for a rate increase; not a forecast.", "market_shock": -.08, "worst_case_shock": -.12, "volatility_multiplier": 1.5, "recovery_days": 90, "sector_shocks": {"bank": .05, "oil_gas": -.10, "cement": -.15, "fertilizer": -.08, "tech": -.15, "pharma": -.05, "textile": -.12, "power": -.10}},
}

_PRICE_PIVOT_CACHE: pd.DataFrame | None = None
_PRICE_PIVOT_CACHE_KEY: tuple[int, int] | None = None


def _get_price_pivot() -> pd.DataFrame | None:
    """Load daily adjusted closes (fall back to close) and invalidate on file change."""
    global _PRICE_PIVOT_CACHE, _PRICE_PIVOT_CACHE_KEY
    path = DATA_DIR / "features" / "features_daily.parquet"
    if not path.exists():
        return None
    stat = path.stat()
    key = (stat.st_mtime_ns, stat.st_size)
    if _PRICE_PIVOT_CACHE is not None and _PRICE_PIVOT_CACHE_KEY == key:
        return _PRICE_PIVOT_CACHE
    frame = pd.read_parquet(path)
    frame["date"] = pd.to_datetime(frame["date"])
    price_col = next((c for c in ("adjusted_close", "adj_close", "close") if c in frame.columns), None)
    if price_col is None:
        return None
    _PRICE_PIVOT_CACHE = frame.pivot_table(index="date", columns="symbol", values=price_col, aggfunc="last").sort_index()
    _PRICE_PIVOT_CACHE_KEY = key
    return _PRICE_PIVOT_CACHE


def _holdings_matrix(holdings: list) -> tuple[pd.DataFrame | None, np.ndarray, list[str], list[str], float]:
    pivot = _get_price_pivot()
    symbols = [str(getattr(h, "symbol", "") or "").strip() for h in holdings]
    values = np.array([max(float(getattr(h, "current_value", 0) or 0), 0.0) for h in holdings], dtype=float)
    total_value = float(values.sum())
    weights = values / total_value if total_value > 0 else np.zeros(len(values))
    available = [i for i, symbol in enumerate(symbols) if symbol and pivot is not None and symbol in pivot.columns and values[i] > 0]
    excluded = [symbols[i] for i in range(len(symbols)) if i not in available]
    if not available or pivot is None:
        return None, np.array([]), [], excluded, total_value
    columns = list(dict.fromkeys(symbols[i] for i in available))
    price_slice = pivot[columns].replace([np.inf, -np.inf], np.nan)
    returns = price_slice.pct_change(fill_method=None).dropna(how="any")
    weights_by_symbol = {symbols[i]: weights[i] for i in available}
    covered_weight = sum(weights_by_symbol.values())
    if returns.empty or covered_weight <= 0:
        return None, np.array([]), columns, excluded, total_value
    local_weights = np.array([weights_by_symbol[s] / covered_weight for s in columns], dtype=float)
    return returns, local_weights, columns, excluded, total_value


def _empty_risk(status: str, message: str, confidence: int, horizon: str, total: float, used: list[str], excluded: list[str]) -> dict[str, Any]:
    return {"status": status, "message": message, "var": None, "cvar": None, "confidence": confidence, "horizon": horizon, "method": "historical_simulation_compounded_overlapping", "num_observations": 0, "annualized_volatility": None, "portfolio_value": round(total, 2), "covered_portfolio_value": 0.0, "currency": "PKR", "symbols_used": used, "symbols_excluded": excluded, "data_as_of": None}


def calculate_var(holdings: list, confidence: int = 95, horizon: str = "1D") -> dict[str, Any]:
    returns, weights, used, excluded, total_value = _holdings_matrix(holdings)
    if total_value <= 0:
        return _empty_risk("no_holdings", "Portfolio has no positive market value.", confidence, horizon, total_value, used, excluded)
    if returns is None:
        return _empty_risk("insufficient_data", "No complete price history for the valued holdings.", confidence, horizon, total_value, used, excluded)
    horizon_days = {"1D": 1, "1W": 5, "1M": 21}.get(horizon, 1)
    # Each asset's buy-and-hold return is compounded over each rolling horizon;
    # current portfolio weights are held fixed at the start of each observation.
    if horizon_days == 1:
        asset_horizon = returns
    else:
        asset_horizon = (1.0 + returns).rolling(horizon_days).apply(np.prod, raw=True) - 1.0
        asset_horizon = asset_horizon.dropna(how="any")
    portfolio = pd.Series(asset_horizon.to_numpy() @ weights, index=asset_horizon.index)
    if portfolio.empty:
        return _empty_risk("insufficient_data", f"At least {horizon_days + 1} complete price rows are required.", confidence, horizon, total_value, used, excluded)
    minimum_observations = 100 if confidence == 99 else 30
    if len(portfolio) < minimum_observations:
        result = _empty_risk("insufficient_data", f"At least {minimum_observations} horizon observations are required for a stable {confidence}% tail estimate.", confidence, horizon, total_value, used, excluded)
        result.update({"num_observations": int(len(portfolio)), "covered_portfolio_value": round(float(sum(max(float(getattr(h, "current_value", 0) or 0), 0) for h in holdings if getattr(h, "symbol", "") in used)), 2), "data_as_of": str(returns.index.max().date())})
        return result
    alpha = 1 - confidence / 100.0
    threshold = float(np.quantile(portfolio, alpha, method="linear"))
    tail = portfolio[portfolio <= threshold]
    covered_value = total_value * float(sum(max(float(getattr(h, "current_value", 0) or 0), 0) for h in holdings if getattr(h, "symbol", "") in used)) / total_value
    return {"status": "partial" if excluded else "available", "message": "Some valued holdings lack usable history; risk reflects covered holdings only." if excluded else "Risk estimated from complete historical observations.", "var": round(threshold, 6), "cvar": round(float(tail.mean()), 6), "confidence": confidence, "horizon": horizon, "method": "historical_simulation_compounded_overlapping", "num_observations": int(len(portfolio)), "annualized_volatility": round(float((returns.to_numpy() @ weights).std(ddof=1) * np.sqrt(252)), 6), "portfolio_value": round(total_value, 2), "covered_portfolio_value": round(covered_value, 2), "var_loss_amount": round(max(0.0, -threshold) * covered_value, 2), "cvar_loss_amount": round(max(0.0, -float(tail.mean())) * covered_value, 2), "currency": "PKR", "symbols_used": used, "symbols_excluded": excluded, "data_as_of": str(returns.index.max().date()), "lookback_start": str(returns.index.min().date())}


def run_monte_carlo_simulation(holdings: list, num_simulations: int = 1000, horizon_days: int = 30, seed: int | None = None) -> dict[str, Any]:
    returns, weights, symbols, excluded, portfolio_value = _holdings_matrix(holdings)
    if portfolio_value <= 0 or returns is None:
        return {"status": "error", "message": "Insufficient valued holdings or complete historical data.", "num_simulations": num_simulations, "horizon_days": horizon_days, "user_id": None, "symbols_used": symbols, "symbols_excluded": excluded}
    if len(returns) < 30:
        return {"status": "error", "message": "At least 30 complete daily observations are required.", "num_simulations": num_simulations, "horizon_days": horizon_days, "user_id": None, "symbols_used": symbols, "symbols_excluded": excluded}
    rng = np.random.default_rng(seed)
    sample = returns.to_numpy(dtype=float)
    mu = sample.mean(axis=0)
    covariance = np.atleast_2d(np.cov(sample, rowvar=False, ddof=1))
    covariance = (covariance + covariance.T) / 2
    # Numerical jitter allows valid simulation with collinear asset series.
    eigval, eigvec = np.linalg.eigh(covariance)
    root_cov = eigvec @ np.diag(np.sqrt(np.maximum(eigval, 0)))
    drift = mu - 0.5 * np.diag(covariance)
    n_assets = len(symbols)
    factors = np.ones((num_simulations, n_assets), dtype=float)
    paths = np.empty((num_simulations, horizon_days + 1), dtype=float)
    paths[:, 0] = 1.0
    for day in range(horizon_days):
        z = rng.standard_normal((num_simulations, n_assets))
        log_returns = drift + z @ root_cov.T
        factors *= np.exp(log_returns)
        paths[:, day + 1] = factors @ weights
    terminal = paths[:, -1] - 1.0
    running_peak = np.maximum.accumulate(paths, axis=1)
    max_drawdowns = np.min(paths / running_peak - 1.0, axis=1)
    percentiles = {f"p{p}": round(float(np.percentile(terminal, p)), 6) for p in (1, 5, 10, 25, 50, 75, 90, 95, 99)}
    return {"status": "completed", "num_simulations": num_simulations, "horizon_days": horizon_days, "portfolio_value": round(portfolio_value, 2), "currency": "PKR", "method": "correlated_multivariate_gbm", "assumptions": "Constant estimated drift/covariance, Gaussian independent daily innovations, fixed initial share quantities; excludes fees, taxes, liquidity and regime changes.", "data_as_of": str(returns.index.max().date()), "symbols_used": symbols, "symbols_excluded": excluded, "params": {"daily_drift": {s: round(float(m), 8) for s, m in zip(symbols, mu)}, "daily_covariance": covariance.tolist(), "annualized_volatility": {s: round(float(np.sqrt(max(covariance[i, i], 0) * 252)), 6) for i, s in enumerate(symbols)}}, "percentiles": percentiles, "stats": {"mean_return": round(float(terminal.mean()), 6), "std_return": round(float(terminal.std()), 6), "prob_loss": round(float((terminal < 0).mean()), 4), "max_drawdown": round(float(max_drawdowns.min()), 6), "mean_max_drawdown": round(float(max_drawdowns.mean()), 6), "tail_observations_p1": max(1, int(np.floor(num_simulations * .01))), "best_case": round(float(terminal.max()), 6)}, "paths_sample": paths[rng.choice(num_simulations, min(50, num_simulations), replace=False)].tolist(), "tail_estimate_reliable": num_simulations >= 1000}


def save_monte_carlo_result(job_id: str, result: dict) -> Path:
    path = MC_RESULTS_DIR / f"{job_id}.json"
    path.write_text(json.dumps(result, default=str))
    return path


def load_monte_carlo_result(job_id: str) -> dict | None:
    path = MC_RESULTS_DIR / f"{job_id}.json"
    return json.loads(path.read_text()) if path.exists() else None


def _normalize_sector(sector: str) -> str:
    value = " ".join(str(sector or "").lower().replace("&", "and").replace("_", " ").split())
    if any(k in value for k in ("bank", "financial", "commercial")): return "bank"
    if any(k in value for k in ("oil", "gas", "exploration", "refinery")): return "oil_gas"
    if "cement" in value: return "cement"
    if "fertili" in value: return "fertilizer"
    if any(k in value for k in ("technology", "tech", "software")): return "tech"
    if any(k in value for k in ("pharma", "pharmaceutical")): return "pharma"
    if "textile" in value: return "textile"
    if any(k in value for k in ("power", "electric", "utility")): return "power"
    return "default"


def run_stress_test(holdings: list, scenario: str) -> dict[str, Any]:
    params = STRESS_SCENARIOS.get(scenario)
    if not params:
        return {"error": f"Unknown scenario: {scenario}"}
    total = sum(max(float(getattr(h, "current_value", 0) or 0), 0.0) for h in holdings)
    impacts = []
    impact_total = 0.0
    for h in holdings:
        value = max(float(getattr(h, "current_value", 0) or 0), 0.0)
        if value == 0: continue
        sector = getattr(h, "sector", "default") or "default"
        shock = params["sector_shocks"].get(_normalize_sector(sector), params["market_shock"])
        impact = value * shock
        worst_impact = value * params["worst_case_shock"]
        impact_total += impact
        impacts.append({"symbol": getattr(h, "symbol", ""), "current_value": round(value, 2), "weight_pct": round(value / total * 100, 2) if total else 0, "sector": sector, "shock_pct": round(shock * 100, 1), "impact_value": round(impact, 2), "worst_case_impact_value": round(worst_impact, 2)})
    return {"status": "available" if total > 0 else "no_holdings", "scenario": scenario, "name": params["name"], "description": params["description"], "method": "illustrative_one_step_sector_shock", "portfolio_impact": round(impact_total / total, 6) if total else 0.0, "portfolio_impact_value": round(impact_total, 2), "worst_case_loss": params["worst_case_shock"], "worst_case_loss_value": round(total * params["worst_case_shock"], 2), "volatility_multiplier": params["volatility_multiplier"], "recovery_days": params["recovery_days"], "assumption_note": "Volatility multiplier and recovery days are scenario labels only; neither is simulated or inferred from portfolio data.", "current_value": round(total, 2), "stressed_value": round(total + impact_total, 2), "currency": "PKR", "holding_impacts": impacts}
