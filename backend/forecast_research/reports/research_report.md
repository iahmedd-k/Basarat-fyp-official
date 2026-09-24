# Standalone PSX forecast model: research report

**Decision:** keep this as an isolated shadow prototype. Do not select it as the production recommendation model yet.

## What was built

- Separate Python module, data cache, model artifact directory, forecast JSON, and SQLite ledger under `backend/forecast_research/`.
- XGBoost multiclass models for 1, 3, and 7 PSX trading sessions; output labels are bearish, neutral, bullish.
- Sixteen point-in-time OHLCV and peer-market features. The peer return feature is computed from same-date, leave-one-symbol-out stock returns and rolled across dates; it is not mislabeled as KSE-100.
- The neutral band is `±0.5 × prior 20-session daily volatility × sqrt(horizon)`. This creates an adaptive classification target; it is not a tested trading threshold.
- Fixed model settings; no broad search, GRU repetition, feature-ablation sweep, binary extreme-return task, or model ensemble.
- Time protocol: train through 2024-12-31, fit one scalar temperature on 2025, test on 2026-01-01 through the latest data date. The final saved models are the same fitted models used for that evaluation; there is no post-calibration refit. The horizon-length rows immediately before each boundary are purged.
- XGBoost per-class additive contributions produce three descriptive model drivers per forecast. They explain class-score movement; they are not causal explanations.
- Versioned artifacts are immutable under `models/versions/`. Latest forecasts are stored in the SQLite ledger with probability vector, selected class, confidence, drivers, `as_of`, target date, freshness, and `model_version`. `settle` fills actual outcomes after enough future data arrives.
- Symbols without a clean feature row within five market sessions of the requested cutoff are omitted, rather than shown with stale predictions.

## Data and results

PSX historical OHLCV was fetched through the third-party `psxdata` client for 103 symbols already present in the repository's raw OHLCV directory. The normalized extract contains 161,271 rows dated 2020-01-01 through 2026-09-23. Input rows were sorted chronologically, de-duplicated, and source anomaly flags preserved. The pipeline also flags close-to-close jumps above 15%; samples with flagged anomalies in the feature lookback or outcome interval are excluded.

| Horizon | Train rows | Calibration rows | Holdout rows | XGBoost macro-F1 | All-neutral macro-F1 | XGBoost balanced accuracy | Chance balanced accuracy |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 session | 92,871 | 23,337 | 17,200 | 0.3500 | 0.2127 | 0.3816 | 0.3333 |
| 3 sessions | 92,245 | 23,083 | 17,167 | 0.3335 | 0.2060 | 0.3705 | 0.3333 |
| 7 sessions | 91,028 | 22,584 | 17,103 | 0.3443 | 0.2103 | 0.3642 | 0.3333 |

The model beats the all-neutral classifier on macro-F1 and is only modestly above chance on balanced accuracy. This is not strong predictive performance. The model's directional recall and confusion matrices are in `evaluation.json`; they show that it misses many bullish and bearish outcomes. The 2026 year-to-date results are the holdout period, not an additional independent year split.

Latest shadow run: **291 forecasts** (97 eligible symbols × 3 horizons), through 2026-09-23, stored under model version `psx-volband-xgb-v1-train20241231-6162441e17`. Six symbols (BNWM, IBFL, JDWS, PKGS, RMPL, SRVI) were omitted because no clean feature row was within five market sessions. Probabilities sum to 1 and each forecast contains three drivers. `target_date` is empty until later market data establishes the next horizon dates. The 291 records remain unsettled until the horizon elapses and actual data is fetched.

Class recall makes the main weakness concrete: bearish / neutral / bullish recall is 0.135 / 0.856 / 0.153 at 1 session, 0.118 / 0.830 / 0.163 at 3 sessions, and 0.182 / 0.757 / 0.154 at 7 sessions. The model is substantially better at identifying neutral outcomes than either directional class.

## Important limitations

1. **No corporate-action-adjusted total return.** PSX history provides raw OHLCV here. Flagging extreme jumps reduces obvious contamination but does not correctly adjust dividends, bonus issues, splits, or rights issues.
2. **Survivorship and coverage bias.** The symbol set is the repository's current raw-data files, not historical point-in-time constituents; delisted and inactive companies are not represented.
3. **Research contamination.** The 2026 dates overlap periods examined in prior repository experiments. The fixed protocol avoids tuning against this holdout in this run, but it is not virgin out-of-sample evidence.
4. **A deliberately old training cutoff.** The evaluated/calibrated artifact was trained only through 2024 to keep calibration and evaluation aligned. It is used for a shadow forecast as of 2026-09-23 but cannot learn 2025–2026 market changes. Retraining requires a new forward calibration and a subsequent untouched evaluation window.
5. **No economic-value test.** This is classification evaluation only. There is no execution simulation, spread/commission/tax modeling, liquidity constraint, portfolio construction, or comparison of net returns.
6. **Calibration has limits.** Temperature scaling was fitted on 2025 and applied unchanged to 2026. It makes probability scoring reproducible; it does not establish calibration for future regimes.
7. **No application endpoint or authenticated watchlist integration.** The prototype deliberately stays separate; the Android app cannot consume it through the existing API without a later, explicit integration task.

## Research choices and references

The evaluation uses chronological splits, purges horizon-overlapping labels at split boundaries, and reports macro-F1, balanced accuracy, classwise precision/recall, log loss, Brier score, and a simple baseline. This avoids selecting hyperparameters on randomly shuffled financial rows. Repeated historical model/configuration searches can inflate reported performance, which is why this implementation fixes one model recipe rather than repeating the earlier sweeps.

- PSX official historical data portal: https://dps.psx.com.pk/historical
- `psxdata` client documentation: https://psxdata.readthedocs.io/en/latest/api/client/
- scikit-learn time-series validation documentation: https://scikit-learn.org/stable/modules/cross_validation.html#time-series-split
- scikit-learn probability calibration documentation: https://scikit-learn.org/stable/modules/calibration.html
- Bailey et al., *The Probability of Backtest Overfitting*: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253
- Harvey, Liu & Zhu, *…and the Cross-Section of Expected Returns*: https://www.nber.org/papers/w20592

## Run locally

From `backend/`:

```powershell
python -m forecast_research.pipeline fetch
python -m forecast_research.pipeline evaluate
python -m forecast_research.pipeline train
python -m forecast_research.pipeline forecast
python -m forecast_research.pipeline settle
```

Run `forecast` after the PSX close using Windows Task Scheduler or cron. That schedule has not been installed, and no live API route was added.
