# API Endpoint Inventory — 2026-09-30

**Source of truth:** OpenAPI generated from `app.main:app` using the current working tree. This inventory covers every OpenAPI HTTP operation, plus hidden compatibility routes and WebSocket routes mounted by `app/main.py`. It records the implemented access assignment; it is not a statement that public routes must be changed to require login.

**Coverage:** 169 documented HTTP operations across 146 paths. WebSockets are listed separately because OpenAPI does not describe them. The routers also mount hidden compatibility routes listed below.

**Access legend:** Public = no Bearer dependency; Authenticated = HTTP Bearer required; Admin = Bearer plus route-level admin authorization. Query/body validation and rate limits are not repeated per row; see endpoint OpenAPI for those details.

## Complete HTTP operation matrix

| Method | Path | Access | Operation |
|---|---|---|---|
| `DELETE` | `/api/v1/admin/community/comments/{comment_id}` | Admin (Bearer; admin authorization) | Delete a comment (admin) |
| `GET` | `/api/v1/admin/community/moderation-actions` | Admin (Bearer; admin authorization) | Get moderation audit log |
| `DELETE` | `/api/v1/admin/community/posts/{post_id}` | Admin (Bearer; admin authorization) | Delete a post (admin) |
| `GET` | `/api/v1/admin/community/posts/{post_id}` | Admin (Bearer; admin authorization) | Get post for admin review |
| `POST` | `/api/v1/admin/community/posts/{post_id}/remove` | Admin (Bearer; admin authorization) | Directly remove a post (admin) |
| `POST` | `/api/v1/admin/community/posts/{post_id}/restore` | Admin (Bearer; admin authorization) | Restore a temporarily hidden post |
| `GET` | `/api/v1/admin/community/reports` | Admin (Bearer; admin authorization) | Get reports for admin review |
| `PATCH` | `/api/v1/admin/community/reports/{report_id}` | Admin (Bearer; admin authorization) | Update report status |
| `GET` | `/api/v1/alerts` | Authenticated (Bearer) | Get user's alerts |
| `POST` | `/api/v1/alerts/quick-rule` | Authenticated (Bearer) | 1-Click automatic price alert for a stock |
| `PATCH` | `/api/v1/alerts/read-all` | Authenticated (Bearer) | Mark all alerts as read |
| `GET` | `/api/v1/alerts/rules` | Authenticated (Bearer) | Get user's alert rules |
| `POST` | `/api/v1/alerts/rules` | Authenticated (Bearer) | Create a new alert rule |
| `GET` | `/api/v1/alerts/rules/check/{symbol}` | Authenticated (Bearer) | Check active alert rules for a specific stock |
| `DELETE` | `/api/v1/alerts/rules/stock/{symbol}` | Authenticated (Bearer) | Delete / disable all alert rules for a stock |
| `DELETE` | `/api/v1/alerts/rules/{rule_id}` | Authenticated (Bearer) | Delete an alert rule |
| `PATCH` | `/api/v1/alerts/rules/{rule_id}` | Authenticated (Bearer) | Update an alert rule |
| `PATCH` | `/api/v1/alerts/{alert_id}/read` | Authenticated (Bearer) | Mark an alert as read |
| `POST` | `/api/v1/assistant/chat` | Authenticated (Bearer) | Send a message to the AI assistant (Standard REST) |
| `POST` | `/api/v1/assistant/chat/stream` | Authenticated (Bearer) | Stream assistant response (Server-Sent Events) |
| `GET` | `/api/v1/assistant/conversations` | Authenticated (Bearer) | List user's conversations |
| `POST` | `/api/v1/assistant/conversations` | Authenticated (Bearer) | Create a new conversation |
| `DELETE` | `/api/v1/assistant/conversations/{conversation_id}` | Authenticated (Bearer) | Delete a conversation |
| `GET` | `/api/v1/assistant/conversations/{conversation_id}` | Authenticated (Bearer) | Get a conversation with messages |
| `PATCH` | `/api/v1/assistant/conversations/{conversation_id}` | Authenticated (Bearer) | Update conversation title |
| `POST` | `/api/v1/assistant/conversations/{conversation_id}/regenerate` | Authenticated (Bearer) | Regenerate the last assistant response |
| `GET` | `/api/v1/assistant/quick-prompts` | Authenticated (Bearer) | Suggested starter prompts for the assistant |
| `POST` | `/api/v1/auth/apple` | Public | Continue with Apple OAuth (iOS / macOS / Web) |
| `POST` | `/api/v1/auth/change-password` | Authenticated (Bearer) | Change password while logged in (Authenticated) |
| `POST` | `/api/v1/auth/forgot-password` | Public | Step 1 of 3: Request 6-digit password reset OTP |
| `POST` | `/api/v1/auth/google` | Public | Continue with Google OAuth (Mobile / Web) |
| `POST` | `/api/v1/auth/login` | Public | Authenticate user with email and password |
| `POST` | `/api/v1/auth/logout` | Public | Logout single session (Revoke refresh token) |
| `POST` | `/api/v1/auth/refresh` | Public | Refresh access token (With automatic token rotation) |
| `POST` | `/api/v1/auth/resend-verification` | Public | Resend email verification OTP code |
| `POST` | `/api/v1/auth/reset-password` | Public | Step 3 of 3: Set new password using reset_token grant |
| `POST` | `/api/v1/auth/signup` | Public | Register a new user account (Sends 6-digit OTP) |
| `POST` | `/api/v1/auth/verify-email` | Public | Verify email OTP & login (Returns JWT tokens) |
| `POST` | `/api/v1/auth/verify-reset-code` | Public | Step 2 of 3: Verify 6-digit OTP (Returns reset_token grant) |
| `DELETE` | `/api/v1/community/comments/{comment_id}` | Authenticated (Bearer) | Delete own comment |
| `POST` | `/api/v1/community/comments/{comment_id}/report` | Authenticated (Bearer) | Report a comment |
| `GET` | `/api/v1/community/feed` | Authenticated (Bearer) | Get community feed with optional keyword search and stock/market filtering |
| `GET` | `/api/v1/community/me` | Authenticated (Bearer) | Get current user's community profile |
| `GET` | `/api/v1/community/me/posts` | Authenticated (Bearer) | Get current user's posts |
| `GET` | `/api/v1/community/notifications` | Authenticated (Bearer) | Get community notifications |
| `POST` | `/api/v1/community/notifications/read-all` | Authenticated (Bearer) | Mark all notifications as read |
| `GET` | `/api/v1/community/notifications/unread-count` | Authenticated (Bearer) | Get unread notification count |
| `POST` | `/api/v1/community/notifications/{notification_id}/read` | Authenticated (Bearer) | Mark notification as read |
| `POST` | `/api/v1/community/posts` | Authenticated (Bearer) | Create a new community post |
| `GET` | `/api/v1/community/posts/market` | Authenticated (Bearer) | Get general market community posts |
| `GET` | `/api/v1/community/posts/search` | Authenticated (Bearer) | Search community posts with multi-factor filters |
| `GET` | `/api/v1/community/posts/stock/{symbol}` | Authenticated (Bearer) | Get all posts related to a specific stock symbol |
| `DELETE` | `/api/v1/community/posts/{post_id}` | Authenticated (Bearer) | Delete own post |
| `GET` | `/api/v1/community/posts/{post_id}` | Authenticated (Bearer) | Get a single post |
| `PATCH` | `/api/v1/community/posts/{post_id}` | Authenticated (Bearer) | Update own post |
| `GET` | `/api/v1/community/posts/{post_id}/comments` | Authenticated (Bearer) | Get comments for a post |
| `POST` | `/api/v1/community/posts/{post_id}/comments` | Authenticated (Bearer) | Create a comment on a post |
| `DELETE` | `/api/v1/community/posts/{post_id}/like` | Authenticated (Bearer) | Unlike a post |
| `POST` | `/api/v1/community/posts/{post_id}/like` | Authenticated (Bearer) | Like a post |
| `POST` | `/api/v1/community/posts/{post_id}/report` | Authenticated (Bearer) | Report a post |
| `GET` | `/api/v1/community/users/{user_id}` | Authenticated (Bearer) | Get another user's public community profile |
| `DELETE` | `/api/v1/community/users/{user_id}/follow` | Authenticated (Bearer) | Unfollow a user |
| `POST` | `/api/v1/community/users/{user_id}/follow` | Authenticated (Bearer) | Follow a user |
| `GET` | `/api/v1/community/users/{user_id}/follow-status` | Authenticated (Bearer) | Get follow status |
| `GET` | `/api/v1/community/users/{user_id}/followers` | Authenticated (Bearer) | Get user's followers |
| `GET` | `/api/v1/community/users/{user_id}/following` | Authenticated (Bearer) | Get users that user is following |
| `GET` | `/api/v1/community/users/{user_id}/posts` | Authenticated (Bearer) | Get another user's public posts |
| `POST` | `/api/v1/devices/register` | Authenticated (Bearer) | Register a device for push notifications |
| `DELETE` | `/api/v1/devices/{device_id}` | Authenticated (Bearer) | Deactivate a push notification device |
| `GET` | `/api/v1/etfs` | Public | List all active PSX ETFs (Public) |
| `GET` | `/api/v1/etfs/{symbol}` | Public | Get single ETF overview & live quote (Public) |
| `GET` | `/api/v1/etfs/{symbol}/history` | Public | Get ETF historical OHLCV prices (Public) |
| `GET` | `/api/v1/etfs/{symbol}/performance` | Public | Get ETF performance vs benchmark (Public) |
| `GET` | `/api/v1/events/calendar` | Authenticated (Bearer) | Get events calendar (earnings, dividends, SBP) |
| `GET` | `/api/v1/forecast/pipeline` | Authenticated (Bearer) | Forecast background job schedule (when predict + evaluate run) |
| `GET` | `/api/v1/forecast/{symbol}` | Authenticated (Bearer) | Predict bullish/bearish/sideways and save to history |
| `GET` | `/api/v1/forecast/{symbol}/history` | Authenticated (Bearer) | Get saved forecast history and real accuracy |
| `GET` | `/api/v1/health` | Public | Health Check |
| `GET` | `/api/v1/health/ready` | Public | Readiness Check |
| `GET` | `/api/v1/ipos` | Public | List PSX IPOs (Public) |
| `GET` | `/api/v1/ipos/calendar` | Public | Get PSX IPO calendar milestones (Public) |
| `GET` | `/api/v1/ipos/performance` | Public | Get IPO listing performance & returns (Public) |
| `GET` | `/api/v1/ipos/{symbol}` | Public | Get specific IPO details (Public) |
| `GET` | `/api/v1/market/all-stocks` | Public | Get all PSX listed stocks (~500 stocks) - alias (public) |
| `GET` | `/api/v1/market/curated` | Public | Get curated stock leaderboards (High Dividend Yield, Best Returning, Value, Liquid) |
| `GET` | `/api/v1/market/gainers` | Public | Get top gaining stocks |
| `GET` | `/api/v1/market/indices` | Public | Get main market indices |
| `GET` | `/api/v1/market/indices/kmi-30` | Public | Get KMI-30 index constituents (Shariah compliant) |
| `GET` | `/api/v1/market/indices/kse-100` | Public | Get KSE-100 index constituents |
| `GET` | `/api/v1/market/indices/kse-30` | Public | Get KSE-30 index constituents |
| `GET` | `/api/v1/market/live` | Public | Live market transport discovery (WebSocket primary + REST fallback) |
| `GET` | `/api/v1/market/losers` | Public | Get top losing stocks |
| `GET` | `/api/v1/market/quotes` | Public | Get all PSX listed stocks (~500 stocks) with manual count limit, search, and sector filters (public) |
| `GET` | `/api/v1/market/sectors/performance` | Public | Get overall PSX sector performance |
| `GET` | `/api/v1/market/sentiment-overview` | Public | Get market sentiment overview |
| `GET` | `/api/v1/market/volume-spikes` | Public | Get stocks with highest volume |
| `GET` | `/api/v1/news` | Authenticated (Bearer) | Get paginated news feed with cursor pagination |
| `GET` | `/api/v1/news/market-status` | Public | Get current market schedule and ingestion status |
| `POST` | `/api/v1/news/refresh` | Authenticated (Bearer) | Manually refresh news feed (async, cooldown-protected) |
| `GET` | `/api/v1/news/refresh/status` | Public | Get refresh job status for polling |
| `GET` | `/api/v1/news/sources` | Public | Get per-source health status (admin/ops) |
| `GET` | `/api/v1/news/{article_id}` | Public | Get a single news article |
| `GET` | `/api/v1/notifications` | Authenticated (Bearer) | Get user notifications |
| `PATCH` | `/api/v1/notifications/read-all` | Authenticated (Bearer) | Mark all notifications as read |
| `PATCH` | `/api/v1/notifications/{notification_id}/read` | Authenticated (Bearer) | Mark a notification as read |
| `GET` | `/api/v1/portfolio` | Authenticated (Bearer) | Get complete portfolio overview with summary and holdings |
| `GET` | `/api/v1/portfolio/allocation` | Authenticated (Bearer) | Get portfolio allocation by stock and sector |
| `GET` | `/api/v1/portfolio/holdings` | Authenticated (Bearer) | Get all active holdings |
| `GET` | `/api/v1/portfolio/holdings/{symbol}` | Authenticated (Bearer) | Get detailed view of a single holding |
| `GET` | `/api/v1/portfolio/performance` | Authenticated (Bearer) | Get portfolio performance over time |
| `GET` | `/api/v1/portfolio/pnl` | Authenticated (Bearer) | Get portfolio profit/loss breakdown |
| `GET` | `/api/v1/portfolio/summary` | Authenticated (Bearer) | Get portfolio summary with live valuations and P&L |
| `GET` | `/api/v1/portfolio/transactions` | Authenticated (Bearer) | Get paginated transaction history with optional filters |
| `POST` | `/api/v1/portfolio/transactions` | Authenticated (Bearer) | Create a new BUY or SELL transaction |
| `POST` | `/api/v1/portfolio/transactions/completed-trade` | Authenticated (Bearer) | Record a past completed trade (both BUY and SELL) in one atomic operation |
| `DELETE` | `/api/v1/portfolio/transactions/{transaction_id}` | Authenticated (Bearer) | Delete a transaction (with validation) |
| `GET` | `/api/v1/portfolio/transactions/{transaction_id}` | Authenticated (Bearer) | Get a single transaction by ID |
| `PATCH` | `/api/v1/portfolio/transactions/{transaction_id}` | Authenticated (Bearer) | Update a transaction (with full re-validation) |
| `PUT` | `/api/v1/portfolio/transactions/{transaction_id}` | Authenticated (Bearer) | Update a transaction (PUT alias of PATCH) |
| `POST` | `/api/v1/prices/bulk` | Authenticated (Bearer) | Get live prices for multiple symbols |
| `GET` | `/api/v1/prices/{symbol}` | Authenticated (Bearer) | Get live price for a symbol (Redis cache TTL ~30s) |
| `GET` | `/api/v1/recommendations` | Authenticated (Bearer) | Get stock recommendations |
| `GET` | `/api/v1/recommendations/engine-weights` | Authenticated (Bearer) | Get current or default engine weights |
| `POST` | `/api/v1/recommendations/engine-weights` | Authenticated (Bearer) | Set custom engine weights |
| `GET` | `/api/v1/recommendations/{symbol}` | Authenticated (Bearer) | Get detailed recommendation for a stock |
| `GET` | `/api/v1/recommendations/{symbol}/target-stop` | Authenticated (Bearer) | Get target price and stop loss |
| `POST` | `/api/v1/risk/monte-carlo` | Authenticated (Bearer) | Start async Monte Carlo simulation (GBM) |
| `GET` | `/api/v1/risk/monte-carlo/{task_id}` | Authenticated (Bearer) | Poll Monte Carlo simulation result |
| `GET` | `/api/v1/risk/stress-test` | Authenticated (Bearer) | Run stress test scenario on portfolio |
| `GET` | `/api/v1/risk/var` | Authenticated (Bearer) | Calculate portfolio Value at Risk and CVaR (Historical Simulation) |
| `GET` | `/api/v1/sentiment/market-overview` | Authenticated (Bearer) | Get overall market sentiment |
| `GET` | `/api/v1/sentiment/{symbol}` | Authenticated (Bearer) | Get sentiment analysis for a stock |
| `GET` | `/api/v1/sentiment/{symbol}/history` | Authenticated (Bearer) | Get historical sentiment time series for a stock |
| `GET` | `/api/v1/sentiment/{symbol}/news` | Authenticated (Bearer) | Get paginated news articles with sentiment for a stock |
| `GET` | `/api/v1/shariah/kmi30` | Public | Get KMI-30 Shariah compliant constituents |
| `GET` | `/api/v1/shariah/{symbol}` | Public | Get Shariah compliance screening for a stock |
| `GET` | `/api/v1/shariah/{symbol}/criteria` | Public | Get detailed Shariah screening criteria |
| `GET` | `/api/v1/shariah/{symbol}/purification` | Public | Calculate purification amount from dividend income |
| `GET` | `/api/v1/stocks/search` | Public | Autocomplete stock search |
| `GET` | `/api/v1/stocks/{symbol}/fundamentals` | Public | Company fundamentals |
| `GET` | `/api/v1/stocks/{symbol}/news` | Public | Get news for a specific stock (stock page News tab) |
| `GET` | `/api/v1/stocks/{symbol}/overview` | Public | Stock overview snapshot |
| `GET` | `/api/v1/stocks/{symbol}/price-history` | Public | Daily OHLCV price history |
| `GET` | `/api/v1/stocks/{symbol}/technical-indicators` | Public | Technical indicator series with overall signal summary |
| `GET` | `/api/v1/users/investment-profile/options` | Public | Get valid options for risk tolerance, investment horizon, and sector preferences |
| `GET` | `/api/v1/users/me` | Authenticated (Bearer) | Get current user profile & investment preferences |
| `PATCH` | `/api/v1/users/me` | Authenticated (Bearer) | Update current user profile and investment preferences |
| `POST` | `/api/v1/users/me` | Authenticated (Bearer) | Set current user profile and investment preferences |
| `PATCH` | `/api/v1/users/me/notification-preferences` | Authenticated (Bearer) | Update notification preferences |
| `GET` | `/api/v1/watchlists` | Authenticated (Bearer) | List all user watchlists |
| `POST` | `/api/v1/watchlists` | Authenticated (Bearer) | Create a new watchlist |
| `GET` | `/api/v1/watchlists/check/{symbol}` | Authenticated (Bearer) | Check if a stock symbol is in user's watchlists |
| `GET` | `/api/v1/watchlists/default` | Authenticated (Bearer) | Get user's default watchlist with live data & AI badges |
| `DELETE` | `/api/v1/watchlists/name/{name}` | Authenticated (Bearer) | Delete a watchlist (by name) |
| `GET` | `/api/v1/watchlists/name/{name}` | Authenticated (Bearer) | Get watchlist details with live stock quotes (by name) |
| `PATCH` | `/api/v1/watchlists/name/{name}` | Authenticated (Bearer) | Update watchlist metadata (by name) |
| `POST` | `/api/v1/watchlists/name/{name}/items` | Authenticated (Bearer) | Add a stock symbol to watchlist (by name) |
| `DELETE` | `/api/v1/watchlists/name/{name}/items/{symbol}` | Authenticated (Bearer) | Remove a stock symbol from watchlist (by name) |
| `PATCH` | `/api/v1/watchlists/name/{name}/items/{symbol}` | Authenticated (Bearer) | Update watchlist item target price or notes (by name) |
| `POST` | `/api/v1/watchlists/toggle/{symbol}` | Authenticated (Bearer) | 1-Tap Toggle stock in default watchlist (Add/Remove) |
| `DELETE` | `/api/v1/watchlists/{watchlist_id}` | Authenticated (Bearer) | Delete a watchlist (by ID) |
| `GET` | `/api/v1/watchlists/{watchlist_id}` | Authenticated (Bearer) | Get watchlist details with live stock quotes (by ID) |
| `PATCH` | `/api/v1/watchlists/{watchlist_id}` | Authenticated (Bearer) | Update watchlist metadata (by ID) |
| `POST` | `/api/v1/watchlists/{watchlist_id}/items` | Authenticated (Bearer) | Add a stock symbol to watchlist (by ID) |
| `DELETE` | `/api/v1/watchlists/{watchlist_id}/items/{symbol}` | Authenticated (Bearer) | Remove a stock symbol from watchlist (by ID) |
| `PATCH` | `/api/v1/watchlists/{watchlist_id}/items/{symbol}` | Authenticated (Bearer) | Update watchlist item target price or notes (by ID) |
| `POST` | `/api/v1/webhooks/clerk` | Public | Clerk Authentication Webhook |
| `GET` | `/api/v1/ws/protocol` | Public | WebSocket + REST fallback protocol (Android / Swagger) |
| `GET` | `/api/v1/ws/stats` | Public | Get real-time WebSocket connection and subscription metrics |

