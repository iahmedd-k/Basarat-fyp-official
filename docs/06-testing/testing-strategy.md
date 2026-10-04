# Testing Strategy

## 1. Testing Levels & Architecture

| Level | Location | Test Scope | Status |
| :--- | :--- | :--- | :---: |
| **Unit Tests** | `backend/tests/unit/` | 19 test files covering schemas, security, alert rules, assistant safety & freshness, ML models, OHLCV history, market service, exceptions | **199/199 Passed (100.0%)** |
| **API Tests** | `backend/tests/api/` | 17 test files covering router responses, status codes, auth flows, and request validation | **Configured & Validated** |
| **Live Production Audit** | `backend/scripts/run_live_oracle_comprehensive_audit.py` | 80 dynamic operations executed against live Oracle VM (`http://193.123.84.223:8000`) across all 15 operational domains | **80/80 Passed (100.0%)** |
| **Chatbot Streaming Audit** | `backend/scripts/test_live_chatbot_streaming.py` | Multi-turn conversational streaming validation over Server-Sent Events (`/assistant/chat/stream`) | **100% Validated** |

---

## 2. Test Execution Commands

```bash
# Run all unit tests
pytest tests/unit/

# Run specific domain test suites
pytest tests/unit/test_assistant_safety.py tests/unit/test_assistant_freshness.py
pytest tests/unit/test_market_service.py tests/unit/test_stock_ohlcv.py

# Run comprehensive live audit against Oracle Cloud deployment
python backend/scripts/run_live_oracle_comprehensive_audit.py

# Run live chatbot SSE streaming conversation test
python backend/scripts/test_live_chatbot_streaming.py
```

---

## 3. Unit Test Suite Coverage Breakdown

| Unit Test Suite | Key Areas Tested |
| :--- | :--- |
| `test_authorization.py` | JWT token extraction, OAuth role checks, bearer parsing, invalid token handling |
| `test_security.py` | Bcrypt password hashing, JWT creation & decoding, token expiration, tampering checks |
| `test_schemas.py` | Pydantic v2 input validation, model sanitization, default transformations |
| `test_assistant_safety.py` | Prompt injection detection, regulatory advice guardrails, intent classification, output sanitization |
| `test_assistant_freshness.py` | Stale market data detection, hard-live request triggers, weekend calendar freshness |
| `test_market_service.py` | Market quote normalization, sector aggregation, top gainers/losers filtering |
| `test_stock_ohlcv.py` | 52-week OHLCV price parsing, duplicate date deduplication, technical indicator warmup |
| `test_stock_search.py` | Company name aliases, ticker search, fuzzy matching |
| `test_alert_evaluation.py` | Price threshold triggers, cooldown timers, risk breach notifications, community pushes |
| `test_alert_rules_api.py` | Alert rule CRUD, stock resolution by ticker and company name |
| `test_settings_production.py` | Production database URL enforcement, CORS configuration, Redis/Celery URL verification |
| `test_exceptions.py` | AppError hierarchy, status code mapping, HTTP error responses |
| `test_ml_fixes.py` | Attention-BiGRU v2 + XGBoost v4 serving schema alignment, probability normalizations |
| `test_recommendation_engine.py` | Multi-signal quantitative weighted scoring and target/stop boundary calculations |

---

## 4. Live Verification Audit Methodology

The live audit suite executes end-to-end HTTP requests against the active deployment with administrative JWT authentication. For every endpoint, the auditor asserts:
1. **HTTP Status Code**: Must return expected success code (`200 OK`, `201 Created`, or `204 No Content`).
2. **Response Time (Latency)**: Records precise round-trip latency in milliseconds.
3. **Null Field Sanitization**: Verifies that no domain fields contain untracked `null` values.
4. **Data Anomaly Verification**: Checks that numeric fields (prices, P/E, EPS, volumes, percentages) contain plausible positive/negative numbers rather than corrupted values.
5. **Dynamic CRUD Lifecycles**: Executes real Creation $\to$ Modification $\to$ Deletion lifecycles for Watchlists, Alerts, Portfolio Trades, and Community Posts with automatic post-test cleanup.
