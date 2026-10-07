# Functional Requirements

## Module 1 — Authentication & User Management

### FR-001 — User Registration with Email OTP

**Actor:** Unregistered User
**Description:** The system shall allow users to register with email, password, and full name. A 6-digit OTP verification code is sent via SendGrid email.
**Preconditions:** User email is not already registered
**Expected Behavior:** Creates an unverified user account, sends OTP email, returns success message
**Implementation:** Implemented
**Related Components:**
- `app/api/v1/auth.py` — `POST /auth/signup`
- `app/services/auth_service.py` — `AuthService.signup()`
- `app/services/email_service.py` — `EmailService.send_verification_code()`

### FR-002 — Email OTP Verification

**Actor:** Unregistered User (pending verification)
**Description:** The system shall verify a 6-digit OTP code and activate the user account, returning JWT access and refresh tokens.
**Preconditions:** User has signed up and received OTP email
**Expected Behavior:** Sets `is_verified = True`, returns access_token and refresh_token
**Implementation:** Implemented
**Related Components:**
- `app/api/v1/auth.py` — `POST /auth/verify-email`
- `app/services/auth_service.py` — `AuthService.verify_email()`

### FR-003 — User Login

**Actor:** Registered, Verified User
**Description:** The system shall authenticate users with email/password credentials and return JWT tokens.
**Preconditions:** User is verified and active
**Expected Behavior:** Returns short-lived access_token (30 min) and rotating refresh_token (7 days)
**Implementation:** Implemented
**Related Components:**
- `app/api/v1/auth.py` — `POST /auth/login`
- `app/services/auth_service.py` — `AuthService.login()`

### FR-004 — Google OAuth Login

**Actor:** Any User
**Description:** The system shall authenticate or register users using a Google OAuth ID Token.
**Preconditions:** Valid Google ID token from Google Sign-In SDK
**Expected Behavior:** Creates or links user account, sets `is_verified = True`, returns JWT tokens
**Implementation:** Implemented
**Related Components:**
- `app/api/v1/auth.py` — `POST /auth/google`
- `app/services/auth_service.py` — `AuthService.authenticate_google()`

### FR-005 — Apple OAuth Login

**Actor:** Any User
**Description:** The system shall authenticate or register users using an Apple Identity Token.
**Preconditions:** Valid Apple ID token from Sign in with Apple SDK
**Expected Behavior:** Creates or links user account, returns JWT tokens
**Implementation:** Implemented
**Related Components:**
- `app/api/v1/auth.py` — `POST /auth/apple`
- `app/services/auth_service.py` — `AuthService.authenticate_apple()`

### FR-006 — Token Refresh with Rotation

**Actor:** Authenticated User
**Description:** The system shall exchange a valid refresh token for new access and refresh tokens. The old refresh token is revoked. Reuse of revoked tokens invalidates all sessions.
**Preconditions:** Valid, unexpired, non-revoked refresh token
**Expected Behavior:** Returns new token pair; old refresh token is marked revoked
**Implementation:** Implemented
**Related Components:**
- `app/api/v1/auth.py` — `POST /auth/refresh`
- `app/services/auth_service.py` — `AuthService.refresh_token()`

### FR-007 — 3-Step Password Reset (OTP + Grant Token)

**Actor:** Registered User
**Description:** The system shall support a 3-step password reset flow: (1) Request OTP → (2) Verify OTP, receive grant token → (3) Set new password with grant token.
**Preconditions:** User has a registered account
**Expected Behavior:** Step 1 sends 6-digit OTP; Step 2 returns reset_token grant (15 min); Step 3 updates password and revokes all sessions
**Implementation:** Implemented
**Related Components:**
- `app/api/v1/auth.py` — `POST /auth/forgot-password`, `POST /auth/verify-reset-code`, `POST /auth/reset-password`
- `app/services/auth_service.py`

### FR-008 — Authenticated Password Change

**Actor:** Authenticated User
**Description:** The system shall allow authenticated users to change their password by providing the current password. All other sessions are revoked.
**Implementation:** Implemented
**Related Components:**
- `app/api/v1/auth.py` — `POST /auth/change-password`

---

## Module 2 — Market Data

### FR-009 — Live Market Summary

**Actor:** Any User
**Description:** The system shall provide PSX market summary including indices, gainers, losers, and most active stocks via Redis-cached snapshots.
**Implementation:** Implemented
**Related Components:**
- `app/api/v1/market.py`
- `app/services/market_service.py`
- `app/tasks/refresh_market_cache.py`

### FR-010 — Live Market Quotes via WebSocket

