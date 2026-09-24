# Prompt for Antigravity: inspect, prepare, and train isolated PSX event models

Copy the prompt below into Antigravity. It is intentionally self-contained: inspect the repository and local files because this brief may be the only context available to you.

---

You are working on the **Basarat PSX stock forecasting project**, located at:

`D:\Ahmed Dev\Projects\Basarat-fyp-official`

Your task is to inspect, make runnable, and—only when the data is actually ready—train two experimental models that add structured Pakistan Stock Exchange (PSX) company-disclosure features:

1. **XGBoost**, using flat stock-date rows.
2. **GRU**, using time-ordered sequences.

The purpose is to evaluate whether official PSX announcements improve out-of-sample forecasts over price/market features. The models and all generated artifacts must stay isolated in:

`backend/research/psx_disclosure_v1/`

Do not modify the existing application, deployed model files, active inference code, existing feature pipelines, database schema, or frontend. Do not merge the research models into the production system. The project owner will review the experiment results before deciding what to merge.

## What already exists

The isolated research folder currently contains:

- `README.md` — experiment overview, inputs and setup.
- `FEATURE_SPEC.md` — proposed ordered feature contract and definitions.
- `common.py` — shared OHLCV loading/fetch, feature construction, disclosure alignment, common target and chronological splits.
- `collect_events.py` — PSX company-announcement archive collector.
- `train_xgb.py` — price-only baseline and event-augmented XGBoost training.
- `train_gru.py` — price-only baseline and event-augmented GRU training.
- `requirements-research.txt` — additional dependencies.
- `data/events_template.csv` and `data/events_coverage_template.json` — event input templates.

Treat these as a draft implementation that requires careful review. Do not assume the code is correct just because it exists. Inspect the complete scripts, the relevant repository code, dependencies, available data and the actual PSX collector responses. Fix defects in this isolated folder as needed and explain every significant change.

## Existing project facts and multiple model generations

The repository has several incompatible forecasting paths. Do not assume they describe one model:

- The base daily pipeline at `backend/app/data/features/run_features.py` uses `backend/app/data/features/gru_feature_list.py`, which declares GRU feature version `2025.09.18.v2` and 36 mostly raw-scale inputs. Its default labels are next-observed-row returns with +/-1% thresholds, and its default sequence length is 30.
- `backend/app/ml/training_xgb/feature_prep.py` declares a separate generic XGBoost feature set of 41 inputs.
- `backend/models/final/final_v2/` has another configuration: five-day fixed +/-1% labels, 45-step GRU sequences, 36 GRU inputs, 34 XGBoost inputs and a stated 0.5/0.5 ensemble.
- `backend/models/final/final_v3/` has a saved 30-feature XGBoost artifact and a manifest dated 2026-09-22. It has no matching GRU artifact in that directory.
- `backend/app/ml/v3/feature_engineer_v3.py` builds another path using a five-row forward return and cross-sectional relative-return targets. Its feature-engineering list declares 32 cross-sectionally ranked features, while the saved final_v3 feature file contains 30 features. Reconcile this if using the existing final_v3 model as a benchmark.

Before claiming that a research score beats production, trace `backend/app/ml/serving/`, model artifact loading, feature selection and the API forecast path to establish which model is actually served and what its true target/horizon is. Record the findings, but do not change serving.

## Research model design intended by the owner

The draft research pipeline deliberately uses one common target for fair GRU/XGBoost comparisons:

- Build a market-session calendar from the union of dates in the OHLCV archive.
- For a stock row at session `t`, measure the close return to the exact fifth following market session. Require observed, positive-volume closes at both ends; do not forward-fill missing target prices.
- Subtract the cross-sectional median five-session return of the other stocks with valid endpoints on that date (leave-one-symbol-out market reference).
- Rank excess returns within each date: bottom 30% class 0 `avoid`; middle 40% class 1 `neutral`; top 30% class 2 `buy`.
- The target means **relative performance**, not “the stock price will rise.” Keep API/product language out of this research folder.
- Keep whole dates together in chronological train/validation/test splits. A sample whose forward target crosses into the next partition must be purged. The last 20% of dates are intended as a sealed test set and must not be used for training, early stopping, feature selection or threshold tuning.

The draft XGBoost candidate has 41 features: 29 cross-sectional ranks of stationary technical/liquidity features, two unranked market-wide macro-change features, and ten unranked event features. Do **not** cross-sectionally rank macro or disclosure features.

The draft GRU candidate has 47 features: 36 stationary price/market features plus 11 announcement/timing inputs. It uses 45 observed stock bars per input sequence, with a 90-calendar-day maximum span check; the forecast horizon remains five union-market sessions. Fit its medians and `StandardScaler` on training dates only and persist them with the model.

For both models, the draft scripts intend to train a price-only baseline and an event-augmented candidate on **the same eligible rows/endpoints**. Compare the candidates on a sealed test set only after choices are frozen.

## Event data and collection

The PSX Company Announcements page is:

`https://dps.psx.com.pk/announcements/companies`

