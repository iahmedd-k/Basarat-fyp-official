# Recommendation API contract for mobile clients

The authenticated recommendation endpoints return flat JSON suitable for Android rendering:

- `GET /api/v1/recommendations`: cards/list.
- `GET /api/v1/recommendations/{symbol}`: detail and component explanation.
- `GET /api/v1/recommendations/{symbol}/target-stop`: risk levels.
- `GET` and `POST /api/v1/recommendations/engine-weights`: configured source weights. Defaults are ML 0.30, technical 0.25, fundamental 0.25, and FinBERT sentiment 0.20. `ml_weight` is the canonical Android field; legacy `gru_weight` remains accepted and returned for older clients. If both are sent, they must match. Older saved three-source preferences retain a zero sentiment weight until updated.

## Fields to display

- Show `signal` prominently and `decision_reason` below it.
- Label `confidence` as **signal strength**, because `confidence_type` is `heuristic_signal_strength`; it is not a probability of success.
- Show `horizon`, `data_as_of`, and `data_freshness` beside the signal. `data_freshness` is `stale` after two weekdays (weekends excluded; exchange holidays are not known), and the response includes calendar/trading-day ages. `generated_at` is when the API assembled the response, not when market data was last updated. Stale market data is also called out in `summary`.
- Prices and ATR levels are in `currency` (PKR). Use `target_stop_method` and `target_stop_reason` to explain ATR levels. A HOLD has no directional target/stop; its `expected_range` is a volatility envelope, not a price forecast.
- Render `signals`, `source_weights`, and `effective_source_weights` for ML, technical, fundamental, and FinBERT sentiment. Sentiment is omitted from the composite when no scored articles are available or its aggregate is older than seven days. Legacy `weights` uses `gru` for the ML component; mobile clients should prefer the canonical `source_*` maps.
- `model_probabilities` are fractions from 0 to 1. Only display them as calibrated probabilities when `probabilities_calibrated` is true; it is false for the current model.
- Treat `status` (`available`, `partial`, or `insufficient_data`) as a visible data-quality indicator. Do not infer freshness from `generated_at`; use `data_as_of`.
- In list responses, `count` is the number returned after `limit`; `total_count` is the number matching filters before the limit.

There is currently no Android application source tree in this repository, so this documents the mobile-facing API contract; an Android UI must bind its views to these response fields in the Android project.
