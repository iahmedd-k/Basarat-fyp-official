# Testing Strategy

## Testing Levels

| Level | Location | Count | Purpose |
|-------|----------|-------|---------|
| **Unit Tests** | `tests/unit/` | 15 files | Isolated component testing |
| **API Tests** | `tests/api/` | 17 files | Endpoint behavior testing |
| **E2E Tests** | `tests/e2e/` + root | 20+ files | Full flow and live system tests |
| **Integration Tests** | `tests/integration/` | Directory exists | Service integration testing |
| **Performance Tests** | `tests/performance/` | Directory exists | Load and performance testing |
| **Security Tests** | `tests/security/` | Directory exists | Security-focused testing |

## Test Framework

- **Framework**: pytest with `asyncio_mode = auto`
- **Markers**: `unit`, `integration`, `api`, `e2e`, `performance`, `security`, `slow`, `regression`
- **Configuration**: `pytest.ini` with strict markers and short tracebacks

## Key Unit Tests

| Test File | Covers |
|-----------|--------|
| `test_authorization.py` | Auth dependencies, token validation |
| `test_security.py` | Password hashing, JWT creation/decoding |
| `test_exceptions.py` | Custom exception hierarchy |
| `test_settings_production.py` | Production config validation |
| `test_schemas.py` | Pydantic schema validation |
| `test_assistant_safety.py` | AI assistant safety guardrails |
| `test_recommendation_engine.py` | Recommendation scoring logic |
| `test_ml_fixes.py` | ML inference edge cases |

## Key API Tests

| Test File | Covers |
|-----------|--------|
| `test_auth_api.py` | Signup, login, refresh, password flows |
| `test_portfolio_api.py` | Portfolio CRUD operations |
| `test_watchlist_api.py` | Watchlist CRUD operations |
| `test_market_api.py` | Market data endpoints |
| `test_stocks_api.py` | Stock detail endpoints |
| `test_sentiment_api.py` | Sentiment analysis endpoints |
| `test_shariah_api.py` | Shariah screening endpoints |
| `test_forecast_api.py` | Forecast endpoints |
| `test_recommendations_api.py` | Recommendation endpoints |

## Test Infrastructure

- **conftest.py** (18KB): Comprehensive fixtures including mock DB sessions, test users, mock services
- **CI Integration**: GitHub Actions runs `tests/api` and `tests/unit` on every push to main
- **Test environment**: `ENVIRONMENT=test`, `REDIS_ENABLED=false`, `USE_CELERY=false`

## Testing Gaps

1. **No code coverage reporting** — No pytest-cov or coverage tool configured
2. **Community module** — Limited API tests for community CRUD
3. **WebSocket tests** — `test_websockets_suite.py` exists at root level but not in CI path
4. **Alert evaluation** — Unit tests exist but integration with live data not tested in CI
5. **ML inference** — Unit tests for edge cases but no integration test with actual model
6. **Email delivery** — No tests for actual SendGrid integration
7. **Push notifications** — No tests for FCM delivery
