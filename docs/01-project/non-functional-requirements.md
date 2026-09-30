# Non-Functional Requirements (NFR) Specification — Basarat

This document outlines the non-functional requirements (NFRs) of the Basarat system, comparing specified design objectives against the actual implementation evidence and existing limitations.

---

## 1. Security & Authentication NFRs

| NFR ID | Requirement Area | Specification & Objective | Current Implementation in Codebase | Evidence from Codebase | Gaps & Known Limitations |
|---|---|---|---|---|---|
| **NFR-SEC-01** | Password Hashing | All user passwords must be securely salted and hashed using cryptographic standards to prevent credential theft. | Salted `bcrypt` hashing with auto-generated salt per user. Plaintext passwords are never logged or stored. | `hash_password()` and `verify_password()` in [security.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/core/security.py#L12-L19). | Password complexity rules enforced in Pydantic schema; zxcvbn entropy scoring is not currently integrated. |
| **NFR-SEC-02** | Token Revocation | JWTs must support immediate global revocation upon logout or password reset without waiting for expiration. | Token versioning (`User.token_version`) embedded into JWT payload (`tv`). Revocation increments `token_version` in DB; middleware rejects mismatched tokens. | `get_current_user()` in [authorization.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/core/authorization.py#L26-L49). | Short-lived access tokens (30 min) require DB lookup per request to verify `token_version` (select by primary key). |
| **NFR-SEC-03** | Refresh Token Security | Refresh tokens must be rotated upon use, stored with unique UUIDs, and revocable per device session. | Refresh tokens stored in `refresh_tokens` table with unique `jti`, indexed by `(user_id, revoked)`. Rotated automatically on `POST /auth/refresh`. | `RefreshToken` model in [user.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/models/user.py#L50-L66) and [auth_service.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/services/auth_service.py). | Token reuse detection (invalidating family if revoked token used) is partially handled via unique constraint violation. |
| **NFR-SEC-04** | Role-Based Access Control | Administrative endpoints must restrict access exclusively to users with `is_admin=True`. | Route dependency `get_current_admin` and `require_roles("admin")` enforcing HTTP 403 `ForbiddenError`. | `get_current_admin` in [authorization.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/core/authorization.py#L83-L88). | Single administrative role exists; granular permission policies (e.g., Content Moderator vs Super Admin) are not separated. |
| **NFR-SEC-05** | Rate Limiting | Protect authentication and public APIs from brute force and denial of service. | In-memory / Redis sliding window rate limiter tracking client IP addresses. | `add_rate_limiting()` in [rate_limiter.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/core/rate_limiter.py). | Header `X-Forwarded-For` uses first value; multi-proxy setups require whitelisting via `TRUSTED_PROXY_IPS`. |
| **NFR-SEC-06** | CORS Isolation | Web origin access must be strictly restricted to trusted domains in production. | `main.py` enforces explicit origin list in `staging`/`production`, rejecting wildcard `*` at startup. | `main.py` lines 132–150 and `Settings` validator in [config.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/core/config.py). | None; properly validated in startup lifespan. |
| **NFR-SEC-07** | AI Prompt Injection & Guardrails | Prevent LLM jailbreaks, system prompt exfiltration, and non-financial misuse. | Regex and heuristic scanner classifying user intent, blocking system prompt overrides, and appending mandatory financial disclaimers. | `classify_intent`, `check_prompt_injection`, `enforce_output_safety` in [assistant_safety.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/services/assistant_safety.py). | Heuristic filter; advanced semantic vector embedding guardrails (e.g. NeMo Guardrails) are planned. |

---

## 2. Performance & Latency NFRs

| NFR ID | Requirement Area | Specification & Objective | Current Implementation in Codebase | Evidence from Codebase | Gaps & Known Limitations |
|---|---|---|---|---|---|
| **NFR-PERF-01** | REST API Latency | P95 latency < 200ms for cached market endpoints; < 500ms for database queries. | Redis caching (`CACHE_TTL_SECONDS=300`) with in-memory fallback; async database queries using `asyncpg`. | `redis_client.py` and `market_service.py` cache decorators. | Complex queries without Redis warm-up can exceed 300ms on cold startup. |
| **NFR-PERF-02** | ML Inference Speed | Directional inference per stock must execute in < 150ms. | Models (Attention-BiGRU + XGBoost) loaded in memory at startup as singletons; NumPy vectorized pre-processing. | `model_loader.py` and `inference.py` in [serving](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/ml/serving/inference.py). | First batch inference suffers minor JIT warmup overhead. |
| **NFR-PERF-03** | Real-Time Quote Fanout | WebSocket quote broadcasts must reach connected clients with < 250ms latency from ingestion. | Redis Pub/Sub listener (`market_live_bus.py`) listens on `market:quotes:live` and broadcasts directly to connected WebSocket connections. | `start_live_bus_listener()` in [market_live_bus.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/services/market_live_bus.py) and `lifespan` in [main.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/main.py). | High concurrency (> 5,000 active connections) on a single Uvicorn worker will require multi-worker / cluster deployment. |
| **NFR-PERF-04** | Asynchronous Simulation Latency | Monte Carlo simulations (10,000 paths) must not block HTTP server event loop. | Offloaded entirely to Celery background workers with client polling pattern (`POST /risk/monte-carlo` -> `task_id` -> `GET /risk/monte-carlo/{id}`). | `start_monte_carlo` in [risk_service.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/services/risk_service.py) and [risk_tasks.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/tasks/risk_tasks.py). | Polling frequency is client-controlled; SSE or WebSocket notification for task completion is recommended. |

---

## 3. Reliability & Availability NFRs

| NFR ID | Requirement Area | Specification & Objective | Current Implementation in Codebase | Evidence from Codebase | Gaps & Known Limitations |
|---|---|---|---|---|---|
| **NFR-REL-01** | Dependency Health Probing | System must expose health and readiness probes reporting status of DB, Redis, Celery worker, and Celery Beat. | Dual endpoints: `/api/v1/health` (liveness + detailed dependency checks) and `/api/v1/health/ready` (readiness). | `health.py` router in [health.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/api/v1/health.py) and `health_service.py`. | `/health` returns 200 even when sub-components are degraded (to prevent Docker crash loops), while reporting component health JSON. |
| **NFR-REL-02** | Upstream Scraper Fault Tolerance | System must gracefully handle PSX rate limits, network timeouts, and portal outages. | 15-minute circuit breaker on HTTP 429/403, exponential backoff, and fallback to last known Redis quote snapshot. | `MARKET_CIRCUIT_BREAKER_SECONDS=900` in [config.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/core/config.py) and [market_service.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/services/market_service.py). | Extended upstream portal outages (> 24 hours) leave cached quotes frozen. |
| **NFR-REL-03** | Celery Worker Resilience | Async jobs must survive worker restarts and avoid message loss. | Late acknowledgment (`task_acks_late=True`), rejection on lost worker (`task_reject_on_worker_lost=True`), and worker prefetch multiplier of 1. | Celery configuration in [celery_app.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/celery_app.py#L37-L39). | Requires tasks to be strictly idempotent to handle redeliveries safely. |

---

## 4. Scalability & Portability NFRs

| NFR ID | Requirement Area | Specification & Objective | Current Implementation in Codebase | Evidence from Codebase | Gaps & Known Limitations |
|---|---|---|---|---|---|
| **NFR-SCAL-01** | Database Connection Pooling | PostgreSQL connections must be pooled and recycled to prevent connection exhaustion. | SQLAlchemy `AsyncEngine` configured with `asyncpg` pool settings, pre-ping connection validation, and explicit session lifecycle management. | `engine` in [base.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/db/base.py) and `get_db` dependency in [session.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/db/session.py). | Supabase transaction pooler requires statement caching disabled (`statement_cache_size=0`). |
| **NFR-SCAL-02** | Containerized Deployment | All backend services, workers, and schedulers must be deployable via immutable container images. | Dockerfile with multi-layer caching, Python 3.11-slim base, and separate compose setups for local dev and cloud production. | [Dockerfile](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/dockerfile), [docker-compose.yml](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/docker-compose.yml), and [docker-compose.production.yml](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/docker-compose.production.yml). | Production compose currently runs 1 API worker and 1 Celery worker on a single EC2 host. |

---

## 5. Observability & Maintainability NFRs

| NFR ID | Requirement Area | Specification & Objective | Current Implementation in Codebase | Evidence from Codebase | Gaps & Known Limitations |
|---|---|---|---|---|---|
| **NFR-OBS-01** | Centralized Logging | Unified log formatting with configurable log levels per environment. | Standard library `logging` configured via `setup_logging()`, logging Uvicorn, Celery, and custom service logs. | `setup_logging()` in [logging.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/core/logging.py). | Structured JSON logging with request correlation IDs (`X-Request-ID`) is recommended for distributed tracing. |
| **NFR-OBS-02** | Exception Handling | Unified error response schemas across the API. | Custom hierarchy `AppError` -> `BadRequestError`, `UnauthorizedError`, `ForbiddenError`, `NotFoundError`, `ConflictError`, `ValidationFailedError`, `ServiceUnavailableError`. | `register_error_handlers()` in [exceptions.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/core/exceptions.py). | Community module uses a dedicated `CommunityError` format (`{"error": CODE, "message": DETAIL}`). |
| **NFR-MAINT-01** | Schema Governance | Database migrations must be fully versioned and reproducible. | 17 Alembic migration versions covering initial schema through watchlists, sentiment, community, and token versioning. | [alembic/versions/](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/alembic/versions). | Migration heads were merged in `h8i9j0k1l2m3_merge_schema_heads.py` to maintain a single deterministic linear history. |

---

## 6. Data Governance & Privacy NFRs

| NFR ID | Requirement Area | Specification & Objective | Current Implementation in Codebase | Evidence from Codebase | Gaps & Known Limitations |
|---|---|---|---|---|---|
| **NFR-PRIV-01** | User PII Protection | User email addresses and profile details must not be exposed to unauthorized parties. | User profile queries restrict private fields (`email`, `hashed_password`, `token_version`, `notification_preferences`) to authenticated owner; public community profile exposes only `username`, `full_name`, `avatar_url`. | `UserResponse` vs `PublicUserProfile` in [community.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/schemas/community.py) and [users.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/api/v1/users.py). | Data retention policies and GDPR-style data export endpoints are not currently implemented. |
| **NFR-PRIV-02** | Anti-Enumeration | Authentication endpoints must not reveal whether an email address is registered. | Signup and password reset endpoints return identical generic response messages regardless of whether the submitted email exists in the database. | `AuthService.signup` and `AuthService.forgot_password` in [auth_service.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/services/auth_service.py#L56-L65). | Fully implemented and verified. |
