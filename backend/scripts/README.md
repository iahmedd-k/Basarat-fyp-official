# Operational & Diagnostic Scripts Index

This directory contains the essential operational, database seeding, data synchronization, and automated testing scripts for the Basarat backend platform.

---

## 1. Database Initialization & Seeding Scripts

| Script | Command | Purpose |
|---|---|---|
| `seed_demo_users.py` | `python -m scripts.seed_demo_users` | **(Recommended)** Seeds verified demo accounts (`admin@basarat.pk`, `trader1@basarat.pk`, `trader2@basarat.pk`) with portfolios. |
| `init_db_tables.py` | `python scripts/init_db_tables.py` | Initializes database tables and schema structures. |
| `seed_admin.py` | `python scripts/seed_admin.py` | Seeds only the primary superadmin account (`admin@basarat.pk`). |
| `seed_all_fundamentals.py` | `python scripts/seed_all_fundamentals.py` | Populates fundamental financial metrics (P/E, P/B, EPS, ROE) for all tracked equities. |
| `seed_route_test_accounts.py`| `python scripts/seed_route_test_accounts.py` | Seeds demo accounts with pre-populated watchlists, portfolios, and alerts for testing. |

---

## 2. Market Data Synchronization Scripts

| Script | Command | Purpose |
|---|---|---|
| `sync_friday_prices.py` | `python scripts/sync_friday_prices.py` | Ingests and synchronizes Friday split-session closing prices from PSX. |
| `sync_kse100_database.py` | `python scripts/sync_kse100_database.py` | Full synchronization of KSE-100 constituent stock profiles, sectors, and metadata. |
| `align_kse100_predictions.py`| `python scripts/align_kse100_predictions.py` | Aligns historical price forecasts with actual subsequent settlement closes. |
| `resolve_db_predictions.py` | `python scripts/resolve_db_predictions.py` | Resolves pending prediction outcomes and computes realized accuracy. |

---

## 3. ML Pipeline & Feature Generation Scripts

| Script | Command | Purpose |
|---|---|---|
| `prepare_feature_assets.py` | `python scripts/prepare_feature_assets.py` | Builds stationary features and cross-sectional rank tensors from raw OHLCV data. |
| `run_ml_pipeline.py` | `python scripts/run_ml_pipeline.py` | Executes the complete ML workflow: Ingestion $\to$ Features $\to$ Predictions $\to$ Recommendations. |
| `retrain_gru_production.py` | `python scripts/retrain_gru_production.py` | Retrains and checkpoints the production Attention-BiGRU sequential model. |
| `retrain_production_model.py`| `python scripts/retrain_production_model.py` | Retrains the production multi-horizon XGBoost classifiers (5D, 10D, 20D). |
| `reproducible_v4_engine.py` | `python scripts/reproducible_v4_engine.py` | Standalone deterministic feature and training verification harness. |

---

## 4. Automated Testing & Live Verification Audits

| Script | Command | Purpose |
|---|---|---|
| `test_live_ai_ml_endpoints.py` | `python scripts/test_live_ai_ml_endpoints.py` | Validates live AI/ML forecast, recommendation, risk, and sentiment API endpoints. |
| `test_live_chatbot_streaming.py` | `python scripts/test_live_chatbot_streaming.py` | Validates Server-Sent Events (SSE) conversational streaming with Groq LLM Copilot. |
| `run_live_oracle_comprehensive_audit.py` | `python scripts/run_live_oracle_comprehensive_audit.py` | Complete 80-point live production endpoint audit with latency and payload validation. |
| `validate_recommendation_engine.py` | `python scripts/validate_recommendation_engine.py` | Validates multi-factor quantitative stock ranking engine scoring logic. |
| `run_crud_lifecycle_verification.py` | `python scripts/run_crud_lifecycle_verification.py` | Validates full Create $\to$ Read $\to$ Update $\to$ Delete lifecycles across domain resources. |
| `diagnose_psx_upstream.py` | `python scripts/diagnose_psx_upstream.py` | Verifies live network connectivity and HTTP response codes from upstream PSX portals. |
| `get_test_token.py` | `python scripts/get_test_token.py` | Generates a valid JWT test token for local manual API testing. |

---

## 5. Archived Scripts (`scripts/archive/`)
One-off inspection scripts, scratch debug files, and temporary test utilities have been safely organized into [`scripts/archive/`](file:///d:/FYP/Basarat-fyp-official/backend/scripts/archive/).
