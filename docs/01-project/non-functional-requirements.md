# Non-Functional Requirements

## NFR-001 — Security: Password Storage

**Requirement:** All user passwords must be hashed before storage.
**Current Implementation:** bcrypt hashing via `app/core/security.py` → `hash_password()`.
**Evidence:** `bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())` in `security.py`.
**Gaps:** None identified.

## NFR-002 — Security: Token Expiry and Rotation

**Requirement:** Access tokens must have short expiry; refresh tokens must support rotation with revocation detection.
**Current Implementation:** Access tokens expire in 30 minutes; refresh tokens in 7 days. Refresh tokens are stored in DB, revoked on use, and reuse triggers full session invalidation.
**Evidence:** `ACCESS_TOKEN_EXPIRE_MINUTES=30`, `REFRESH_TOKEN_EXPIRE_DAYS=7` in `config.py`; `RefreshToken` model with `revoked` flag.
**Gaps:** No token blacklist for access tokens; they remain valid until expiry.

## NFR-003 — Security: Rate Limiting

**Requirement:** Authentication and sensitive endpoints must be rate-limited.
**Current Implementation:** SlowAPI rate limiter with per-user/IP key extraction. Auth endpoints limited to 3-15 requests/minute depending on endpoint.
**Evidence:** `@limiter.limit("5/minute")` on login/signup; `@limiter.limit("3/minute")` on password reset in `auth.py`.
**Gaps:** Rate limits are in-memory (not shared across workers). Nginx adds additional connection-level limiting.

## NFR-004 — Security: Input Validation

**Requirement:** All API inputs must be validated before processing.
**Current Implementation:** Pydantic v2 schemas for all request/response models.
**Evidence:** `app/schemas/` directory with 12 schema modules.
**Gaps:** None identified for API inputs.

## NFR-005 — Performance: Caching

**Requirement:** Frequently accessed data should be cached to reduce database load.
**Current Implementation:** Redis cache with configurable TTL (default 300s). In-memory fallback when Redis is unavailable.
**Evidence:** `app/core/redis.py` — `cache_get()`, `cache_set()` with `_mem_cache` fallback.
**Gaps:** No cache warming strategy beyond startup market warmup.

## NFR-006 — Performance: Database Connection Pooling

**Requirement:** Database connections must be pooled for efficient resource use.
**Current Implementation:** SQLAlchemy async engine with `pool_size=3`, `max_overflow=2`, `pool_recycle=1200`, `pool_pre_ping=True`.
**Evidence:** `app/db/base.py` engine configuration.
**Gaps:** Pool sizes are conservative (designed for Supabase free-tier connection limits).

## NFR-007 — Reliability: Background Task Processing

**Requirement:** Long-running tasks must not block API responses.
**Current Implementation:** Celery workers with Redis broker handle ML inference, news scraping, sentiment analysis, and scheduled tasks. In-process fallback via ThreadPoolExecutor when Celery is disabled.
**Evidence:** `app/celery_app.py`, `app/core/task_runner.py`.
**Gaps:** In-process fallback is bounded to 4 threads; tasks don't survive restarts.

## NFR-008 — Reliability: Health Monitoring

**Requirement:** The system must expose health endpoints for liveness and readiness probes.
**Current Implementation:** `/health` (liveness) and `/health/ready` (readiness checking DB, Redis, Celery worker, Celery Beat).
**Evidence:** `app/api/v1/health.py`, `app/services/health_service.py`.
**Gaps:** No external uptime monitoring service identified in the codebase.

## NFR-009 — Scalability: Horizontal Scaling Considerations

**Requirement:** The system should support horizontal scaling.
**Current Implementation:** Stateless API design with externalized state (PostgreSQL, Redis). WebSocket state is in-process per API instance.
**Evidence:** Architecture separates API, worker, and beat into independent Docker containers.
**Gaps:** WebSocket connections are not shared across instances (no sticky sessions or Redis-backed WS adapter for multi-instance). Single API instance in current deployment.

## NFR-010 — Maintainability: Code Organization

**Requirement:** Code should follow consistent patterns for maintainability.
**Current Implementation:** Layered architecture: API routes → services → repositories/models. Centralized configuration, exception handling, and authorization dependencies.
**Evidence:** `app/api/v1/`, `app/services/`, `app/models/`, `app/schemas/`, `app/core/`.
**Gaps:** Some services (e.g., `stock_service.py` at 69KB) are very large and could benefit from decomposition.

## NFR-011 — Availability: Containerized CI/CD Deployment

**Requirement:** Deployments should minimize downtime and verify health before service activation.
**Current Implementation:** Containerized deployment on Oracle Cloud Infrastructure with automated migration execution, container restarting, and readiness health probe verification (`/health`, `/api/v1/health/ready`).
**Evidence:** `.github/workflows/deploy-oracle.yml`, `docker-compose.production.yml`, `docs/07-deployment/oracle-deployment.md`.
**Gaps:** None identified for single-node compute deployment.

## NFR-012 — Observability: Logging

**Requirement:** The system should produce structured, actionable logs.
**Current Implementation:** Python `logging` module with format: `%(asctime)s | %(levelname)-8s | %(name)s | %(message)s`. Docker JSON-file driver with 10MB rotation.
**Evidence:** `app/core/logging.py`, `docker-compose.yml` logging config.
**Gaps:** No structured JSON logging. No centralized log aggregation system identified.

## NFR-013 — Portability: Containerization

**Requirement:** The application should run in any Docker-compatible environment.
**Current Implementation:** Multi-stage Dockerfile with non-root user, health checks, and pinned dependencies (`requirements.lock` with hashes).
**Evidence:** `dockerfile`, `docker-compose.yml`, `docker-compose.production.yml`.
**Gaps:** None identified.

## NFR-014 — Testability: Test Infrastructure

**Requirement:** The system should support automated testing.
**Current Implementation:** pytest with markers (unit, integration, api, e2e, performance, security), async support, and CI integration.
**Evidence:** `pytest.ini`, `tests/` directory with 32+ unit tests, 16+ API tests, and multiple E2E suites.
**Gaps:** No code coverage reporting tool configured. Some modules have thin unit test coverage.

## NFR-015 — Privacy: Sensitive Data Handling

**Requirement:** Sensitive data must not be exposed in logs or API responses.
**Current Implementation:** Passwords are never returned in API responses. Global exception handler masks internal errors. SendGrid API key and secrets are environment variables.
**Evidence:** `register_error_handlers()` in `exceptions.py` returns generic error for unhandled exceptions.
**Gaps:** No PII anonymization in logs. Firebase credentials JSON file is committed to `.gitignore` but present in the repository.

## NFR-016 — Usability: API Documentation

**Requirement:** The API should be self-documenting.
**Current Implementation:** OpenAPI/Swagger auto-generated at `/docs` and `/redoc`. All 16 endpoint groups tagged with descriptions.
**Evidence:** `TAGS_METADATA` in `main.py`, comprehensive endpoint descriptions in route decorators.
**Gaps:** None identified.