The draft `collect_events.py` sends date-range POST requests to the portal's current HTML announcements endpoint, paginates month-by-month, saves raw rows and emits the `events.csv` schema. This is not a documented stable API; confirm the live response structure, pagination behavior and date-filter semantics. Fail loudly on layout changes, pagination errors or partial ranges. Do not call an empty parse a complete archive without checking the portal response.

The intended eight-year backfill command (run from `backend`) is:

```powershell
python research/psx_disclosure_v1/collect_events.py --from 2018-09-24 --to 2026-09-24
```

The collector should write:

- `backend/research/psx_disclosure_v1/data/psx_announcements_raw.csv`
- `backend/research/psx_disclosure_v1/data/events.csv`
- `backend/research/psx_disclosure_v1/data/events_coverage.json`

It must **not** mark coverage verified automatically. Verify requested and completed months, pagination totals, symbol/date coverage, duplicates, amended notices, timestamps and a manual sample against the portal. A manually set `coverage_verified: true` is an explicit completeness attestation and must not be set merely to bypass a script guard. If PSX's historical feed cannot return a complete range, collect prospectively and do not create false historical zero-event rows.

The announcements table provides publication date/time, ticker, title and document link. It does not provide structured EPS, dividend-per-share or meeting-date fields. The draft CSV leaves these blank. If numeric features are required, inspect the linked official documents, add a conservative parser only if it can be audited (scanned PDFs may need OCR), preserve document/source identifiers and record parse failures. Do not invent values from titles or infer a value from sentiment.

CSV columns:

`symbol,published_at,title,document_url,event_type,meeting_date,dividend_pkr_per_share,dividend_face_value_pct,face_value_pkr,ex_date,eps_current,eps_comparison,eps_period,eps_basis,source_id`

Rules:

- Publication timestamp is the time the fact first became available; preserve Pakistan Standard Time offset or another explicit timezone.
- For a close-based feature row, a notice after the PSX close cutoff must become available on the next PSX session. Weekend and holiday notices map to the next session.
- Distinguish a board agenda “to consider results/dividend” from a published result or declared dividend.
- EPS comparisons require comparable reporting periods and comparable consolidated/unconsolidated basis. The derived feature is `(EPS_current - EPS_comparison) / close`, which accommodates zero/negative EPS better than a percentage growth ratio.
- Dividend yield uses explicit cash dividend per share divided by current close. Convert a face-value percentage only if face value is known from a reliable source. Do not mix percent-of-face-value and PKR-per-share units.
- No disclosure or sentiment feature may be assigned to dates before publication.
- Missing archive coverage is not the same as an observed day with no disclosure.

## Candidate event inputs

XGBoost's ten event inputs:

1. `evt_results_published`
2. `evt_dividend_announced`
3. `evt_bonus_or_rights`
4. `evt_board_meeting_notice`
5. `evt_material_info`
6. `evt_count_5s`
7. `sessions_since_results`
8. `sessions_to_board_meeting`
9. `dividend_yield`
10. `eps_delta_over_price`

GRU's eleven event inputs:

1. `evt_results_published`
2. `evt_dividend_announced`
3. `evt_bonus_or_rights`
4. `evt_board_meeting_notice`
5. `evt_material_info`
6. `sessions_since_results`
7. `sessions_to_board_meeting`
8. `dividend_yield`
9. `eps_delta_over_price`
10. `dividend_parsed`
11. `eps_parsed`

`evt_count_5s` counts unique notices in the current and prior four sessions. Board-meeting timing can only use a meeting date from a notice already published by the feature cutoff. Dividend yield should expire at the known ex-date or a defined cap; EPS should expire at the next results notice or a defined cap. Missing numeric disclosures remain missing in XGBoost; for the GRU, impute using training-only medians and include the availability masks.

The draft v1 omits credit-rating and management-change features because they are rare and title-only classification is unreliable. Keep that scope unless data audits show reliable historical coverage and extraction precision.

## Data availability and eight-year setup

Daily OHLCV currently lives at `backend/data/raw/ohlcv/all_symbols.parquet`. The repository's `backend/app/data/scraper/ohlcv.py` uses `psx-data-reader` with a direct DPS fallback. `psxdata` is also present for universe data. The research `common.py --fetch --years 8` tries an eight-year download for symbols found in the existing archive and current frozen universe and saves a separate copy under the research folder.

Do not claim eight years merely because `--years 8` was supplied. Inspect actual first/last dates, per-symbol bar counts, active/suspended/retired symbols, zero-volume observations, duplicates and gaps. This source may be survivorship-biased because the frozen universe can reflect current constituents. Include delisted/removed names if a point-in-time history source is available.

Investigate price adjustment. If OHLCV is unadjusted, corporate actions (dividends, bonus/right issues, splits) can make price returns and labels false. Exclude or adjust affected intervals using reliable corporate-action records before drawing conclusions. The source archive does not currently guarantee adjusted prices.

## Setup expected

Work from `backend` in a dedicated virtual environment so repository dependencies and model artifacts remain isolated. Install the repository backend requirements plus:

```powershell
python -m pip install -r requirements.txt
python -m pip install -r research/psx_disclosure_v1/requirements-research.txt
```

