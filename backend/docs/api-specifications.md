# Basarat — API Specifications
### Trade Recommendation & Assistance System for PSX

**Version:** 1.1 | **Document:** API Specifications | **Source of truth:** Basarat Execution Document — §2 (Global API & Data Standards) and per-module Endpoint Tables (§6)

**Base URL:** `https://api.basarat.app/api/v1`  
**Auth:** Bearer JWT — `Authorization: Bearer <access_token>`. Access token TTL 15 min; refresh token TTL 7 days, rotated on use (web: httpOnly cookie; Android: EncryptedSharedPreferences/DataStore).

---

## 1. Global Conventions (apply to every endpoint below)

### 1.1 Response Envelopes

**Success:**
```json
{ "success": true, "data": { ... }, "meta": { "timestamp": "2026-01-15T10:00:00Z" } }
```

**Error:**
```json
{ "success": false, "error": { "code": "VALIDATION_ERROR", "message": "...", "field": "email" } }
```

### 1.2 Pagination (list endpoints)

Query params `?page=1&limit=20` — response carries `meta: { page, limit, total, has_next }`.

### 1.3 HTTP Status Conventions

| Code | Meaning |
|---|---|
| 200 | Success |
| 201 | Created |
| 400 | Validation error |
| 401 | Unauthenticated |
| 403 | Forbidden (e.g. non-KMI-30 access under free tier) |
| 404 | Not found |
| 429 | Rate limited |
| 500 | Server error |

### 1.4 Rate Limiting

- Standard endpoints: **100 req/min per user**.
- `/assistant/chat` and `/risk/monte-carlo`: **10 req/min** (compute-heavy).

### 1.5 Realtime

- **WebSocket:** `wss://api.basarat.app/ws/market/live`
  - Subscribe: `{"action":"subscribe","symbols":["OGDC","LUCK"]}`
  - Server push: `{"type":"tick","symbol":"OGDC","price":...,"change_pct":...,"ts":...}`
- Fallback rule: 3 failed WS attempts → grace to REST polling.

---

## 2. Core System Routes

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | Root info: name, version, environment |
| GET | `/health` | Liveness probe — `{status:"ok"}` (no DB/Redis check) |
| GET | `/health/ready` | Readiness — pings DB + Redis, per-dependency status |
| GET | `/docs` | OpenAPI / Swagger UI |
| GET | `/api/v1/version` | Build/version string |

---

## 3. Module Endpoint Contracts

### 3.1 Module 1 — User Management & Auth

| Method | Endpoint | Body / Query | Notes |
|---|---|---|---|
| POST | `/auth/signup` | `email, password, full_name` | returns access + refresh |
| POST | `/auth/login` | `email, password` | — |
| POST | `/auth/refresh` | `refresh_token` | rotates token |
| POST | `/auth/logout` | — | blacklists refresh token |
| POST | `/auth/forgot-password` | `email` | — |
| POST | `/auth/reset-password` | `token, new_password` | — |
| GET | `/users/me` | — | profile + risk profile |
| PATCH | `/users/me` | `full_name, phone` | — |
| PATCH | `/users/me/risk-profile` | `risk_tolerance, sector_preferences, investment_horizon` | — |
| PATCH | `/users/me/notification-preferences` | `channels[], categories[]` | — |
| POST | `/devices/register` | `fcm_token, platform` | FCM registration (shared w/ M9) |

### 3.2 Module 2 — Market Dashboard

| Method | Endpoint | Query | Notes |
|---|---|---|---|
| GET | `/market/indices` | — | KSE-100/30, KMI-30 snapshot |
| GET | `/market/sector-heatmap` | — | `[{sector, avg_change_pct, stock_count}]` |
| GET | `/market/top-gainers` | `limit=10` | — |
| GET | `/market/top-losers` | `limit=10` | — |
| GET | `/market/volume-spikes` | `limit=10` | — |
| GET | `/market/sentiment-overview` | — | `{score:-1..1, label}` |
| WS | `/ws/market/live` | — | live tick stream |

### 3.3 Module 3 — Stock Analysis

