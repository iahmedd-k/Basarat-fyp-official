# Basarat PSX Forecasting Models — Claude Review Context

**Purpose:** Give an independent reviewer enough repository and model context to assess whether the proposed PSX disclosure features and the next training run are correct. This document describes what was found in the repository on 2026-09-24. Treat it as a review brief, not as proof that any artifact is the model currently deployed in production.

## Instructions to reviewer

Review the current implementation and data, not just this document. Identify critical correctness, leakage, data availability, training, evaluation, and serving risks. Distinguish facts confirmed in code/artifacts from assumptions that require inspection. Do not assume a proposed feature is implemented. Recommend concrete checks and changes before anyone starts a new training run. In particular, resolve the version/artifact inconsistencies listed below before declaring which model is the authoritative production baseline.

## Project and task context

This is a Pakistan Stock Exchange (PSX) forecasting project. The repository contains price scraping, technical feature engineering, macro joins, multiple model-generation paths, saved artifacts, an API serving path, and an official PSX announcement service. The intended new input is structured information from PSX company disclosures: event categories, disclosed numbers, and announcement/meeting timing. The goal is to test whether those facts add predictive value over the existing models; do not replace sentiment in product/API behavior unless that is separately requested.

Relevant code paths:

- `backend/app/data/scraper/ohlcv.py` — PSX daily OHLCV fetching; tries `psx-data-reader` and has a direct DPS historical-page fallback.
- `backend/app/data/features/technical_indicators.py` — project-owned pandas calculations for technical indicators.
- `backend/app/data/features/macro_features.py` and `backend/data/config/macro/` — macro feature source/join.
- `backend/app/data/features/run_features.py` — daily feature, label, sequence pipeline.
- `backend/app/data/features/gru_feature_list.py` — explicit ordered current GRU pipeline feature contract.
- `backend/app/data/features/sequence_builder.py` — creates GRU windows; scaler is expected to be handled in training on training data only.
- `backend/app/data/features/labeling.py` — default one-observation-ahead close return labels.
- `backend/app/ml/training_xgb/feature_prep.py` — legacy/current generic XGBoost flat feature builder.
- `backend/app/ml/v3/feature_engineer_v3.py` — separate v3 cross-sectional five-trading-row target and ranked features.
- `backend/app/services/psx_announcement_service.py` — announcement fetch, broad title-based event classification, heuristic sentiment, DB storage.
- `backend/app/tasks/news_tasks.py` and `backend/app/celery_app.py` — scheduled announcement/news task configuration.
- `backend/app/ml/serving/` and `backend/app/api/v1/forecast.py` — inspect to confirm actual serving artifact and feature contract.

Declared backend data dependencies include `psxdata`, `psx-data-reader`, and `pypsx-toolkit`. The existing OHLCV implementation uses `psx-data-reader` with its own scraper fallback; the universe loader calls `psxdata.indices()`. No reviewed model training code currently consumes structured announcement facts.

## Existing models and an important version ambiguity

There are multiple generations and feature contracts in the tree. Do not conflate them:

1. `backend/app/data/features/gru_feature_list.py` declares `GRU_FEATURE_VERSION = "2025.09.18.v2"` and 36 inputs. `backend/data/features/feature_columns.json` and `gru_feature_version.json` agree with that 36-column list. This is the current base `run_features.py` GRU pipeline contract.
2. `backend/app/ml/training_xgb/feature_prep.py` declares a different XGBoost feature set: 23 base features + 17 engineered features + `symbol_id` = 41 inputs. This code uses a legacy/shared daily parquet path and a one-day classification target indirectly tied to the base feature labeling path.
3. `backend/models/final/final_v2/` contains a separate stationary-feature modeling generation: 36 GRU inputs, 34 XGBoost inputs, a 45-step GRU sequence, five-day horizon, +/-1% thresholds, and equal 0.5/0.5 ensemble weights in `config.json`. Its XGBoost list includes `symbol_id`.
4. `backend/models/final/final_v3/` contains `xgb_model.ubj`, `xgb_features.json` (30 names), and `model_manifest.json` identifying `xgb_v3_production`, trained 2026-09-22, 79,451 samples, 30 features, three classes, and uncalibrated probabilities. There is no corresponding GRU artifact or GRU feature JSON in this directory.
5. `backend/app/ml/v3/feature_engineer_v3.py` creates a distinct v3 dataset: five-row/trading-observation forward return, benchmark-relative excess return, cross-sectional rank classification (top 30% / middle 40% / bottom 30%), and 32 cross-sectional rank-normalized columns according to its declared `feature_columns` list. The saved `backend/models/final/final_v3/xgb_features.json` has 30 features and no `symbol_id`; the v3 engineer itself does not add `symbol_id` to its rank feature list. The 30-vs-32 discrepancy remains to investigate, as does whether the final artifact was trained from this exact output and whether serving uses the same contract.

