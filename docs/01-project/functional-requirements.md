# Functional Requirements Specification — Basarat

This document details the functional requirements of the Basarat platform, mapped directly to the implementation within the codebase.

---

## Module 1: Authentication & User Identity

### FR-001 — User Registration (Email & Password)
- **Actor:** Unauthenticated Guest
- **Preconditions:** Valid email address and strong password (minimum 8 characters).
- **Expected Behavior:** System creates an unverified user record with a bcrypt-hashed password, generates a 6-digit OTP code with a 10-minute expiration, stores its SHA-256 hash in `email_verification_tokens`, dispatches the OTP via transactional email (SendGrid/SMTP), and returns a generic success message without leaking email existence (anti-enumeration).
- **Implementation Status:** Implemented
- **Related Components:**
  - Route: `POST /api/v1/auth/signup` ([auth.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/api/v1/auth.py))
  - Service: `AuthService.signup` ([auth_service.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/services/auth_service.py))
  - Schema: `SignupRequest`, `GenericMessageResponse` ([auth.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/schemas/auth.py))
  - Model: `User`, `EmailVerificationToken` ([user.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/models/user.py))

### FR-002 — Email Verification via 6-Digit OTP
- **Actor:** Registered User (Unverified)
- **Preconditions:** Active unverified user account and valid 6-digit OTP.
- **Expected Behavior:** System verifies the SHA-256 hash of the submitted OTP against `email_verification_tokens`, validates that the token is not expired and not previously used, marks the token as used, updates `User.is_verified = True`, and issues an access JWT (30m) and refresh JWT (7d) with an initial `token_version`.
- **Implementation Status:** Implemented
- **Related Components:**
  - Route: `POST /api/v1/auth/verify-email`
  - Service: `AuthService.verify_email`
  - Model: `User`, `EmailVerificationToken`, `RefreshToken`

### FR-003 — Standard User Login
- **Actor:** Registered User (Verified)
- **Preconditions:** Valid email and password credentials.
- **Expected Behavior:** System verifies bcrypt password hash. If verified and active, creates a new `RefreshToken` record in PostgreSQL with a unique UUID `jti`, issues an access token signed with `SECRET_KEY` (containing `sub`, `exp`, `type="access"`, `tv=token_version`), and returns access/refresh tokens alongside a `UserSummary` object.
- **Implementation Status:** Implemented
- **Related Components:**
  - Route: `POST /api/v1/auth/login`
  - Service: `AuthService.login`

### FR-004 — Access Token Refresh with Rotation
- **Actor:** Authenticated Client
- **Preconditions:** Valid, non-revoked refresh token.
- **Expected Behavior:** System validates token signature, extracts `jti`, confirms the token exists in `refresh_tokens` and is not revoked, marks the old token as revoked (`revoked=True`, `revoked_at=now()`), generates a new refresh token and access token, and returns both to the client.
- **Implementation Status:** Implemented
- **Related Components:**
  - Route: `POST /api/v1/auth/refresh`
  - Service: `AuthService.refresh_token`

### FR-005 — 3-Step Secure Password Reset Flow
- **Actor:** Registered User
- **Preconditions:** Access to registered email inbox.
- **Expected Behavior:**
  1. **Step 1 (`POST /auth/forgot-password`):** Generates a 6-digit OTP, saves its SHA-256 hash in `password_reset_tokens`, and sends it via email.
  2. **Step 2 (`POST /auth/verify-reset-code`):** Validates the OTP and returns a short-lived (15-minute) signed JWT `reset_token` grant (`type="password_reset_grant"`).
  3. **Step 3 (`POST /auth/reset-password`):** Validates the grant token, hashes the new password, updates `User.hashed_password`, and increments `User.token_version` by 1 to revoke all existing sessions.
- **Implementation Status:** Implemented
- **Related Components:**
  - Routes: `POST /api/v1/auth/forgot-password`, `POST /api/v1/auth/verify-reset-code`, `POST /api/v1/auth/reset-password`
  - Service: `AuthService.forgot_password`, `AuthService.verify_reset_code`, `AuthService.reset_password_with_token`

