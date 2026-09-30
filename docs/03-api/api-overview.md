# API Overview & Endpoint Directory — Basarat

## 1. Overview & Base Endpoints

- **Base API URL:** `http://localhost:8000/api/v1` (Development) / `https://api.basarat.pk/api/v1` (Production)
- **OpenAPI Schema:** `GET /api/v1/openapi.json`
- **Interactive Swagger UI:** `GET /docs`
- **Interactive ReDoc UI:** `GET /redoc`
- **Total Endpoints:** 169 Documented HTTP Operations across 146 OpenAPI paths, plus 4 WebSocket paths.

---

## 2. Endpoint Summary Matrix by Module

### 2.1 Module 1: Authentication & Identity (`/auth`)

| Method | Path | Access | Purpose |
|---|---|---|---|
| `POST` | `/api/v1/auth/signup` | Public | Register new user account; sends 6-digit email OTP (anti-enumeration). |
| `POST` | `/api/v1/auth/verify-email` | Public | Verify 6-digit email OTP; activates account and returns JWT token pair. |
| `POST` | `/api/v1/auth/resend-verification` | Public | Resend email verification 6-digit OTP code. |
| `POST` | `/api/v1/auth/login` | Public | Authenticate with email & password; returns access & refresh tokens. |
| `POST` | `/api/v1/auth/refresh` | Public | Rotate refresh token and issue new access token. |
| `POST` | `/api/v1/auth/logout` | Public / Bearer | Revoke refresh token and invalidate active sessions. |
| `POST` | `/api/v1/auth/forgot-password` | Public | Step 1/3: Request 6-digit password reset OTP to email. |
| `POST` | `/api/v1/auth/verify-reset-code` | Public | Step 2/3: Verify 6-digit OTP; returns 15m `reset_token` JWT grant. |
| `POST` | `/api/v1/auth/reset-password` | Public | Step 3/3: Submit new password with `reset_token` grant; bumps `token_version`. |
| `POST` | `/api/v1/auth/change-password` | Authenticated | Change password for logged-in user with current password verification. |
| `POST` | `/api/v1/auth/google` | Public | Federated authentication via Google OAuth 2.0 ID token. |
| `POST` | `/api/v1/auth/apple` | Public | Federated authentication via Apple Sign-In ID token. |

---

### 2.2 Module 2: User Profiles & Devices (`/users`, `/devices`, `/webhooks`)

| Method | Path | Access | Purpose |
|---|---|---|---|
| `GET` | `/api/v1/users/me` | Authenticated | Get current user's profile and investment risk preferences. |
| `PATCH` | `/api/v1/users/me` | Authenticated | Update user profile, full name, avatar, and risk profile. |
| `POST` | `/api/v1/users/me` | Authenticated | Set user profile (alias for complete replacement). |
| `PATCH` | `/api/v1/users/me/notification-preferences` | Authenticated | Update notification channel toggles (email, push, alerts). |
| `GET` | `/api/v1/users/investment-profile/options` | Public | Get valid enum options for risk tolerance, horizons, and sectors. |
| `POST` | `/api/v1/devices/register` | Authenticated | Register mobile FCM device token for push notifications. |
| `DELETE` | `/api/v1/devices/{device_id}` | Authenticated | Deactivate and remove a registered mobile device. |
| `POST` | `/api/v1/webhooks/clerk` | Public | Webhook endpoint for Clerk authentication identity sync. |

---

### 2.3 Module 3: Market Discovery & Stocks (`/market`, `/stocks`, `/prices`)