**Review requirement:** Trace training scripts, manifests, model loading, inference feature selection, API behavior, and artifact paths. State which baseline is actually served today. The phrase “current GRU model” is not safely established from the inspected files. Validate input dimensions and column order against the serialized model and its fitted scaler/preprocessor. Do not overwrite or silently change existing artifacts.

## Current feature list: base GRU pipeline (36)

These are the exact ordered features in `backend/app/data/features/gru_feature_list.py` and `backend/data/features/feature_columns.json`:

1. `open` — daily open price
2. `high` — daily high price
3. `low` — daily low price
4. `close` — daily close price
5. `volume` — daily traded volume
6. `sma_20` — 20-observation simple moving average of close
7. `sma_50` — 50-observation simple moving average of close
8. `ema_12` — 12-observation exponential moving average of close
9. `ema_26` — 26-observation exponential moving average of close
10. `return_5d` — close percentage change over five observations
11. `return_10d` — close percentage change over ten observations
12. `atr_14` — 14-observation average true range
13. `bb_lower` — lower Bollinger band, 20 observations and 2 standard deviations
14. `bb_mid` — middle Bollinger band, 20-observation average
15. `bb_upper` — upper Bollinger band, 20 observations and 2 standard deviations
16. `volume_zscore_20` — volume z-score relative to a rolling 20-observation window
17. `rsi_14` — 14-observation Relative Strength Index
18. `rsi_roc` — RSI change versus five observations earlier
19. `macd` — Moving Average Convergence Divergence line
20. `macd_signal` — MACD signal line
21. `macd_hist` — MACD histogram
22. `adx_14` — 14-observation Average Directional Index
23. `consecutive_up_days` — count of consecutive positive daily returns
24. `consecutive_down_days` — count of consecutive negative daily returns
25. `pkr_usd_rate` — joined Pakistani rupee/US dollar rate
26. `policy_rate` — joined policy rate
27. `close_to_sma20_ratio` — close / SMA-20 minus one
28. `close_to_sma50_ratio` — close / SMA-50 minus one
29. `ema_cross_ratio` — EMA-12 / EMA-26 minus one
30. `bollinger_pos` — close position within Bollinger bands, clipped to [0,1]
31. `daily_range_pct` — (high - low) / close
32. `volume_change_1d` — one-observation volume percentage change
33. `market_return_5d` — project-computed equal-weighted universe return over five observations
34. `market_return_20d` — project-computed equal-weighted universe return over twenty observations
35. `stock_return_20d` — stock close percentage change over twenty observations
36. `stock_relative_return_20d` — stock 20-observation return minus computed index/universe return

The implementation also computes columns not in this GRU contract, such as raw `macd`, intermediate market index returns, and technical fields. Presence in the parquet does not make a column a model input.

## Existing generic XGBoost feature list (41)

This is the ordered set constructed by `backend/app/ml/training_xgb/feature_prep.py`; it is **not** the 30-feature final_v3 artifact list. In code, the list consists of these 23 base features, 17 engineered features, and `symbol_id`:

### Base (23)

`rsi_14`, `macd`, `macd_hist`, `macd_signal`, `atr_14`, `sma_20`, `sma_50`, `ema_12`, `ema_26`, `bb_upper`, `bb_mid`, `bb_lower`, `close`, `open`, `high`, `low`, `volume`, `volume_zscore_20`, `pkr_usd_rate`, `policy_rate`, `index_return_5d`, `index_return_20d`, `stock_relative_return_20d`.

### Engineered (17)

`return_1d`, `return_5d_eng`, `return_10d_eng`, `return_20d`, `rolling_std_5d`, `rolling_std_20d`, `vol_adj_return_1d`, `vol_adj_return_5d`, `vol_adj_return_10d`, `rsi_14_lag5`, `rsi_14_lag10`, `macd_hist_lag5`, `consecutive_up_days`, `consecutive_down_days`, `close_min_20d`, `close_max_20d`, `close_position_20d`.

### Identifier (1)

`symbol_id` — numeric stock ID.

Potential review point: raw prices/volume and ordinal symbol IDs can encode scale or arbitrary ID ordering. Determine whether that is intentional and validated; do not assume tree-model invariance makes symbol ID semantically neutral.

