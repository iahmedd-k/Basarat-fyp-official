# ADR-005: GRU + XGBoost Ensemble for Stock Forecasting

## Status
Accepted / Implemented

## Context
The system needs to predict PSX stock price direction (bullish/bearish/sideways).

## Decision
Dual-model ensemble: GRU (TensorFlow 2.16) for temporal patterns + XGBoost for feature-based classification, with automated weekly retraining and quality gates.

## Alternatives
- **LSTM only**: GRU is more parameter-efficient
- **Transformer models**: Higher compute cost for limited PSX data
- **Single model**: Ensemble reduces single-model bias

## Consequences
- TensorFlow CPU dependency (~500MB+)
- Cold start ~2 minutes for model loading
- Production worker concurrency=1 due to memory
- Model registry tracks versions and promotion decisions

## Current Implementation
- Model loader: `app/ml/serving/model_loader.py`
- Inference: `app/ml/serving/inference.py`
- Prediction store: `app/ml/serving/prediction_store.py`
- Promotion: `app/ml/serving/promotion.py`
- Weekly retraining: `app/tasks/weekly_retraining.py`
