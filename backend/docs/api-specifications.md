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
| GET | `/forecast/{symbol}` | `horizon=1D\|1W\|1M` | `{direction, bullish_pct, bearish_pct, sideways_pct, confidence}` |
| GET | `/forecast/{symbol}/history` | `limit=30` | past predictions vs realized outcome |

### 3.5 Module 5 — Recommendation Engine

| Method | Endpoint | Query/Body | Notes |
|---|---|---|---|
| GET | `/recommendations` | `risk_profile` (default user's), `sector` optional | list of signals |
| GET | `/recommendations/{symbol}` | — | full detail incl. reasoning breakdown |
| GET | `/recommendations/{symbol}/target-stop` | — | `target_price, stop_loss, method` |
| POST | `/recommendations/engine-weights` | `{gru_weight, technical_weight, fundamental_weight}` | optional/advanced |

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

| Method | Endpoint | Query | Notes |
|---|---|---|---|
| GET | `/news` | `symbol=, sentiment=, page, limit` | paginated feed |
| GET | `/news/{id}` | — | summary + sentiment + impact |
| GET | `/events/calendar` | `from=, to=` | earnings/dividend/SBP events |

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

| Method | Endpoint | Body/Query | Notes |
|---|---|---|---|
| GET | `/community/feed` | `page, limit, symbol` | — |
| POST | `/community/posts` | `symbol, stance, rationale_text` | — |
| POST | `/community/posts/{id}/vote` | `direction: up\|down` | — |
| GET | `/community/posts/{id}/comments` | — | — |
| POST | `/community/posts/{id}/comments` | `text` | — |
| GET | `/community/leaderboard` | `period=weekly\|monthly\|all_time` | — |
| POST | `/community/posts/{id}/report` | `reason` | moderation |

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
