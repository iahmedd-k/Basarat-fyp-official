# Recommendation Engine Review & Architecture

See full comprehensive documentation at: **[`08-recommendation-engine.md`](./08-recommendation-engine.md)**.

## Summary & Quick Reference

The **Basarat Recommendation Engine** (`backend/app/services/recommendation_service.py`) combines:
1. **AI/ML Directional Forecast:** 30% default weight ($P_{\text{Up}} - P_{\text{Down}}$).
2. **Technical Momentum:** 25% default weight (RSI, MACD, Moving Averages).
3. **Fundamental Valuation:** 25% default weight (P/E, P/B, Dividend Yield).
4. **FinBERT News Sentiment:** 20% default weight ($P_{\text{Pos}} - P_{\text{Neg}}$ with 3-day exponential decay).

### Dynamic Risk Limits:
- **ATR 14 Target Price:** $P_{\text{entry}} + (\text{Multiplier} \times \text{ATR}_{14})$
- **ATR 14 Stop Loss:** $P_{\text{entry}} - (\text{Multiplier} \times \text{ATR}_{14})$
- **User Customization:** Users can override weights and risk profile (`conservative`, `moderate`, `aggressive`) via profile preferences.
