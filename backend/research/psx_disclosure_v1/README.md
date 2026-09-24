# Isolated PSX disclosure model experiments (v1)

This is a standalone research area. It does not modify the application, current model artifacts, or existing feature pipelines. It builds one shared, point-in-time dataset and trains two separate candidate models: a three-class XGBoost model and a GRU sequence model. Outputs stay under this directory.

## Important data limitation

The checked-in OHLCV archive is a small (~3 MB) snapshot. This environment could not inspect its Parquet row dates because the available Python runtime has no Parquet engine. The existing scraper defaults to five years, but the pipeline here defaults to an **eight-year request** to maximize available history. PSX may not return eight years for every symbol; the run writes exact symbol/date coverage and requires at least 500 market sessions, but you must inspect actual dates and per-symbol coverage before interpreting model results. Do not assume the requested span equals the retrieved span.

The checked-in source does not contain a verified point-in-time historical event archive. The PSX Company Announcements portal exposes date filters, and `collect_events.py` uses its current HTML endpoint to request monthly historical ranges. This endpoint is not a documented stable API, so inspect its output and coverage report. The collector creates `events.csv` with facts visible in the announcement table; it does not extract EPS, dividend terms, or meeting dates from linked PDFs. Enrich those fields from official documents before training numeric features. If historical event coverage is insufficient, collect prospectively; never turn missing history into historical “no event” zeros.

## Files

- `common.py` — data loading, optional eight-year fetch, stationary feature engineering, event alignment, common target and chronological split definitions.
- `train_xgb.py` — XGBoost training, validation-based early stopping, sealed test metrics, saved isolated artifacts.
- `train_gru.py` — GRU sequence training with train-only imputation/scaling, the same target and date splits, sealed test metrics.
- `requirements-research.txt` — additional research runtime packages; install into a separate environment if needed.
- `data/` and `models/` — created only when scripts run; outputs are not committed as current application artifacts.

## Inputs

Start from `backend/data/raw/ohlcv/all_symbols.parquet`. The optional fetch command attempts an eight-year historical refresh for symbols present in the existing archive and current frozen universe, using the repository's existing PSX scraper interface. It writes to this research directory only. PSX restrictions, retired symbols, changes to DPS, or incomplete market histories can prevent the requested span.

Run a historical backfill from the repository's `backend` directory:

```powershell
python research/psx_disclosure_v1/collect_events.py --from 2018-09-24 --to 2026-09-24
```

The collector writes `data/psx_announcements_raw.csv`, `data/events.csv`, and an unverified `data/events_coverage.json`. It paginates monthly date ranges and saves progress after each month. If any month fails, it records the failure and stops. It deduplicates raw notices by a content hash. The requested date range does not prove that every PSX notice was returned: inspect completed/failed months, spot-check counts against the portal, validate ticker/date coverage, and review duplicate or amended notices. Only after that audit should you set `coverage_verified` to `true` in the coverage JSON.

`events.csv` has these columns:

`symbol,published_at,title,document_url,event_type,meeting_date,dividend_pkr_per_share,dividend_face_value_pct,face_value_pkr,ex_date,eps_current,eps_comparison,eps_period,eps_basis,source_id`

`published_at` is saved with the Pakistan Standard Time offset. `event_type` is mapped from the announcement title. Numeric values and `meeting_date` are blank by default because the PSX table links to documents rather than supplying those facts as structured fields. Populate them only after reading the linked official notice/report. A face-value percentage is converted only when `face_value_pkr` is explicitly supplied. EPS values are used only when the periods and consolidated/unconsolidated basis are comparable. Keep source URLs/IDs. No sentiment field is used.

The collector's coverage JSON is not accepted for event training until `coverage_verified` is explicitly true. If numeric fields are not enriched, category and timing features can still be generated, while parsed-value features remain missing and the GRU's parsed masks remain false. For meaningful disclosure training, the pipeline requires at least 24 months of timestamped archive coverage. `--allow-price-only` is an explicit diagnostic mode and its outputs are marked as not an event model.

## Run

Run from the repository's `backend` directory in an environment with backend dependencies plus `requirements-research.txt`:

```powershell
python research/psx_disclosure_v1/common.py --years 8 --fetch --allow-price-only
```

After creating the verified event CSV and coverage JSON, rebuild and train both price-only baselines and event-augmented candidates on the same event-covered rows:

```powershell
python research/psx_disclosure_v1/train_xgb.py --rebuild
python research/psx_disclosure_v1/train_gru.py --rebuild
```

If the eight-year snapshot is already prepared, omit `--fetch`. If building the price-only diagnostic before historical disclosure data exists:

```powershell
python research/psx_disclosure_v1/train_xgb.py --allow-price-only
python research/psx_disclosure_v1/train_gru.py --allow-price-only
```

Each run rebuilds shared features into `research/psx_disclosure_v1/data/`. Outputs are written to `models/xgb/` and `models/gru/`; never copy these into the application model directories before separately reviewing results and compatibility.

## Modeling choices

- Common target: next **five sessions on the union PSX market calendar**, not five rows in an individual symbol file. Rows need an actual positive-volume close both at the feature date and target date. A missing target price is excluded, not forward-filled.
- Target: cross-sectional excess return over the leave-one-symbol-out median market return. Per date, bottom 30% is `avoid`, middle 40% is `neutral`, top 30% is `buy`. Both models use this same target for fair comparison. It predicts relative performance, not absolute price direction.
- Whole dates remain together. Chronological train/validation/test partitions purge labels whose five-session outcome crosses the next partition. A final 20% of market sessions is reserved as the sealed test; it is not used for early stopping or tuning.
- XGBoost consumes ranked cross-sectional technical features and unranked macro/event features. The timestamped event features are never cross-sectionally ranked.
- GRU consumes a 45-observation stationary feature sequence, ending on each eligible prediction date. Its target horizon is still five market sessions. Sequence eligibility checks maximum calendar span to avoid very stale histories.
- A price-only baseline and an event-augmented model are both trained on identical event-covered rows. Test metrics must be reported only after choices are frozen.
- The final event block is intentionally compact and deterministic: results, dividend, bonus/rights, board notice, material info; event count over five sessions (XGBoost only); sessions since results; sessions to next known board meeting; dividend yield; EPS change divided by the contemporaneous close. GRU additionally receives two parse-availability masks. No rating/management fields are included in v1 because they are rare and title-only classification is unreliable.

## Interpretation cautions

The existing v3 pipeline computes cross-sectional ranks for macro variables and computes `policy_rate_chg_20d` with a dataframe-wide diff; those paths are deliberately not reused. The research implementation computes macro changes on the market-date series and keeps them unranked. It also does not use current index constituents as a sample filter. This does not eliminate survivorship bias in the available OHLCV archive; historical delisted/removed symbols are still needed to address that.

The target is not adjusted for corporate actions unless adjusted OHLCV is supplied. Review ex-dividend dates, bonus/right issues, splits and book closures before accepting price-return metrics. Parsed payout yield is capped at 60 sessions or the provided ex-date; EPS delta is capped at 126 sessions or the next results notice. No scripts here have been run against the actual parquet or events because this environment lacks a Parquet engine and the historical event archive is absent. First user run is expected to reveal coverage and compatibility issues.