**Actor:** Any User
**Description:** The system shall stream live PSX stock quotes over WebSocket connections. Clients may subscribe to specific symbols.
**Implementation:** Implemented
**Related Components:**
- `app/api/v1/ws.py`
- `app/services/websocket_manager.py`
- `app/services/market_live_bus.py`

---

## Module 3 — Stocks & Watchlists

### FR-011 — Stock Detail and Search

**Actor:** Any User
**Description:** The system shall provide individual stock quotes, company profiles, fundamental data, and search functionality.
**Implementation:** Implemented
**Related Components:**
- `app/api/v1/stocks.py`
- `app/services/stock_service.py`

### FR-012 — Watchlist Management

**Actor:** Authenticated User
**Description:** The system shall allow users to create, update, and delete watchlists with stock items, target prices, and notes. One default watchlist per user.
**Implementation:** Implemented
**Related Components:**
- `app/api/v1/watchlist.py`
- `app/services/watchlist_service.py`
- `app/models/watchlist.py`

---

## Module 4 — Forecasting

### FR-013 — ML Directional Forecast

**Actor:** Any User
**Description:** The system shall provide ML-based directional stock forecasts (bullish/bearish/sideways) using a GRU + XGBoost ensemble model. Predictions include confidence percentages.
**Implementation:** Implemented
**Related Components:**
- `app/api/v1/forecast.py`
- `app/ml/serving/inference.py`
- `app/ml/serving/prediction_store.py`
- `app/models/prediction.py`

### FR-014 — Daily Forecast Pipeline

**Actor:** System (Celery Beat)
**Description:** The system shall automatically run a daily pipeline five minutes after the PSX close (Mon-Thu 15:35 and Fri 16:35 PKT under the configured standard schedule). It refreshes final OHLCV closes for the union of registered stocks, cached market quote symbols, and existing OHLCV files, then generates features and predictions and evaluates past predictions. The pipeline shall skip weekends and exchange holidays. Before incremental scraping, missing per-symbol files are restored from persisted stock prices where available; new quote-only symbols are initially fetched for up to one year. OHLCV requests are paced in batches of 50 with a 15-second pause between batches, and the refresh task has an extended deadline for the full market universe.
**Implementation:** Implemented
**Related Components:**
- `app/tasks/daily_workflow.py`
- `app/data/scraper/run_after_close.py`
- `app/celery_app.py` — weekday-specific daily-workflow schedules

---

## Module 5 — Recommendations

### FR-015 — Quantitative Stock Recommendations

**Actor:** Any User
**Description:** The system shall generate automated buy/hold/sell stock rankings based on quantitative signals.
**Implementation:** Implemented
**Related Components:**
- `app/api/v1/recommendations.py`
- `app/services/recommendation_service.py`

---

## Module 6 — Portfolio

### FR-016 — Portfolio Transaction Management

**Actor:** Authenticated User
**Description:** The system shall allow users to record buy/sell transactions with quantity, price, fee, and date. The system computes holdings, P&L, and sector allocations.
**Implementation:** Implemented
**Related Components:**
- `app/api/v1/portfolio.py`
- `app/services/portfolio_service.py`
- `app/services/portfolio_calculation.py`
- `app/models/portfolio.py`

---

## Module 7 — Risk & Sentiment

### FR-017 — Portfolio Risk Analytics

**Actor:** Authenticated User
**Description:** The system shall compute portfolio risk metrics including VaR (95%, 99%), CVaR, Sharpe ratio, beta, Monte Carlo simulations, and stress tests.
**Implementation:** Implemented
**Related Components:**
- `app/api/v1/risk.py`
- `app/services/risk_service.py`
- `app/models/risk.py`

### FR-018 — News Sentiment Analysis

**Actor:** Any User
**Description:** The system shall provide FinBERT-based sentiment analysis (positive/negative/neutral) for PSX news articles, with aggregate scores per stock over rolling windows.
**Implementation:** Implemented
**Related Components:**
- `app/api/v1/sentiment.py`
- `app/services/sentiment_service.py`
- `app/models/sentiment.py`

---

## Module 8 — News & Events

### FR-019 — Financial News Aggregation

**Actor:** Any User
**Description:** The system shall ingest and serve financial news from PSX, Mettis, OGRA, FBR/MOF sources with sentiment scoring and symbol tagging.
**Implementation:** Implemented
**Related Components:**
- `app/api/v1/news.py`
- `app/services/news_service.py`
- `app/tasks/scrape_news.py`
- `app/services/news_pipeline/`

### FR-020 — Corporate Events Calendar

**Actor:** Any User
**Description:** The system shall provide a calendar of PSX corporate events (AGMs, earnings, dividends).
**Implementation:** Implemented
**Related Components:**
- `app/api/v1/events.py`
- `app/services/event_service.py`

---

## Module 9 — Alerts & Notifications

