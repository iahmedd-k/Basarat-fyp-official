# Recommendation API response contract

Recommendation responses now group fields by purpose and omit raw per-indicator diagnostics:

- List and detail items use `decision`, `components`, `market_data`, and `risk` objects. Each component reports its score, availability, configured weight, and effective weight. Unavailable scores are `null`, not zero, and include an `availability_reason`.
- `GET /api/v1/recommendations/{symbol}/target-stop` returns the same grouped decision, market data, and risk objects.
- `GET /api/v1/recommendations/engine-weights` returns `{"weights":{"ml":0.30,"technical":0.25,"fundamental":0.25,"sentiment":0.20}}` by default. POST accepts the legacy flat weight request (including `gru_weight`) and returns the grouped shape. Older saved three-source preferences retain a zero sentiment weight until updated.

## Fields to display

- Read the actionable direction and reason from `decision`; `confidence` is heuristic signal strength, not a probability.
- Read component scores and availability from `components`. Missing sources have `score: null` plus `availability_reason`; the service reweights the available components.
- Read `market_data.freshness` and its age fields before displaying a recommendation. Data more than two weekdays old, or with unknown freshness, downgrades stale BUY/SELL signals to HOLD, sets confidence to zero, and suppresses target/stop/range levels. An existing HOLD remains an ordinary HOLD. `decision.suppressed` and `decision.suppression_reason` are set only when a directional signal was downgraded.
- Prices and ATR levels are in `market_data.currency` (PKR). `risk` contains levels and their explanation; these are volatility estimates, not forecasts or execution guarantees.
- `generated_at` is when the API assembled the response, not when market data was last updated. In list responses, `count` is returned after `limit`; `total_count` is the number matching filters before the limit.

There is currently no Android application source tree in this repository, so this documents the mobile-facing API contract; an Android UI must bind its views to these response fields in the Android project.
