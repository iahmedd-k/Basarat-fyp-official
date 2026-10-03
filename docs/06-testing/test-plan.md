# Test Plan

## Testing Objectives

1. Verify all API endpoints return correct responses for valid inputs
2. Verify authentication and authorization enforcement
3. Verify ownership-based access control
4. Verify error handling for invalid inputs and edge cases
5. Verify background task execution
6. Verify ML inference produces valid predictions

## Scope

- All REST API endpoints under `/api/v1/`
- Authentication and authorization flows
- Database CRUD operations via services
- Input validation via Pydantic schemas
- Error response format consistency
- Rate limiting behavior

## Test Environment

- Python 3.11.9
- `ENVIRONMENT=test`
- `REDIS_ENABLED=false` (in-memory fallback)
- `USE_CELERY=false` (in-process execution)
- Mock database sessions via conftest fixtures

## Existing Tests

| Module | Test File | Status |
|--------|-----------|--------|
| Auth | `tests/api/test_auth_api.py` | Exists |
| Portfolio | `tests/api/test_portfolio_api.py` | Exists |
| Watchlist | `tests/api/test_watchlist_api.py` | Exists |
| Market | `tests/api/test_market_api.py` | Exists |
| Stocks | `tests/api/test_stocks_api.py` | Exists |
| Forecast | `tests/api/test_forecast_api.py` | Exists |
| Sentiment | `tests/api/test_sentiment_api.py` | Exists |
| Shariah | `tests/api/test_shariah_api.py` | Exists |
| Risk | `tests/api/test_risk_api.py` | Exists |
| News | `tests/api/test_news_api.py` | Exists |
| Recommendations | `tests/api/test_recommendations_api.py` | Exists |
| Alerts | `tests/api/test_alerts_api.py` | Exists |
| Users | `tests/api/test_users_api.py` | Exists |
| System | `tests/api/test_system_api.py` | Exists |
| Clerk Webhook | `tests/api/test_clerk_webhook.py` | Exists |

## Required Tests (Not Yet Identified in CI)

| Module | Test Area | Priority |
|--------|-----------|----------|
| Community | Post CRUD, comments, follows | High |
| Community | Moderation actions | High |
| Assistant | Chat conversation flow | Medium |
| ETFs | CRUD operations | Medium |
| IPOs | CRUD operations | Medium |
| Devices | FCM token registration | Low |
| WebSocket | Connection and subscription | Medium |

## Recommended Tests

| Area | Description | Priority |
|------|-------------|----------|
| Security | SQL injection patterns | High |
| Security | JWT manipulation | High |
| Performance | Concurrent request handling | Medium |
| Integration | ML model loading and inference | Medium |
| Integration | SendGrid email delivery (mock) | Low |
| Integration | Cloudinary upload (mock) | Low |