### FR-006 — Single-Session and All-Session Logout
- **Actor:** Authenticated User
- **Preconditions:** Valid access token and/or refresh token.
- **Expected Behavior:** Revokes the specific refresh token in the database, increments the user's `token_version` to immediately invalidate all outstanding access JWTs, and clears active sessions.
- **Implementation Status:** Implemented
- **Related Components:**
  - Route: `POST /api/v1/auth/logout`
  - Service: `AuthService.logout`

### FR-007 — Social Identity Federation (Google & Apple OAuth)
- **Actor:** Any User
- **Preconditions:** Valid ID token from Google Identity Services or Apple Sign-In.
- **Expected Behavior:** Verifies ID token signature with provider public keys, extracts email, verified status, and unique provider subject ID (`oauth_id`), retrieves or provisions the user record, and generates Basarat access and refresh JWTs.
- **Implementation Status:** Implemented
- **Related Components:**
  - Routes: `POST /api/v1/auth/google`, `POST /api/v1/auth/apple`
  - Service: `AuthService.google_auth`, `AuthService.apple_auth`

---

## Module 2: Market Data & Streaming

### FR-008 — Real-Time Market Overview & Indices
- **Actor:** Public / Any User
- **Preconditions:** Market data cache populated in Redis or sync service reachable.
- **Expected Behavior:** Returns high-level summary of PSX performance, status (Market Open / Closed), total volume, value traded, advancing/declining counts, and performance of KSE-100, KSE-30, and KMI-30 indices.
- **Implementation Status:** Implemented
- **Related Components:**
  - Routes: `GET /api/v1/market/indices`, `GET /api/v1/market/indices/{index_name}`
  - Service: `MarketService.get_indices`, `MarketService.get_market_summary`

### FR-009 — Market Discovery & Leaderboards
- **Actor:** Public / Any User
- **Preconditions:** None.
- **Expected Behavior:** Returns top 10 gainers, top 10 losers, top volume leaders, volume spike anomalies, and curated investment leaderboards (High Dividend Yield, Best 1-Year Return, Value Picks, Most Liquid).
- **Implementation Status:** Implemented
- **Related Components:**
  - Routes: `GET /api/v1/market/gainers`, `GET /api/v1/market/losers`, `GET /api/v1/market/volume-spikes`, `GET /api/v1/market/curated`
  - Service: `MarketService.get_gainers`, `MarketService.get_losers`, `MarketService.get_volume_leaders`, `MarketService.get_curated_stocks`

### FR-010 — Real-Time WebSocket Quote Stream
- **Actor:** Public / Client Application
- **Preconditions:** WebSocket connection established to `/api/v1/ws/market`.
- **Expected Behavior:** Client subscribes to symbol channels (`{"action": "subscribe", "symbols": ["ENGRO", "LUCK", "OGDC"]}`). Server streams live price updates whenever new quotes are published on the Redis `market:quotes:live` pub/sub bus. Supports heartbeat ping/pong (`{"action": "ping"}`).
- **Implementation Status:** Implemented
- **Related Components:**
  - Route: `WebSocket /api/v1/ws/market`, `WebSocket /ws/market` ([ws.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/api/v1/ws.py))
  - Services: `WebSocketManager`, `MarketLiveBus` ([market_live_bus.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/services/market_live_bus.py))

---

## Module 3: Stock Fundamentals & Technicals

### FR-011 — Stock Profile, Overview & Search
- **Actor:** Public / Any User
- **Preconditions:** None.
- **Expected Behavior:** Provides search autocomplete across 500+ PSX equities by ticker symbol or company name. Returns comprehensive overview with market cap, sector, 52-week high/low, P/E ratio, EPS, dividend yield, and current live quote.
- **Implementation Status:** Implemented
- **Related Components:**
  - Routes: `GET /api/v1/stocks/search`, `GET /api/v1/stocks/{symbol}/overview`
  - Service: `StockService.search_stocks`, `StockService.get_stock_overview`