| Method | Endpoint | Query | Notes |
|---|---|---|---|
| GET | `/stocks/search` | `q=` | autocomplete `{symbol,name,sector}` |
| GET | `/stocks/{symbol}/overview` | — | ltp, change, day range, market cap |
| GET | `/stocks/{symbol}/price-history` | `range=1D\|1W\|1M\|1Y` | OHLCV array |
| GET | `/stocks/{symbol}/technical-indicators` | `indicators=RSI,MACD,BB,SMA,ADX&period=14` | per-indicator series |
| GET | `/stocks/{symbol}/fundamentals` | — | EPS, PE, ROE, D/E, div yield |

### 3.4 Module 4 — ML Forecasting (GRU)

| Method | Endpoint | Query | Notes |
|---|---|---|---|
| GET | `/forecast/{symbol}` | `horizon=1D\|1W\|1M` | Typed response: direction/confidence, percentage probabilities, dates, price levels, optional model breakdown and market context. See Swagger's example for the complete JSON and units. |
| GET | `/forecast/{symbol}/history` | `limit=30` | past predictions vs realized outcome |

### 3.5 Module 5 — Recommendation Engine

| Method | Endpoint | Query/Body | Notes |
|---|---|---|---|
| GET | `/recommendations` | `risk_profile` (default user's), `sector` optional | list of signals |
| GET | `/recommendations/{symbol}` | — | full detail incl. reasoning breakdown |
| GET | `/recommendations/{symbol}/target-stop` | — | `target_price, stop_loss, method` |
| POST | `/recommendations/engine-weights` | `{gru_weight, technical_weight, fundamental_weight}` | optional/advanced |

### Forecast and recommendation response examples (Android)

These endpoints return the JSON object shown below directly; they do not wrap it in a `success`/`data` envelope. Fields with no available market or price data are present as `null`. Keep null-aware UI states for targets, ranges, and market context.

#### `GET /forecast/OGDC?horizon=1D`

```json
{
  "symbol": "OGDC",
  "horizon": "1D",
  "direction": "bullish",
  "confidence": 0.584,
  "probabilities": { "bullish": 58.4, "bearish": 22.0, "sideways": 19.6 },
  "as_of_date": "2026-09-22",
  "target_date": "2026-09-23",
  "current_price": 142.5,
  "target_price": 148.0,
  "expected_range": null,
  "stop_loss": 138.0,
  "signal_rating": "Strong Buy",
  "upside_pct": 3.86,
  "downside_pct": -3.16,
  "risk_reward_ratio": 1.22,
  "model_version": "ensemble",
  "gate_reason": "agree(bullish)",
  "models": {
    "gru": { "direction": "bullish", "bullish_pct": 61.0, "bearish_pct": 20.0, "sideways_pct": 19.0, "gap_pp": 41.0 },
    "xgb": { "direction": "bullish", "bullish_pct": 56.0, "bearish_pct": 24.0, "sideways_pct": 20.0, "gap_pp": 32.0 }
  },
  "market_context": {
    "market_return_5d": 0.012,
    "market_return_20d": 0.034,
    "stock_return_20d": -0.058,
    "stock_relative_return_20d": -0.092
  }
}
```

#### `GET /recommendations?risk_profile=moderate&limit=20`

```json
{
  "count": 1,
  "risk_profile": "moderate",
  "recommendations": [
    {
      "symbol": "OGDC",
      "name": "OGDC",
      "sector": "Energy",
      "signal": "BUY",
      "confidence": 0.72,
      "composite_score": 0.36,
      "current_price": 142.5,
      "target_price": 148.0,
      "stop_loss": 138.0,
      "expected_range": null,
      "upside_pct": 3.86,
      "downside_pct": -3.16,
      "risk_reward_ratio": 1.22,
      "summary": "Strong buy: rsi: RSI=35.2"
    }
  ]
}
```

#### `GET /recommendations/OGDC`

```json
{
  "symbol": "OGDC",
  "signal": "BUY",
  "confidence": 0.72,
  "composite_score": 0.36,
  "signals": { "ml": 0.45, "technical": 0.38, "fundamental": 0.15 },
  "target_price": 148.0,
  "stop_loss": 138.0,
  "expected_range": null,
  "current_price": 142.5,
  "atr_14": 2.75,
  "upside_pct": 3.86,
  "downside_pct": -3.16,
  "risk_reward_ratio": 1.22,
  "target_stop_method": "atr_band",
  "risk_profile": "moderate",
  "reasoning": {
    "ml": { "rsi": "RSI=35.2", "macd": "MACD_hist=0.0012" },
    "technical": { "rsi": "RSI=35.2", "macd": "MACD_cross=0.0012" },
    "fundamental": { "pe": "P/E=8.5" }
  },
  "weights": { "gru": 0.4, "technical": 0.35, "fundamental": 0.25 }
}
```

**Screen mapping and units:** `signal`/`direction` drive the badge; `confidence` is a 0–1 score (multiply by 100 for display); forecast `probabilities` and model percentages are already 0–100; `composite_score` and `signals.*` are signed scores in -1..1; price fields are PKR; `upside_pct`/`downside_pct` are signed percentages; `risk_reward_ratio` is unitless; forecast market returns are decimal ratios (0.012 = 1.2%). Dates are ISO `YYYY-MM-DD`. Forecast confidence is an uncalibrated model score, not a promise of accuracy. `expected_range` is an object with `low`, `high`, and `method` when the signal is sideways; otherwise it is `null`.

### 3.6 Module 6 — Portfolio Management

| Method | Endpoint | Body | Notes |
|---|---|---|---|
| GET | `/portfolio` | — | holdings + total value |
| POST | `/portfolio/holdings` | `symbol, quantity, avg_buy_price, purchase_date` | — |
| PATCH | `/portfolio/holdings/{id}` | any field | — |
| DELETE | `/portfolio/holdings/{id}` | — | — |
| GET | `/portfolio/pnl` | — | unrealized P&L summary |
| GET | `/portfolio/allocation` | — | sector breakdown array |
| GET | `/portfolio/risk-metrics` | — | VaR, Sharpe, max_drawdown |

### 3.7 Module 7 — Risk & Sentiment Analytics

| Method | Endpoint | Query/Body | Notes |
|---|---|---|---|
| GET | `/risk/var` | `confidence=95, horizon=1D` | portfolio-level |
| GET | `/risk/cvar` | `confidence=95` | — |
| POST | `/risk/monte-carlo` | `{num_simulations, horizon_days}` | async → `job_id` |
| GET | `/risk/monte-carlo/{job_id}` | — | poll result: distribution, percentiles |
| GET | `/risk/stress-test` | `scenario=2008_crash\|pkr_devaluation` | — |
| GET | `/sentiment/{symbol}` | — | `{score, label, article_count, trend}` |
| GET | `/sentiment/market-overview` | — | overall market mood |

### 3.8 Module 8 — News & Events Intelligence

| Method | Endpoint | Query / Body | Notes |
|---|---|---|---|
| GET | `/news` | `symbol=, sentiment=, source=, event_type=, page=, limit=` | Paginated feed with multi-filter. DB read only — never scrapes. |
| GET | `/news/{id}` | — | Full article: symbols, event type, sentiment label + score, impact score |
| POST | `/news/refresh` | — | Manual refresh with cooldown protection (5 min). Returns status, last_updated, refresh_available, next_refresh_at |
| GET | `/news/market-status` | — | Current PKT time, market window (market_hours/post_market/closed), next ingestion window |
| GET | `/events/calendar` | `from=, to=, event_type=, symbol=` | Earnings/dividend/SBP monetary policy events, filtered by date range |

**News refresh behaviour:**
- `POST /news/refresh` respects a configurable cooldown (default 5 min) — repeated clicks within the cooldown return `refresh_available: false` with `next_refresh_at`.
- Outside PSX market hours (before 09:30, after 17:00 PKT, weekends), refresh returns `status: "skipped_outside_hours"` without scraping.
- During market hours (09:30–15:30) and post-market (15:30–17:00), refresh triggers the full ingestion pipeline.
- The same `run_pipeline()` function is used by both `POST /news/refresh` and the scheduled Celery task — single implementation, no duplication.

**News response shape:**
```json
{
  "items": [
    {
      "id": "abc123",
      "title": "OGDC reports strong quarterly earnings",
      "url": "https://brecorder.com/news/...",
      "source": "Business Recorder",
      "source_type": "financial_media",
      "summary": "...",
      "symbols": ["OGDC"],
      "company_names": ["Oil and Gas Development Company"],
      "event_type": "earnings",
      "sentiment_label": "positive",
      "sentiment_score": 0.91,
      "impact_score": 78,
      "published_at": "2026-09-16T10:30:00",
      "created_at": "2026-09-16T10:35:00"
    }
  ],
  "total": 150,
  "page": 1,
  "limit": 20,
  "has_more": true
}
```

### 3.9 Module 9 — Alerts & Notifications

| Method | Endpoint | Body | Notes |
|---|---|---|---|
| GET | `/alerts/rules` | — | user's active rules |
| POST | `/alerts/rules` | `type, symbol, condition, threshold_value, channels[]` | — |
| PATCH | `/alerts/rules/{id}` | any field | — |
| DELETE | `/alerts/rules/{id}` | — | — |
| GET | `/notifications` | `page, limit, unread_only` | — |
| PATCH | `/notifications/{id}/read` | — | — |
| POST | `/devices/register` | `fcm_token, platform` | shared with Module 1 |

### 3.10 Module 10 — Community Trading Hub

All `/community` endpoints except `GET /community/share/{short_code}` require a Bearer access token.
Errors use the shared app error shape: `{error, message, field?, extras?}` (e.g. `INVALID_STOCK_TAG`,
`CONTENT_REJECTED`, `RATE_LIMITED`, `POST_NOT_FOUND`, `FORBIDDEN`, `MAX_DEPTH_EXCEEDED`).

| Method | Endpoint | Body/Query | Notes |
|---|---|---|---|
| POST | `/community/posts` | `{content (1-500), symbols[1-3], sentiment?, mediaUrl?}` | 201; 1-3 real tickers; content filter; 30s/post Redis rate-limit → 429 |
| GET | `/community/feed` | `cursor?, limit (≤50), filter=all\|following` | cursor-paginated; `following` behaves like `all` in v1 |
| GET | `/community/stocks/{symbol}/posts` | `cursor?, limit` | posts tagged to one ticker |
| GET | `/community/posts/{postId}` | — | single post |
| DELETE | `/community/posts/{postId}` | — | owner only, soft delete → 204 |
| POST | `/community/posts/{postId}/like` | — | toggle; returns `{postId, likedByMe, likeCount}` |
| POST | `/community/posts/{postId}/comments` | `{content (1-300), parentCommentId?}` | depth 2 max; 201 |
| GET | `/community/posts/{postId}/comments` | `cursor?, limit` | top-level + one level of replies |
| POST | `/community/reports` | `{targetType: POST\|COMMENT, targetId, reason}` | idempotent; auto-flags post at threshold |
| POST | `/community/posts/{postId}/share` | — | returns `{shortUrl, shortCode}` |
| GET | `/community/share/{shortCode}` | — | **public**; teaser + `{deepLink, androidPackage, playStoreUrl}` only |

### 3.11 Module 11 — Shariah Compliance Screener

| Method | Endpoint | Query | Notes |
|---|---|---|---|
| GET | `/shariah/{symbol}` | — | overall score + compliance label |
| GET | `/shariah/{symbol}/criteria` | — | per-criterion pass/fail + ratios |
| GET | `/shariah/{symbol}/purification` | `holding_qty, holding_value` | computed purification amount |
| GET | `/shariah/kmi30` | — | KMI-30 constituent symbols |

### 3.12 Module 12 — Personal AI Assistant

| Method | Endpoint | Body/Query | Notes |
|---|---|---|---|
| POST | `/assistant/chat` | `message, conversation_id?` | full response or streamed |
| GET | `/assistant/conversations` | — | list: title, last_message_at |
| GET | `/assistant/conversations/{id}` | — | full message history |
| GET | `/assistant/quick-prompts` | — | predefined prompt suggestions |

---

## 4. API Contract Rules (for every endpoint)

1. Every expensive endpoint is a thin handler: check Redis cache → return on hit → compute on miss → write back → return (see Caching Strategy in System Architecture).
2. All endpoints except signup/login/forgot-password require authentication (NFR-4).
3. Error envelopes always carry a machine-readable `code`; clients map codes to localized copy, never parse raw messages.
4. Pagination meta is consistent: `{page, limit, total, has_next}` on every list endpoint.
5. No number is returned as a bare assertion: forecasts, recommendations, sentiment, and risk values carry confidence/methodology indicators (NFR-7).
6. News endpoints return **summaries + source links only** — never full copyrighted article bodies (ToS).

---
*Derived from the Basarat Execution Document — Section 2 (Global API & Data Standards) and the per-module endpoint tables in Section 6.*
