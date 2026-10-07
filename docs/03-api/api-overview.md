# API Overview

## Base URL
- **Local Development**: `http://localhost:8000/api/v1`
- **Production (Oracle Cloud VM)**: `http://193.123.84.223:8000/api/v1`
- **Interactive Swagger Docs**: `http://193.123.84.223:8000/docs`
- **ReDoc Specification**: `http://193.123.84.223:8000/redoc`

## API Version
`v1` (all API resources versioned under `/api/v1/`, with root liveness probe at `/health`).

---

## 1. Authentication Endpoints (`/api/v1/auth`)

| Method | Path | Auth Required | Purpose |
| :--- | :--- | :---: | :--- |
| `POST` | `/auth/signup` | No | Register new user account with password rules |
| `POST` | `/auth/verify-email` | No | Verify email registration OTP code |
| `POST` | `/auth/resend-verification` | No | Resend email registration OTP |
| `POST` | `/auth/login` | No | Email/password login returning JWT access + refresh tokens |
| `POST` | `/auth/google` | No | Google OAuth identity login |
| `POST` | `/auth/apple` | No | Apple OAuth identity login |
| `POST` | `/auth/refresh` | No | Rotate JWT refresh token for new access token |
| `POST` | `/auth/logout` | No | Revoke active refresh token |
| `POST` | `/auth/forgot-password` | No | Request 6-digit password reset OTP email |
| `POST` | `/auth/verify-reset-code` | No | Validate password reset code |
| `POST` | `/auth/reset-password` | No | Set new account password with verified reset code |
| `POST` | `/auth/change-password` | Yes | Update password for authenticated user |

---

## 2. User Profile & Risk Management (`/api/v1/users`)

| Method | Path | Auth Required | Purpose |
| :--- | :--- | :---: | :--- |
| `GET` | `/users/me` | Yes | Get authenticated user profile details |
| `PATCH` | `/users/me` | Yes | Partially update profile (full name, phone, bio, preferences) |
| `GET` | `/users/me/risk-profile` | Yes | Get current user's risk tolerance, horizon, and sectors |
| `PATCH` | `/users/me/risk-profile` | Yes | Update investment risk profile and target horizons |
| `GET` | `/users/risk-profile/options` | No | Get available risk tolerance levels and horizons |

---

## 3. Market Data & Indices (`/api/v1/market`)

| Method | Path | Auth Required | Purpose |
| :--- | :--- | :---: | :--- |
| `GET` | `/market/live` | No | Live market discovery & connection transport status |
| `GET` | `/market/indices` | No | Overview of benchmark indices (KSE-100, KSE-30, KMI-30, ALLSHR) |
| `GET` | `/market/indices/{code}` | No | Index constituents breakdown (e.g. `kse-100`, `kse-30`, `kmi-30`) |
| `GET` | `/market/quotes` | No | Paginated, searchable live PSX stock quotes snapshot |
| `GET` | `/market/gainers` | No | Top price gainers sorted by % change |
| `GET` | `/market/losers` | No | Top price losers sorted by % change |
| `GET` | `/market/volume-spikes` | No | Unusually high volume activity leaders |
| `GET` | `/market/sectors` | No | Sector-wide performance overview and aggregate volume |
| `GET` | `/market/sentiment-overview` | No | Market mood, advance/decline ratio, and top movers |
| `GET` | `/market/curated` | No | Curated investment baskets (Dividend Leaders, Growth, Value) |

---

## 4. Stocks, Technicals & Fundamentals (`/api/v1/stocks`)

| Method | Path | Auth Required | Purpose |
| :--- | :--- | :---: | :--- |
| `GET` | `/stocks/search?q={query}` | No | Fast search by ticker symbol or company name |
| `GET` | `/stocks/popular` | No | Most popular / high-activity PSX tickers |
| `GET` | `/stocks/screener` | No | Multi-parameter stock screener (P/E, market cap, dividend, sector) |
| `GET` | `/stocks/{symbol}/overview` | No | Complete stock snapshot (price, volume, change, 52W range) |
| `GET` | `/stocks/{symbol}/price-history` | No | Daily OHLCV price series (1D, 1W, 1M, 1Y) |
| `GET` | `/stocks/{symbol}/technical-indicators` | No | Calculated indicators (RSI, MACD, BB, SMA, ADX) with signal summary |
| `GET` | `/stocks/{symbol}/fundamentals` | No | Full company profile, ratios, financials, trading limits & sector peers |