## Separate final_v3 XGBoost feature list (30)

`backend/models/final/final_v3/xgb_features.json` currently contains the following exact ordered list:

1. `dist_52w_high_csrank`
2. `mom_12m_1m_csrank`
3. `ret_1d_csrank`
4. `ret_3d_csrank`
5. `ret_5d_csrank`
6. `ret_10d_csrank`
7. `ret_20d_csrank`
8. `amihud_illiquidity_csrank`
9. `is_lower_circuit_csrank`
10. `volatility_10d_csrank`
11. `volatility_20d_csrank`
12. `volatility_60d_csrank`
13. `norm_atr14_csrank`
14. `hl_range_csrank`
15. `co_range_csrank`
16. `dist_sma20_csrank`
17. `dist_sma50_csrank`
18. `dist_ema12_csrank`
19. `dist_ema26_csrank`
20. `bb_pct_b_csrank`
21. `bb_width_csrank`
22. `rsi_norm_csrank`
23. `macd_norm_csrank`
24. `macd_hist_norm_csrank`
25. `volume_zscore_20_csrank`
26. `vol_growth_5d_csrank`
27. `vol_growth_20d_csrank`
28. `rel_to_index_5d_csrank`
29. `rel_to_index_20d_csrank`
30. `pkr_usd_ret_20d_csrank`

This is the strongest available evidence for a current final XGBoost artifact, but serving must still be traced to confirm it is truly active. Note that the v3 engineer declares 32 rank features, while this artifact lists only 30; compare exact names and training data before treating either as the canonical v3 contract.

## Technical indicator and pipeline facts

- `technical_indicators.py` computes indicators with project-owned pandas functions; adding a separate technical-analysis dependency is not necessary to get these existing inputs.
- Features are grouped by symbol to avoid rolling across ticker boundaries. It sorts by symbol/date and drops the first 50 observations per symbol for warmup.
- `run_features.py` computes technical indicators, joins macro data, maps symbol IDs, assigns labels, writes the daily parquet, validates a fixed GRU feature list, and builds sequences.
- Default base labels in `labeling.py` use the next available row for the same symbol: `close[t+1]/close[t]-1`; classes use +/-1% thresholds and map bullish=0, bearish=1, sideways=2. This is not necessarily the target used in either final_v2 or final_v3.
- `sequence_builder.py` default window is 30 (final_v2 config states 45). It labels a window using the last timestep’s label, and windows are symbol-specific.
- Scaling must be fit on the training portion only and persisted with the matching model. Confirm actual training code does this; do not infer from sequence building comments.
- The v3 feature engineer shifts each symbol’s close by five rows for a five-observation target. “Trading day” here effectively means next five available rows for a symbol; inspect missing-date alignment and benchmark/index calculation.

## PSX data/library context

- `psx-data-reader` is the primary OHLCV library attempt in this repo, with direct PSX DPS scraping fallback because a PSX column change reportedly broke the library.
- `psxdata` is used for index constituents in the symbol-universe loader. Its documented `fundamentals(symbol)` interface returns a financial-report filing list with symbol, year, report type, period-ended date, posting date/time, and document reference. That interface should not be assumed to yield parsed EPS or financial statement values.
- PSX DPS exposes company announcements, financial reports and payout-related information. The repository announcement scraper currently posts to the DPS announcements endpoint and retrieves notice table fields including date/time, symbol, company, title, and document link where available.
- The dependency `pypsx-toolkit` is declared, and its current external documentation advertises fundamentals/dividends and technical analytics. The repository paths inspected for this report do not show it being used in the forecasting feature pipeline. Verify installed version, actual return schemas, history depth, licensing/usage terms, rate limits, and point-in-time availability before adopting it.
- Current PSX company announcements are not automatically a historically complete event dataset. Establish historical coverage and timestamp fidelity. If adequate history is unavailable, collect prospectively and defer training on announcement-derived signals until there is enough point-in-time history.

## Current PSX announcement processing

`backend/app/services/psx_announcement_service.py`:

