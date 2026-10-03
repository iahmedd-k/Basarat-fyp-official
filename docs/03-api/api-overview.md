# API Overview

## Base URL
- Development: `http://localhost:8000/api/v1`
- Production: `https://<ec2-host>:8000/api/v1` (behind Nginx)

## API Version
v1 (all endpoints under `/api/v1/`)

## Authentication Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/auth/signup` | No | Register with email/password |
| POST | `/auth/verify-email` | No | Verify email OTP |
| POST | `/auth/resend-verification` | No | Resend OTP |
| POST | `/auth/login` | No | Email/password login |
| POST | `/auth/google` | No | Google OAuth login |
| POST | `/auth/apple` | No | Apple OAuth login |
| POST | `/auth/refresh` | No | Refresh token rotation |
| POST | `/auth/logout` | No | Revoke refresh token |
| POST | `/auth/forgot-password` | No | Request password reset OTP |
| POST | `/auth/verify-reset-code` | No | Verify reset OTP |
| POST | `/auth/reset-password` | No | Set new password |
| POST | `/auth/change-password` | Yes | Change password (authenticated) |

## User Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/users/me` | Yes | Get current user profile |
| PUT | `/users/me` | Yes | Update profile |
| PUT | `/users/me/risk-profile` | Yes | Update risk profile |

## Market Data Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/market/summary` | No | PSX market summary |
| GET | `/market/indices` | No | Index values |
| GET | `/market/gainers` | No | Top gainers |
| GET | `/market/losers` | No | Top losers |
| GET | `/market/active` | No | Most active |
| GET | `/market/quotes` | No | Cached quote snapshot (REST fallback) |
| GET | `/market/live` | No | Live market discovery (WS/REST) |

## Stock Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/stocks/search` | No | Search stocks |
| GET | `/stocks/{symbol}` | No | Stock detail |
| GET | `/stocks/{symbol}/ohlcv` | No | Historical OHLCV |

## Portfolio Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/portfolio` | Yes | Portfolio summary |
| POST | `/portfolio/transactions` | Yes | Add transaction |
| GET | `/portfolio/transactions` | Yes | List transactions |
| DELETE | `/portfolio/transactions/{id}` | Yes | Delete transaction |

## Watchlist Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/watchlist` | Yes | List watchlists |
| POST | `/watchlist` | Yes | Create watchlist |
| PUT | `/watchlist/{id}` | Yes | Update watchlist |
| DELETE | `/watchlist/{id}` | Yes | Delete watchlist |
| POST | `/watchlist/{id}/items` | Yes | Add item |
| DELETE | `/watchlist/{id}/items/{symbol}` | Yes | Remove item |

## Forecast Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/forecast/{symbol}` | No | Get prediction for stock |
| GET | `/forecast/pipeline` | No | Pipeline schedule info |
| POST | `/forecast/predict` | Yes (Admin) | Trigger prediction |

## Community Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/community/posts` | Optional | List posts (feed) |
| POST | `/community/posts` | Yes | Create post |
| GET | `/community/posts/{id}` | Optional | Get post detail |
| DELETE | `/community/posts/{id}` | Yes (Owner) | Delete post |
| POST | `/community/posts/{id}/like` | Yes | Like/unlike post |
| POST | `/community/posts/{id}/report` | Yes | Report post |
| GET | `/community/posts/{id}/comments` | Optional | List comments |
| POST | `/community/posts/{id}/comments` | Yes | Add comment |
| POST | `/community/follow/{user_id}` | Yes | Follow user |
| DELETE | `/community/follow/{user_id}` | Yes | Unfollow user |

## AI Assistant Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/assistant/conversations` | Yes | Create conversation |
| GET | `/assistant/conversations` | Yes | List conversations |
| POST | `/assistant/conversations/{id}/messages` | Yes | Send message |
| GET | `/assistant/conversations/{id}/messages` | Yes | Get messages |

## Health Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/health` | No | Liveness probe |
| GET | `/health/ready` | No | Readiness probe (DB, Redis, Celery) |

> **Note:** This is a representative subset. The full API has 100+ endpoints. Refer to the auto-generated Swagger UI at `/docs` for complete specification.
