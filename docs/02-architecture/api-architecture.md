# API Architecture

## API Style
RESTful JSON API with WebSocket support. All REST endpoints are versioned under `/api/v1/`.

## Versioning
- API prefix: `/api/v1`
- OpenAPI spec: `/api/v1/openapi.json`
- Swagger UI: `/docs`
- ReDoc: `/redoc`

## Router Structure

22 route modules organized across 14 functional modules, all registered in `app/main.py`.

| Router Module | Prefix | Auth Required | Tag |
|--------------|--------|---------------|-----|
| `auth.py` | `/api/v1/auth` | Partial | Auth |
| `users.py` | `/api/v1/users` | Yes | Users |
| `devices.py` | `/api/v1/devices` | Yes | Devices |
| `webhooks.py` | `/api/v1/webhooks` | Varies | Webhooks |
| `market.py` | `/api/v1/market` | No | Market |
| `stocks.py` | `/api/v1/stocks` | No | Stocks |
| `watchlist.py` | `/api/v1/watchlist` | Yes | Watchlist |
| `forecast.py` | `/api/v1/forecast` | Partial | Forecast |
| `recommendations.py` | `/api/v1/recommendations` | No | Recommendations |
| `portfolio.py` | `/api/v1/portfolio` | Yes | Portfolio |
| `risk.py` | `/api/v1/risk` | Yes | Risk |
| `sentiment.py` | `/api/v1/sentiment` | No | Sentiment |
| `news.py` | `/api/v1/news` | No | News |
| `events.py` | `/api/v1/events` | No | Events |
| `alerts.py` | `/api/v1/alerts` | Yes | Alerts |
| `notifications.py` | `/api/v1/notifications` | Yes | Notifications |
| `shariah.py` | `/api/v1/shariah` | No | Shariah |
| `community/` | `/api/v1/community` | Partial | Community |
| `assistant/chat.py` | `/api/v1/assistant` | Yes | Assistant |
| `ws.py` | `/api/v1/ws` | Optional | WebSockets |
| `etfs.py` | `/api/v1/etfs` | Partial (admin CRUD) | ETFs |
| `ipos.py` | `/api/v1/ipos` | Partial (admin CRUD) | IPOs |
| `admin/community.py` | `/api/v1/admin/community` | Admin | Admin Community |
| `health.py` | `/api/v1/health` | No | Health |
| `system.py` | `/api/v1/system` | No | System (hidden from Swagger) |

## Authentication Dependencies

Three FastAPI dependencies defined in `app/core/authorization.py`:

| Dependency | Purpose | Failure Behavior |
|-----------|---------|-----------------|
| `get_current_user` | Requires valid Bearer access token; returns `User` object | 401 Unauthorized |
| `get_optional_current_user` | Returns `User` or `None` (no error on missing token) | Returns None |
| `get_current_admin` | Requires `is_admin=True` on the user | 403 Forbidden |
| `require_roles(*roles)` | Factory for role-based access (user/admin) | 403 Forbidden |

## Service Layer Interaction

Routes inject services via FastAPI `Depends()`:

```python
def _get_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)

@router.post("/auth/login")
async def login(data: LoginRequest, service: AuthService = Depends(_get_service)):
    return await service.login(email=data.email, password=data.password)
```

## Schema Validation

All request/response models use Pydantic v2 schemas from `app/schemas/`:
- `auth.py` — Login, signup, token, password reset schemas
- `stock.py` — Stock detail, search, OHLCV schemas
- `portfolio.py` — Transaction, holdings, P&L schemas
- `community.py` — Post, comment, follow, report schemas
- `market.py` — Market summary, quotes schemas
- `news.py` — News article, filter schemas
- `watchlist.py` — Watchlist, item schemas
- `assistant.py` — Chat message, conversation schemas
- `etf.py` — ETF listing schemas
- `ipo.py` — IPO listing schemas
- `shariah.py` — Shariah screening schemas

## Error Response Format

### Standard Errors (AppError subclasses)
```json
{
  "success": false,
  "error": {
    "code": "NOT_FOUND",
    "message": "Resource not found"
  }
}
```

### Community Errors (CommunityError)
```json
{
  "error": "COMMUNITY_ERROR",
  "message": "Community request failed",
  "field": "content"
}
```

### Unhandled Exceptions
```json
{
  "success": false,
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "An unexpected error occurred"
  }
}
```

## Rate Limiting

SlowAPI middleware with per-user-ID (authenticated) or per-IP (anonymous) key extraction.

| Endpoint Category | Limit |
|------------------|-------|
| Signup | 5/minute |
| Login | 5/minute |
| Token Refresh | 10/minute |
| Email Verification | 10/minute |
| Resend Verification | 3/minute |
| Forgot Password | 3/minute |
| Reset Password | 3/minute |
| Change Password | 5/minute |
| Google/Apple OAuth | 15/minute |

Nginx adds: 20 requests/second with burst 50, 20 concurrent connections per IP.

## Status Code Strategy

| Code | Usage |
|------|-------|
| 200 | Successful read/update operation |
| 201 | Resource created (signup) |
| 204 | No content (logout) |
| 400 | Bad request / validation error |
| 401 | Missing or invalid authentication |
| 403 | Insufficient permissions |
| 404 | Resource not found |
| 409 | Conflict (duplicate resource) |
| 422 | Validation failed |
| 429 | Rate limit exceeded |
| 500 | Internal server error |
| 503 | Service unavailable |

## Content Type

All endpoints accept and return `application/json`. Community post creation supports `multipart/form-data` for image uploads.

## Pagination

Cursor-based and offset pagination used across different endpoints (community posts, news, notifications). Query parameters: `cursor`, `limit`, `offset`.