- Classifies titles into `earnings`, `dividend`, `board_meeting`, `material_information`, `general_meeting`, `shareholding`, or `other` with keyword rules.
- Generates rule-based sentiment; fallback rules can label broad event classes bullish, so sentiment is not ground truth and should not be used as a substitute for disclosed facts.
- Parses announcement date/time as Pakistan Standard Time and converts to UTC; if parsing fails, `_parse_pkt_datetime()` currently falls back to the current time. Review this carefully: substituting now for an unparseable historical disclosure can create incorrect point-in-time features. Preserve parse status and source text rather than inventing a timestamp.
- Stores announcements as `NewsArticle` and links symbols. The selected table fields may not include enough document text to parse EPS, dividend amount, rating direction or meeting date. PDF downloads/text extraction and parser provenance may be required.
- Generates a fallback company page URL when no PDF document link is found. Deduplicating only by URL can be insufficient when this fallback URL repeats for one ticker.
- Feature classification currently omits explicit `rating_change` and `management_change` event classes.

## Proposed structured disclosure feature definitions for review

Design principles: deterministic, auditable, sparse, point-in-time, and trained/evaluated as an ablation against the verified current artifact. Keep raw disclosure facts and parser metadata in an event table; derive daily model columns from that canonical table. A missing disclosure fact is not numeric zero. Keep the publication timestamp distinct from financial period end, board meeting date, and the date the model can first act on the information.

### Proposed common event feature set (16 features)

1. `event_earnings` — 1 if an earnings/results notice becomes available during the feature observation interval; otherwise 0.
2. `event_dividend` — 1 if dividend/payout terms become available during the interval; otherwise 0.
3. `event_board_meeting` — 1 if a board meeting notice is published during the interval; otherwise 0.
4. `event_rating_change` — 1 if a rating action is disclosed during the interval; otherwise 0.
5. `event_management_change` — 1 if an appointment, resignation or similar management event is disclosed during the interval; otherwise 0.
6. `event_material_information` — 1 if a material company disclosure not covered above is published during the interval; otherwise 0.
7. `event_count_5d` — count of unique disclosures published during the trailing five PSX trading-session intervals, including today only if available by the prediction cutoff. Prefer trading sessions over calendar days to align with model rows; specify exact boundary behavior.
8. `days_since_earnings` — elapsed PSX trading sessions since the latest earnings/results notice; cap to a documented maximum and add a has-history indicator if needed.
9. `days_since_dividend` — elapsed PSX trading sessions since the latest dividend/payout notice; cap to a documented maximum and add a has-history indicator if needed.
10. `days_to_board_meeting` — sessions until the next scheduled board meeting known at the cutoff; missing if none is known. Do not calculate from a notice that was not yet published at cutoff.
11. `upcoming_board_meeting_7d` — 1 if a board meeting is scheduled within the next seven PSX trading sessions as known at cutoff; otherwise 0.
12. `dividend_per_share` — parsed cash dividend amount per share in PKR, only when units and terms are unambiguous. Do not mix percentage of face value with rupees per share.
13. `eps_current` — parsed current reported EPS, with period/unit/currency scope retained.
14. `eps_comparison` — parsed EPS for a comparable prior-year period, only if the periods and units are comparable.
15. `eps_yoy_change` — derived EPS change. Reviewer must recommend safe representation for zero/negative/restated EPS; a raw difference or signed/log transform may be safer than percentage change in such cases.
16. `rating_direction` — +1 upgrade, -1 downgrade, 0 reaffirmation; missing when no explicit rating action is parsed. Consider rating agency/outlook/watch status if data permits, but do not broaden scope silently.

This is **16**, not 17. In all features, “event day” must be based on information availability at the model cutoff, not just the date stamped on the notice. News arriving after the cutoff should only affect the next eligible prediction row. Decide whether event flags/counts persist for a defined window or only fire on the arrival date; the names above assume arrival-day flags and explicit trailing/elapsed-time features.

### Candidate next GRU feature set (50 total)

Keep the exact current 36 base GRU features listed above, then append these 14 in a documented stable order:

`event_earnings`, `event_dividend`, `event_board_meeting`, `event_rating_change`, `event_management_change`, `event_material_information`, `event_count_5d`, `days_since_earnings`, `days_since_dividend`, `days_to_board_meeting`, `upcoming_board_meeting_7d`, `dividend_per_share`, `eps_yoy_change`, `rating_direction`.

Raw `eps_current` and `eps_comparison` are not in this first GRU proposal. Assess whether their omission loses useful information and whether all 14 are robust enough for sequence modeling. Recalculate/validate preprocessing dimensions, input order, missing-value treatment, feature metadata, and serialized model/scaler together.

### Candidate next XGBoost feature set