| Method | Path | Access | Purpose |
|---|---|---|---|
| `GET` | `/api/v1/market/indices` | Public | Get summary of KSE-100, KSE-30, and KMI-30 indices. |
| `GET` | `/api/v1/market/indices/{index_name}` | Public | Get constituents and performance for a specific index. |
| `GET` | `/api/v1/market/gainers` | Public | Get top 10 gaining stocks in the current session. |
| `GET` | `/api/v1/market/losers` | Public | Get top 10 losing stocks in the current session. |
| `GET` | `/api/v1/market/volume-spikes` | Public | Get stocks with abnormal volume surges. |
| `GET` | `/api/v1/market/curated` | Public | Curated leaderboards (High Yield, Best 1Y, Value, Liquid). |
| `GET` | `/api/v1/market/quotes` | Public | Search, paginate, and filter ~500 PSX stock quotes from cache. |
| `GET` | `/api/v1/market/sectors/performance` | Public | Overall PSX sector-by-sector performance comparison. |
| `GET` | `/api/v1/market/sentiment-overview` | Public | Macro market-wide FinBERT sentiment aggregate. |
| `GET` | `/api/v1/market/live` | Public | Transport discovery endpoint for WebSockets and REST fallback. |
| `GET` | `/api/v1/stocks/search` | Public | Autocomplete search for PSX stocks by ticker or company name. |
| `GET` | `/api/v1/stocks/{symbol}/overview` | Public | Comprehensive stock snapshot with live quote, cap, and 52w range. |
| `GET` | `/api/v1/stocks/{symbol}/price-history` | Public | Daily historical OHLCV candlestick price history. |
| `GET` | `/api/v1/stocks/{symbol}/fundamentals` | Public | Financial ratios, P/E, EPS, ROE, debt ratios, and balance sheets. |
| `GET` | `/api/v1/stocks/{symbol}/technical-indicators` | Public | Calculated technical indicators (RSI, MACD, EMA, Bollinger). |
| `GET` | `/api/v1/stocks/{symbol}/news` | Public | Paginated news articles specifically tagged with the given stock. |
| `GET` | `/api/v1/prices/{symbol}` | Authenticated | Fast quote cache lookup (Redis TTL ~30s) for portfolio UI. |
| `POST` | `/api/v1/prices/bulk` | Authenticated | Batch live quote lookup for multiple symbols. |

---

### 2.4 Module 4: Watchlists (`/watchlists`)

| Method | Path | Access | Purpose |
|---|---|---|---|
| `GET` | `/api/v1/watchlists` | Authenticated | List all custom watchlists owned by the user. |
| `POST` | `/api/v1/watchlists` | Authenticated | Create a new custom watchlist. |
| `GET` | `/api/v1/watchlists/default` | Authenticated | Get default watchlist with live quotes and baseline price changes. |
| `POST` | `/api/v1/watchlists/toggle/{symbol}` | Authenticated | 1-Tap toggle (Add/Remove) of a stock in user's default watchlist. |
| `GET` | `/api/v1/watchlists/check/{symbol}` | Authenticated | Check if a stock symbol exists in any of user's watchlists. |
| `GET` | `/api/v1/watchlists/{id}` | Authenticated | Get specific watchlist by ID with live price enrichment. |
| `PATCH` | `/api/v1/watchlists/{id}` | Authenticated | Update watchlist metadata (name, description, default flag). |
| `DELETE` | `/api/v1/watchlists/{id}` | Authenticated | Delete a watchlist and all contained items. |
| `POST` | `/api/v1/watchlists/{id}/items` | Authenticated | Add a stock symbol to a specific watchlist with target price. |
| `DELETE` | `/api/v1/watchlists/{id}/items/{symbol}` | Authenticated | Remove a stock symbol from a watchlist. |
| `PATCH` | `/api/v1/watchlists/{id}/items/{symbol}` | Authenticated | Update target price or personal notes for a watchlist item. |

---

### 2.5 Module 5: Machine Learning Forecasting (`/forecast`)

| Method | Path | Access | Purpose |
|---|---|---|---|
| `GET` | `/api/v1/forecast/{symbol}` | Authenticated | Run Attention-BiGRU + XGBoost inference, apply gating, and persist. |
| `GET` | `/api/v1/forecast/{symbol}/history` | Authenticated | Get chronological forecast history with realized accuracy flags. |
| `GET` | `/api/v1/forecast/pipeline` | Authenticated | Get daily forecasting cron schedule and last run status. |

---

### 2.6 Module 6: Quantitative Recommendations (`/recommendations`)

| Method | Path | Access | Purpose |
|---|---|---|---|
| `GET` | `/api/v1/recommendations` | Authenticated | Get ranked stock recommendations (Strong Buy -> Strong Sell). |
| `GET` | `/api/v1/recommendations/{symbol}` | Authenticated | Get multi-factor breakdown and score analysis for a stock. |
| `GET` | `/api/v1/recommendations/{symbol}/target-stop` | Authenticated | Calculate dynamic ATR-based target price and stop loss. |
| `GET` | `/api/v1/recommendations/engine-weights` | Authenticated | Get active scoring factor weights for the current user. |
| `POST` | `/api/v1/recommendations/engine-weights` | Authenticated | Set custom weighting preferences across technical/fundamental/sentiment. |

