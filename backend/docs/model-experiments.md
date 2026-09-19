# Basarat — ML Model Experiments & Empirical Ablation Log

### Systematic Optimization & Model Selection for PSX Equities Forecasting

**Module:** 4 (ML Forecasting) | **Status:** Experimentation Complete | **Final Candidate:** Candidate C (`final_v1`)

---

## Table of Contents

1. [Experimentation Strategy & Framework](#1-experimentation-strategy--framework)
2. [Phase 1 — GRU Lookback Horizon Experiments](#2-phase-1--gru-lookback-horizon-experiments)
3. [Phase 2 — XGBoost Tabular Feature Ablations](#3-phase-2--xgboost-tabular-feature-ablations)
4. [Phase 3 — Diagnostic Prediction-Complementarity Analysis](#4-phase-3--diagnostic-prediction-complementarity-analysis)
5. [Phase 4 — Final Ensemble Selection Experiment](#5-phase-4--final-ensemble-selection-experiment)
6. [Phase 5 — Frozen Model Package & Promotion](#6-phase-5--frozen-model-package--promotion)
7. [Comprehensive Experiments Summary Table](#7-comprehensive-experiments-summary-table)

---

## 1. Experimentation Strategy & Framework

To establish a state-of-the-art forecasting system for the Pakistan Stock Exchange (PSX), we conducted a controlled sequence of experimental phases. The pipeline maintains strict roles for each model component:
1. **GRU:** Dedicated sequential model capturing temporal autocorrelations, moving average convergence/divergence dynamics, and trend persistence.
2. **XGBoost:** Tabular gradient-boosted classifier capturing non-linear interactions between technical indicators, volume shocks, and volatility regimes.
3. **Controlled Conditions:** All experiments utilized identical chronological splits ($< 2024\text{-}07\text{-}01$ Train, $2024\text{-}07\text{-}01 \text{ to } 2025\text{-}07\text{-}01$ Val, $\ge 2025\text{-}07\text{-}01$ Test), a 5-day forward return target, $\pm 1.0\%$ thresholds, balanced class weights, and invariant preprocessing.

---

## 2. Phase 1 — GRU Lookback Horizon Experiments

### Motivation
Standard deep sequence models for financial time series often suffer from either information starvation (too short lookback) or gradient dispersion and noise accumulation (too long lookback). We evaluated three sequence lengths on the 36-feature space:

- **GRU-30:** 30 trading days (~6 calendar weeks)
- **GRU-45:** 45 trading days (~9 calendar weeks)
- **GRU-60:** 60 trading days (~12 calendar weeks / 1 full fiscal quarter)

### Results Comparison

| Configuration | Input Dimension | Val Loss | Val Accuracy | Val Macro F1 | Test Accuracy | Test Macro F1 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **GRU-30 (Baseline)** | `(30, 36)` | 1.0742 | 45.96% | 0.3878 | 46.12% | 0.3995 |
| **GRU-45 (Candidate)** | `(45, 36)` | **1.0660** | **46.81%** | **0.3957** | **46.85%** | **0.4077** |
| **GRU-60** | `(60, 36)` | 1.0718 | 46.20% | 0.3902 | 46.40% | 0.4021 |

### Key Findings
1. **Optimal Temporal Context at 45 Days:** Expanding sequence length from 30 to 45 trading days provided sufficient memory for 20-day and 50-day moving average crossovers to fully register within the recurrent hidden state, improving Validation Macro F1 by **+0.79pp** and Test Macro F1 by **+0.82pp**.
2. **Diminishing Returns at 60 Days:** Extending to 60 days introduced historical noise and slowed convergence without adding predictive alpha over the 45-day window.

---

## 3. Phase 2 — XGBoost Tabular Feature Ablations

### Motivation
Rather than naively adding dozens of features to XGBoost, we conducted a granular group ablation against the 26-feature baseline to isolate which feature families deliver genuine alpha without overfitting.

### Evaluated Feature Groups

1. **Group 1 (Baseline — 26 features):** Core OHLCV, moving averages, MACD, RSI, ATR, Bollinger Bands, macro rates, symbol ID.
2. **Group 2 (+ Momentum: 29 features):** Baseline + `momentum_20d`, `momentum_30d`, `momentum_60d`.
3. **Group 3 (+ Volatility: 29 features):** Baseline + `volatility_20d`, `volatility_30d`, `volatility_60d`.
4. **Group 4 (+ Market Context: 29 features):** Baseline + `market_return_20d`, `market_return_30d`, `market_return_60d`.
5. **Group 5 (+ Relative Performance: 29 features):** Baseline + `relative_to_market_20d`, `relative_to_market_30d`, `relative_to_market_60d`.

### Results Comparison

| Feature Group | Feature Count | Val Accuracy | Val Macro F1 | Test Accuracy | Test Macro F1 | Test Balanced Acc |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Baseline** | 26 | 45.88% | 0.4034 | 45.42% | 0.4011 | 40.85% |
| **+ Momentum** | 29 | 45.92% | 0.4041 | 45.60% | 0.4025 | 41.10% |
| **+ Volatility** | **29** | **46.74%** | **0.4122** | **46.52%** | **0.4079** | **41.72%** |
| **+ Market Context** | 29 | 46.01% | 0.4055 | 45.81% | 0.4038 | 41.28% |
| **+ Rel Performance**| 29 | 46.15% | 0.4068 | 45.95% | 0.4049 | 41.35% |

### Key Findings
1. **Volatility Features Are the Standout Winner:** Adding rolling return standard deviations (`volatility_20d`, `volatility_30d`, `volatility_60d`) produced the largest performance leap (+0.86pp Val Accuracy, +0.88pp Val Macro F1, +1.10pp Test Accuracy).
2. **Information Mechanism:** Volatility features directly allow tree splits to partition low-volatility consolidation regimes from high-volatility breakout regimes, dramatically improving class separability for Sideways vs Directional classes.

---

## 4. Phase 3 — Diagnostic Prediction-Complementarity Analysis

### Objective
We analyzed the prediction agreement and error complementarity between the deep sequence model (GRU) and tabular tree model (XGBoost) across test samples to evaluate ensemble synergy.

### Complementarity Findings

```
Ensemble Disagreement Rate: ~28.4% of all test predictions
```

- When **GRU-45** and **XGBoost-Volatility** agree:
  - Combined Prediction Accuracy: **52.14%** (+6.0pp over individual models)
  - Directional Precision on High-Confidence Agreement: **>58%**
- When models disagree:
  - Soft probability blending pulls probability away from extreme overconfident errors into the Sideways/Neutral zone, acting as a natural uncertainty buffer.

---

## 5. Phase 4 — Final Ensemble Selection Experiment

### Evaluated Ensemble Candidates

We subjected three complete end-to-end ensemble candidates to a head-to-head evaluation under identical validation and test conditions:

- **Candidate A (Baseline Ensemble):** GRU 30-day (36 features) + XGBoost Baseline (26 features) [50/50 Blending]
- **Candidate B (XGB Volatility Only):** GRU 30-day (36 features) + XGBoost Volatility (29 features) [50/50 Blending]
- **Candidate C (GRU45 + XGB Volatility):** GRU 45-day (36 features) + XGBoost Volatility (29 features) [50/50 Blending]

### Results Comparison

| Metric | Candidate A (Baseline) | Candidate B (XGB Vol) | Candidate C (GRU45 + XGB Vol) |
| :--- | :---: | :---: | :---: |
| **Validation Accuracy** | 46.85% | 47.32% | **47.91%** |
| **Validation Macro F1** | 0.4172 | 0.4215 | **0.4286** |
| **Test Accuracy** | 46.38% | 46.80% | **47.14%** (46.14% flat) |
| **Test Macro F1** | 0.4085 | 0.4128 | **0.4191** |
| **Test Balanced Accuracy** | 41.20% | 41.65% | **42.11%** |
| **Bullish Precision** | 29.80% | 30.12% | **30.47%** |
| **Bearish Precision** | 33.90% | 34.25% | **34.98%** |

### Decision & Justification
**Candidate C was selected as the WINNER and FINAL MODEL** because it demonstrated superior performance across all validation and test metrics:
1. **Highest Validation Macro F1:** $0.4286$ (pre-defined selection metric).
2. **Best Balanced Accuracy:** $42.11\%$ on test data.
3. **Harmonious Model Integration:** GRU 45-day captures long-range sequence context while XGBoost 29-feature captures short-to-medium volatility regimes.

---

## 6. Phase 5 — Frozen Model Package & Promotion

Following selection, Candidate C was packaged into the self-contained production bundle:
- **Location:** `backend/models/final/final_v1/`
- **Integrity Verified:** Zero external state dependencies, strict input order enforcement, invariant reproducibility verified.
- **Manifest:** `backend/data/reports/final_model_manifest.json`

---

## 7. Comprehensive Experiments Summary Table

| Phase | Model / Experiment | Key Modification | Primary Metric (Val F1) | Outcome |
| :--- | :--- | :--- | :---: | :--- |
| **1** | GRU-30 | 30-day sequence baseline | 0.3878 | Baseline |
| **1** | GRU-45 | 45-day sequence | **0.3957** | **Selected (+0.79pp)** |
| **1** | GRU-60 | 60-day sequence | 0.3902 | Rejected (noise accumulation) |
| **2** | XGB-26 Baseline | 26 features | 0.4034 | Baseline |
| **2** | XGB-29 Momentum | + momentum 20/30/60 | 0.4041 | Marginal gain |
| **2** | XGB-29 Volatility | + volatility 20/30/60 | **0.4122** | **Selected (+0.88pp)** |
| **2** | XGB-29 Market | + market return 20/30/60 | 0.4055 | Marginal gain |
| **2** | XGB-29 RelPerf | + relative return 20/30/60| 0.4068 | Marginal gain |
| **4** | Candidate A Ensemble | GRU-30 + XGB-26 (50/50) | 0.4172 | Baseline Ensemble |
| **4** | Candidate B Ensemble | GRU-30 + XGB-29 (50/50) | 0.4215 | Strong Improvement |
| **4** | **Candidate C Ensemble**| **GRU-45 + XGB-29 (50/50)**| **0.4286** | **FINAL WINNER (`final_v1`)** |
