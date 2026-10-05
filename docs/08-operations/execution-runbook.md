# BASARAT — Execution Document
### Trade Recommendation & Assistance System for PSX
**Version:** 1.1 | **Prepared for:** Project Team | **Supervisor:** Dr. Faheem Ullah
**Confirmed Stack:** FastAPI (single shared backend) · React/Vite (Web, full parity) · Kotlin/Jetpack Compose (Android, full parity) · PostgreSQL + Redis · TensorFlow (GRU) + LangChain · Celery/APScheduler (jobs) · FCM (push)

> **How to use this document:** Each module is a self-contained work package — tasks, API contract, Android screen spec, React page spec, and Definition of Done. Backend endpoints are shared; both clients consume identically. Build module-by-module in the order given in Section 6 (Execution Phases), not module-by-platform.

---

## Table of Contents

0. [Tech Stack Decisions & Rationale](#0-tech-stack-decisions--rationale)
&nbsp;&nbsp;0.1 [Docker & Local Development Environment](#01-docker--local-development-environment)
&nbsp;&nbsp;0.2 [Firebase Setup (Push Notifications)](#02-firebase-setup-push-notifications)
1. [System Architecture & User Flow](#1-system-architecture--user-flow)
2. [Global API & Data Standards](#2-global-api--data-standards)
3. [Backend Project Structure & Core Routes](#3-backend-project-structure--core-routes)
4. [Android App Architecture](#4-android-app-architecture)
5. [React Web App Architecture](#5-react-web-app-architecture)
6. [Modules 1–12](#6-modules)
7. [Execution Phases & Order](#7-execution-phases--order)
8. [Consolidated Functional & Non-Functional Requirements](#8-consolidated-functional--non-functional-requirements)
9. [Database Entity Overview](#9-database-entity-overview-high-level)
10. [Models & Libraries Used](#10-models--libraries-used)
11. [Role Ownership Map](#11-role-ownership-map)

---

## 0. Tech Stack Decisions & Rationale

| Original (from proposal) | Decision | Why |
|---|---|---|
| Node.js + FastAPI | **FastAPI only** | ML (TensorFlow), NLP (FinBERT), AI Assistant (LangChain) are all Python-native. One backend = one auth system, one DB layer, no inter-service calls. Node's async I/O advantage is replaced by FastAPI's native `async def` + WebSockets. |
| Next.js | **React + Vite** | No SSR/SEO need — this is an authenticated dashboard, not a public site. Vite avoids Next.js's own API-route layer being accidentally used as a second backend. |
| (missing) Job scheduling | **Celery + Redis** (or APScheduler for MVP) | Scraping, GRU inference, and sentiment scoring must run on schedules independent of request/response cycles. |
| (missing) Push delivery | **Firebase Cloud Messaging (FCM)** | Needed for Alerts & Notifications module on Android; web uses in-app + optional browser push later. |
| (missing) Deployment | **Docker Compose** (FastAPI + Postgres + Redis + Celery worker), single VM for FYP scope | Keeps ops simple for a 3-person team; swap for Kubernetes only if scaling becomes a real requirement. |
| (missing) CI | **GitHub Actions**: lint + test on PR to `main` | Minimum viable guardrail before a supervisor demo. |

**Locked assumption going forward:** one FastAPI backend, versioned at `/api/v1/`, consumed identically by React (web) and Kotlin (Android), full 12-module parity on both clients.

---

### 0.1 Docker & Local Development Environment

> Scope note: this is for **local development consistency across the team only**. Production deployment is explicitly out of scope for now — no cloud hosting, no CI/CD deploy step is being planned at this stage. Docker here just means "everyone runs the exact same backend, DB, and cache with one command."

**Services in `docker-compose.yml`:**

| Service | Image / Build | Purpose |
|---|---|---|
| `api` | built from local `Dockerfile` (Python 3.11-slim + FastAPI + Uvicorn) | the FastAPI app |
| `db` | `postgres:16` | PostgreSQL, with a named volume so data persists across restarts |
| `redis` | `redis:7-alpine` | cache + Celery broker |
| `celery_worker` | same build as `api`, different entrypoint (`celery -A app.celery_app worker`) | runs scraping/ML/sentiment/alert jobs |
| `celery_beat` | same build as `api`, entrypoint `celery -A app.celery_app beat` | schedules the periodic jobs (market refresh, forecast retrain, news scrape) |

**Local dev workflow:**
1. `docker compose up --build` starts all five services.
2. `api` connects to `db` and `redis` using service names as hostnames (`postgresql://user:pass@db:5432/basarat`, `redis://redis:6379/0`) — never `localhost` inside containers.
3. `.env` (git-ignored) holds secrets/config; `.env.example` is committed with placeholder values so every team member's setup matches.
4. Alembic migrations run via `docker compose exec api alembic upgrade head`.

**Minimum `.env` keys to define now** (so nothing is discovered mid-build): `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET_KEY`, `JWT_ACCESS_TTL_MIN`, `JWT_REFRESH_TTL_DAYS`, `FIREBASE_CREDENTIALS_PATH`, `LLM_API_KEY` (for the Assistant module), `ENV` (`local`/`staging`).

---

### 0.2 Firebase Setup (Push Notifications)

**Decision:** Firebase Cloud Messaging (FCM) is the single push-delivery mechanism for Android (and can extend to web push later — not required now).

**One-time setup (do this in Phase 0, not when you reach Module 9):**
1. Create a Firebase project in the Firebase console.
2. Register the Android app (package name) → download `google-services.json` → place in the Android project, add the Google Services Gradle plugin.
3. Generate a **service account key** (Project Settings → Service Accounts) → this JSON is what the **backend** uses to send pushes via the Firebase Admin SDK — store its path in `FIREBASE_CREDENTIALS_PATH`, never commit it to git.
4. Add `firebase-admin` to the backend's Python dependencies.

**Runtime flow (end-to-end, so it's unambiguous who does what):**
1. Android app requests an FCM token on first launch / after login.
2. Android calls `POST /devices/register` with `{fcm_token, platform: "android"}` (Module 1/9 endpoint, already specified).
3. Backend stores the token against the user in the `devices` table.
4. When an alert rule (Module 9) or a system event fires, the backend uses the Firebase Admin SDK server-side to send a push to the stored token(s) for that user.
5. Android receives it via `FirebaseMessagingService` — foreground: show as an in-app banner; background: system tray notification, tapping deep-links into the app (per Module 9's DoD).
6. If a token is invalidated (uninstall, FCM returns `UNREGISTERED`), backend removes it from `devices` on the next failed send — don't let dead tokens pile up.

---

## 1. System Architecture & User Flow

```
                         ┌─────────────────────┐
                         │   PostgreSQL (core)  │
                         │   Redis (cache/queue)│
                         └─────────▲─────────────┘
                                   │
        ┌──────────────────────────────────────────────┐
        │              FastAPI Backend (/api/v1)         │
        │  ┌───────────┐ ┌───────────┐ ┌───────────────┐ │
        │  │ REST Routers│ │ WebSocket │ │ Celery Workers│ │
        │  │ (12 modules)│ │ (live tkr)│ │ (scrape/ML/   │ │
        │  │             │ │           │ │  sentiment)   │ │
        │  └───────────┘ └───────────┘ └───────────────┘ │
        └───────▲───────────────────▲──────────▲──────────┘
                │                   │          │
     ┌──────────┴───────┐  ┌────────┴──────┐  ┌┴────────────────┐
     │ Kotlin Android App│  │ React Web App │  │ External sources │
     │ (Jetpack Compose) │  │ (Vite + TS)   │  │ PSX, Yahoo Fin,  │
     └────────────────────┘  └───────────────┘  │ Dawn/BR news, SBP│
                                                  └──────────────────┘
```

**Data flow for market data:** Celery beat schedules scraping jobs (PSX pages, Yahoo Finance) → normalized OHLCV written to Postgres → Redis cache holds latest ticks → FastAPI serves REST for snapshots + WebSocket for live push → both clients render identically from the same payload shape.

### End-to-End User Flow (typical session)

```
 App Open
    │
    ▼
 Splash (check local token)
    │
    ├── No valid token ──► Login / Signup ──► (first time only) Risk Profile Onboarding
    │                                                                      │
    ▼                                                                      │
 Home (bottom nav) ◄──────────────────────────────────────────────────────┘
    │
    ├── Dashboard tab ─► live indices/heatmap/gainers (Module 2)
    │       └─ tap a stock ─► Stock Detail (Module 3) ─► tap "Forecast" ─► Forecast (Module 4)
    │                                              └─ tap "Recommendation" ─► Recommendation Detail (Module 5)
    │                                              └─ Shariah badge ─► Shariah Screener (Module 11)
    │
    ├── Portfolio tab ─► Holdings (Module 6) ─► Risk Dashboard (Module 7) ─► Monte Carlo (Module 7)
    │       └─ Add Holding ─► picks symbol via same search as Stock Analysis
    │
    ├── Community tab ─► Feed (Module 10) ─► Post Detail/Thread
    │
    ├── Assistant tab ─► Chat (Module 12), which can internally query any module's data on the user's behalf
    │
    ├── Bell icon (any screen) ─► Notification Center (Module 9) ─► tap notification ─► deep-links into the
    │       relevant screen above (e.g. a price alert opens Stock Detail directly)
    │
    └── Profile tab ─► Profile / Notification Settings / Alert Rules (Modules 1 & 9)

 Background (independent of user navigation):
   Celery beat → scrapes market/news data → updates cache/DB → WebSocket pushes live ticks to
   whichever screen is open → rule engine evaluates alert conditions → Firebase push sent → notification
   badge appears even if the user is on an unrelated screen.
```

This is the flow every screen-transition decision (Section 4) should be checked against: a screen exists because it's a **stop on this map**, not because a module has a matching backend table.

---

## 2. Global API & Data Standards
*(applies to every module below — don't repeat per-module)*

**Base URL:** `https://api.basarat.app/api/v1`
**Auth:** Bearer JWT in `Authorization: Bearer <token>` header. Access token 15 min TTL, refresh token 7 days TTL (rotated on use, stored httpOnly cookie on web, EncryptedSharedPreferences/DataStore on Android).

**Standard success envelope:**
```json
{ "success": true, "data": { ... }, "meta": { "timestamp": "..." } }
```
**Standard error envelope:**
```json
{ "success": false, "error": { "code": "VALIDATION_ERROR", "message": "...", "field": "email" } }
```
**Pagination (list endpoints):** query params `?page=1&limit=20`, response `meta: { page, limit, total, has_next }`.

**HTTP status conventions:** 200 success · 201 created · 400 validation · 401 unauthenticated · 403 forbidden (e.g. non-KMI30 access under free tier) · 404 not found · 429 rate limited · 500 server error.

**WebSocket namespace:** `wss://api.basarat.app/ws/market/live` — client subscribes with `{"action":"subscribe","symbols":["OGDC","LUCK"]}`, server pushes `{"type":"tick","symbol":"OGDC","price":...,"change_pct":...,"ts":...}`.

**Rate limiting:** 100 req/min per user on standard endpoints, 10 req/min on `/assistant/chat` and `/risk/monte-carlo` (compute-heavy).

**Caching strategy (Redis as general response cache):** Redis is not just for tokens/queues — it sits in front of every expensive-to-compute or expensive-to-scrape endpoint. Rule of thumb: if recomputing on every request means re-running indicator math, re-scraping a source, or re-invoking a model, cache it and serve from Redis until the next scheduled refresh, not on every hit.

| Data | Cache key pattern | TTL | Refreshed by |
|---|---|---|---|
| Market indices / heatmap / gainers-losers / spikes | `market:indices`, `market:heatmap`, `market:gainers` | 30–60s | Celery job on schedule, overwrites cache |
| Technical indicators per symbol | `indicators:{symbol}:{period}` | 5 min | Recomputed on cache miss or by scheduled job for KMI-30/KSE-100 universe |
| Fundamentals per symbol | `fundamentals:{symbol}` | 24h | Quarterly-ish source data, cheap to keep daily |
| GRU forecast per symbol+horizon | `forecast:{symbol}:{horizon}` | 1h (or until next scheduled inference run) | Celery inference job writes result, API just reads |
| Recommendation signal per symbol+risk profile | `recommendation:{symbol}:{risk_tolerance}` | 1h | Recomputed alongside forecast refresh |
| Sentiment score per symbol | `sentiment:{symbol}` | 1h | Sentiment aggregation job |
| Shariah screening per symbol | `shariah:{symbol}` | 24h (quarterly data, generous cache is safe) | Manual/quarterly refresh job |
| VaR/CVaR/stress test per portfolio | `risk:{user_id}:var`, `risk:{user_id}:stress` | 5–15 min or invalidate on holdings change | Recomputed on holdings mutation or TTL expiry |
| Monte Carlo simulation result | `montecarlo:{job_id}` | 1h (result only, since inputs were a one-off request) | Written once when the async job completes |
| News feed page | `news:feed:{page}:{filters_hash}` | 5–10 min | New articles invalidate relevant pages |

**Cache invalidation rule:** anything derived from user-mutable data (portfolio holdings, alert rules) invalidates on write, not just TTL. Anything derived from market/external data (prices, news, forecasts) relies on TTL + scheduled job overwrite — never invalidated by a user action.

**Endpoint behavior:** every "expensive" endpoint above should be a thin FastAPI handler that does `cache.get(key)` first, and only falls through to the real computation/scrape on a miss (with the result written back to cache before returning) — this is the pattern to implement once and reuse, not something to hand-roll per module.

---

## 3. Backend Project Structure & Core Routes

**Folder structure** (FastAPI, one app, routers per module — mirrors the 12 modules above 1:1 so anyone can find a module's code instantly):

```
basarat-backend/
├── app/
│   ├── main.py                     # FastAPI() instance, router registration, startup/shutdown events
│   ├── core/
│   │   ├── config.py                # Settings via pydantic-settings, reads .env
│   │   ├── security.py              # JWT create/verify, password hashing
│   │   └── logging.py
│   ├── db/
│   │   ├── session.py               # SQLAlchemy engine + session dependency
│   │   └── base.py                  # Declarative Base import hub for Alembic
│   ├── cache/
│   │   └── redis_client.py          # Redis connection + get/set/invalidate helpers (Section 2 cache pattern)
│   ├── celery_app.py                # Celery instance + beat schedule config
│   ├── models/                      # SQLAlchemy ORM models, one file per entity group
│   │   ├── user.py
│   │   ├── stock.py
│   │   ├── portfolio.py
│   │   ├── forecast.py
│   │   ├── risk.py
│   │   ├── news.py
│   │   ├── alert.py
│   │   ├── community.py
│   │   ├── shariah.py
│   │   └── assistant.py
│   ├── schemas/                     # Pydantic request/response models, mirrors models/
│   ├── routers/                     # one file per module — this is what main.py wires up
│   │   ├── auth.py                  # Module 1
│   │   ├── users.py                 # Module 1
│   │   ├── market.py                # Module 2
│   │   ├── stocks.py                # Module 3
│   │   ├── forecast.py              # Module 4
│   │   ├── recommendations.py       # Module 5
│   │   ├── portfolio.py             # Module 6
│   │   ├── risk.py                  # Module 7
│   │   ├── sentiment.py             # Module 7
│   │   ├── news.py                  # Module 8
│   │   ├── events.py                # Module 8
│   │   ├── alerts.py                # Module 9
│   │   ├── notifications.py         # Module 9
│   │   ├── devices.py               # Module 1/9
│   │   ├── community.py             # Module 10
│   │   ├── shariah.py                # Module 11
│   │   ├── assistant.py             # Module 12
│   │   └── system.py                # health/readiness/root — see Core Routes below
│   ├── services/                    # business logic, one file per module — routers stay thin, call these
│   │   ├── auth_service.py
│   │   ├── market_service.py
│   │   ├── indicator_service.py     # RSI/MACD/BB/SMA/ADX math
│   │   ├── forecast_service.py      # GRU inference wrapper
│   │   ├── recommendation_service.py
│   │   ├── portfolio_service.py
│   │   ├── risk_service.py          # VaR/CVaR/Monte Carlo/stress test
│   │   ├── sentiment_service.py     # FinBERT wrapper
│   │   ├── news_service.py
│   │   ├── alert_service.py
│   │   ├── notification_service.py  # Firebase Admin SDK wrapper
│   │   ├── community_service.py
│   │   ├── shariah_service.py
│   │   └── assistant_service.py     # LangChain agent + tools
│   ├── tasks/                       # Celery task definitions, called by celery_app + beat schedule
│   │   ├── scrape_market.py
│   │   ├── scrape_news.py
│   │   ├── run_forecast_inference.py
│   │   ├── compute_sentiment.py
│   │   ├── evaluate_alert_rules.py
│   │   └── retrain_gru_model.py
│   ├── ml/                          # model artifacts + training scripts, kept separate from request-path code
│   │   ├── gru_model.py
│   │   ├── train.py
│   │   └── saved_models/            # versioned model files (gitignored, or tracked via DVC/artifact storage)
│   └── ws/
│       └── market_ticker.py         # WebSocket endpoint + connection manager
├── alembic/                         # DB migrations
├── tests/                           # mirrors app/ structure, one test file per service/router
├── Dockerfile
├── docker-compose.yml
├── requirements.txt (or pyproject.toml)
├── .env.example
└── README.md
```

**Core system routes** (not tied to any single module — build these in Phase 0, every module depends on them existing):

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | Root info: API name, version, environment — quick sanity check |
| GET | `/health` | Liveness probe: process is up, returns `{status: "ok"}` — no DB/Redis check |
| GET | `/health/ready` | Readiness probe: actually pings DB and Redis, returns per-dependency status — use this one for "is the system actually usable" checks |
| GET | `/docs` | Auto-generated OpenAPI/Swagger UI (FastAPI default — keep it enabled at least through development) |
| GET | `/api/v1/version` | Returns build/version string — useful once you have more than one deployed environment |

---

## 4. Android App Architecture (Kotlin — for the sole Android dev)

**Pattern:** MVVM + Repository, single-activity + Compose Navigation.

| Layer | Tech |
|---|---|
| UI | Jetpack Compose (Material 3) |
| Navigation | Compose Navigation, one `NavHost`, routes per screen listed in each module below |
| State | `ViewModel` + `StateFlow` per screen, exposed as a single `UiState` sealed class: `Loading / Success(data) / Error(message) / Empty` |
| Networking | Retrofit + OkHttp (auth interceptor auto-attaches/refreshes JWT), Moshi/kotlinx.serialization for JSON |
| Local persistence | Room (offline cache for portfolio, watchlist, chat history), DataStore (auth tokens, user prefs) |
| DI | Hilt |
| Real-time | OkHttp WebSocket client wrapped in a `MarketTickerRepository` exposing `Flow<Tick>` |
| Push | Firebase Cloud Messaging, token registered via `/devices/register` on login |
| Charts | Vico or MPAndroidChart (candlestick + line, needed in Stock Analysis, Forecasting, Portfolio) |

**Global navigation routes (all screens across modules, for the NavHost skeleton):**
`splash → auth/login → auth/signup → onboarding/risk_profile → home(bottom nav: dashboard, portfolio, community, assistant, profile) → stock/{symbol} → forecast/{symbol} → recommendations → recommendations/{symbol} → risk/dashboard → risk/monte_carlo → news/feed → news/{id} → events/calendar → alerts/rules → alerts/create → notifications → community/feed → community/post/{id} → community/create → shariah/{symbol} → shariah/purification → shariah/kmi30 → assistant/chat → settings/profile → settings/notifications`

**Every screen spec below lists:** Purpose · Data fields shown · ViewModel state (`UiState` fields) · API calls it triggers · **Entry point** (how the user gets there) · **Exit actions** (where it can navigate to next). Build to this exactly — it's the contract between the Android dev and the module owner's backend work, and it should read as "here is everything that appears on this screen, in this order, and here is what happens when the user taps something."

### When to create a new screen vs. a component within an existing screen

This is the rule to apply every time a module spec below feels ambiguous:

1. **New screen** if the content represents a distinct user goal reached via navigation (a route in the NavHost) — e.g. "view stock detail," "configure an alert," "read one article." If it has its own back-stack entry, it's a screen.
2. **Component / section within a screen** if it's a sub-view of the same goal — e.g. the "Chart" and "Fundamentals" **tabs** inside Stock Detail are not two screens, they're one screen with a `TabRow` and two composable content blocks driven by one `selectedTab` state var.
3. **Bottom sheet / dialog**, not a new screen, for short, interruptive actions that return to the same context — e.g. a filter picker, a confirm-delete dialog, a quick like/report action on a community post.
4. **Reusable component** (not screen-specific) the moment the same visual pattern appears in 2+ modules — build it once in a shared `components/` package. Concretely, build these as shared components from day one: `StockRow` (symbol/name/ltp/change — used in search, watchlists, gainers/losers, KMI-30 list), `SignalBadge` (BUY/SELL/HOLD), `SentimentChip`, `LoadingState`/`ErrorState`/`EmptyState` (every `UiState` renders through the same three composables), `PriceChart` (candlestick, reused in Stock Detail, Forecast, Portfolio Holding Detail).
5. If you're unsure, check the **End-to-End User Flow diagram** in Section 1 — if what you're building isn't a labeled stop on that map, it's probably a component of an existing stop, not a new screen.

---

## 5. React Web App Architecture

**Pattern:** feature-folder structure, one page per module route, shared design system.

| Layer | Tech |
|---|---|
| Build | Vite + TypeScript |
| Routing | React Router v6, routes mirror Android routes 1:1 (see above) for consistency |
| State/data | TanStack Query (server state/caching) + Zustand (light client state: auth, theme) |
| Forms | React Hook Form + Zod validation |
| Charts | Recharts or Lightweight-Charts (TradingView) for candlesticks |
| Real-time | native `WebSocket` wrapped in a `useMarketTicker(symbols)` hook |
| Styling | Tailwind CSS |
| Auth | JWT in memory + httpOnly refresh cookie, Axios interceptor for silent refresh |

Each module below gives the React page's data needs alongside the Android screen spec — same API, same fields, just noted once per module to avoid duplication.

---
## 6. Modules

---

### Module 1 — User Management (Auth, Profile, Risk Profile)
**Track:** Full-Stack

**Backend Tasks**
- [ ] User table (email, hashed password, phone optional, created_at)
- [ ] Signup/login with bcrypt + JWT issuance (access + refresh)
- [ ] Refresh-token rotation endpoint + revoke-on-logout (Redis blacklist)
- [ ] Rate limiting middleware (per-IP + per-user)
- [ ] Risk profile model: `risk_tolerance` enum (Conservative/Moderate/Aggressive), `sector_preferences` array, `investment_horizon`
- [ ] Notification preference model (channels: push/email/in-app; categories: price/forecast/news/risk)
- [ ] Forgot/reset password flow (email token, 15-min expiry)
- [ ] Device token registration table (for FCM, links to user)

**Android Tasks**
- [ ] Splash → auto-login check (valid refresh token in DataStore) → route to Home or Login
- [ ] Login/Signup forms with inline validation
- [ ] Risk-profile onboarding (3–4 question wizard) shown once post-signup
- [ ] Profile screen + edit + notification settings
- [ ] Auth interceptor: attach access token, auto-refresh on 401, force logout on refresh failure

**API Endpoints**
| Method | Endpoint | Body / Query | Notes |
|---|---|---|---|
| POST | `/auth/signup` | `email, password, full_name` | returns access+refresh |
| POST | `/auth/login` | `email, password` | |
| POST | `/auth/refresh` | `refresh_token` | rotates token |
| POST | `/auth/logout` | — | blacklists refresh token |
| POST | `/auth/forgot-password` | `email` | |
| POST | `/auth/reset-password` | `token, new_password` | |
| GET | `/users/me` | — | profile + risk profile |
| PATCH | `/users/me` | `full_name, phone` | |
| PATCH | `/users/me/risk-profile` | `risk_tolerance, sector_preferences, investment_horizon` | |
| PATCH | `/users/me/notification-preferences` | `channels[], categories[]` | |
| POST | `/devices/register` | `fcm_token, platform` | |

**Android Screens & Data**
| Screen | Purpose | Data fields shown | ViewModel `UiState` | API calls |
|---|---|---|---|---|
| Splash | Auth check | app logo, loading spinner | `isChecking: Boolean` | — (reads local token) |
| Login | Auth | email, password, "forgot password" link, error text | `email, password, isLoading, errorMsg` | `POST /auth/login` |
| Signup | Auth | full_name, email, password, confirm_password | `..., passwordStrength` | `POST /auth/signup` |
| Risk Profile Onboarding | Personalization | 3 questions (tolerance, horizon, preferred sectors — multi-select chips) | `selectedTolerance, selectedHorizon, selectedSectors: List<String>` | `PATCH /users/me/risk-profile` |
| Profile | View/edit | avatar initials, full_name, email, risk_tolerance badge, member_since | `user: UserProfile?, isEditing` | `GET/PATCH /users/me` |
| Notification Settings | Prefs | toggle rows: Price Alerts, Forecasts, News, Risk Warnings; channel toggles (push/email) | `prefs: NotificationPrefs` | `PATCH /users/me/notification-preferences` |

**Navigation flow:** Splash checks for a valid token → unauthenticated users land on Login/Signup; on success, first-time users are routed through Risk Profile Onboarding once, then everyone lands on Home. Profile and Notification Settings are reachable anytime from the bottom nav's Profile tab. Logging out from Profile routes back to Login — this is the only screen with no "back" affordance other than that.

**Definition of Done**
- [ ] Signup/login/refresh/logout work end-to-end on both clients against staging API
- [ ] Invalid credentials, expired token, and network-error states all show correct UI (not a blank screen)
- [ ] Risk profile persists and is retrievable by Recommendation Engine (Module 5) and Risk Analytics (Module 7)
- [ ] Passwords never logged or returned in any response
- [ ] Rate limiting verified with a script hitting login 20x/min → 429 after threshold

---

### Module 2 — Market Dashboard
**Track:** Backend

**Backend Tasks**
- [ ] Scraper/adapter for KSE-100, KSE-30, KMI-30 index values (Celery job, every 30–60s during market hours)
- [ ] Sector heatmap aggregation (group listed stocks by sector, compute avg % change)
- [ ] Top gainers/losers query (top 10 by % change, filter min volume to avoid penny-stock noise)
- [ ] Volume spike detection (current volume vs 20-day avg, threshold e.g. 2x)
- [ ] Market sentiment aggregate (rolls up FinBERT scores from Module 8, cached hourly)
- [ ] WebSocket broadcast channel for subscribed symbols

**React/Android Tasks**
- [ ] Dashboard home: index ticker strip, sector heatmap grid, 4-tile row (gainers/losers/spikes/sentiment)
- [ ] WebSocket connection lifecycle (connect on screen visible, disconnect on background/unmount)
- [ ] Pull-to-refresh (Android) / manual refresh button (Web) as WS fallback

**API Endpoints**
| Method | Endpoint | Query | Notes |
|---|---|---|---|
| GET | `/market/indices` | — | KSE-100/30, KMI-30 snapshot |
| GET | `/market/sector-heatmap` | — | array of `{sector, avg_change_pct, stock_count}` |
| GET | `/market/top-gainers` | `limit=10` | |
| GET | `/market/top-losers` | `limit=10` | |
| GET | `/market/volume-spikes` | `limit=10` | |
| GET | `/market/sentiment-overview` | — | `{score: -1..1, label}` |
| WS | `/ws/market/live` | subscribe payload | live tick stream |

**Android Screens & Data**
| Screen | Purpose | Data fields shown | ViewModel State | API calls |
|---|---|---|---|---|
| Dashboard Home | Market snapshot | index cards: `name, value, change_pct, change_abs`; heatmap cells: `sector, color(by %), avg_change_pct`; gainers/losers rows: `symbol, name, ltp, change_pct`; spike rows: `symbol, volume, avg_volume, spike_ratio`; sentiment badge: `label, score` | `indices, heatmap, gainers, losers, spikes, sentiment, isLoading, liveTicks: Map<String,Tick>` | `GET indices/heatmap/gainers/losers/spikes/sentiment` on load, then WS for live deltas |

**Navigation flow:** This is the default landing tab on Home (bottom nav). Tapping any stock row — a gainer, loser, volume spike, or a symbol inside the heatmap drill-down — navigates to Stock Detail (Module 3), passing the symbol as a navigation argument. Nothing else on this screen navigates forward; it's the hub, not a leaf.

**Definition of Done**
- [ ] Dashboard loads under 2s on first paint (cached snapshot), live values update via WS within 1s of a new tick
- [ ] Heatmap colors correctly map negative→red, positive→green, zero→neutral, verified against real data
- [ ] Fallback to REST polling if WebSocket connection fails 3x
- [ ] Matches identically on Android and Web for the same data (screenshot-diff check)

---

### Module 3 — Stock Analysis
**Track:** Frontend/UX

**Backend Tasks**
- [ ] OHLCV storage + retrieval per symbol, multiple ranges (1D/1W/1M/1Y)
- [ ] Technical indicator computation service: RSI, MACD, Bollinger Bands, SMA, ADX (use `ta-lib` or `pandas-ta`)
- [ ] Fundamentals ingestion: EPS, P/E, ROE, Debt-to-Equity, Dividend Yield (from scraped filings/Yahoo Finance)
- [ ] Symbol search/autocomplete (indexed by symbol + company name)

**Android/React Tasks**
- [ ] Stock search screen with debounced autocomplete
- [ ] Stock detail screen: candlestick chart (range selector), indicator overlay toggles, fundamentals tab
- [ ] Cache last-viewed 10 stocks locally for instant reopen

**API Endpoints**
| Method | Endpoint | Query | Notes |
|---|---|---|---|
| GET | `/stocks/search` | `q=` | autocomplete, returns `symbol, name, sector` |
| GET | `/stocks/{symbol}/overview` | — | ltp, change, day range, market cap |
| GET | `/stocks/{symbol}/price-history` | `range=1D\|1W\|1M\|1Y` | OHLCV array |
| GET | `/stocks/{symbol}/technical-indicators` | `indicators=RSI,MACD,BB,SMA,ADX&period=14` | per-indicator series |
| GET | `/stocks/{symbol}/fundamentals` | — | EPS, PE, ROE, D/E, div yield |

**Android Screens & Data**
| Screen | Purpose | Data fields shown | ViewModel State | API calls |
|---|---|---|---|---|
| Stock Search | Find a stock | search bar, result rows: `symbol, name, sector, ltp` | `query, results: List<StockSummary>, isLoading` | `GET /stocks/search` (debounced 300ms) |
| Stock Detail — Chart tab | Price/technicals | header: `symbol, name, ltp, change_pct`; range chips (1D/1W/1M/1Y); candlestick chart; indicator toggle chips (RSI/MACD/BB/SMA/ADX) with sub-charts | `overview, priceHistory, selectedRange, activeIndicators: Set<String>, indicatorData` | `GET overview, price-history, technical-indicators` |
| Stock Detail — Fundamentals tab | Company health | rows: `EPS, P/E Ratio, ROE, Debt-to-Equity, Dividend Yield`, each with a one-line plain-language note | `fundamentals: FundamentalsData?` | `GET /stocks/{symbol}/fundamentals` |

**Navigation flow:** Entry points are Stock Search, tapping any stock row anywhere in the app (Dashboard, Portfolio, Community, KMI-30 list), or Portfolio's "Add Holding" flow. Once on Stock Detail: "Chart" and "Fundamentals" are **tabs on the same screen**, not separate routes (per the screen-creation rule in Section 4). A "View Forecast" action navigates forward to Forecast (Module 4); a "View Recommendation" action navigates to Recommendation Detail (Module 5); the Shariah badge navigates to the Shariah Screener (Module 11) — all three carry the same `symbol` forward.

**Definition of Done**
- [ ] Indicator math validated against a known reference (e.g. TradingView value for the same symbol/date) within acceptable tolerance
- [ ] Chart renders correctly for symbols with sparse/gappy data (halted stocks, new listings)
- [ ] Search returns results in <300ms for cached/indexed symbols

---

### Module 4 — ML Forecasting (GRU)
**Track:** Full-Stack

**Backend Tasks**
- [ ] Feature pipeline: OHLCV + technical indicators + macro features (SBP rate, PKR/USD) as model input
- [ ] GRU model (TensorFlow/Keras) trained per-sector or single multi-symbol model — decide based on data volume; document choice
- [ ] Classification output: bullish/bearish/sideways + confidence, per horizon (1D/1W/1M)
- [ ] Model versioning + scheduled retraining job (weekly, via Celery beat)
- [ ] Prediction logging table (for the "history: predicted vs actual" trust screen)
- [ ] Model serving via a lightweight inference endpoint (load model once at startup, not per-request)

**Android/React Tasks**
- [ ] Forecast screen: stock selector, horizon toggle, forecast bar chart, confidence readout
- [ ] "How accurate has this been?" expandable section showing past prediction vs actual

**API Endpoints**
| Method | Endpoint | Query | Notes |
|---|---|---|---|
| GET | `/forecast/{symbol}` | `horizon=1D\|1W\|1M` | Typed response with `probabilities.{bullish,bearish,sideways}` (percent), `confidence` (0–1), dates, price levels, optional model details and market context. Full example is in Swagger. |
| GET | `/forecast/{symbol}/history` | `limit=30` | past predictions vs realized outcome |

**Android Screens & Data**
| Screen | Purpose | Data fields shown | ViewModel State | API calls |
|---|---|---|---|---|
| Forecast | View ML prediction | stock selector, horizon toggle (1D/1W/1M), bar chart (`forecast.probabilities.bullish/bearish/sideways`, percent), confidence (`forecast.confidence × 100`), trend label + one-line summary, "prediction history" expandable list (`date, predicted_direction, actual_direction, was_correct`) | `symbol, horizon, forecast: ForecastData?, history: List<PredictionRecord>, isLoading` | `GET /forecast/{symbol}`, `GET /forecast/{symbol}/history` |

**Navigation flow:** Entry is exclusively from Stock Detail's "View Forecast" action (Module 3), arriving with `symbol` pre-set. The "prediction history" list is an **expandable section on this same screen**, not a separate route. Back returns to Stock Detail; there's no forward navigation from here.

**Definition of Done**
- [ ] Model achieves and documents a baseline accuracy on held-out PSX data (report the number honestly — this becomes a thesis defense point)
- [ ] Inference latency <500ms per request (model pre-loaded, not reloaded per call)
- [ ] Every UI-shown prediction includes a confidence score — never shown as a bare directional claim
- [ ] Clear in-app disclaimer that forecasts are probabilistic, per System Limitations in the proposal

---
### Module 5 — Recommendation Engine
**Track:** Full-Stack

**Backend Tasks**
- [ ] Signal synthesis logic: combine GRU forecast + technical indicator signals + fundamental screen into a BUY/SELL/HOLD verdict
- [ ] Weighting configuration (default weights per input source, adjustable — document formula clearly for thesis writeup)
- [ ] Personalization: filter/adjust by user's `risk_tolerance` and `sector_preferences` (Module 1)
- [ ] Target price + stop-loss calculation (e.g. ATR-based or % band off current price — pick and document one method)
- [ ] Recommendation caching (recompute on schedule, not per-request, since inputs are expensive)

**Android/React Tasks**
- [ ] Recommendations list (personalized feed) + detail screen
- [ ] Optional: engine weight config panel (nice-to-have, can be admin-only or hidden behind a settings toggle)

**API Endpoints**
| Method | Endpoint | Query/Body | Notes |
|---|---|---|---|
| GET | `/recommendations` | `risk_profile` (defaults to user's), `sector` optional filter | list of signals |
| GET | `/recommendations/{symbol}` | — | full detail incl. reasoning breakdown |
| GET | `/recommendations/{symbol}/target-stop` | — | target_price, stop_loss, method used |
| POST | `/recommendations/engine-weights` | `{gru_weight, technical_weight, fundamental_weight}` | optional/advanced, if built |

**Android Screens & Data**
| Screen | Purpose | Data fields shown | ViewModel State | API calls |
|---|---|---|---|---|
| Recommendations List | Personalized signals | rows: `symbol, name, signal (BUY/SELL/HOLD badge), confidence, sector` | `recommendations: List<Signal>, filterSector, isLoading` | `GET /recommendations` |
| Recommendation Detail | Why this signal | `symbol, signal, target_price, stop_loss, confidence`; reasoning breakdown: contribution of GRU forecast / technicals / fundamentals (mini bar or list) | `detail: SignalDetail?` | `GET /recommendations/{symbol}` |
| Engine Weight Config (optional) | Power-user tuning | sliders: `gru_weight, technical_weight, fundamental_weight` (sum to 100%) | `weights: EngineWeights` | `POST /recommendations/engine-weights` |

**Navigation flow:** Entry is a "Recommendations" item on the Home bottom nav (or a card on Dashboard) for the list screen, or directly from Stock Detail's "View Recommendation" action for the detail screen with `symbol` pre-set. Engine Weight Config is reached only via a settings icon on the list screen — it's a power-user screen, not part of the main flow, so don't surface it prominently.

**Definition of Done**
- [ ] Every recommendation is explainable — detail screen must show *why*, not just the verdict
- [ ] Same user + same inputs → same signal (deterministic given cached inputs; no randomness in a demo)
- [ ] Target price/stop-loss method documented in code comments and the final report (examiners will ask)

---

### Module 6 — Portfolio Management
**Track:** Backend

**Backend Tasks**
- [ ] Holdings table: `symbol, quantity, avg_buy_price, purchase_date`, per user
- [ ] P&L calculation (unrealized, using latest market price)
- [ ] Sector allocation aggregation
- [ ] Risk metrics: VaR, Sharpe Ratio, max drawdown at the portfolio level (uses Module 7's risk engine)

**Android/React Tasks**
- [ ] Portfolio overview screen, add/edit/delete holding, holding detail

**API Endpoints**
| Method | Endpoint | Body | Notes |
|---|---|---|---|
| GET | `/portfolio` | — | holdings list + total value |
| POST | `/portfolio/holdings` | `symbol, quantity, avg_buy_price, purchase_date` | |
| PATCH | `/portfolio/holdings/{id}` | any of the above | |
| DELETE | `/portfolio/holdings/{id}` | — | |
| GET | `/portfolio/pnl` | — | unrealized P&L summary |
| GET | `/portfolio/allocation` | — | sector breakdown array |
| GET | `/portfolio/risk-metrics` | — | VaR, Sharpe, max_drawdown |

**Android Screens & Data**
| Screen | Purpose | Data fields shown | ViewModel State | API calls |
|---|---|---|---|---|
| Portfolio Overview | Snapshot | header: `total_value, total_pnl, total_pnl_pct`; holdings list rows: `symbol, quantity, avg_buy_price, ltp, pnl, pnl_pct`; sector allocation donut; risk tile: `VaR, Sharpe, max_drawdown` | `holdings: List<Holding>, pnl, allocation, riskMetrics, isLoading` | `GET /portfolio, /pnl, /allocation, /risk-metrics` |
| Add/Edit Holding | Input | form: `symbol (autocomplete), quantity, avg_buy_price, purchase_date` | `form: HoldingForm, isSaving, errorMsg` | `POST/PATCH /portfolio/holdings` |
| Holding Detail | Deep-dive on one position | `symbol, quantity, avg_buy_price, ltp, pnl, pnl_pct, weight_in_portfolio`, mini price chart | `holding: HoldingDetail?` | `GET /portfolio` (filtered client-side) or dedicated `GET /portfolio/holdings/{id}` if added |

**Navigation flow:** Entry is the Home bottom nav's "Portfolio" tab, landing on Overview. From there: the "+" button opens Add Holding (a full screen, not a sheet, since it involves a symbol search sub-flow); tapping any holding row opens Holding Detail; the risk tile navigates forward to the Risk Dashboard (Module 7). Add/Edit Holding's symbol field reuses the same search component as Module 3's Stock Search.

**Definition of Done**
- [ ] P&L recalculates correctly on every price tick without a full page reload
- [ ] Deleting/editing a holding updates allocation and risk metrics immediately
- [ ] Handles zero-holdings empty state with a clear CTA ("Add your first holding")

---
### Module 7 — Risk & Sentiment Analytics
**Track:** Shared (Frontend/UX for sentiment UI, Backend + Full-Stack for risk math)

**Backend Tasks**
- [ ] VaR/CVaR calculation (historical simulation or parametric — pick one, document it)
- [ ] Monte Carlo simulation engine (N runs, configurable horizon; run async via Celery since it's compute-heavy, poll or WS for result)
- [ ] Stress test presets (e.g. 2008-style shock, PKR devaluation scenario, applied to current portfolio)
- [ ] Threshold-breach alert trigger (hooks into Module 9)
- [ ] FinBERT sentiment pipeline: ingest Module 8's news + Module 10's community posts → per-stock and market-level sentiment score
- [ ] Sentiment aggregation job (rolling window, e.g. 7-day decay-weighted average)

**Android/React Tasks**
- [ ] Risk analytics dashboard (VaR/CVaR, stress test results)
- [ ] Monte Carlo screen (trigger simulation, show result distribution)
- [ ] Sentiment badge/detail per stock (surfaced also inside Module 3's stock detail)

**API Endpoints**
| Method | Endpoint | Query/Body | Notes |
|---|---|---|---|
| GET | `/risk/var` | `confidence=95, horizon=1D` | portfolio-level |
| GET | `/risk/cvar` | `confidence=95` | |
| POST | `/risk/monte-carlo` | `{num_simulations, horizon_days}` | async job, returns `job_id` |
| GET | `/risk/monte-carlo/{job_id}` | — | poll for result: distribution array, percentiles |
| GET | `/risk/stress-test` | `scenario=2008_crash\|pkr_devaluation` | |
| GET | `/sentiment/{symbol}` | — | `{score, label, article_count, trend}` |
| GET | `/sentiment/market-overview` | — | overall market mood |

**Android Screens & Data**
| Screen | Purpose | Data fields shown | ViewModel State | API calls |
|---|---|---|---|---|
| Risk Dashboard | Portfolio risk snapshot | `VaR_95, CVaR_95` (in currency + %), stress test result cards (`scenario, projected_loss_pct`), breach alerts banner if threshold crossed | `varData, cvarData, stressResults, isLoading` | `GET /risk/var, /cvar, /stress-test` |
| Monte Carlo | Run simulation | inputs: `num_simulations (slider), horizon_days`; output: histogram of outcomes, `p5, p50, p95` outcome values | `simInput, jobId, result: MonteCarloResult?, isRunning` | `POST /risk/monte-carlo` then poll `GET .../{job_id}` |
| Sentiment Detail | Stock-level mood | `score (-1 to 1), label (Positive/Neutral/Negative), article_count, 7-day trend sparkline` | `sentiment: SentimentData?` | `GET /sentiment/{symbol}` |

**Navigation flow:** Risk Dashboard is entered from Portfolio's risk tile. Its "Run Simulation" button navigates forward to the Monte Carlo screen. Sentiment Detail is **not a standalone nav destination** on its own — it's most often surfaced as a badge/section embedded inside Stock Detail (Module 3); only build it as a separate full screen if the embedded version proves too cramped.

**Definition of Done**
- [ ] VaR/CVaR formulas documented with the exact method used (parametric vs historical) — needed for the FYP report's methodology section
- [ ] Monte Carlo doesn't block the UI thread; job runs async, screen shows progress state
- [ ] Sentiment score updates within a reasonable window (e.g. hourly) of new news/community volume, not stale for days
- [ ] Threshold-breach alert actually fires into Module 9 when a real portfolio crosses a configured VaR limit

---

### Module 8 — News and Events Intelligence
**Track:** Backend

**Backend Tasks**
- [ ] Scraping pipeline for Dawn Business, Business Recorder, Geo News, ARY Business, The News (respect robots.txt / ToS — document source legitimacy for the report)
- [ ] Article dedup + symbol-tagging (NER or keyword match against listed company names)
- [ ] FinBERT sentiment classification per article (positive/negative/neutral + impact score)
- [ ] Event calendar ingestion: earnings dates, dividend declarations, SBP monetary policy dates

**Android/React Tasks**
- [ ] News feed (filterable by sentiment/symbol), article detail, event calendar view

**API Endpoints**
| Method | Endpoint | Query | Notes |
|---|---|---|---|
| GET | `/news` | `symbol=, sentiment=, page, limit` | paginated feed |
| GET | `/news/{id}` | — | full article summary + sentiment + impact |
| GET | `/events/calendar` | `from=, to=` | earnings/dividends/SBP events |

**Android Screens & Data**
| Screen | Purpose | Data fields shown | ViewModel State | API calls |
|---|---|---|---|---|
| News Feed | Browse news | filter chips (sentiment: All/Positive/Negative/Neutral), article cards: `headline, source, published_at, sentiment_chip, impact_badge, related_symbols` | `articles: List<NewsItem> (paged), filter, isLoading, isLoadingMore` | `GET /news` (paginated) |
| News Detail | Read article | `headline, source, published_at, summary` (short — do not scrape/display full copyrighted body), `sentiment_score, related_symbols, external link` | `article: NewsDetail?` | `GET /news/{id}` |
| Events Calendar | Upcoming events | calendar/list view: `event_type (earnings/dividend/SBP), symbol (if applicable), date, description` | `events: List<CalendarEvent>, selectedMonth` | `GET /events/calendar` |

**Navigation flow:** News Feed is entered from Home (a "News" tab/icon) or from Stock Detail (symbol-filtered feed, same screen, just with a pre-applied filter — not a separate route). Tapping an article opens News Detail, whose external-source link opens outside the app (a browser tab), not an in-app webview requirement. Events Calendar is a tab within the News Feed screen, not a separate destination.

**Definition of Done**
- [ ] Only summaries/metadata stored/displayed, not full scraped article bodies (copyright/ToS risk — link out to source instead)
- [ ] Sentiment classification spot-checked against a manually labeled sample (report accuracy honestly)
- [ ] Event calendar reflects at least earnings + SBP policy dates correctly for the current quarter at demo time

---
### Module 9 — Alerts and Notifications
**Track:** Shared (integration checkpoint — touches Modules 2, 4, 7, 8)

**Backend Tasks**
- [ ] Alert rule model: `type (price/forecast/news/risk), symbol (nullable for portfolio-wide), condition (above/below/crosses), threshold_value`
- [ ] Rule evaluation job (runs against live ticks / new forecasts / new risk calcs, triggers notification on match)
- [ ] Notification table (persisted, `read/unread` state) + delivery dispatcher (push via FCM, in-app, email)
- [ ] Device token management (register/deregister, ties to Module 1)

**Android/React Tasks**
- [ ] Alert rules list + create/edit rule form
- [ ] Notification center (bell icon, unread badge)
- [ ] FCM integration on Android (foreground + background handling)

**API Endpoints**
| Method | Endpoint | Body | Notes |
|---|---|---|---|
| GET | `/alerts/rules` | — | user's active rules |
| POST | `/alerts/rules` | `type, symbol, condition, threshold_value, channels[]` | |
| PATCH | `/alerts/rules/{id}` | any field | |
| DELETE | `/alerts/rules/{id}` | — | |
| GET | `/notifications` | `page, limit, unread_only` | |
| PATCH | `/notifications/{id}/read` | — | |
| POST | `/devices/register` | `fcm_token, platform` | (shared with Module 1) |

**Android Screens & Data**
| Screen | Purpose | Data fields shown | ViewModel State | API calls |
|---|---|---|---|---|
| Alert Rules | Manage rules | rows: `type_icon, symbol/portfolio, condition_summary ("Price above 150"), enabled_toggle` | `rules: List<AlertRule>, isLoading` | `GET /alerts/rules` |
| Create/Edit Alert | Configure a rule | form: `type dropdown, symbol (autocomplete, hidden if type=risk), condition dropdown, threshold_value, channel checkboxes` | `form: AlertRuleForm, isSaving` | `POST/PATCH /alerts/rules` |
| Notification Center | Inbox | list rows: `icon(by type), title, body, timestamp, read/unread dot`; tap → deep link to relevant screen (stock/forecast/portfolio) | `notifications: List<Notification> (paged), unreadCount` | `GET /notifications`, `PATCH .../read` |

**Navigation flow:** Alert Rules is entered from Profile. Notification Center is entered from a bell icon present on every screen's top bar (a persistent global entry point, not module-specific). Tapping a notification deep-links directly into whatever screen it's about (a price alert opens Stock Detail with the symbol pre-loaded; a risk-breach alert opens the Risk Dashboard) — this is the one place where navigation doesn't follow the normal tab-based flow, so route it explicitly per notification `type`.

**Definition of Done**
- [ ] A test alert rule (e.g. "notify if OGDC crosses 150") actually fires end-to-end: rule created → condition met in test data → push received on device
- [ ] Notification tap deep-links to the correct screen with correct data (not just app home)
- [ ] Duplicate notifications for the same trigger event are suppressed (debounce/cooldown per rule)

---

### Module 10 — Community Trading Hub
**Track:** Frontend/UX

**Backend Tasks**
- [x] Post model: `content, sentiment (bullish/bearish/neutral), media_url?, status, like_count, comment_count` + N `post_stock_tags` (1–3 symbols validated against real tickers)
- [x] Like toggle (one row per `(post_id, user_id)`, denormalized count)
- [x] Comment threads (parent_id, depth capped at 2; soft-delete)
- [x] Basic content moderation (profanity blocklist + all-caps/repeat/URL ratchet at creation; report endpoint with auto-flag at threshold)
- [x] Posting rate limit (one post per 30s per user, Redis fail-open)
- [x] Share via short-code deep links (`GET /community/share/{short_code}` is public)
- [ ] Leaderboard by prediction accuracy — deferred (needs stance-resolution vs later price movement)

**Android/React Tasks**
- [ ] Community feed, create post, post detail/thread (leaderboard deferred — no accuracy resolution yet)

**API Endpoints**
| Method | Endpoint | Body/Query | Notes |
|---|---|---|---|
| POST | `/community/posts` | `{content, symbols[1-3], sentiment?, mediaUrl?}` | 201; content filter; 429 on rate limit |
| GET | `/community/feed` | `cursor?, limit, filter=all\|following` | `following` == `all` in v1 |
| GET | `/community/stocks/{symbol}/posts` | `cursor?, limit` | per-symbol feed |
| GET | `/community/posts/{postId}` | — | |
| DELETE | `/community/posts/{postId}` | — | owner only |
| POST | `/community/posts/{postId}/like` | — | toggle |
| POST | `/community/posts/{postId}/comments` | `{content, parentCommentId?}` | depth 2 |
| GET | `/community/posts/{postId}/comments` | `cursor?, limit` | |
| POST | `/community/reports` | `{targetType, targetId, reason}` | idempotent |
| POST | `/community/posts/{postId}/share` | — | returns shortCode |
| GET | `/community/share/{shortCode}` | — | public, no auth |

**Android Screens & Data**
| Screen | Purpose | Data fields shown | ViewModel State | API calls |
|---|---|---|---|---|
| Community Feed | Browse ideas | post cards: `user{name,avatarUrl} (author_name), symbols[{symbol,price,changePercent}] (stance badge from sentiment), content (preview), like_count, comment_count, createdAt` | `posts: List<Post> (paged, cursor), isLoading` | `GET /community/feed` |
| Create Post | Share idea | form: `symbols (1-3, autocomplete), sentiment toggle, content (multiline, ≤500)` | `form: PostForm, isSaving` | `POST /community/posts` |
| Post Detail / Thread | Discuss | full post + `comments: List<Comment>` with one reply level, comment input | `post: PostDetail?, comments, commentText, isLiked` | `GET post`, `GET comments`, `POST comment/like/delete` |

**Navigation flow:** Entry is the Home bottom nav's "Community" tab, landing on Feed. The "+" button opens Create Post (full screen — it needs the same symbol search as elsewhere). Tapping a post opens Post Detail/Thread. Voting is replaced by likes (`POST /posts/{id}/like`, optimistic toggle). Reporting happens inline via the post/comment overflow menu (bottom sheet), never a full navigation. Shares deep-link back into Post Detail.

**Definition of Done**
- [ ] Like counts and liked state update optimistically in UI and reconcile with server truth
- [ ] Create Post enforces 1–3 valid tickers + ≤500 chars and surfaces `CONTENT_REJECTED`/`RATE_LIMITED` errors from the shared error shape
- [ ] Basic abuse handling in place (report endpoint wired to `reports` table; auto-flag at threshold, even if manually reviewed for FYP scope)

---
### Module 11 — Shariah Compliance Screener
**Track:** Backend

**Backend Tasks**
- [ ] AAOIFI/SECP criteria engine: business activity screen (non-compliant sectors exclusion), debt-to-market-cap ratio threshold, interest income ratio threshold, receivables-to-assets threshold
- [ ] Compliance score computation (pass/fail per criterion + overall score, e.g. Compliant/Questionable/Non-Compliant)
- [ ] KMI-30 benchmark alignment flag
- [ ] Purification calculator: `(interest_income_ratio × dividend_received)` per holding, standard AAOIFI purification method — document formula
- [ ] Data sourced from published financial statements (quarterly refresh)

**Android/React Tasks**
- [ ] Shariah screener detail screen, purification calculator, KMI-30 list

**API Endpoints**
| Method | Endpoint | Query | Notes |
|---|---|---|---|
| GET | `/shariah/{symbol}` | — | overall score + compliance label |
| GET | `/shariah/{symbol}/criteria` | — | per-criterion pass/fail with actual ratio values |
| GET | `/shariah/{symbol}/purification` | `dividend_income` (PKR) | `dividend_income × verified purification_rate`; unavailable if no verified rate exists |
| GET | `/shariah/kmi30` | — | list of KMI-30 constituent symbols |

**Android Screens & Data**
| Screen | Purpose | Data fields shown | ViewModel State | API calls |
|---|---|---|---|---|
| Shariah Screener | Compliance check | `symbol, overall_score, compliance_label (Compliant/Questionable/Non-Compliant), KMI-30 badge if applicable`; criteria checklist: `business_activity: pass/fail, debt_ratio: value vs threshold, interest_income_ratio: value vs threshold, receivables_ratio: value vs threshold` | `screenerData: ShariahData?, isLoading` | `GET /shariah/{symbol}`, `/criteria` |
| Purification Calculator | Compute purification | input: `dividend_income` (PKR; may be calculated by the client from a holding and dividend per share); output: `purification_amount, method_note`. Never substitute total holding market value for dividend income; display unavailable when no verified rate exists. | `input: PurificationInput, result: PurificationResult?` | `GET /shariah/{symbol}/purification` |
| KMI-30 List | Browse benchmark | rows: `symbol, name, sector, ltp` | `constituents: List<StockSummary>` | `GET /shariah/kmi30` |

**Navigation flow:** Entry is Stock Detail's Shariah badge (carrying `symbol`), or a dedicated "Shariah Screener" entry point if you add one to Home/Profile. From the screener: "Calculate Purification" navigates to the Purification Calculator (pre-filled with quantity/value if the user arrived from a Portfolio holding, otherwise blank inputs); "View KMI-30" navigates to the KMI-30 List, whose rows tap through back into Stock Detail like any other stock row.

**Definition of Done**
- [ ] Criteria thresholds match the exact AAOIFI/SECP standard cited in the references (verifiable, not guessed)
- [ ] Every "non-compliant" verdict shows *why* (which specific ratio failed), not just a red badge
- [ ] In-app disclaimer present: screener does not replace a qualified Shariah scholar's ruling (per proposal's stated limitation)
- [ ] Purification formula documented in report methodology, matching a cited AAOIFI standard

---

### Module 12 — Personal AI Assistant
**Track:** Full-Stack

**Backend Tasks**
- [ ] LangChain agent wired to internal tools: stock lookup (Module 3), portfolio query (Module 6), risk query (Module 7), Shariah query (Module 11), forecast query (Module 4) — implement as LangChain tools calling internal service functions directly (not looping back through HTTP)
- [ ] Conversation persistence (per-user, message history)
- [ ] Guardrails: refuse to give definitive financial advice as fact, always frame as informational (consistent with the proposal's stated non-advisory positioning)
- [ ] Quick-prompt shortcut set (predefined common queries)

**Android/React Tasks**
- [ ] Chat UI (message bubbles, typing indicator), quick-prompt chip row, conversation history

**API Endpoints**
| Method | Endpoint | Body | Notes |
|---|---|---|---|
| POST | `/assistant/chat` | `message, conversation_id (nullable → creates new)` | streams or returns full response |
| GET | `/assistant/conversations` | — | list of past conversations (title, last_message_at) |
| GET | `/assistant/conversations/{id}` | — | full message history |
| GET | `/assistant/quick-prompts` | — | predefined prompt suggestions |

**Android Screens & Data**
| Screen | Purpose | Data fields shown | ViewModel State | API calls |
|---|---|---|---|---|
| Chat | Converse with assistant | message list: `role (user/assistant), text, timestamp`; quick-prompt chips row (e.g. "How's my portfolio?", "Is OGDC Shariah compliant?"); message input + send button; typing indicator while waiting | `messages: List<ChatMessage>, conversationId, inputText, isAssistantTyping` | `POST /assistant/chat`, `GET /quick-prompts` |
| Conversation History | Past chats | rows: `title/preview, last_message_at` | `conversations: List<ConversationSummary>` | `GET /assistant/conversations` |

**Navigation flow:** Entry is the Home bottom nav's "Assistant" tab, landing on a fresh or most-recent Chat. A "History" icon in the top bar opens Conversation History; tapping a past conversation reopens Chat with that `conversation_id` loaded and prior messages restored. The Assistant does not navigate the user to other module screens directly — it answers in-place using data from those modules, per Module 12's DoD.

**Definition of Done**
- [ ] Assistant correctly answers at least one query per domain (stock, portfolio, risk, Shariah, forecast) using live data, not hallucinated numbers
- [ ] Every response citing a number (price, VaR, compliance score) is grounded in an actual tool call — no fabricated figures
- [ ] Conversation history persists across app restarts
- [ ] Response latency acceptable for a chat UX (<3s typical, with typing indicator covering the wait)

---
## 7. Execution Phases & Order

Build in this sequence — each phase unblocks the next; don't parallelize across phases, only within one.

| Phase | Modules | Why this order |
|---|---|---|
| **0. Foundation** | Global API standards, DB schema, Auth (Module 1) | Nothing else works without auth + a shared DB + agreed JSON contracts |
| **1. Core Data** | Market Dashboard (2), Stock Analysis (3) | Every other module (forecasting, recommendations, portfolio, alerts) depends on having real price/indicator data flowing |
| **2. Intelligence Layer** | ML Forecasting (4), Recommendation Engine (5) | Depends on Phase 1 data being reliable |
| **3. User Value** | Portfolio Management (6), Risk & Sentiment Analytics (7) | Depends on Phase 1 (prices) and benefits from Phase 2 (forecasts feed risk context) |
| **4. Awareness** | News & Events (8), Alerts & Notifications (9) | Sentiment (7) needs News (8) as an input — build News first within this phase |
| **5. Compliance & Social** | Shariah Screener (11), Community Hub (10) | Independent of each other, can run in parallel between the two remaining devs |
| **6. Consolidation** | Personal AI Assistant (12) | Must be last — it's a thin orchestration layer over every other module's data |
| **7. Hardening** | Testing & QA, Documentation & Demo | Per your Gantt chart's final two bars |

This mapping keeps your existing Gantt chart largely intact but clarifies the *dependency* reasoning behind the order, which is worth a sentence in your report's methodology section.

---

## 8. Consolidated Functional & Non-Functional Requirements

**Functional Requirements**

| ID | Requirement |
|---|---|
| FR-1 | System shall allow user signup/login via email and password with JWT-based session management |
| FR-2 | System shall allow users to configure a risk profile used to personalize recommendations |
| FR-3 | System shall display live KSE-100, KSE-30, KMI-30 index values updating in real time |
| FR-4 | System shall display a sector heatmap, top gainers/losers, and volume spikes |
| FR-5 | System shall compute and display RSI, MACD, Bollinger Bands, SMA, and ADX for any KSE-100 stock |
| FR-6 | System shall display fundamental metrics (EPS, P/E, ROE, D/E, Dividend Yield) per stock |
| FR-7 | System shall forecast short-term price direction (bullish/bearish/sideways) using a GRU model, with confidence score, across 1D/1W/1M horizons |
| FR-8 | System shall generate personalized BUY/SELL/HOLD signals with target price and stop-loss |
| FR-9 | System shall allow users to record and track portfolio holdings with real-time P&L |
| FR-10 | System shall compute portfolio-level VaR, CVaR, Sharpe Ratio, and max drawdown |
| FR-11 | System shall run Monte Carlo simulations against a user's portfolio |
| FR-12 | System shall run stress tests against predefined historical shock scenarios |
| FR-13 | System shall aggregate Pakistani financial news with FinBERT-based sentiment scoring per stock |
| FR-14 | System shall maintain an event calendar for earnings, dividends, and SBP policy dates |
| FR-15 | System shall allow users to configure custom alert rules and receive push/in-app notifications |
| FR-16 | System shall provide a community feed for posting and liking trade ideas, with moderation (leaderboard deferred) |
| FR-17 | System shall screen any KSE-100 stock against AAOIFI/SECP Shariah criteria with a compliance score and purification calculator |
| FR-18 | System shall provide a conversational AI assistant answering natural-language queries grounded in the user's live data |
| FR-19 | All modules shall be available with functional parity on both Android and Web clients |

**Non-Functional Requirements**

| ID | Requirement |
|---|---|
| NFR-1 (Performance) | Dashboard first paint <2s; live tick delivery <1s end-to-end |
| NFR-2 (Performance) | Compute-heavy operations (Monte Carlo, model inference) must not block the UI thread on any client |
| NFR-3 (Security) | Passwords hashed (bcrypt); JWT access tokens short-lived; refresh tokens rotated and revocable |
| NFR-4 (Security) | All endpoints require authentication except signup/login/forgot-password |
| NFR-5 (Reliability) | WebSocket disconnects must fall back gracefully to REST polling |
| NFR-6 (Scalability) | Backend stateless where possible (session state in Redis, not in-process) so it can be horizontally scaled later |
| NFR-7 (Usability) | Every AI-generated number (forecast, recommendation, risk metric) must show a confidence/methodology indicator, never presented as guaranteed fact |
| NFR-8 (Compliance) | Explicit in-app disclaimer that the system is not a licensed investment advisor (per SECP, per proposal's stated limitation) |
| NFR-9 (Data quality) | Scraping pipelines must handle source downtime/format changes without crashing the whole ingestion job |
| NFR-10 (Consistency) | Android and Web must render identical data for identical API responses — no platform-specific business logic |

---

## 9. Database Entity Overview (high-level — refine into full ERD before Phase 0 ends)

**Core entities:** `users, risk_profiles, notification_preferences, devices` · `stocks, price_history (OHLCV), fundamentals, technical_indicators_cache` · `forecasts, prediction_history` · `recommendations` · `portfolio_holdings` · `risk_snapshots, monte_carlo_jobs` · `sentiment_scores` · `news_articles, calendar_events` · `alert_rules, notifications` · `posts, post_stock_tags, post_likes, comments, reports, share_links, leaderboard_snapshots` · `shariah_screenings, purification_records` · `assistant_conversations, assistant_messages`

**Cross-cutting keys:** every user-owned table carries `user_id`; every stock-related table carries `symbol` as a foreign key to a single `stocks` master table — keep this normalized from day one, it's what makes cross-module joins (e.g. portfolio risk using live prices) clean.

---

## 10. Models & Libraries Used

Locking these in now so the choice doesn't drift mid-build — every module above assumes these exact tools.

| Purpose | Model / Library | Type | Notes |
|---|---|---|---|
| Price movement forecasting | Custom GRU network | Deep learning, trained in-house (TensorFlow/Keras) | Trained on PSX historical OHLCV + technical indicators + SBP rate / PKR-USD features; retrained weekly via Celery beat (Module 4) |
| News & community sentiment | FinBERT (`ProsusAI/finbert` or equivalent finance-tuned checkpoint) | Pretrained NLP classifier, via HuggingFace `transformers` | Not trained in-house — used as-is for positive/negative/neutral classification + confidence (Modules 7 & 8) |
| Technical indicators (RSI, MACD, Bollinger Bands, SMA, ADX) | `pandas-ta` (or `ta-lib` if available in the deploy environment) | Deterministic math library, not an ML model | Computed server-side, cached per Section 2's strategy (Module 3) |
| Symbol/company tagging in news articles | Keyword/alias matching against the `stocks` master table (start simple) | Rule-based | Upgrade path: spaCy NER if keyword matching proves too noisy — not required for MVP |
| Personal AI Assistant orchestration | LangChain (agent + tool-calling framework) | Orchestration layer, not a model itself | Binds to internal service functions (stock/portfolio/risk/Shariah/forecast) as LangChain "tools" — see Module 12 |
| Personal AI Assistant — underlying LLM | *Decision needed, lock before Phase 6:* a hosted LLM API (e.g. an OpenAI or Anthropic chat-completion model) called via LangChain | Third-party API, not self-hosted | Self-hosting an LLM is out of scope for a 3-person FYP in this timeline — budget for API usage in the report's constraints section |
| Push notification delivery | Firebase Cloud Messaging (Admin SDK, server-side) | Infra, not a model | See Section 0.2 |
| Caching / task queue | Redis | Infra | General-purpose cache (Section 2) + Celery broker |
| Risk calculations (VaR/CVaR/Monte Carlo) | `numpy` / `scipy` (custom implementation, not a pretrained model) | Statistical computation | Method (historical vs. parametric VaR) must be fixed once and documented — see Module 7's DoD |

---

## 11. Role Ownership Map

Roles below correspond to the **Track** labels already given per module in Section 6 — this table just summarizes which track owns what, without tying it to a specific person, so it stays valid regardless of who ends up on which track.

| Track | Modules owned | Also responsible for |
|---|---|---|
| **Full-Stack** | User Management (1), ML Forecasting (4), Recommendation Engine (5), Personal AI Assistant (12) | Overall backend/frontend coordination, cross-module integration checkpoints |
| **Backend** | Market Dashboard (2), Portfolio Management (6), News & Events (8), Shariah Screener (11) | Web scraping pipeline, DB schema ownership, Docker/Celery setup (Section 0.1) |
| **Frontend/UX** | Stock Analysis (3), Community Hub (10), sentiment UI (part of 7) | Android + React UI/UX consistency across all modules, shared component library (Section 4) |
| **Shared** | Risk Analytics (7, math split across Backend + Full-Stack), Alerts & Notifications (9) | — |

**Note:** Module 7 (Risk & Sentiment) and Module 9 (Alerts) touch every other module's outputs — treat these as integration checkpoints where all three tracks sync, not solo work.

---
*End of execution document. Update the checkboxes in each module's Tasks/DoD sections directly as you build — this doc is meant to be a living tracker, not a one-time read.*