The research dependencies include Parquet support (`pyarrow`), scikit-learn, XGBoost, joblib and TensorFlow. Confirm the user's Python version, TensorFlow platform support, available RAM/disk/GPU and PSX network access. Do not overwrite or alter existing environments. If TensorFlow is unavailable on the platform, explain the blocker and provide a supported environment setup instead of silently skipping GRU.

The local agent environment that prepared this brief could not read Parquet because it lacked `pyarrow`; the data dates and actual event feed were not inspected here. Therefore **no training result or end-to-end success has been established**. Your first job is readiness inspection and focused run validation, not a claim that the models are ready.

## Train commands after readiness checks

From the repository's `backend` directory:

```powershell
# Optional eight-year OHLCV refresh and a diagnostic price-only feature build.
python research/psx_disclosure_v1/common.py --years 8 --fetch --allow-price-only

# After an audited events.csv exists and coverage_verified is true, rebuild and train both variants.
python research/psx_disclosure_v1/train_xgb.py --rebuild
python research/psx_disclosure_v1/train_gru.py --rebuild
```

All generated features, reports and model outputs must remain in `research/psx_disclosure_v1/data/` and `research/psx_disclosure_v1/models/`. The intended model outputs are separate baseline and event-augmented subfolders for each model family, with ordered feature names, train-only preprocessing, manifests, hashes and metrics. Do not copy them into `backend/models/final`.

## What to inspect and fix before training

Review every item below against code and data. Report which are confirmed, fixed, or still blocked:

1. **Code correctness:** inspect feature generation, macro joins, target labels, event timestamps, coverage guards, duplicate handling, split purging, sequence indexing, model input order, metrics, serialization and output paths. Fix exceptions and incorrect assumptions only inside the research folder.
2. **PSX collector validation:** manually fetch a small date range and compare row counts/content with the official portal before attempting the eight-year backfill. Verify that `count` and `offset` paginate all notices, date ranges are inclusive, symbols are correct, and the HTML parser doesn't silently skip rows. Respect reasonable request pacing and use retry/backoff.
3. **Dataset coverage report:** actual price years/sessions, symbols per year, active and delisted limitations, OHLCV missingness, positive-volume availability, event coverage months, notices by month/symbol/category, parse failure count, duplicate/amendment count and percentage of rows with parsed numbers.
4. **Point-in-time leakage checks:** publication cutoff, after-close handling, weekends/holidays, future meeting information, feature windows, macro effective dates, current stock in market benchmark, cross-sectional ranking per date, and no future knowledge in imputation/scalers.
5. **Train/validation/test:** dates remain disjoint by whole market date; any sample with a five-session label crossing the next split is purged; test dates stay untouched until variants and hyperparameters are frozen. Consider a purge/embargo of at least the five-session target horizon and an expanding walk-forward sensitivity analysis.
6. **Feature data types/missingness:** event flags should be zero only inside verified archive coverage. Unavailable coverage must be excluded or explicitly masked. XGBoost can handle sparse numeric NaNs. GRU must use training-only imputation/scaling and parse masks. Check all model arrays are finite after preprocessing.
7. **Baseline comparisons:** compare price-only and event-augmented models on identical rows and target labels. Separate event-category/timing signal from parsed numeric signal where data volume permits. Do not select a model using sealed-test results.
8. **Evaluation:** report per-class confusion matrix, accuracy, balanced accuracy, macro F1, log loss and multiclass Brier score. For the ranking target, report daily Spearman information coefficient and top-quintile long-only excess returns, top-minus-bottom spread and turnover; add realistic transaction costs before investment claims. Report by year, liquidity bucket and sector, plus uncertainty intervals or date-block bootstrap where feasible. Probabilities are not calibrated by default.
9. **Reproducibility:** record exact data snapshot and SHA-256, code revision, package versions, model seeds, date cutoffs, ordered feature names, preprocessing hashes, target definition and all selected training settings in each manifest.
10. **Do not overstate evidence:** event features may add no directional value, particularly if announcements are reflected in the same day's close. Treat an event-related result as predictive only if it is stable in held-out periods and genuinely available at the simulated prediction cutoff.

## Your response to the project owner

First give a short readiness verdict: “ready to run,” “can run price-only diagnostics only,” or “blocked,” with specific reasons. Then:

1. List setup steps and exact PowerShell commands for this machine/repository.
2. Report the actual PSX collector behavior and whether a complete eight-year announcement archive was obtained; include any failed months or parser coverage gaps.
3. Report actual OHLCV and event data coverage before training.
4. Summarize code defects found and the isolated files changed to fix them.
5. If the data is ready, run the baseline and event-augmented XGBoost and GRU experiments as separate artifacts under the research folder; provide commands, run logs, metrics, and artifact paths. Do not touch deployed models.
6. If not ready, do not fake or backfill missing values. State exactly what data/setup is missing, provide the safe price-only command if useful, and explain how to resume.
7. Give the owner a recommendation based on the sealed test comparison, while clearly distinguishing relative stock ranking from absolute direction forecasting.

---

**End of prompt.**