---

### 2.7 Module 7: Portfolio Management & Risk Suite (`/portfolio`, `/risk`)

| Method | Path | Access | Purpose |
|---|---|---|---|
| `GET` | `/api/v1/portfolio` | Authenticated | Complete portfolio overview with summary, holdings, and allocation. |
| `GET` | `/api/v1/portfolio/summary` | Authenticated | Live portfolio valuation, invested capital, and total P&L. |
| `GET` | `/api/v1/portfolio/holdings` | Authenticated | List active stock holdings with Average Cost Basis and quantities. |
| `GET` | `/api/v1/portfolio/holdings/{symbol}` | Authenticated | Detailed single holding performance and transaction breakdown. |
| `GET` | `/api/v1/portfolio/allocation` | Authenticated | Stock and sector percentage concentration breakdown. |
| `GET` | `/api/v1/portfolio/pnl` | Authenticated | Realized and unrealized profit and loss analytics. |
| `GET` | `/api/v1/portfolio/performance` | Authenticated | Time-series historical portfolio valuation trajectory. |
| `GET` | `/api/v1/portfolio/transactions` | Authenticated | Paginated transaction ledger with date/symbol filters. |
| `POST` | `/api/v1/portfolio/transactions` | Authenticated | Record a new BUY or SELL transaction. |
| `POST` | `/api/v1/portfolio/transactions/completed-trade` | Authenticated | Record an atomic historical round-trip trade (BUY + SELL). |
| `GET` | `/api/v1/portfolio/transactions/{id}` | Authenticated | Get a single transaction by ID. |
| `PATCH` | `/api/v1/portfolio/transactions/{id}` | Authenticated | Update a transaction with full ledger re-validation. |
| `DELETE` | `/api/v1/portfolio/transactions/{id}` | Authenticated | Delete a transaction and recalculate holdings. |
| `GET` | `/api/v1/risk/var` | Authenticated | Calculate Historical & Parametric Value-at-Risk (95/99%) and CVaR. |
| `POST` | `/api/v1/risk/monte-carlo` | Authenticated | Start async 10,000-path Monte Carlo GBM simulation (Returns `task_id`). |
| `GET` | `/api/v1/risk/monte-carlo/{task_id}` | Authenticated | Poll Monte Carlo simulation status and percentiles. |
| `GET` | `/api/v1/risk/stress-test` | Authenticated | Run macroeconomic stress test scenarios (Interest rates, crashes). |

---

### 2.8 Module 8: Shariah Screening (`/shariah`)

| Method | Path | Access | Purpose |
|---|---|---|---|
| `GET` | `/api/v1/shariah/{symbol}` | Public | Get overall AAOIFI & KMI-30 compliance status for a stock. |
| `GET` | `/api/v1/shariah/{symbol}/criteria` | Public | Detailed financial ratio breakdown (Debt, Illiquid, Non-compliant income). |
| `GET` | `/api/v1/shariah/{symbol}/purification` | Public | Calculate exact dividend purification deduction per share. |
| `GET` | `/api/v1/shariah/kmi30` | Public | Get list of all KMI-30 Shariah-compliant index constituents. |

---

### 2.9 Module 9: News & Sentiment (`/news`, `/sentiment`, `/events`)

| Method | Path | Access | Purpose |
|---|---|---|---|
| `GET` | `/api/v1/news` | Authenticated | Paginated financial news feed with cursor/timestamp filtering. |
| `GET` | `/api/v1/news/{article_id}` | Public | Get full single news article details and tagged symbols. |
| `POST` | `/api/v1/news/refresh` | Authenticated | Trigger manual async news refresh (rate-limit cooldown protected). |
| `GET` | `/api/v1/news/refresh/status` | Public | Check status of an ongoing manual news refresh task. |
| `GET` | `/api/v1/news/market-status` | Public | Ingestion schedule status and current market session state. |
| `GET` | `/api/v1/news/sources` | Public | Operational health metrics of individual scraping sources. |
| `GET` | `/api/v1/sentiment/{symbol}` | Authenticated | Current FinBERT sentiment score and label for a stock. |
| `GET` | `/api/v1/sentiment/{symbol}/history` | Authenticated | Historical sentiment time-series for chart rendering. |
| `GET` | `/api/v1/sentiment/{symbol}/news` | Authenticated | Paginated news articles for a stock with individual sentiment scores. |
| `GET` | `/api/v1/sentiment/market-overview` | Authenticated | Aggregate market-wide financial sentiment overview. |
| `GET` | `/api/v1/events/calendar` | Authenticated | PSX corporate events calendar (AGMs, earnings, dividends). |

