# Requirements Specification — Basarat

## 1. System Requirements

The Basarat platform provides a multi-tenant, cloud-deployable financial analysis and intelligence system for the Pakistan Stock Exchange (PSX).

### 1.1 Operating Environment & Software Dependencies
- **Backend Runtime:** Python 3.11+ (CPython 3.11.9 recommended).
- **Frontend Runtime:** Node.js 18+ (LTS recommended) with npm/npx.
- **Relational Datastore:** PostgreSQL 16+ with ACID compliance, JSONB support, and full relational integrity.
- **In-Memory Cache & Message Broker:** Redis 7+ with Pub/Sub capabilities, key eviction (LRU), and persistence (RDB/AOF).
- **Asynchronous Task Worker:** Celery 5.4+ with Celery Beat daemon.
- **Operating System:** Linux (Ubuntu 22.04 LTS / Debian 12 recommended for production; Windows 11 / macOS supported for development).

---

## 2. User Requirements

| Requirement ID | Target User | Requirement Statement | Implementation Status |
|---|---|---|---|
| **UR-001** | All Users | The system shall allow users to register an account using an email address and a strong password, or sign in using Google or Apple OAuth. | **Implemented** |
| **UR-002** | All Users | The system shall require email verification via a 6-digit one-time passcode (OTP) before activating new accounts. | **Implemented** |
| **UR-003** | All Users | The system shall provide a secure password recovery flow utilizing a time-limited 6-digit OTP sent to the user's verified email. | **Implemented** |
| **UR-004** | All Users | The system shall allow users to customize their investment profile, including risk tolerance (Conservative, Moderate, Aggressive), investment horizon (Short, Medium, Long), and preferred market sectors. | **Implemented** |
| **UR-005** | Public / All | The system shall provide real-time and near-real-time quotes, index summaries (KSE-100, KSE-30, KMI-30), top gainers, losers, and volume leaders for PSX equities without requiring mandatory login. | **Implemented** |
| **UR-006** | Registered User | The system shall enable users to create multiple custom stock watchlists, bookmark stocks with 1-tap toggles, and view real-time price changes relative to when the stock was added (`added_price`). | **Implemented** |
| **UR-007** | Registered User | The system shall deliver AI-powered directional market forecasts (Bullish, Bearish, Sideways) with probability confidence percentages for active PSX stocks. | **Implemented** |
| **UR-008** | Registered User | The system shall track historical forecast performance against actual closing prices to provide transparent model accuracy metrics. | **Implemented** |
| **UR-009** | Registered User | The system shall generate multi-factor quantitative stock rankings (Buy, Hold, Sell) and allow users to customize the scoring weights across Technical, Fundamental, Sentiment, and Valuation factors. | **Implemented** |
| **UR-010** | Registered User | The system shall provide a portfolio transaction ledger supporting BUY and SELL trades, automatic calculation of Average Cost Basis (ACB), realized and unrealized P&L, and asset allocation charts. | **Implemented** |
| **UR-011** | Registered User | The system shall compute portfolio risk metrics including Parametric and Historical Value-at-Risk (VaR 95/99), Conditional VaR (CVaR), Sharpe ratio, Beta, and asynchronous Monte Carlo simulations. | **Implemented** |
| **UR-012** | Public / All | The system shall screen PSX stocks for Islamic Shariah compliance under AAOIFI and KMI-30 standards, and provide an accurate dividend purification calculator. | **Implemented** |
| **UR-013** | Registered User | The system shall ingest financial news and official PSX disclosures, perform FinBERT NLP sentiment scoring, and display rolling sentiment trends per stock. | **Implemented** |
| **UR-014** | Registered User | The system shall provide a context-aware conversational AI assistant that analyzes user portfolios, answers stock queries, and adheres to strict financial safety disclaimers. | **Implemented** |
| **UR-015** | Registered User | The system shall provide a community social feed where users can publish posts, share stock charts, comment, like, follow other users, and report policy violations. | **Implemented** |
| **UR-016** | Administrator | The system shall provide an administrative moderation console to review reported posts/comments, dismiss reports, restore content, or enforce immediate removals. | **Implemented** |

---

## 3. Software Architecture & Functional Requirements

### 3.1 Data Ingestion & Market Processing Requirements
- **SR-DAT-01:** The system shall ingest end-of-day and intraday OHLCV market data from the Pakistan Stock Exchange during active trading hours (09:15 to 15:30 PKT, Monday through Friday). *(Implemented)*
- **SR-DAT-02:** The system shall throttle scraping requests and enforce a 15-minute circuit breaker upon receiving HTTP 429 or 403 responses from upstream sources. *(Implemented)*
- **SR-DAT-03:** The system shall store market quote snapshots in Redis with an automated Time-To-Live (TTL) of 90 seconds to prevent stale data delivery. *(Implemented)*
- **SR-DAT-04:** The system shall publish live quote updates onto a Redis Pub/Sub channel (`market:quotes:live`) for fanout to active WebSocket clients. *(Implemented)*

### 3.2 Machine Learning & Analytics Requirements
- **SR-ML-01:** The system shall load pre-trained Attention-BiGRU and XGBoost model artifacts into memory at application startup and serve inference in < 150ms per stock. *(Implemented)*
- **SR-ML-02:** If any ML model artifact is missing or corrupt, the system shall fail gracefully, either falling back to single-model mode or returning a structured HTTP 503 response. *(Implemented)*
- **SR-ML-03:** The system shall abstain from generating directional forecasts when the model confidence is below defined thresholds or when ensemble sub-models diverge significantly. *(Implemented)*
- **SR-ML-04:** The system shall execute an automated daily reconciliation workflow at 18:00 PKT to compute `actual_direction` and update the `was_correct` audit flag in the `predictions` table. *(Implemented)*

