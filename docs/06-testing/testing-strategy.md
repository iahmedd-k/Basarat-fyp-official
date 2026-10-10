# Testing Strategy

Basarat uses a multi-tiered test suite ensuring full code correctness, strict schema validation, security barriers, and live deployment verification.

---

## 1. Testing Levels & Architecture

| Level | Location | Test Scope | Status |
| :--- | :--- | :--- | :---: |
| **Unit Tests** | `backend/tests/unit/` | Core business logic, FinBERT NLP pipeline, Risk models, OHLCV parsing, Alert evaluation, Stock search aliases | **342/342 Passed (100.0%)** |
| **Security Tests** | `backend/tests/security/` | JWT token integrity, bcrypt hashing, tenant isolation, RBAC role checks, SQL injection & input sanitization | **20/20 Passed (100.0%)** |
| **API Integration Tests** | `backend/tests/api/` | All 25 domain routers, error contracts, edge-case date range validations, Pydantic type constraints | **265/265 Passed (100.0%)** |
| **Total Test Suite** | `backend/tests/` | Comprehensive test coverage across all subsystems | **627/627 Passed (100.0%)** |
| **Live Production Gateway** | `https://api.basarat.live` | Live Swagger OpenAPI schema verification and probe validation | **100% Operational** |

---

## 2. Test Execution Commands

```bash
# Run full backend test suite (Unit + Security + API)
pytest tests/ -v

# Run unit tests only
pytest tests/unit/ -v

# Run API integration tests only
pytest tests/api/ -v

# Run security & auth authorization test suite
pytest tests/security/ -v
```

---

## 3. Unit Test Suite Coverage Breakdown

| Unit Test Suite | Key Areas Tested |
| :--- | :--- |
| `test_authorization.py` | JWT token extraction, OAuth role checks, bearer parsing, invalid token handling |
| `test_security.py` | Bcrypt password hashing, JWT creation & decoding, token expiration, tampering checks |
| `test_schemas.py` | Pydantic v2 input validation, model sanitization, default transformations |
| `test_news_pipeline.py` | FinBERT NLP sentiment scoring, mock fallback on weights offline, batch normalization |
| `test_risk_service.py` | VaR, CVaR, zero-volatility safeguards, cold Redis quote fallback |
| `test_assistant_safety.py` | Prompt injection detection, regulatory advice guardrails, intent classification, output sanitization |
| `test_assistant_freshness.py` | Stale market data detection, hard-live request triggers, weekend calendar freshness |
| `test_market_service.py` | Market quote normalization, sector aggregation, top gainers/losers filtering |
| `test_stock_ohlcv.py` | 52-week OHLCV price parsing, duplicate date deduplication, technical indicator warmup |
| `test_stock_search.py` | Company name aliases, ticker search, fuzzy rank ordering |
| `test_alert_evaluation.py` | Price threshold triggers, cooldown timers, risk breach notifications, anti-flapping |
| `test_portfolio_calculation.py`| FIFO realized PnL, holdings calculation, cash balance tracking |
| `test_events_api.py` | Corporate events calendar, inverted date range protection (`from > to`) |
| `test_users_api.py` | Investment profile serialization, risk tolerance options, email change lifecycle |
| `test_exceptions.py` | AppError hierarchy, status code mapping, HTTP error responses |
| `test_recommendation_engine.py`| Multi-signal quantitative weighted scoring and target/stop boundary calculations |

---

## 4. Live Verification Audit Methodology

The live production deployment at `https://api.basarat.live` is continuously monitored for:
1. **HTTP Status Code**: Must return expected success code (`200 OK`, `201 Created`, or `204 No Content`).
2. **Response Time (Latency)**: Average API response latency stays under 150ms for cached routes.
3. **Unified Error Contract**: All failure cases consistently return `{"success": false, "error": {"code": ..., "message": ...}}`.
4. **Data Anomaly Verification**: Checks that numeric fields (prices, P/E, EPS, volumes, percentages) contain plausible positive/negative numbers rather than corrupted values.
5. **Dynamic CRUD Lifecycles**: Executes real Creation $\to$ Modification $\to$ Deletion lifecycles for Watchlists, Alerts, Portfolio Trades, and Community Posts with automatic post-test cleanup.