---

### 2.10 Module 10: AI Investment Assistant (`/assistant`)

| Method | Path | Access | Purpose |
|---|---|---|---|
| `POST` | `/api/v1/assistant/chat` | Authenticated | Send user query; returns standard JSON response with financial context. |
| `POST` | `/api/v1/assistant/chat/stream` | Authenticated | Stream AI response tokens in real-time via Server-Sent Events (SSE). |
| `GET` | `/api/v1/assistant/conversations` | Authenticated | List all active conversation threads for the current user. |
| `POST` | `/api/v1/assistant/conversations` | Authenticated | Create a new conversation thread. |
| `GET` | `/api/v1/assistant/conversations/{id}` | Authenticated | Get full message history for a conversation thread. |
| `PATCH` | `/api/v1/assistant/conversations/{id}` | Authenticated | Rename conversation thread title. |
| `DELETE` | `/api/v1/assistant/conversations/{id}` | Authenticated | Delete a conversation thread and all contained messages. |
| `POST` | `/api/v1/assistant/conversations/{id}/regenerate`| Authenticated | Regenerate the latest assistant response in a conversation. |
| `GET` | `/api/v1/assistant/quick-prompts` | Authenticated | Get suggested starter prompts based on user portfolio and market state. |

---

### 2.11 Module 11: Community & Moderation (`/community`, `/admin/community`)

| Method | Path | Access | Purpose |
|---|---|---|---|
| `GET` | `/api/v1/community/feed` | Authenticated | Get personalized community social feed. |
| `POST` | `/api/v1/community/posts` | Authenticated | Create a new community post (tagged to stock or general market). |
| `GET` | `/api/v1/community/posts/search` | Authenticated | Search community posts with multi-factor filters. |
| `GET` | `/api/v1/community/posts/market` | Authenticated | Get general market discussion posts. |
| `GET` | `/api/v1/community/posts/stock/{symbol}`| Authenticated | Get posts discussing a specific stock ticker. |
| `GET` | `/api/v1/community/posts/{id}` | Authenticated | Get a single post with author profile and metrics. |
| `PATCH` | `/api/v1/community/posts/{id}` | Authenticated | Update post content (author only). |
| `DELETE` | `/api/v1/community/posts/{id}` | Authenticated | Delete post (author only). |
| `POST` | `/api/v1/community/posts/{id}/like` | Authenticated | Like a post (optimistic counter). |
| `DELETE` | `/api/v1/community/posts/{id}/like` | Authenticated | Unlike a post. |
| `GET` | `/api/v1/community/posts/{id}/comments` | Authenticated | Get threaded comments on a post. |
| `POST` | `/api/v1/community/posts/{id}/comments` | Authenticated | Add a comment or reply to a post. |
| `DELETE` | `/api/v1/community/comments/{id}` | Authenticated | Delete a comment (author only). |
| `POST` | `/api/v1/community/posts/{id}/report` | Authenticated | Report a post for spam, abuse, or misleading content. |
| `POST` | `/api/v1/community/comments/{id}/report`| Authenticated | Report a comment for policy violations. |
| `GET` | `/api/v1/community/me` | Authenticated | Get current user's community profile. |
| `GET` | `/api/v1/community/me/posts` | Authenticated | Get all posts authored by the current user. |
| `GET` | `/api/v1/community/users/{id}` | Authenticated | Get public community profile of another user. |
| `GET` | `/api/v1/community/users/{id}/posts` | Authenticated | Get public posts of another user. |
| `POST` | `/api/v1/community/users/{id}/follow` | Authenticated | Follow another user. |
| `DELETE` | `/api/v1/community/users/{id}/follow` | Authenticated | Unfollow a user. |
| `GET` | `/api/v1/community/users/{id}/follow-status`| Authenticated | Check if current user is following target user. |
| `GET` | `/api/v1/community/users/{id}/followers`| Authenticated | List followers of a user. |
| `GET` | `/api/v1/community/users/{id}/following`| Authenticated | List users followed by target user. |
| `GET` | `/api/v1/community/notifications` | Authenticated | Get community social notifications (likes, replies, follows). |
| `POST` | `/api/v1/community/notifications/read-all`| Authenticated | Mark all community notifications as read. |
| `GET` | `/api/v1/admin/community/reports` | Admin | Review reported posts and comments queue. |
| `PATCH` | `/api/v1/admin/community/reports/{id}` | Admin | Dismiss or mark report as reviewed. |
| `POST` | `/api/v1/admin/community/posts/{id}/restore`| Admin | Restore an auto-hidden post. |
| `POST` | `/api/v1/admin/community/posts/{id}/remove` | Admin | Directly remove post and record moderation action. |
| `DELETE` | `/api/v1/admin/community/posts/{id}` | Admin | Hard delete a post (admin override). |
| `DELETE` | `/api/v1/admin/community/comments/{id}` | Admin | Hard delete a comment (admin override). |
| `GET` | `/api/v1/admin/community/moderation-actions`| Admin | Get audit log of all administrative moderation actions. |