XGBoost feature contracts are version-specific. Do **not** simply say “current 41 + 16 = 57” unless the selected baseline is the generic 41-feature pipeline and that is confirmed as the model under evaluation. If comparing to final_v3, the candidate would be the verified 30 final_v3 features plus 16 announcement features = 46. The proposal is to add all 16 structured features to whichever single XGBoost baseline is confirmed, yielding a fixed documented order. Compare results using identical splits, labels, eligible samples, and evaluation logic. Do not replace the production artifact during an experiment.

## Required training and validation review

1. **Authoritative baseline:** identify the actual serving model(s), target/horizon, class map, feature order, scaler/encoder, thresholds, and artifact paths. Reconcile generic 41-feature XGB, final_v2 34-feature XGB, final_v3 30-feature XGB, and current GRU paths.
2. **Point-in-time event alignment:** use source publication timestamps and a stated forecast cutoff in PKT. Ensure after-close notices are not available to that day’s close-based prediction; test weekend/holiday and malformed timestamps. Do not backfill a notice into dates before it was published.
3. **Historical event data:** quantify per-symbol and per-event coverage over time. Validate data availability and event/parser status by period. If event labels exist only for recent history, avoid pretending that older rows are clean zeros.
4. **Parser audit:** manually review a stratified sample of notices and extracted values, including negatives, parentheses, units, face-value percentages, cumulative/dividend language, revised reports, rating affirmations, and board-meeting schedule formats. Measure precision/recall or exact-match rates per extracted field; preserve original document URL/text and parser version.
5. **Entity/deduplication:** verify ticker mapping and document identity. Do not rely solely on repeated fallback company-page URLs. Handle amended/corrected notices without erasing what was knowable at earlier times.
6. **Missingness and scaling:** distinguish “no event,” “event with value absent,” and “data unavailable/parser failed.” Fit imputation/scaling only on training data and serialize those transforms. Check GRU all-zero or missing sparse features do not break normalization.
7. **Time-based splits:** train on earlier periods, validate on later periods, and reserve a final untouched test period. For overlapping multi-day horizons, use appropriate purging/embargo around split boundaries. Ensure each cross-sectional date is kept in a single split if labels depend on date-wise rankings.
8. **Ablations:** compare current baseline vs baseline + event categories/timing vs baseline + parsed numeric disclosures; isolate each event family. Use the same sample rows or explicitly report sample loss from missing event data.
9. **Metrics:** report balanced accuracy, macro F1, per-class precision/recall, confusion matrix, and probabilistic metrics such as log loss/Brier score where meaningful. For ranking/cross-sectional targets, include ranking/top-bottom portfolio diagnostics and transaction-cost-aware results if claimed as investment performance. Compare by year, sector, liquidity and symbol coverage; use uncertainty intervals where feasible.
10. **Model artifact safety:** feature change means a new version and retraining; verify ordered feature names and count in model artifact/manifest, class mapping, sequence/window dimensions, scaler, training cutoff, dataset hash and code revision. Add inference compatibility checks. Never load a model with a mismatched feature order or scaler silently.
11. **Market mechanics:** inspect corporate actions, unadjusted prices/bonus issues, illiquid and suspended stocks, PSX circuit limits, survivorship/universe changes, and how holidays/missing rows affect rolling windows and the target.

## Questions Claude should answer

1. Which exact model/artifact and target does production inference use today? Prove it from call paths and artifact metadata.
2. Are there discrepancies or likely bugs between the v3 feature-engineering code, saved 30-feature final artifact, training data and serving code?
3. Is the existing base GRU feature pipeline’s label/horizon compatible with final_v2 or the currently served endpoint?
4. Are feature calculations causal and correctly aligned? Inspect in particular the v3 policy-rate change (currently computed with `df["policy_rate"].diff(20)` after sorting by symbol/date, rather than explicitly grouped by symbol or computed once per date), FX return grouping/calculation, market benchmark construction, cross-sectional ranks, target timestamps, and adjustment for corporate actions. Macro cross-sectional ranks should be constant by date when inputs are correctly aligned; verify before retaining them.
5. Is the event dataset sufficiently historical, timestamp-accurate and broad enough for a credible backtest? What should be collected prospectively?
6. Are the 16 proposed disclosure features precise and useful? Identify redundant, leakage-prone, unsupported or better-encoded variables. Recommend an exact final ordered list for each confirmed model family.
7. What target/horizon and split design should be used for a fair baseline comparison? Explain purging/embargo needs for overlapping targets.
8. What concrete code, tests/checks, data audits and artifact changes are required before a new model-training run?
9. Provide a prioritized verdict: blockers first, then required changes, then optional improvements. Do not claim a feature helps unless supported by out-of-sample evidence.

## End of review context