### FR-012 — Technical Indicators & Signal Generation
- **Actor:** Public / Any User
- **Preconditions:** Sufficient historical OHLCV data for the requested symbol.
- **Expected Behavior:** Computes key technical indicators over daily timeframes: RSI (14), MACD (12, 26, 9), Exponential Moving Averages (EMA 20, 50, 200), Simple Moving Averages (SMA 20, 50, 200), Bollinger Bands (20, 2), Average True Range (ATR), and Stochastic Oscillator. Generates an overall technical momentum summary (Bullish, Bearish, or Neutral).
- **Implementation Status:** Implemented
- **Related Components:**
  - Route: `GET /api/v1/stocks/{symbol}/technical-indicators`
  - Service: `StockService.get_technical_indicators`

---

## Module 4: Watchlist Management

### FR-013 — Custom Watchlists & 1-Tap Toggle
- **Actor:** Authenticated User
- **Preconditions:** User is authenticated.
- **Expected Behavior:** Allows creating multiple named watchlists, marking a default watchlist, and bookmarking stocks. Supports 1-tap toggling (`POST /watchlists/toggle/{symbol}`) that automatically creates a default watchlist if none exists.
- **Implementation Status:** Implemented
- **Related Components:**
  - Routes: `GET /api/v1/watchlists`, `POST /api/v1/watchlists`, `POST /api/v1/watchlists/toggle/{symbol}`
  - Service: `WatchlistService.toggle_stock_in_default`, `WatchlistService.create_watchlist`
  - Model: `Watchlist`, `WatchlistItem`

### FR-014 — Watchlist Live Enrichment & Price Change Since Added
- **Actor:** Authenticated User
- **Preconditions:** Watchlist contains stock items.
- **Expected Behavior:** Returns watchlist items enriched with real-time quote, price change since added (`((current_price - added_price) / added_price) * 100`), target price progress, latest ML directional forecast badge, and FinBERT sentiment rating.
- **Implementation Status:** Implemented
- **Related Components:**
  - Route: `GET /api/v1/watchlists/{watchlist_id}`, `GET /api/v1/watchlists/default`
  - Service: `WatchlistService.get_watchlist_by_id`, `WatchlistService.get_default_watchlist`

---

## Module 5: Machine Learning Forecasting

### FR-015 — On-Demand & Daily Directional Forecast Inference
- **Actor:** Authenticated User / Daily Celery Task
- **Preconditions:** Stock has sufficient historical features in `features_daily.parquet` or computed sequence.
- **Expected Behavior:** Runs inference through the Attention-BiGRU (v2) and XGBoost (v4) models. Computes probability breakdown (Bullish %, Bearish %, Sideways %), identifies top predicted class, applies confidence gating, persists the result to `predictions` table, and returns prediction metadata with model audit details.
- **Implementation Status:** Implemented
- **Related Components:**
  - Routes: `GET /api/v1/forecast/{symbol}`, `GET /api/v1/forecast/pipeline`
  - Services: `inference.predict_for_symbol`, `PredictionStore.save_prediction`
  - Tasks: `daily_workflow.generate_predictions`

### FR-016 — Historical Forecast Accuracy Tracking
- **Actor:** Authenticated User
- **Preconditions:** Past predictions exist for the requested symbol.
- **Expected Behavior:** Retrieves chronological forecast history with as-of dates, target dates, predicted directions, actual realized directions, and boolean `was_correct` markers. Calculates rolling empirical accuracy percentage.
- **Implementation Status:** Implemented
- **Related Components:**
  - Route: `GET /api/v1/forecast/{symbol}/history`
  - Service: `PredictionStore.get_forecast_history`

---

## Module 6: Quantitative Recommendations