---

### 2.12 Module 12: ETFs & IPOs (`/etfs`, `/ipos`)

| Method | Path | Access | Purpose |
|---|---|---|---|
| `GET` | `/api/v1/etfs` | Public | List all active PSX Exchange Traded Funds. |
| `GET` | `/api/v1/etfs/{symbol}` | Public | Get single ETF overview, NAV, and live quote. |
| `GET` | `/api/v1/etfs/{symbol}/history` | Public | Historical OHLCV performance of an ETF. |
| `GET` | `/api/v1/etfs/{symbol}/performance` | Public | Benchmark tracking comparison for an ETF. |
| `GET` | `/api/v1/ipos` | Public | List PSX Initial Public Offerings. |
| `GET` | `/api/v1/ipos/calendar` | Public | Get upcoming book building and subscription calendar. |
| `GET` | `/api/v1/ipos/performance` | Public | Post-listing percentage returns and issue performance. |
| `GET` | `/api/v1/ipos/{symbol}` | Public | Get comprehensive details for a specific IPO. |

---

### 2.13 Module 13: Alerts, Notifications & Health (`/alerts`, `/notifications`, `/health`, `/ws`)

| Method | Path | Access | Purpose |
|---|---|---|---|
| `GET` | `/api/v1/alerts` | Authenticated | Get user's triggered price and metric alert history. |
| `PATCH` | `/api/v1/alerts/read-all` | Authenticated | Mark all alerts as read. |
| `PATCH` | `/api/v1/alerts/{id}/read` | Authenticated | Mark single alert as read. |
| `GET` | `/api/v1/alerts/rules` | Authenticated | List all active alert trigger rules for current user. |
| `POST` | `/api/v1/alerts/rules` | Authenticated | Create a custom price/indicator alert rule. |
| `POST` | `/api/v1/alerts/quick-rule` | Authenticated | 1-Click price alert rule creation for a stock. |
| `GET` | `/api/v1/alerts/rules/check/{symbol}`| Authenticated | Check if active alert rules exist for a stock. |
| `PATCH` | `/api/v1/alerts/rules/{id}` | Authenticated | Update alert rule condition or threshold. |
| `DELETE` | `/api/v1/alerts/rules/{id}` | Authenticated | Delete an alert rule. |
| `DELETE` | `/api/v1/alerts/rules/stock/{symbol}`| Authenticated | Delete all alert rules associated with a stock symbol. |
| `GET` | `/api/v1/notifications` | Authenticated | In-app notification inbox. |
| `PATCH` | `/api/v1/notifications/read-all` | Authenticated | Mark all notifications as read. |
| `PATCH` | `/api/v1/notifications/{id}/read`| Authenticated | Mark single notification as read. |
| `GET` | `/api/v1/health` | Public | Detailed health check (PostgreSQL, Redis, Celery). |
| `GET` | `/api/v1/health/ready` | Public | Readiness probe for container ingress. |
| `GET` | `/api/v1/ws/protocol` | Public | Protocol specification for WebSocket and REST fallback clients. |
| `GET` | `/api/v1/ws/stats` | Public | Real-time WebSocket connection and active subscription metrics. |
| `WSS` | `/api/v1/ws/market` | Public / WS | Real-time PSX live quote subscription stream. |
| `WSS` | `/api/v1/ws/alerts` | Public / WS | Personalized real-time user alert notification stream. |
