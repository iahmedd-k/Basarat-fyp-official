# ADR-005: Dual-Model Machine Learning Ensemble for PSX Forecasting

## Status
**Accepted / Implemented**

## Context
Financial time-series forecasting for emerging equity markets like the Pakistan Stock Exchange (PSX) suffers from high market noise, regime shifts, and non-stationarity. Single-architecture models (pure LSTM or pure Gradient Boosting) frequently overfit or fail to capture both sequential temporal patterns and cross-sectional tabular features simultaneously.

## Decision
Adopt a **Hybrid Dual-Model Ensemble Architecture** combining Deep Learning with Gradient Boosted Decision Trees:

1. **Temporal Sequential Model — Stationary Attention-BiGRU (v2 Production):**
   - Architecture: Input (45-day lookback window x 79 normalized stationary features) -> SpatialDropout1D -> Conv1D (64 filters) -> LayerNorm -> Bidirectional GRU (64 units) -> LayerNorm -> Bidirectional GRU (32 units) -> Temporal Attention Pooling -> Dense layers -> Sigmoid output.
   - Purpose: Captures multi-timeframe sequential momentum, volatility clustering, and price action dynamics.
2. **Tabular & Event Classifier — XGBoost v4:**
   - Architecture: Gradient Boosted Trees trained on technical indicators, fundamental valuation ratios (P/E, ROE, Debt/Equity), and corporate event flags.
   - Purpose: Provides strong non-linear tabular decision boundaries and prevents deep learning hallucination during low-volatility regimes.
3. **Serving & Gating Layer:**
   - Load pre-trained weights (`gru_best_weights.weights.h5`, `xgb_model.ubj`, `gru_scaler.joblib`) into memory at startup as singletons.
   - Combine model class probabilities using weighted voting.
   - Enforce **Confidence Gating**: If top class probability is below threshold or if sub-models show irreconcilable divergence, classify prediction as `sideways` or record explicit `gate_reason`.
   - Record sub-model predictions (`gru_direction`, `xgb_direction`, probability gaps) in the `predictions` table for comprehensive auditability.

## Alternatives Considered
- **Pure LSTM / Vanilla RNN:** Rejected due to vanishing gradient problems on 45-day sequences and lack of temporal attention mechanisms.
- **Pure Transformer (Informer / PatchTST):** Considered, but required significantly larger training datasets (> 100k samples) to generalize effectively on PSX without severe overfitting.
- **Static Linear Regressions / ARIMA:** Rejected because they cannot capture non-linear relationships, macroeconomic regime shifts, or cross-factor momentum.

## Consequences
- **Positive:** Superior out-of-sample directional accuracy and robustness; graceful fallback to single-model mode if one artifact is unavailable; full audit trail of model decisions.
- **Negative / Trade-off:** Memory footprint at startup requires ~500MB RAM to load TensorFlow and XGBoost weights; retraining requires running both deep learning and tree pipelines.

## Current Implementation
- Model architecture and startup loader in [app/ml/serving/model_loader.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/ml/serving/model_loader.py).
- Ensemble inference engine in [app/ml/serving/inference.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/ml/serving/inference.py).
- Prediction storage and audit logging in [app/ml/serving/prediction_store.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/ml/serving/prediction_store.py).