### FR-017 — Multi-Factor Stock Scoring & Ranking
- **Actor:** Authenticated User
- **Preconditions:** Stocks have up-to-date technicals, fundamentals, sentiment, and forecasts.
- **Expected Behavior:** Evaluates stocks across four quantitative dimensions:
  1. Technical Score (0-100): RSI, MACD, Trend Alignment.
  2. Fundamental Score (0-100): P/E relative to sector, ROE, Debt/Equity.
  3. Sentiment Score (0-100): FinBERT rolling 30-day sentiment ratio.
  4. ML Forecast Score (0-100): Directional ensemble probability.
  Calculates composite score, generates recommendation action (STRONG_BUY, BUY, HOLD, SELL, STRONG_SELL), target price, stop-loss price, and risk level.
- **Implementation Status:** Implemented
- **Related Components:**
  - Routes: `GET /api/v1/recommendations`, `GET /api/v1/recommendations/{symbol}`, `GET /api/v1/recommendations/{symbol}/target-stop`
  - Service: `RecommendationService.get_recommendations`, `RecommendationService.calculate_target_stop`

### FR-018 — User-Customizable Factor Weights
- **Actor:** Authenticated User
- **Preconditions:** User is authenticated.
- **Expected Behavior:** Allows users to adjust the weighting coefficients of Technical, Fundamental, Sentiment, and Valuation factors (must sum to 1.0), persisting custom weights to `User.recommendation_weights`.
- **Implementation Status:** Implemented
- **Related Components:**
  - Routes: `GET /api/v1/recommendations/engine-weights`, `POST /api/v1/recommendations/engine-weights`
  - Service: `RecommendationService.get_engine_weights`, `RecommendationService.set_engine_weights`

---

## Module 7: Portfolio Management & Risk Suite

### FR-019 — Portfolio Transaction Ledger & Position Tracking
- **Actor:** Authenticated User
- **Preconditions:** User owns the portfolio account.
- **Expected Behavior:** Records BUY and SELL transactions with symbol, quantity, execution price, brokerage fee, and date. Validates that SELL transactions do not exceed available holdings. Calculates current open positions, Average Cost Basis (ACB), total invested amount, current market valuation, and unrealized/realized P&L.
- **Implementation Status:** Implemented
- **Related Components:**
  - Routes: `GET /api/v1/portfolio`, `POST /api/v1/portfolio/transactions`, `POST /api/v1/portfolio/transactions/completed-trade`
  - Service: `PortfolioService.get_portfolio_summary`, `PortfolioService.create_transaction`
  - Model: `PortfolioTransaction`

### FR-020 — Portfolio Risk Analytics (VaR & CVaR)
- **Actor:** Authenticated User
- **Preconditions:** User has active holdings with price history.
- **Expected Behavior:** Calculates 1-day and 10-day Value-at-Risk (VaR) at 95% and 99% confidence levels using Historical Simulation and Parametric approaches. Calculates Conditional Value-at-Risk (CVaR / Expected Shortfall), portfolio Beta against the KSE-100 benchmark, and annualized Sharpe ratio.
- **Implementation Status:** Implemented
- **Related Components:**
  - Route: `GET /api/v1/risk/var`
  - Service: `RiskService.calculate_portfolio_var`

### FR-021 — Asynchronous Monte Carlo Portfolio Simulation
- **Actor:** Authenticated User
- **Preconditions:** User has active portfolio holdings.
- **Expected Behavior:** Spawns a background Celery task executing 10,000 Geometric Brownian Motion (GBM) simulation paths over user-defined forecast horizons (30, 60, 90, 180, 365 days). Returns a `task_id` for polling (`GET /risk/monte-carlo/{task_id}`) that outputs confidence percentiles (5th, 25th, 50th, 75th, 95th) and probability of profit.
- **Implementation Status:** Implemented
- **Related Components:**
  - Routes: `POST /api/v1/risk/monte-carlo`, `GET /api/v1/risk/monte-carlo/{task_id}`
  - Service: `RiskService.start_monte_carlo`
  - Task: `risk_tasks.run_monte_carlo_simulation`