### FR-021 — Custom Alert Rules

**Actor:** Authenticated User
**Description:** The system shall allow users to create price-based alert rules on stocks. Rules are evaluated every 5 minutes via Celery Beat.
**Implementation:** Implemented
**Related Components:**
- `app/api/v1/alerts.py`
- `app/services/alert_service.py`
- `app/tasks/alert_tasks.py`
- `app/models/alert.py`

### FR-022 — Push Notifications

**Actor:** Authenticated User
**Description:** The system shall send Firebase Cloud Messaging push notifications for triggered alerts and risk breaches.
**Implementation:** Implemented (requires Firebase configuration)
**Related Components:**
- `app/api/v1/notifications.py`
- `app/api/v1/devices.py`
- `app/services/notification_service.py`
- `app/tasks/push_notifications.py`

---

## Module 10 — Shariah Screening

### FR-023 — Shariah Compliance Screening

**Actor:** Any User
**Description:** The system shall screen PSX stocks for Shariah compliance using AAOIFI criteria and KMI-30 index data. Provides debt ratios and dividend purification calculators.
**Implementation:** Implemented
**Related Components:**
- `app/api/v1/shariah.py`
- `app/services/shariah_service.py`
- `app/models/shariah.py`

---

## Module 11 — Community

### FR-024 — Social Trading Posts

**Actor:** Authenticated User
**Description:** The system shall allow users to create, edit, delete stock discussion posts (STOCK type linked to a symbol, or GENERAL_MARKET type). Posts support image attachments via Cloudinary.
**Implementation:** Implemented
**Related Components:**
- `app/api/v1/community/posts.py`
- `app/services/community_service.py`
- `app/models/community.py`

### FR-025 — Comments and Replies

**Actor:** Authenticated User
**Description:** The system shall support threaded comments and replies on community posts.
**Implementation:** Implemented
**Related Components:**
- `app/api/v1/community/comments.py`

### FR-026 — Follow Network

**Actor:** Authenticated User
**Description:** The system shall allow users to follow/unfollow other users and view follower/following lists.
**Implementation:** Implemented
**Related Components:**
- `app/api/v1/community/follows.py`

### FR-027 — Content Moderation

**Actor:** Admin User
**Description:** The system shall support reporting posts/comments, automatic hiding after threshold reports, and admin moderation actions (delete, restore).
**Implementation:** Implemented
**Related Components:**
- `app/api/v1/admin/community.py`
- `app/models/community.py` — `CommunityReport`, `CommunityModerationAction`

---

## Module 12 — AI Assistant

### FR-028 — AI Investment Chatbot

**Actor:** Authenticated User
**Description:** The system shall provide an AI investment assistant that can answer questions about PSX stocks, portfolio, and market conditions. Uses Groq LLM with market context injection and safety guardrails. Supports streaming responses.
**Implementation:** Implemented
**Related Components:**
- `app/api/v1/assistant/chat.py`
- `app/services/assistant_service.py`
- `app/services/assistant_context.py`
- `app/services/assistant_safety.py`
- `app/services/groq_client.py`

---

## Module 13 — ETFs & IPOs

### FR-029 — ETF Directory

**Actor:** Any User
**Description:** The system shall provide ETF listings with fund details, expense ratios, and Shariah compliance status. Admin CRUD supported.
**Implementation:** Implemented
**Related Components:**
- `app/api/v1/etfs.py`
- `app/services/etf_service.py`
- `app/models/etf.py`

### FR-030 — IPO Calendar and Tracking

**Actor:** Any User
**Description:** The system shall provide IPO listings with book building dates, subscription periods, pricing, and post-listing performance. Admin CRUD supported.
**Implementation:** Implemented
**Related Components:**
- `app/api/v1/ipos.py`
- `app/services/ipo_service.py`
- `app/models/ipo.py`

---

## Module 14 — Background Processing

### FR-031 — Weekly Model Retraining

**Actor:** System (Celery Beat)
**Description:** The system shall retrain ML models weekly (Sunday 04:00 PKT) and promote candidates only if accuracy/F1 improvements exceed thresholds.
**Implementation:** Implemented
**Related Components:**
- `app/tasks/weekly_retraining.py`
- `app/ml/serving/promotion.py`
- `app/models/model_registry.py`
- `app/models/training_run.py`

### FR-032 — News Ingestion Pipeline

**Actor:** System (Celery Beat)
**Description:** The system shall automatically ingest news every 30 minutes during market hours, with sentiment scoring via FinBERT.
**Implementation:** Implemented
**Related Components:**
- `app/tasks/scrape_news.py`
- `app/tasks/news_tasks.py`
- `app/tasks/sentiment_tasks.py`