### 3.3 Sentiment Analysis & NLP Requirements
- **SR-NLP-01:** The system shall ingest financial articles from multiple feeds (PSX announcements, Mettis Global, official gazettes) and compute SHA-256 hashes of the content to prevent duplicate storage. *(Implemented)*
- **SR-NLP-02:** The system shall submit unclassified article text to the HuggingFace Inference API running the FinBERT model to extract Positive, Negative, and Neutral probabilities. *(Implemented)*
- **SR-NLP-03:** If the HuggingFace API is unavailable or unconfigured, the system shall fall back to rule-based financial lexicon and EPS heuristics. *(Implemented)*
- **SR-NLP-04:** The system shall pre-calculate rolling sentiment aggregates across 1D, 1W, 1M, 3M, 6M, and 1Y periods. *(Implemented)*

---

## 4. External Service & Integration Requirements

| Integration | Provider / Protocol | Purpose | Fallback / Failure Mode | Status |
|---|---|---|---|---|
| **Transactional Email** | SendGrid API / SMTP | Delivering 6-digit OTP verification codes and password reset links. | Logs warning; returns `status: disabled` if credentials omitted. | **Implemented** |
| **Large Language Model** | Groq Cloud API (REST/SSE) | Generating conversational responses for the Stock AI Assistant (`openai/gpt-oss-20b`, `qwen/qwen3.8-27b`). | Falls back to backup model or returns error explaining LLM downtime. | **Implemented** |
| **Financial Sentiment NLP** | HuggingFace Inference API (`ProsusAI/finbert`) | Domain-specific sentiment classification of PSX news and disclosures. | Falls back to rule-based keyword / EPS heuristics. | **Implemented** |
| **OAuth Identity** | Google OAuth 2.0 & Apple Sign-In | Federated social authentication on mobile and web. | Standard email/password signup remains fully functional. | **Implemented** |
| **Push Notifications** | Firebase Cloud Messaging (FCM) HTTP v1 | Mobile alerts on price triggers, risk breaches, and community interactions. | Disabled if `FIREBASE_ENABLED=false` or service account JSON missing. | **Partially Implemented** |
| **Media Cloud Storage** | Cloudinary REST API | Uploading, optimizing, and serving user community post attachments. | Local temp directory fallback / image upload rejected with clear error. | **Implemented** |
| **Authentication Webhooks** | Clerk Webhook API | External user synchronization via HMAC-SHA256 signature verification. | Rejects unverified requests with HTTP 400. | **Implemented** |

---

## 5. Security & Data Protection Requirements

- **SEC-01 (Password Security):** Passwords shall be hashed using salted `bcrypt` with automatic salt generation before persistence in PostgreSQL. *(Implemented)*
- **SEC-02 (Token Lifecycle & Revocation):** Access tokens shall use signed JWTs (`HS256`) with a 30-minute expiration. Every token must contain a token version claim (`tv`). If the user's `token_version` is bumped (e.g. on logout or password change), all outstanding access tokens are invalidated immediately. *(Implemented)*
- **SEC-03 (Refresh Token Rotation):** Refresh tokens shall have a 7-day lifetime, be tracked by a unique UUID `jti` in the database, and be rotated upon every refresh invocation. *(Implemented)*
- **SEC-04 (Role-Based Access Control):** Administrative endpoints (`/api/v1/admin/*`, `/api/v1/etfs` POST/PUT, `/api/v1/ipos` POST/PUT) shall strictly enforce `is_admin == True` via dependency injection (`get_current_admin`). *(Implemented)*
- **SEC-05 (Resource Ownership Enforcement):** All user-owned entities (Watchlists, Portfolio Transactions, Alerts, Devices, Assistant Conversations, Community Posts/Comments) shall strictly enforce user ID matching at the database query level. Non-owners shall receive HTTP 404 or HTTP 403. *(Implemented)*
- **SEC-06 (Rate Limiting):** Public authentication and resource-intensive endpoints shall be throttled using sliding-window Redis rate limiters to prevent brute-force attacks and denial-of-service. *(Implemented)*
- **SEC-07 (CORS Isolation):** In staging and production environments, wildcard origins (`*`) shall be rejected at startup, requiring an explicit domain whitelist. *(Implemented)*
- **SEC-08 (AI Prompt Injection & Safety):** All user prompts to the AI Assistant shall be scanned for prompt injection attacks and malicious instructions. AI responses must append financial disclaimers. *(Implemented)*

---

## 6. Non-Functional Requirements Summary

- **Performance:** REST endpoint response times shall be < 200ms (P95) for cached market data and < 500ms for database queries.
- **Reliability & Uptime:** Health checks (`/api/v1/health` and `/api/v1/health/ready`) shall report component-level status for PostgreSQL, Redis, Celery workers, and Celery Beat.
- **Data Integrity:** Portfolio transactions shall maintain foreign key constraints against active stock symbols and user accounts with atomic database transactions.
- **Maintainability:** Codebase shall maintain modular separation between API routers, service layers, repository layers, Pydantic schemas, and SQLAlchemy ORM models.