---

## Module 8: Shariah Compliance Screening

### FR-022 — AAOIFI & KMI-30 Screening Rules
- **Actor:** Public / Any User
- **Preconditions:** Stock financial statement data available.
- **Expected Behavior:** Evaluates companies against Shariah screening thresholds:
  1. Business Activity: Rejects conventional banking, insurance, alcohol, gambling, tobacco, etc.
  2. Debt-to-Total-Assets: Must be < 37%.
  3. Non-Compliant Investments to Total Assets: Must be < 33%.
  4. Illiquid Assets to Total Assets: Must be > 25%.
  5. Non-Compliant Income to Total Revenue: Must be < 5%.
  Returns overall compliance status (Compliant / Non-Compliant) with granular ratio breakdowns.
- **Implementation Status:** Implemented
- **Related Components:**
  - Routes: `GET /api/v1/shariah/{symbol}`, `GET /api/v1/shariah/{symbol}/criteria`, `GET /api/v1/shariah/kmi30`
  - Service: `ShariahService.screen_stock`, `ShariahService.get_kmi30_constituents`

### FR-023 — Dividend Purification Calculator
- **Actor:** Public / Any User
- **Preconditions:** Stock has Shariah screening ratios recorded.
- **Expected Behavior:** Calculates the exact dollar/rupee amount of non-compliant income per share that must be purified (donated to charity without tax benefit) based on the company's non-compliant income ratio and total dividend payout.
- **Implementation Status:** Implemented
- **Related Components:**
  - Route: `GET /api/v1/shariah/{symbol}/purification`
  - Service: `ShariahService.calculate_purification`

---

## Module 9: News & FinBERT Sentiment Analysis

### FR-024 — Multi-Source News Ingestion & Deduplication
- **Actor:** Celery Beat Cron / Authenticated User (Manual Refresh)
- **Preconditions:** External news sources reachable.
- **Expected Behavior:** Ingests articles from PSX company announcements, Mettis Global, and economic feeds. Computes SHA-256 `content_hash` to reject duplicates. Associates articles with matching PSX stock symbols in the `news_article_symbols` junction table.
- **Implementation Status:** Implemented
- **Related Components:**
  - Routes: `GET /api/v1/news`, `POST /api/v1/news/refresh`, `GET /api/v1/news/{article_id}`
  - Task: `scrape_news.run`
  - Models: `NewsArticle`, `NewsArticleSymbol`

### FR-025 — FinBERT Sentiment Scoring & Aggregation
- **Actor:** Celery Background Task / Sentiment Service
- **Preconditions:** Unscored articles in `news_articles`.
- **Expected Behavior:** Submits article headlines and summaries to FinBERT NLP model. Assigns Bullish, Bearish, or Neutral label with confidence score (-1.0 to +1.0). Updates rolling sentiment aggregates (1D, 1W, 1M, 3M, 6M, 1Y) per stock.
- **Implementation Status:** Implemented
- **Related Components:**
  - Routes: `GET /api/v1/sentiment/{symbol}`, `GET /api/v1/sentiment/market-overview`, `GET /api/v1/sentiment/{symbol}/history`
  - Service: `SentimentService.get_stock_sentiment`
  - Task: `sentiment_tasks.compute_article_sentiment`

---

## Module 10: Stock AI Investment Assistant

