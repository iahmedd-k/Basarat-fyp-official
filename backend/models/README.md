# Machine Learning Models Directory

This directory stores all serialized machine learning model binaries, neural weights, pre-fitted scalers, feature column definitions, deployment manifests, and evaluation reports for the Basarat prediction engine. Every artifact exists in **exactly one canonical location** with zero duplication.

---

## 1. Directory Structure

```
backend/models/
│
├── README.md                           # Master models documentation and artifact index
│
├── production/
│   └── v3/                              # Active production ensemble, versioned independently
│       │
│       ├── gru_model.keras             # Attention-BiGRU Keras network architecture
│       ├── gru_best_weights.weights.h5 # Trained neural weights (45-day lookback window)
│       ├── gru_scaler.joblib           # Pre-fitted RobustScaler for 79 sequential features
│       ├── gru_features.json           # Ordered list of 79 GRU feature names
│       ├── gru_train_medians.json      # Imputation fallback medians for cold-start symbols
│       ├── gru_metrics.json            # Out-of-sample BiGRU evaluation metrics & IC
│       │
│       ├── xgb_model.ubj               # Production 5D (1-Week) XGBoost binary
│       ├── xgb_model_10d.ubj           # Production 10D (2-Week) XGBoost binary
│       ├── xgb_model_20d.ubj           # Production 20D (1-Month) XGBoost binary
│       ├── xgb_features.json           # 5D feature column registry (70 rank features)
│       ├── xgb_features_10d.json       # 10D feature column registry
│       ├── xgb_features_20d.json       # 20D feature column registry
│       ├── xgb_metrics.json            # 5D out-of-sample evaluation metrics
│       ├── xgb_metrics_10d.json        # 10D out-of-sample evaluation metrics
│       ├── xgb_metrics_20d.json        # 20D out-of-sample evaluation metrics
│       │
│       ├── model_manifest.json         # Active deployment manifest & confidence gates
│       └── multi_horizon_summary.json  # Multi-horizon (5D, 10D, 20D) validation summary
│
└── archive/                            # Legacy model artifacts and archive documentation
```

`backend/models/` contains serialized ML artifacts. Database schemas are Python modules under `backend/app/models/`; they are not stored here.

---

## 2. Active Model Specifications

| Subsystem | Architecture | Artifact File | Size | Role |
|---|---|---|---|---|
| **Sequential Deep Learning** | Attention-BiGRU v2 | `gru_model.keras` & `gru_best_weights.weights.h5` | ~2.6 MB | 45-day sequential price velocity & momentum |
| **5D (1-Week) Forecaster** | XGBoost v4 | `xgb_model.ubj` | ~254 KB | 5-day swing momentum & technical reversals |
| **10D (2-Week) Forecaster** | XGBoost 10D | `xgb_model_10d.ubj` | ~162 KB | 10-day intermediate liquidity & sector trend |
| **20D (1-Month) Forecaster**| XGBoost 20D | `xgb_model_20d.ubj` | ~132 KB | 20-day institutional valuation & macro spread |

---

## 3. Serving & Loader Integration

- **Loader**: `backend/app/ml/serving/model_loader.py` preloads the bundle from `backend/models/production/v3/` at server startup.
- **Inference Engine**: `backend/app/ml/serving/inference.py` applies horizon-aware inference for `1D`, `1W`/`5D`, `2W`/`10D`, and `1M`/`20D`.
- **REST Endpoint**: `GET /api/v1/forecast/{symbol}?horizon={H}` in `backend/app/api/v1/forecast.py`.
