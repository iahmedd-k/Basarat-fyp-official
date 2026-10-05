# ML Deployment & Inference Documentation

## 1. Dual-Model Serving Architecture

In production, both **Attention-BiGRU v2** and **Multi-Horizon XGBoost v4** are preloaded into memory at application startup, executed concurrently per inference request, and blended via dynamic horizon weights.

```mermaid
flowchart TD
    subgraph ClientReq ["API Client Request"]
        REQ["GET /api/v1/forecast/{symbol}?horizon=1W<br/>(Options: 1D, 1W/5D, 2W/10D, 1M/20D)"]
    end

    subgraph MemoryLoaded ["Preloaded Model Singleton (model_loader.py)"]
        GRU_IN_MEM["artifacts.model<br/>(gru_model.keras + scaler.joblib)"]
        XGB_IN_MEM["artifacts.xgb_models<br/>5D, 10D, 20D UBJ Models"]
    end

    subgraph ConcurrentExecution ["Concurrent Inference (inference.py)"]
        GRU_RUN["_run_gru(symbol, 45d_sequence)<br/>Outputs: P_GRU (p_up, p_down)"]
        XGB_RUN["_run_xgb(symbol, date, horizon)<br/>Outputs: P_XGB (p_up, p_down)"]
    end

    subgraph BlendingEngine ["Horizon-Aware Ensemble Decision (_ensemble_decide)"]
        DECIDE["Blend Probabilities by Horizon:<br/>- 1D:  65% BiGRU + 35% XGBoost<br/>- 1W:  50% BiGRU + 50% XGBoost<br/>- 2W:  40% BiGRU + 60% XGBoost<br/>- 1M:  30% BiGRU + 70% XGBoost"]
        NEAR_TIE{"Spread |P_up - P_down| <= 5.0%?"}
        NEAR_TIE -->|Yes| UNCERTAIN["Direction: 'sideways' / 'uncertain'"]
        NEAR_TIE -->|No| DIRECTION["Direction: 'bullish' or 'bearish'"]
    end

    subgraph ResponseBuilding ["Output Response & Dynamic Targets"]
        TARGET_STOP["Dynamic ATR Target & Stop-Loss<br/>Target = Close + 2.0*ATR<br/>Stop = Close - 1.5*ATR"]
        RETURN["ForecastResponse (P_up, P_down, Direction, Target, StopLoss)"]
    end

    REQ --> GRU_RUN
    REQ --> XGB_RUN
    GRU_IN_MEM --> GRU_RUN
    XGB_IN_MEM --> XGB_RUN
    GRU_RUN --> DECIDE
    XGB_RUN --> DECIDE
    DECIDE --> NEAR_TIE
    UNCERTAIN --> TARGET_STOP
    DIRECTION --> TARGET_STOP
    TARGET_STOP --> RETURN
```

---

## 2. Dynamic Target & Stop-Loss Calculation

For every generated prediction, actionable risk-reward parameters are computed dynamically using price volatility and Average True Range (ATR):

### 2.1 Bullish Signals ($P_{\text{Bullish}} > 50\%$):
$$\text{Target Price} = \text{Close} + (2.0 \times \text{ATR}_{14})$$
$$\text{Stop Loss} = \text{Close} - (1.5 \times \text{ATR}_{14})$$
$$\text{Risk-to-Reward Ratio} = \frac{\text{Target Price} - \text{Close}}{\text{Close} - \text{Stop Loss}} = \frac{2.0}{1.5} \approx 1.33$$

### 2.2 Bearish Signals ($P_{\text{Bearish}} > 50\%$):
$$\text{Target Price} = \text{Close} - (2.0 \times \text{ATR}_{14})$$
$$\text{Stop Loss} = \text{Close} + (1.5 \times \text{ATR}_{14})$$

---

## 3. Quantitative Recommendation Engine Integration

Predictions feed into the multi-factor ranking service (`app/services/recommendation_service.py`):

$$\text{Final Score} = 0.35 \cdot S_{\text{Tech}} + 0.35 \cdot S_{\text{Fund}} + 0.20 \cdot S_{\text{ML\_Forecast}} + 0.10 \cdot S_{\text{Sentiment}}$$

Where:
- $S_{\text{Tech}} \in [0, 100]$: RSI, MACD histogram, and Bollinger position composite.
- $S_{\text{Fund}} \in [0, 100]$: P/E percentile, ROE, Dividend Yield, and Debt-to-Equity.
- $S_{\text{ML\_Forecast}} \in [0, 100]$: $100 \times P_{\text{Bullish}}$ from calibrated model output.
- $S_{\text{Sentiment}} \in [0, 100]$: $50 + (50 \times \text{FinBERT Compound Score})$.

---

## 4. Production Artifacts Layout

```
backend/models/production/v3/
├── gru_model.keras                 # Keras Attention-BiGRU sequential model
├── gru_best_weights.weights.h5     # Checkpointed neural weights
├── gru_scaler.joblib               # RobustScaler fitted on training dataset
├── gru_features.json               # 79 sequential feature names
├── xgb_model.ubj                   # 5D (1-Week) production model
├── xgb_model_10d.ubj               # 10D (2-Week) production model
├── xgb_model_20d.ubj               # 20D (1-Month) production model
├── xgb_features.json               # 70 cross-sectional rank feature names
├── model_manifest.json             # Manifest verifying active production status
└── multi_horizon_summary.json      # Empirical validation scores (5D, 10D, 20D)
```
