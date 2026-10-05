# ML Model Architecture Documentation

## 1. Subsystem Architecture Overview

The Basarat intelligence layer employs an **institutional dual-model ensemble** combining sequential deep learning with tabular gradient boosted decision trees:
- **Sequential Price Dynamics**: **Attention-BiGRU v2** (Bidirectional Gated Recurrent Units with temporal attention pooling over a 45-day lookback window).
- **Tabular Cross-Sectional Alpha**: **XGBoost v4** (Multi-horizon gradient boosted trees trained on cross-sectional rank features).
- **Dual-Model Inference**: Both models are loaded simultaneously into memory at application startup, executed concurrently on each inference request, and blended via **Horizon-Aware Weighted Softmax Calibration**.
- **Financial NLP Sentiment**: **FinBERT** transformer model.
- **Conversational Decision Copilot**: **Groq Llama 3.3 70B** with financial RAG context and safety filters.

```mermaid
flowchart TD
    subgraph DataInputs ["Point-in-Time Data Feeds"]
        SEQ_IN["45-Day Sequential Tensor<br/>(Shape: 1, 45, 79)"]
        TAB_IN["Point-in-Time Tabular Row<br/>(70 Cross-Sectional Rank Features)"]
    end

    subgraph DualModelExec ["Concurrent Model Execution (Inference Engine)"]
        SEQ_IN --> BIGRU["Attention-BiGRU v2<br/>(gru_model.keras / gru_best_weights.weights.h5)<br/>Captures sequential momentum & price velocity"]
        TAB_IN --> XGB["Multi-Horizon XGBoost v4<br/>(xgb_model.ubj / xgb_model_10d.ubj / xgb_model_20d.ubj)<br/>Captures cross-sectional valuation & alpha interactions"]
    end

    subgraph HorizonBlending ["Horizon-Aware Ensemble Blending (_ensemble_decide)"]
        BIGRU --> P_GRU["P_GRU: [P_up, P_down]"]
        XGB --> P_XGB["P_XGB: [P_up, P_down]"]
        
        P_GRU & P_XGB --> BLEND["Dynamic Weight Matrix<br/>• 1D:  65% GRU + 35% XGB<br/>• 1W (5D):  50% GRU + 50% XGB<br/>• 2W (10D): 40% GRU + 60% XGB<br/>• 1M (20D): 30% GRU + 70% XGB"]
    end

    subgraph DecisionGate ["Confidence & Near-Tie Decision Gate"]
        BLEND --> NEAR_TIE{"|P_up - P_down| <= 5.0pp?"}
        NEAR_TIE -->|Yes (Near-Tie)| SIDEWAYS["Emit SIDEWAYS / UNCERTAIN Direction"]
        NEAR_TIE -->|No (Clear Spread)| ACTIONABLE["Emit Confident Direction (BULLISH / BEARISH)"]
    end
```

---

## 2. Sequential Deep Learning Model: Attention-BiGRU v2

### 2.1 Architecture Specification
The Attention-BiGRU model (`gru_model.keras`) processes a **45-trading-day rolling sequence** of 79 normalized price, volume, and momentum indicators:

```
Input: Tensor of shape (Batch_Size, Lookback_Window=45, Feature_Dim=79)
  │
  ├── 1. SpatialDropout1D (Rate = 0.10)
  ├── 2. 1D Convolutional Layer (Filters = 64, Kernel_Size = 3, Activation = ReLU)
  ├── 3. Layer Normalization
  ├── 4. Bidirectional GRU Layer 1 (Units = 64, Dropout = 0.15, Return Sequences = True)
  ├── 5. Layer Normalization
  ├── 6. Bidirectional GRU Layer 2 (Units = 32, Dropout = 0.15, Return Sequences = True)
  ├── 7. Layer Normalization
  │
  ├── 8. Temporal Attention Pooling
  │      - Dense Score Layer: score = Dense(1, activation='tanh')(x)
  │      - Attention Weights: weights = Softmax(axis=1)(score)
  │      - Context Vector: pooled = sum(x * weights, axis=1)
  │
  ├── 9. Dense Linear Layer (Units = 32, Activation = ReLU) + Dropout (0.20)
  ├── 10. Dense Linear Layer (Units = 16, Activation = ReLU) + Dropout (0.10)
  └── 11. Output Dense Layer (Units = 1, Activation = Sigmoid -> P_up)
```

---

## 3. Tabular Gradient Boosting Model: XGBoost v4

### 3.1 Multi-Horizon Model Files
In production, XGBoost is specialized across distinct forward holding horizons:

| Horizon | Artifact Filename | Focus Area |
|---|---|---|
| **5D (1-Week)** | `xgb_model.ubj` / `xgb_model_5d.ubj` | 5-day swing momentum & short-term reversals |
| **10D (2-Week)** | `xgb_model_10d.ubj` | 10-day intermediate trend & liquidity flows |
| **20D (1-Month)**| `xgb_model_20d.ubj` | 20-day valuation, 52W high distance & macroeconomic factors |

---

## 4. Horizon-Aware Ensemble Weighting Table

The blending weights dynamically balance fast technical signals with institutional fundamental factors:

| Horizon Code | Horizon Name | Holding Period | BiGRU Weight | XGBoost Weight | Primary Driver |
|---|---|---|:---:|:---:|---|
| **`1D`** | Intraday / Next-Day | 1 Trading Day | **65%** | 35% | High-frequency sequence velocity & price patterns |
| **`1W`** | 1-Week (5D) | 5 Trading Days | **50%** | **50%** | **Balanced Ensemble (Standard Production Baseline)** |
| **`2W`** | 2-Week (10D) | 10 Trading Days| 40% | **60%** | Cross-sectional intermediate momentum & volatility |
| **`1M`** | 1-Month (20D) | 20 Trading Days| 30% | **70%** | Institutional valuation, P/E, 52W high distance & macro |

---

## 5. Financial NLP & Conversational AI Models

- **FinBERT Financial Sentiment**: Processes unstructured corporate disclosures and news text, outputting class probabilities for `[Positive, Negative, Neutral]`.
- **Groq Llama 3.3 70B AI Copilot**: Ultra-fast conversational assistant enriched with live ticker metrics, technical RSI/MACD readings, KMI-30 Shariah criteria, and regulatory disclaimers.
