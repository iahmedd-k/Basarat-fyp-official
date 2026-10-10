# 📁 Scripts Directory Structure

This directory contains essential operational tools, database seeders, data synchronization utilities, ML training pipelines, and deployment scripts for the Basarat platform.

---

### 📂 Directory Layout

```
scripts/
├── seed/            # Database initialization, tables, and demo user seeders
├── data/            # OHLCV backfill, prediction resolution, and metadata sync tools
├── ml/              # Production model retraining and end-to-end ML pipeline
└── deploy/          # Remote deployment and sync scripts
```

---

## 1. 🗄️ Database Initialization & Seeding (`scripts/seed/`)

| Script | Command | Purpose |
| :--- | :--- | :--- |
| **`seed_demo_users.py`** | `python -m scripts.seed.seed_demo_users` | **(Recommended)** Seeds demo accounts (`admin@basarat.pk`, `trader1@basarat.pk`, `trader2@basarat.pk`) with portfolios. |
| **`init_db_tables.py`** | `python scripts/seed/init_db_tables.py` | Initializes database tables and schema structures. |
| **`seed_admin.py`** | `python scripts/seed/seed_admin.py` | Seeds only the primary superadmin account (`admin@basarat.pk`). |
| **`seed_all_fundamentals.py`** | `python scripts/seed/seed_all_fundamentals.py` | Populates fundamental financial metrics (P/E, P/B, EPS, ROE) for tracked equities. |
| **`seed_and_sync_500_stocks_fast.py`** | `python scripts/seed/seed_and_sync_500_stocks_fast.py` | Rapidly populates catalog and historical prices for 500+ PSX symbols. |

---

## 2. 📈 Market Data & Synchronization (`scripts/data/`)

| Script | Command | Purpose |
| :--- | :--- | :--- |
| **`sync_kse100_database.py`** | `python scripts/data/sync_kse100_database.py` | Syncs KSE-100 constituent stock profiles, sectors, and metadata to DB. |
| **`align_kse100_predictions.py`** | `python scripts/data/align_kse100_predictions.py` | Aligns historical price forecasts with actual subsequent settlement closes. |
| **`resolve_db_predictions.py`** | `python scripts/data/resolve_db_predictions.py` | Resolves pending prediction outcomes and computes realized accuracy. |
| **`backfill_missing_ohlcv.py`** | `python scripts/data/backfill_missing_ohlcv.py` | Identifies and backfills gaps in historical daily OHLCV files. |

---

## 3. 🤖 Machine Learning & Forecasting Pipelines (`scripts/ml/`)

| Script | Command | Purpose |
| :--- | :--- | :--- |
| **`run_ml_pipeline.py`** | `python scripts/ml/run_ml_pipeline.py` | Executes complete ML workflow: Ingestion $\to$ Features $\to$ Predictions $\to$ Recommendations. |
| **`retrain_gru_production.py`** | `python scripts/ml/retrain_gru_production.py` | Retrains and checkpoints the production Attention-BiGRU sequential model. |
| **`retrain_production_model.py`** | `python scripts/ml/retrain_production_model.py` | Retrains production multi-horizon XGBoost classifiers (5D, 10D, 20D). |

---

## 4. 🚀 Deployment Utilities (`scripts/deploy/`)

| Script | Command | Purpose |
| :--- | :--- | :--- |
| **`fast_deploy_remote.py`** | `python scripts/deploy/fast_deploy_remote.py` | Synchronizes local code changes directly to remote Oracle instance. |
| **`deploy_remote_changes.py`** | `python scripts/deploy/deploy_remote_changes.py` | Deploys containers and restarts remote services. |