---

## 5. Shariah Screening Engine (`/api/v1/shariah`)

| Method | Path | Auth Required | Purpose |
| :--- | :--- | :---: | :--- |
| `GET` | `/shariah/stocks` | No | List all verified Shariah-compliant PSX equities |
| `GET` | `/shariah/search?q={query}` | No | Search within Shariah-compliant equities |
| `GET` | `/shariah/status/{symbol}` | No | Detailed Shariah compliance status and criteria badge |
| `GET` | `/shariah/metrics/{symbol}` | No | Quantitative KMI financial ratios (debt/equity, illiquid assets, income) |
| `GET` | `/shariah/screen` | No | Interactive Shariah compliance screening parameter test |
| `GET` | `/shariah/summary` | No | Overall Shariah market statistics and compliance breakdown |

---

## 6. ML Forecasts & Quantitative Recommendations (`/api/v1/recommendations`, `/api/v1/forecast`)

| Method | Path | Auth Required | Purpose |
| :--- | :--- | :---: | :--- |
| `GET` | `/recommendations/{symbol}` | No | Multi-signal recommendation (ML + Technical + Fundamental + Sentiment) |
| `GET` | `/recommendations/{symbol}/target-stop` | No | ATR-based target price, stop loss, and risk-reward calculation |
| `GET` | `/recommendations/top-picks` | No | Top ranked buy/sell recommendations across PSX universe |
| `GET` | `/recommendations/engine-weights` | No | Default and configured signal engine weights |
| `POST` | `/recommendations/engine-weights` | Yes | Customize user-specific recommendation weighting |
| `GET` | `/forecast/{symbol}` | No | Versioned, normalized multi-horizon response from BiGRU + XGBoost forecasts and persisted PSX market data (1D, 1W, 2W, 1M) |

---

## 7. News & Sentiment Analysis (`/api/v1/news`, `/api/v1/sentiment`)

| Method | Path | Auth Required | Purpose |
| :--- | :--- | :---: | :--- |
| `GET` | `/news` | No | Real-time PSX financial news with sentiment labels |
| `GET` | `/news/{id}` | No | Get individual news article details |
| `GET` | `/sentiment/market-overview` | No | Market-wide aggregate sentiment score and mood |
| `GET` | `/sentiment/{symbol}` | No | Stock-specific FinBERT sentiment breakdown |
| `GET` | `/sentiment/{symbol}/history` | No | Historical sentiment trend over time |
| `GET` | `/sentiment/{symbol}/news` | No | Recent news articles specifically tagged for symbol |

---

## 8. Risk Analytics (`/api/v1/risk`)

| Method | Path | Auth Required | Purpose |
| :--- | :--- | :---: | :--- |
| `GET` | `/risk/var` | Yes | Portfolio Value at Risk (Parametric & Historical VaR, CVaR) |
| `GET` | `/risk/stress-test` | Yes | Stress-testing simulations against historical crises (2008, COVID, FX) |

---

## 9. Watchlists Management (`/api/v1/watchlists`)

| Method | Path | Auth Required | Purpose |
| :--- | :--- | :---: | :--- |
| `GET` | `/watchlists` | Yes | List all watchlists created by authenticated user |
| `POST` | `/watchlists` | Yes | Create a new custom watchlist |
| `GET` | `/watchlists/default` | Yes | Get user's primary default watchlist |
| `GET` | `/watchlists/{id}` | Yes | Get watchlist details with live quote prices |
| `PATCH` | `/watchlists/{id}` | Yes | Update watchlist title, description, or default status |
| `DELETE` | `/watchlists/{id}` | Yes | Delete watchlist |
| `POST` | `/watchlists/{id}/items` | Yes | Add stock symbol with optional target alert price |
| `DELETE` | `/watchlists/{id}/items/{symbol}` | Yes | Remove stock symbol from watchlist |
| `GET` | `/watchlists/check/{symbol}` | Yes | Quick check if symbol exists across user watchlists |

---

## 10. Portfolio Tracking & Analytics (`/api/v1/portfolio`)

