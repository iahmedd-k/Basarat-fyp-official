# ADR-009: Quantitative Rule-Based Recommendation Engine

## Status
**Accepted / Implemented**

## Context
Retail equity investors require objective, actionable, multi-factor stock signals (Strong Buy, Buy, Hold, Sell, Strong Sell) that harmonize disparate data streams: technical price trends, fundamental financial ratios, news sentiment, and machine learning forecast probabilities. A purely black-box ML model lacks explainability, while purely manual technical analysis is labor-intensive and subjective.

## Decision
Implement a **Multi-Factor Quantitative Scoring Engine** with customizable weight coefficients:

1. **Four Factor Pillars (Scored 0–100):**
   - **Technical Momentum (Weight default: 0.35):** Evaluates RSI (14), MACD histogram momentum, Exponential Moving Average alignment (EMA 20 > EMA 50 > EMA 200), and Bollinger Band positioning.
   - **Fundamental Valuation (Weight default: 0.25):** Evaluates Price-to-Earnings (P/E) relative to sector median, Return on Equity (ROE), and Debt-to-Equity ratios.
   - **Financial Sentiment (Weight default: 0.20):** Evaluates FinBERT rolling 30-day sentiment score and disclosure tone.
   - **ML Directional Forecast (Weight default: 0.20):** Evaluates the Attention-BiGRU + XGBoost ensemble directional probability.
2. **Composite Score & Action Mapping:**
   $$\text{Composite Score} = \sum_{i=1}^{4} (w_i \times \text{Factor Score}_i)$$
   - **$\ge 75$:** STRONG_BUY
   - **$60 - 74$:** BUY
   - **$40 - 59$:** HOLD
   - **$25 - 39$:** SELL
   - **$< 25$:** STRONG_SELL
3. **Automated Risk Target & Stop-Loss Calculation:**
   - Computes dynamic target prices and stop-loss levels based on Average True Range (ATR) and recent support/resistance levels.
4. **User-Customizable Weighting:**
   - Users can customize their factor preferences (e.g. Fundamental Value investors can set Fundamental=0.50, Technical=0.10), stored in `User.recommendation_weights`.

## Alternatives Considered
- **Pure Black-Box Deep Learning Ranking:** Rejected because users cannot understand why a stock was recommended, and models can fail dramatically during black swan market events.
- **Static Hardcoded Ranks:** Rejected because different investor personas (growth vs value vs momentum) require tailored weighting.

## Consequences
- **Positive:** Transparent, fully explainable investment rationale; mathematically rigorous; user-customizable; robust against single-source data errors.
- **Negative / Trade-off:** Requires up-to-date inputs across technicals, fundamentals, sentiment, and ML predictions to compute complete scores.

## Current Implementation
- Engine logic in [app/services/recommendation_service.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/services/recommendation_service.py).
- Router in [app/api/v1/recommendations.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/api/v1/recommendations.py).