### FR-026 — Context-Aware Investment Copilot
- **Actor:** Authenticated User
- **Preconditions:** User has an active chat session.
- **Expected Behavior:** Receives user chat query, retrieves conversation history, builds dynamic financial context (user's current portfolio holdings, watchlist tickers, live quotes, risk profile), formats system prompts, checks for prompt injection attacks, invokes Groq LLM API, appends financial disclaimer, and persists message exchange.
- **Implementation Status:** Implemented
- **Related Components:**
  - Route: `POST /api/v1/assistant/chat`
  - Service: `AssistantService.send_message`, `ContextBuilder.build_context`
  - Models: `AssistantConversation`, `AssistantMessage`

### FR-027 — Server-Sent Events (SSE) Response Streaming
- **Actor:** Authenticated User
- **Preconditions:** Client supports EventSource / HTTP streaming.
- **Expected Behavior:** Streams LLM response tokens chunk-by-chunk over SSE (`text/event-stream`), enabling real-time typing animation in web and mobile interfaces while persisting full response upon stream completion.
- **Implementation Status:** Implemented
- **Related Components:**
  - Route: `POST /api/v1/assistant/chat/stream`
  - Service: `AssistantService.stream_message`

---

## Module 11: Community Social Network & Moderation

### FR-028 — Social Feed, Posts, Comments & Likes
- **Actor:** Authenticated User
- **Preconditions:** User profile is verified.
- **Expected Behavior:** Allows users to create posts tagged with stock tickers or general market tags, upload images (stored via Cloudinary), post threaded comments, like/unlike posts with optimistic counters, and follow/unfollow other investors.
- **Implementation Status:** Implemented
- **Related Components:**
  - Routes: `GET /api/v1/community/feed`, `POST /api/v1/community/posts`, `POST /api/v1/community/posts/{id}/comments`, `POST /api/v1/community/posts/{id}/like`, `POST /api/v1/community/users/{id}/follow`
  - Service: `CommunityService`
  - Models: `CommunityPost`, `CommunityComment`, `CommunityPostLike`, `CommunityFollow`

### FR-029 — User Reporting & Admin Moderation Workflow
- **Actor:** Authenticated User (Reporter) / Admin (Moderator)
- **Preconditions:** Inappropriate post or comment exists.
- **Expected Behavior:** Users can submit reports with reason codes (SPAM, OFF_TOPIC, MISLEADING, ABUSIVE, OTHER). If reports exceed threshold (default 3), post is auto-hidden (`status="TEMPORARILY_HIDDEN"`). Admins can inspect reported queues, review full context, dismiss reports, restore posts, or enforce direct permanent removals with audit log recording.
- **Implementation Status:** Implemented
- **Related Components:**
  - Routes: `POST /api/v1/community/posts/{id}/report`, `GET /api/v1/admin/community/reports`, `POST /api/v1/admin/community/posts/{id}/remove`, `POST /api/v1/admin/community/posts/{id}/restore`
  - Service: `CommunityService.report_post`, `CommunityService.moderate_post`
  - Models: `CommunityReport`, `CommunityModerationAction`

---

## Module 12: ETFs & IPOs Directory

### FR-030 — PSX ETFs Catalog & Performance
- **Actor:** Public / Any User
- **Preconditions:** ETF records populated in database.
- **Expected Behavior:** Lists all active PSX ETFs with category, fund manager, expense ratio, Shariah status, live NAV/price, historical OHLCV chart, and performance benchmarking.
- **Implementation Status:** Implemented
- **Related Components:**
  - Routes: `GET /api/v1/etfs`, `GET /api/v1/etfs/{symbol}`, `GET /api/v1/etfs/{symbol}/performance`
  - Service: `ETFService.get_all_etfs`, `ETFService.get_etf_details`
  - Model: `ETF`

### FR-031 — PSX IPO Pipeline & Calendar
- **Actor:** Public / Any User
- **Preconditions:** IPO records populated in database.
- **Expected Behavior:** Tracks upcoming and completed PSX Initial Public Offerings. Displays issue size, floor price, strike price, book building dates, public subscription dates, prospectus links, and post-listing percentage returns.
- **Implementation Status:** Implemented
- **Related Components:**
  - Routes: `GET /api/v1/ipos`, `GET /api/v1/ipos/calendar`, `GET /api/v1/ipos/performance`, `GET /api/v1/ipos/{symbol}`
  - Service: `IPOService.get_all_ipos`, `IPOService.get_ipo_calendar`
  - Model: `IPO`
