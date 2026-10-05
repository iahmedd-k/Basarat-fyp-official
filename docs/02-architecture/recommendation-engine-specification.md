# Recommendation pipeline review and validation contract

## Scope

The live implementation combines an XGBoost direction score, technical rules, and a small fundamental heuristic. Its composite score is a rules-based ranking, not an expected return, calibrated probability, or investment suitability assessment. ATR levels are volatility distances, not forecasts or guaranteed execution prices.

## Changes made in this revision

- The `final_v3` serving model now has an explicit class-ID mapping. Serving converts class probabilities by label and uses bullish probability minus bearish probability. It rejects missing mappings and feature-count mismatches.
- The ML component is suppressed for rows outside (or lacking proof of membership in) the same `is_primary_universe` liquidity population used to train the three-class production model.
- Serving no longer substitutes raw features or `0.5` values when a required cross-sectional rank is missing. It reports the ML component unavailable and exposes partial/insufficient-data status.
- The technical-indicator fallback was removed from the ML component so RSI/MACD/SMA do not get counted twice. Composite weights are renormalized over available components and returned with the response.
- The two-class binary Buy/Avoid retraining scripts now write to experiment directories. `run_ml_pipeline.py` remains the owner of the three-class `final_v3` serving artifacts, removing competing writers to one model path.
- Per-user weights are persisted in the user row. Requests must sum to 1, and list/detail/target-stop calculations use the saved weights.
- Cache keys include risk profile, sector, and weights. Personalized weights bypass the shared default cache. Redis results expire after 15 minutes; the versioned disk cache expires after the 4-hour refresh interval and older cache formats are rejected.
- The target-stop endpoint uses the same calculation and recommendation direction as the detail endpoint. The horizon is one trading week to match the model label horizon. HOLD has a symmetric ATR range without a directional stop.
- Error responses no longer include internal exception text. The API reports data status and the daily feature date when available.

## Validation required before calling signals decision-grade

These are research and data requirements, not values to guess in code:

1. Rebuild the model from the canonical training entry point and verify its exported class mapping and exact feature list match the serving artifacts.
2. Evaluate the complete API scoring rule in chronological, point-in-time walk-forward tests, with an embargo at least as long as the forward label horizon. Record all tried configurations; use a final untouched holdout for the chosen strategy.
3. Report class precision/recall, balanced accuracy, calibration curves/Brier or log loss, coverage by confidence bucket, and strategy returns after fees, slippage, liquidity limits, circuit limits, and market impact. Compare with simple PSX/index and no-trade baselines.
4. Select BUY/SELL thresholds and source weights only on a validation period, freeze them, and evaluate once on the untouched test period. The current `0.15` thresholds and default weights remain heuristic until this study is completed.
5. Replace single-metric P/E and trailing return rules with point-in-time, sector-relative valuation and quality data before describing that component as fundamental valuation. Until such data exists, treat it as an exploratory heuristic.
6. Add market-data source, observed-at timestamp, market session, and staleness policy to responses. Prices and ATR levels currently derive from the daily feature dataset.
7. Verify migration `j1k2l3m4n5o6` against the target local database before deployment. This task does not apply migrations to any external database.

## Research basis

- Scikit-learn explains that classifier probability outputs need calibration checks before they can be interpreted as empirical confidence: <https://scikit-learn.org/stable/modules/calibration.html>.
- Scikit-learn's time-series split keeps train dates before test dates and supports a gap between them: <https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html>.
- Bailey, Borwein, López de Prado, and Zhu describe why ordinary holdout testing can be unreliable after selecting among many backtests: <https://scholarworks.wmich.edu/math_pubs/42/>.
- XGBoost documents `XGBClassifier` probability outputs and model metadata; serving must preserve and verify the label/feature contract: <https://xgboost.readthedocs.io/en/stable/python/python_api.html>.