| Method | Path | Auth Required | Purpose |
| :--- | :--- | :---: | :--- |
| `GET` | `/portfolio` | Yes | Complete portfolio summary (Total Value, Cost, Unrealized P&L) |
| `GET` | `/portfolio/holdings` | Yes | Individual stock holdings with weights, cost basis, and current price |
| `GET` | `/portfolio/pnl` | Yes | Realized and unrealized P&L breakdown |
| `GET` | `/portfolio/performance` | Yes | Historical portfolio equity curve (1W, 1M, 3M, 1Y) |
| `GET` | `/portfolio/allocation` | Yes | Asset & sector allocation distribution |
| `GET` | `/portfolio/transactions` | Yes | List all buy/sell transactions |
| `POST` | `/portfolio/transactions` | Yes | Record a buy/sell trade transaction |
| `DELETE` | `/portfolio/transactions/{id}` | Yes | Delete transaction and recalculate holdings |

---

## 11. Social Community (`/api/v1/community`)

| Method | Path | Auth Required | Purpose |
| :--- | :--- | :---: | :--- |
| `GET` | `/community/feed` | Yes | Public community trading feed |
| `POST` | `/community/posts` | Yes | Publish a stock idea or market insight post |
| `GET` | `/community/posts/search?q={query}` | Yes | Search community discussions by keyword or ticker |
| `GET` | `/community/posts/{id}` | Yes | Get post details and replies |
| `DELETE` | `/community/posts/{id}` | Yes | Delete user's own post |
| `POST` | `/community/posts/{id}/like` | Yes | Like or unlike a post |
| `POST` | `/community/posts/{id}/comments` | Yes | Add comment or reply to post |
| `DELETE` | `/community/comments/{id}` | Yes | Delete user's comment |
| `GET` | `/community/me` | Yes | User's social profile stats (posts count, followers, following) |

---

## 12. IPOs & ETFs (`/api/v1/ipos`, `/api/v1/etfs`)

| Method | Path | Auth Required | Purpose |
| :--- | :--- | :---: | :--- |
| `GET` | `/ipos` | No | All upcoming, active, and past PSX IPO listings |
| `GET` | `/ipos/calendar` | No | IPO timeline calendar and subscription dates |
| `GET` | `/ipos/performance` | No | Post-listing historical price performance |
| `GET` | `/etfs` | No | Exchange Traded Funds listings, prices, and expense ratios |

---

## 13. Alerts & Push Notifications (`/api/v1/alerts`, `/api/v1/notifications`)

| Method | Path | Auth Required | Purpose |
| :--- | :--- | :---: | :--- |
| `GET` | `/alerts/rules` | Yes | List user's active price alert rules |
| `POST` | `/alerts/rules` | Yes | Create custom condition alert (price above/below, % move) |
| `POST` | `/alerts/quick-rule` | Yes | One-tap quick price target alert |
| `DELETE` | `/alerts/rules/{id}` | Yes | Delete alert rule |
| `DELETE` | `/alerts/rules/stock/{symbol}` | Yes | Delete all alerts for a stock symbol |
| `GET` | `/notifications` | Yes | User notification inbox |
| `PATCH` | `/notifications/{id}/read` | Yes | Mark notification as read |
| `POST` | `/devices/register` | Yes | Register FCM token for mobile push notifications |

---

## 14. Stock AI Assistant (`/api/v1/assistant`)

| Method | Path | Auth Required | Purpose |
| :--- | :--- | :---: | :--- |
| `POST` | `/assistant/chat` | Yes | Standard REST synchronous chat message |
| `POST` | `/assistant/chat/stream` | Yes | High-performance Server-Sent Events (SSE) live streaming response |
| `GET` | `/assistant/quick-prompts` | Yes | Starter prompt chips for conversational onboarding |
| `GET` | `/assistant/conversations` | Yes | List user's chat conversation sessions |
| `GET` | `/assistant/conversations/{id}/messages` | Yes | Retrieve full message history of a conversation |
| `DELETE` | `/assistant/conversations/{id}` | Yes | Delete conversation history |

---

## 15. WebSocket & System Health (`/api/v1/ws`, `/health`)

| Method | Path | Auth Required | Purpose |
| :--- | :--- | :---: | :--- |
| `WS` | `/api/v1/ws` | No | Real-time WebSocket stream for live ticker quotes & alerts |
| `GET` | `/health` | No | Liveness probe returning `{"status": "ok"}` |
| `GET` | `/api/v1/health/ready` | No | Readiness probe verifying DB, Redis, Celery Worker, Beat, and ML models |
