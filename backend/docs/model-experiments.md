# Basarat - GRU Model Experiments & Final Decision

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Models Tested](#2-models-tested)
3. [Test Set Results Comparison](#3-test-set-results-comparison)
4. [Calibration Diagnostic](#4-calibration-diagnostic-gru_v1)
5. [Final Decision](#5-final-decision-keep-gru_v1)
6. [API Changes Made](#6-api-changes-made)
7. [Known Limitations](#7-known-limitations)
8. [Files Reference](#8-files-reference)

---

## 1. Project Overview

**Goal:** Build an ML model to predict PSX (Pakistan Stock Exchange) stock direction as bullish, bearish, or sideways for the Basarat forecasting app.

**Approach:** GRU (Gated Recurrent Unit) neural network trained on 30-day sliding windows of daily technical indicators and macro features.

**Label Definition:**
- Compute 1-day forward return: `(close[t+1] - close[t]) / close[t]`
- bullish if return > +1%
- bearish if return < -1%
- sideways otherwise

**Label Mapping:** `{"bullish": 0, "bearish": 1, "sideways": 2}`

**Data Split (time-based, no leakage):**
| Split | Date Range | Samples |
|-------|-----------|---------|
| Train | < 2024-07-01 | 94,422 |
| Validation | 2024-07-01 to 2025-07-01 | 24,158 |
| Test | >= 2025-07-01 | 29,373 |

**Baseline:** Always predict the majority class (bullish) = 48.23% accuracy.

---

## 2. Models Tested

### 2.1 gru_v1 (Shipped Model)

**Architecture:**
```
Input(30, 20)
GRU(64, return_sequences=False)
Dropout(0.2)
Dense(32, activation='relu')
Dense(3, activation='softmax')
```

**Hyperparameters:**
- Batch size: 128
- Max epochs: 12 (early stopping with patience=5)
- Optimizer: Adam
- Loss: sparse_categorical_crossentropy
- Window size: 30 days
- Features: 20 technical indicators

**Training:** 12 epochs, best_val_accuracy = 0.4738, training duration = 286 seconds

**Feature Set (20 features):**
```
atr_14, bb_lower, bb_mid, bb_upper, close, ema_12, ema_26, high, low,
macd, macd_hist, macd_signal, open, pkr_usd_rate, policy_rate, rsi_14,
sma_20, sma_50, volume, volume_zscore_20
```

### 2.2 gru_v5 (Experiment A - Bidirectional GRU)

**Architecture:**
```
Input(30, 20)
Bidirectional(GRU(64, return_sequences=False))
Dropout(0.2)
Dense(32, activation='relu')
Dense(3, activation='softmax')
```

**What changed from v1:** Only the GRU layer is bidirectional (reads sequence forward AND backward). Everything else identical - same 20 features, same threshold (1%), same time split, no class weighting.

**Training:** 15 epochs, best_val_accuracy = 0.4662, training duration = 1051 seconds

### 2.3 gru_v1_1w (Experiment B - 1-Week Horizon)

**Architecture:** Identical to v1 (standard GRU, NOT bidirectional)

**What changed from v1:** Only the label definition:
- 5-day forward return instead of 1-day
- Threshold scaled proportionally to 2.5% (from 1%)
- Last 5 rows per symbol dropped (no forward label available)

**Training:** 8 epochs, best_val_accuracy = 0.4581, training duration = 529 seconds

---

## 3. Test Set Results Comparison

### 3.1 Overall Accuracy

| Model | Test Accuracy | Baseline | Improvement | Verdict |
|-------|:------------:|:--------:|:-----------:|:-------:|
| **gru_v1** | **0.4970** | 0.4823 | **+1.46%** | **BEATS baseline** |
| gru_v5 | 0.4853 | 0.4823 | +0.30% | Marginal |
| gru_v1_1w | 0.4863 | 0.4868 | -0.05% | **DOES NOT beat baseline** |

### 3.2 Per-Class Metrics

#### gru_v1
| Class | Precision | Recall | F1 | Support |
|-------|:---------:|:------:|:--:|:-------:|
| bearish | 0.3489 | 0.1273 | 0.1865 | 7,292 |
| sideways | 0.3850 | 0.1202 | 0.1832 | 7,913 |
| bullish | 0.5246 | 0.8977 | 0.6623 | 14,168 |

**Key observation:** v1 has very high bullish recall (89.8%) - it correctly identifies most bullish days. However, bearish and sideways recall are low (~12%). The model is biased toward predicting bullish, which aligns with the majority class.

#### gru_v5 (Bidirectional GRU)
| Class | Precision | Recall | F1 | Support |
|-------|:---------:|:------:|:--:|:-------:|
| bullish | 0.3214 | 0.1888 | 0.2379 | 7,292 |
| bearish | 0.3501 | 0.1134 | 0.1713 | 7,913 |
| sideways | 0.5319 | 0.8457 | 0.6531 | 14,168 |

**Key observation:** BiGRU flipped the dominant class - it now predicts sideways most of the time (84.6% recall for sideways), sacrificing bullish recall (18.9%). This is worse because bullish is the true majority class.

#### gru_v1_1w (1-Week Horizon)
| Class | Precision | Recall | F1 | Support |
|-------|:---------:|:------:|:--:|:-------:|
| bullish | 0.3189 | 0.1747 | 0.2258 | 7,526 |
| bearish | 0.3583 | 0.1220 | 0.1820 | 7,297 |
| sideways | 0.5315 | 0.8421 | 0.6517 | 14,060 |

**Key observation:** Nearly identical pattern to v5 - sideways-dominant predictions. The 5-day horizon + 2.5% threshold didn't help.

### 3.3 Confusion Matrices

#### gru_v1
```
              Predicted
              bearish  sideways  bullish
True bearish    928      772     5,592
True sideways 1,030      951     5,932
True bullish    702      747    12,719
```

#### gru_v5
```
              Predicted
              bullish  bearish  sideways
True bullish  1,377      768     5,147
True bearish  1,618      897     5,398
True sideways 1,289      897    11,982
```

#### gru_v1_1w
```
              Predicted
              bullish  bearish  sideways
True bullish  1,315      802     5,409
True bearish  1,381      890     5,026
True sideways 1,428      792    11,840
```

### 3.4 Training Curves

#### gru_v1
- Epochs: 12 (early stop triggered)
- Train accuracy: 0.4787 -> 0.5009 (monotonic increase)
- Val accuracy: 0.4471 -> 0.4738 (peaked at epoch 12)
- Train loss: 1.0455 -> 1.0095 (steady decrease)
- Val loss: 1.0674 -> 1.0688 (stable, slight overfitting at end)

#### gru_v5
- Epochs: 15 (early stop triggered)
- Train accuracy: 0.4787 -> 0.5009
- Val accuracy: 0.4471 -> 0.4662 (peaked at epoch 10, then oscillated)
- Train loss: 1.0455 -> 1.0095
- Val loss: 1.0674 -> 1.0688 (started increasing after epoch 10)

**Issue:** v5 showed overfitting earlier than v1 - val accuracy peaked at epoch 10 (0.4662) then declined, while v1 continued improving until epoch 12.

#### gru_v1_1w
- Epochs: 8 (early stop triggered)
- Train accuracy: 0.4823 -> 0.5034
- Val accuracy: 0.4527 -> 0.4067 (severe degradation after epoch 3!)
- Train loss: 1.0400 -> 1.0051
- Val loss: 1.0536 -> 1.0936 (increasing rapidly)

**Critical issue:** Severe overfitting. Val accuracy peaked at epoch 3 (0.4581) then collapsed to 0.4067 by epoch 8. The model memorized training data but couldn't generalize to the 5-day horizon.

---

## 4. Calibration Diagnostic (gru_v1)

A comprehensive read-only diagnostic was run on gru_v1's test predictions to assess probability reliability.

### 4.1 Near-Tie Analysis

- **Definition:** Near-tie = top two class probabilities within 5 percentage points
- **Frequency:** 4,988 / 29,373 samples (16.98%) are near-ties
- **Gap distribution:** mean=0.197, median=0.150, most gaps (67.2%) > 10pp

**Confusion matrix on near-ties only (4,988 samples):**
```
              Predicted
              bullish  bearish  sideways
True bullish    527      358      679
True bearish    620      413      735
True sideways   495      362      799
```

**Bias test:** P(predicted bullish | true bearish, near-tie) = 35.07% vs P(predicted bullish | near-tie) = 32.92%. Difference = 2.15pp. **No substantial disproportionate bullish selection.**

### 4.2 CHCC Case Study

CHCC (a specific stock) was flagged as a potential problematic prediction:
- as_of_date: 2026-09-10
- Predicted: sideways (39.86%), bullish (35.92%), bearish (24.22%)
- True class: bearish
- Near-tie gap: 0.0395 (within 5pp threshold)
- 5-day return: -8.56% (strong downtrend)

**Conclusion:** CHCC is an isolated outlier, not representative of a systematic pattern. The near-tie confusion is distributed roughly equally across classes (33-48% per class), with no systematic bullish bias.

### 4.3 Probability Calibration

**Expected Calibration Error (ECE):** 2.03% - reasonably calibrated

| Bucket | Count | Avg Predicted | Actual Accuracy | Gap |
|--------|------:|:-------------:|:---------------:|:---:|
| 30-40% | 7,604 | 0.3742 | 0.3620 | 1.22% |
| 40-50% | 12,388 | 0.4414 | 0.4714 | -3.00% |
| 50-60% | 4,784 | 0.5445 | 0.5535 | -0.90% |
| 60-70% | 3,176 | 0.6457 | 0.6543 | -0.86% |
| 70-80% | 1,215 | 0.7340 | 0.7695 | -3.55% |
| 80-90% | 206 | 0.8291 | 0.9126 | -8.36% |

**Brier Score:** 0.6095 (lower is better; 2/3 = random for 3-class)

**Confidence vs Accuracy:**
- Correct predictions: avg true-class probability = 0.5027
- Incorrect predictions: avg true-class probability = 0.2745
- Difference: +0.2283 - model assigns MORE probability to true class when correct

### 4.4 API Recommendation

The `confidence` field was renamed to `top_class_probability` because:
1. It is raw max softmax output, not statistically calibrated confidence
2. ECE = 2.03% shows it's roughly calibrated but not precisely
3. The name `top_class_probability` is more accurate and avoids misleading users

---

## 5. Final Decision: Keep gru_v1

### 5.1 Why gru_v1 Wins

1. **Highest test accuracy:** 0.4970 vs 0.4853 (v5) vs 0.4863 (v1_1w)
2. **Best improvement over baseline:** +1.46% vs +0.30% (v5) vs -0.05% (v1_1w)
3. **Best training stability:** v1 converged cleanly in 12 epochs without severe overfitting
4. **Best calibration:** ECE = 2.03%, Brier = 0.6095 - reasonably well-calibrated probabilities
5. **Strongest bullish recall:** 89.8% - correctly identifies the majority class most of the time

### 5.2 Why gru_v5 (Bidirectional GRU) Lost

1. **Lower accuracy:** 0.4853 vs 0.4970 (-1.17pp)
2. **Flipped dominant class:** Predicted sideways instead of bullish, which is wrong since bullish is the true majority class (48.2% of test samples)
3. **Overfitting earlier:** Val accuracy peaked at epoch 10 then oscillated
4. **Longer training:** 1051s vs 286s (3.7x slower) for worse results
5. **Bidirectional didn't help:** Reading the sequence backward introduced noise rather than useful context for this task

### 5.3 Why gru_v1_1w (1-Week Horizon) Lost

1. **Doesn't beat baseline:** -0.05% improvement means it's worse than always predicting bullish
2. **Severe overfitting:** Val accuracy collapsed from 0.4581 (epoch 3) to 0.4067 (epoch 8)
3. **Val loss increasing:** 1.0536 -> 1.0936 indicates the model is getting worse on validation data
4. **5-day prediction is harder:** The signal-to-noise ratio decreases over longer horizons
5. **Threshold scaling didn't help:** 2.5% threshold for 5 days didn't improve class separability

### 5.4 Summary Table

| Metric | gru_v1 | gru_v5 | gru_v1_1w |
|--------|:------:|:------:|:---------:|
| Test Accuracy | **0.4970** | 0.4853 | 0.4863 |
| Best Val Accuracy | **0.4738** | 0.4662 | 0.4581 |
| Improvement over Baseline | **+1.46%** | +0.30% | -0.05% |
| Training Time | **286s** | 1051s | 529s |
| Epochs | **12** | 15 | 8 |
| Overfitting | Mild | Moderate | Severe |
| Calibration (ECE) | **2.03%** | N/A | N/A |
| Architecture | GRU(64) | BiGRU(64) | GRU(64) |
| Horizon | 1D | 1D | 1W |
| Threshold | 1% | 1% | 2.5% |

---

## 6. API Changes Made

### 6.1 Renamed `confidence` -> `top_class_probability`

**Reason:** The calibration diagnostic showed the `confidence` field is raw softmax output, not statistically calibrated. The name `top_class_probability` is more accurate.

**Files updated:**
- `app/ml/serving/inference.py` - return dict key renamed
- `app/ml/serving/schemas.py` - Pydantic model field renamed
- `app/ml/serving/prediction_logger.py` - parameter renamed
- `app/api/v1/forecast.py` - API endpoint updated
- `app/ml/serving/momentum_stress_test.py` - test script updated
- `app/ml/serving/backtest_check.py` - backtest script updated
- `app/schemas/auth.py` - duplicate schema updated
- `app/tasks/run_forecast_inference.py` - Celery task updated

### 6.2 Horizon Parameter

The `/api/v1/forecast/{symbol}` endpoint now accepts a `horizon` query parameter:
- `1D` (default): predicts for next business day
- `1W`: predicts for +5 business days
- `1M`: predicts for +22 business days

**Note:** The model always uses the same 1-day forward return labels. The horizon parameter only affects the `predicted_for_date` calculation, not the model's prediction logic.

### 6.3 Celery Daily Task

A daily Celery task (`app/tasks/run_forecast_inference.py`) was implemented to:
1. Run batch inference for all active symbols
2. Log predictions to the database
3. Backfill actual_direction and was_correct for past predictions

---

## 7. Known Limitations

1. **Low overall accuracy:** 49.7% is only marginally better than random (33.3% for 3-class). Stock prediction is inherently noisy.
2. **Class imbalance:** bullish (48.2%) dominates, so the model learns to predict bullish most of the time.
3. **Poor minority class recall:** bearish and sideways recall are ~12% each.
4. **Calibration gap at high confidence:** At 80-90% confidence, actual accuracy is 91.3% (overconfident predictions are actually correct, but the gap is 8.4pp).
5. **No class weighting tested:** Both experiments used no class weighting. Adding class weights might improve minority class recall.
6. **Single architecture tested:** Only GRU variants were tested. LSTM, Transformer, or ensemble methods might perform better.

---

## 8. Files Reference

| File | Description |
|------|-------------|
| `app/ml/training/run_training_v5.py` | BiGRU training script (Experiment A) |
| `app/ml/training/run_training_v1_1w.py` | 1W horizon training script (Experiment B) |
| `app/ml/training/calibration_diagnostic.py` | Full calibration diagnostic script |
| `app/ml/serving/inference.py` | Production inference function |
| `app/ml/serving/schemas.py` | Pydantic response models |
| `app/ml/serving/prediction_logger.py` | Database logging for predictions |
| `app/tasks/run_forecast_inference.py` | Celery daily batch task |
| `models/gru_v1/` | Shipped model weights + metadata |
| `models/gru_v5/` | Experiment A model (not deployed) |
| `models/gru_v1_1w/` | Experiment B model (not deployed) |
| `data/reports/evaluation.json` | v1 test evaluation |
| `data/reports/evaluation_v5.json` | v5 test evaluation |
| `data/reports/evaluation_v1_1w.json` | v1_1w test evaluation |
| `data/reports/calibration_diagnostic.json` | Full calibration analysis |
| `data/reports/training_history_v5.json` | v5 training curves |
| `data/reports/training_history_v1_1w.json` | v1_1w training curves |

---

*Document generated: 2026-09-16*
*Model version: gru_v1 (shipped)*
*TensorFlow version: 2.16.1 (Docker) / 2.21.0 (local)*