## WebSocket routes

The market WebSocket router is mounted both under the versioned API prefix and at the legacy root path:

| Transport | Path | Access assignment |
|---|---|---|
| WebSocket | `/api/v1/ws/market` | Public connection; application protocol handles subscriptions |
| WebSocket | `/ws/market` | Public legacy alias; application protocol handles subscriptions |
| WebSocket | `/api/v1/ws/alerts` | Public connection; JWT authentication is optional, and required for personalized alerts |
| WebSocket | `/ws/alerts` | Public legacy alias; JWT authentication is optional, and required for personalized alerts |

## Hidden HTTP compatibility routes

These routes are deliberately excluded from the OpenAPI schema and therefore do not appear in the operation matrix:

| Method | Path | Access | Disposition |
|---|---|---|---|
| `GET` | `/` | Public | Root service metadata |
| `GET` | `/api/v1/` | Public | Versioned root alias |
| `GET` | `/api/v1/ready` | Public | Deprecated readiness alias; use `/api/v1/health/ready` |
| `GET` | `/health` | Public | Unversioned health alias |
| `GET` | `/health/ready` | Public | Unversioned readiness alias |

## Access assignment corrections

The prior release assessment marked market, stock, and Shariah read routes as authenticated. The live implementation does not require a user token for these reads: the route signatures have no `get_current_user` dependency, their OpenAPI operations have no Bearer security requirement, and existing tests request representative market, stock, and Shariah data anonymously. They are therefore recorded as public, consistent with the public market-data design. This inventory corrects the assessment; it does not silently change the API contract.

The source contains additional endpoints omitted from the prior partial list, including signup verification and OAuth, investment-profile options, device deletion, watchlists, market discovery and quote routes, forecast pipeline status, completed-trade creation, alert shortcuts and read-all operations, community search/market views, assistant prompts/streaming, ETF/IPO catalogs and admin management, and WebSocket protocol/status endpoints. All documented HTTP operations appear in the matrix above.

## Verification limits

This is a route registration and declared security-assignment inventory generated from the imported FastAPI application. It confirms registration and the declared Bearer/admin dependencies; it does not establish database-backed runtime success, provider availability, rate-limit behavior, or authorization correctness for every handler. Those require integration checks against configured dependencies.
