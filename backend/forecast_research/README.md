# Isolated PSX forecast research pipeline

This directory is a standalone prototype. It does not import or write to the existing application/model pipeline. Data, fitted models, forecast snapshots, and the SQLite prediction ledger stay under this directory.

## Scope

- One fixed XGBoost multiclass classifier per horizon (1, 3, and 7 PSX trading sessions).
- Bullish / neutral / bearish labels use the point-in-time 20-session realized volatility, scaled by `0.5 * sqrt(horizon)`. This is a classification target, not a buy/sell instruction.
- Features are built from past OHLCV only. Peer-market return is a same-date median of available per-symbol returns, excluding the predicted symbol; it is not represented as KSE-100.
- Time split: train through 2023-12-31, calibrate probabilities on 2024, and use 2025 onward as the historical holdout. Horizon rows are purged at split boundaries so labels cannot use prices from the next period. The project has prior experiments covering overlapping dates, so this is not a pristine research holdout.
- Final model artifacts are then refit on all eligible observations to support shadow inference. Holdout metrics are from the pre-refit model.
- Scheduled CLI inference stores versioned forecasts in the local SQLite ledger. A separate outcome updater fills actual outcomes when the horizon elapses.

## Run

From `backend/` with the project environment:

```powershell
python -m forecast_research.pipeline fetch
python -m forecast_research.pipeline evaluate
python -m forecast_research.pipeline train
python -m forecast_research.pipeline forecast
python -m forecast_research.pipeline settle
```

`forecast` accepts optional symbols (`--symbols HBL,OGDC`) and as-of date (`--as-of YYYY-MM-DD`). For scheduling, invoke `forecast` once after the PSX close on each trading day using Task Scheduler/cron. There is intentionally no route wired into the existing API.

## Data limitations

The public `psxdata` client returns OHLCV and an anomaly flag, not a verified total-return adjusted close or point-in-time constituent history. The pipeline flags source anomalies and extreme close-to-close jumps and excludes affected feature/label windows; this reduces obvious corporate-action contamination but cannot replace authoritative split/bonus/dividend adjustment data. Universe is the symbols present in this repository's raw OHLCV directory at fetch time, so historical survivorship bias remains. Result should be treated as a local shadow model pending point-in-time universe and corporate-action adjustment data.

## Research notes

- PSX official historical market-data page: https://dps.psx.com.pk/historical
- `psxdata` client documentation: https://psxdata.readthedocs.io/en/latest/api/client/
- scikit-learn time-series split guidance: https://scikit-learn.org/stable/modules/cross_validation.html#time-series-split
- Probability calibration guidance: https://scikit-learn.org/stable/modules/calibration.html
- Backtest selection bias / multiple testing: Bailey et al., https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2308659 and Harvey, Liu & Zhu, https://www.nber.org/papers/w20592

This experiment uses no broad model/configuration sweep: the prior repository already tested GRU windows, XGBoost feature ablations/ensembles, binary extreme-return ranking, and LightGBM/Ridge horizon variants. This pipeline changes the forecast target to 1/3/7-session volatility-scaled three-class outcomes and sets one fixed model recipe before evaluating.
