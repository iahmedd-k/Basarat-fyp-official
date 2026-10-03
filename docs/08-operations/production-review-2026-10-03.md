# Basarat Production Engineering Review

**Review date:** 2026-10-03
**Scope:** Backend application, API contract, data-ingestion paths, Celery infrastructure, Docker/Compose deployment, configuration, tests, and the supplied endpoint audit.
**Release recommendation:** **Do not release as a production candidate yet.** The Compose deployment has since been simplified, but application and runtime release gates remain.

## Executive summary

The project has a good architectural direction in several areas: FastAPI routers are separated by domain, data refresh work is moving behind Celery, Redis-backed single-flight coordination was added for several market-data paths, and production workers are separated by workload. The production Compose file also renders successfully with the required deployment variables.

The remaining risk is not one isolated defect. The system still has contract, runtime, and operational inconsistencies that can produce a deployment that starts but is not functionally complete. The highest-priority issues are:

1. Application runtime failures from the supplied endpoint audit still need to be reproduced against a fully seeded dependency stack.
2. Push notifications remain disabled unless Firebase credentials are deliberately injected.
3. Data ingestion must preserve the last known-good generation when a scrape is partial or rate-limited.
4. The supplied endpoint run recorded only 62 successful operations out of 169, with 29 client-side/runtime timeouts and four server-side 500 responses. Negative authentication cases account for some intentional failures, but the portfolio 500s and widespread timeouts require triage before release.

The endpoint evidence remains historical: this report has not been re-run against a fully provisioned seeded environment. The application now returns correlation IDs on every response, rejects missing transaction updates as 404s, and no longer silently falls back to in-process execution when Celery dispatch is configured but invalid. These changes improve diagnosability and correctness, but do not replace a seeded endpoint rerun.
5. There is no repository CI workflow visible under `.github/workflows`, so the tested state is not automatically protected.
6. A Firebase service-account file is present in the workspace. It is ignored rather than tracked, but it must be treated as a sensitive credential and must never be committed or copied into an image.

## Severity model

- **P0 — release blocker:** security, data loss, or deployment failure is likely.
- **P1 — high:** major user journey or reliability failure under normal operation.
- **P2 — medium:** material maintainability, observability, or correctness risk.
- **P3 — low:** cleanup or improvement that should be scheduled.

## Findings

| ID | Severity | Area | Finding | Evidence | Required action |
|---|---|---|---|---|---|
| P0-01 | P0 | Security/configuration | CORS and host-header controls must be explicit in production. | **Fixed:** `main.py` uses `settings.CORS_ORIGINS` and `TrustedHostMiddleware`; production settings reject wildcard and localhost origins/hosts. | Set deployed `CORS_ORIGINS` and `ALLOWED_HOSTS` in the container environment and add an integration test for approved/rejected origins and hosts. |
| P0-02 | P0 | Deployment/secrets | Firebase is unavailable unless credentials are explicitly provisioned. | The simplified Compose stack does not bind-mount a service-account file and clears `FIREBASE_CREDENTIALS_PATH`. | Keep Firebase disabled unless credentials are injected by the runtime secret mechanism. Never copy the JSON into the image. |
| P0-03 | P0 | Secrets | A Firebase service-account credential exists in the workspace. | The supplied tagged file is a Firebase admin service-account JSON. It is ignored by Git, but it is still present on disk. | Rotate the credential if it has ever been uploaded, shared, logged, or copied into an image. Keep it in a secret manager or deployment secret only; do not inspect, print, or commit its contents. |
| P0-04 | P0 | Release validation | The release image was not built successfully in this environment. | Docker build reached dependency installation and failed downloading a large wheel with a PyPI read timeout. | Retry in CI with a registry/cache and publish/scan the image. The application requirements already use `tensorflow-cpu`; avoid adding GPU dependencies to the lockfile. |
| P1-01 | P1 | Runtime/API | The endpoint audit shows broad functional instability. | `Raw Reports/endpoints.json`: 169 operations, 62 successes, 111 failures, 29 runtime timeouts, 4 HTTP 500s, 2 HTTP 503s. Some 401/422 responses are expected negative tests, but portfolio transaction endpoints returned 500 and multiple domains timed out. | Re-run with a real seeded database and service health checks. Treat every 500 and timeout as a defect until explained. Add endpoint smoke tests with explicit latency and response-contract assertions. |
| P1-02 | P1 | API contract | Several advertised flows are unavailable or not configured in the audit environment. | Forecast returned `503` because the ML model was not loaded; Clerk webhook returned `503` because it was not configured; stock search returned an empty payload; news refresh and events timed out. | Make feature readiness explicit. Either provision dependencies in the environment or return a documented `503` with readiness metadata. Do not present disabled capabilities as production-ready. |
| P1-03 | P1 | Local infrastructure | The local Postgres healthcheck uses the wrong username. | **Fixed:** `backend/docker-compose.yml` now uses interpolated `POSTGRES_USER` and `POSTGRES_DB`. | Run a clean-start local Compose smoke test. |
| P1-04 | P1 | Scheduling/data | Scraper output needs single-writer and crash-safe log semantics. | **Fixed:** scrape runs now use an output-directory lock and fetch logs use atomic replacement writes. | Exercise concurrent invocation and stale-lock recovery in an integration test. |
| P1-05 | P1 | Data correctness | Scraper freshness and partial-success semantics need a durable publication boundary. | **Fixed:** runs stage Parquet output in a run directory and publish the generation only when every symbol is successful or skipped; failed/rate-limited runs preserve the previous dataset. | Add a test for partial failure and verify readers never consume the staging directory. |
| P1-06 | P1 | Background jobs | Celery task reliability is improved but still lacks a complete idempotency and dead-letter policy. | `task_acks_late=True` and `task_reject_on_worker_lost=True` are global; task-specific idempotency keys, retry budgets, dead-letter handling, and task-result retention are not consistently enforced in the reviewed configuration. | Define idempotency keys for every write/notification task, cap retries by failure class, configure result expiry and queue alerts, and document replay/recovery procedures. |
| P1-07 | P1 | Service lifecycle | API readiness previously ignored ML model availability. | **Improved:** readiness now reports `ml_model` and returns HTTP 503 when it is unavailable. | Add a startup/readiness integration test with missing model artifacts and verify the liveness endpoint remains available. |
| P1-08 | P1 | Deployment topology | Production Compose previously depended on externally pre-created volumes and network. | **Fixed:** the simplified Compose stack uses ordinary project-scoped named volumes and the default Compose network. | Validate a clean `docker compose up` with the required database URL and `.env` configuration. |
| P2-01 | P2 | Security middleware | No application-level trusted-host or HTTPS enforcement is visible. | `main.py` adds CORS and rate limiting but no `TrustedHostMiddleware` or `HTTPSRedirectMiddleware`; TLS is therefore entirely dependent on an external ingress. | Document the ingress contract and enforce allowed hosts at the edge. Add forwarded-protocol handling only for explicitly trusted proxies and verify secure cookie/token behavior. |
| P2-02 | P2 | Rate limiting | Rate-limit identity depends on proxy configuration and silently falls back when token parsing fails. | `backend/app/core/rate_limiter.py` accepts `X-Forwarded-For` only for configured proxy IPs, but broad exception handling suppresses token parsing errors and the production proxy contract is not tested. | Add proxy integration tests, structured counters for invalid tokens and spoof attempts, and a documented trusted-proxy chain. Avoid broad silent catches in identity/security code. |
| P2-03 | P2 | Error handling | Several broad exception handlers convert unexpected failures into generic business errors or silently continue. | Examples include broad catches in API services, Redis coordination, rate limiting, and the Celery worker-process initialization hook. | Preserve the user-safe response while recording exception type, request/task ID, and dependency context. Do not suppress failures that affect correctness or readiness. |
| P2-04 | P2 | Observability | Operational signals are documented but not yet demonstrated as implemented end-to-end. | The review found no visible CI workflow and no evidence in the supplied audit of request IDs, metrics, traces, queue-depth alerts, scraper freshness alerts, or upstream request counters. | Add structured JSON logs, correlation IDs, metrics for cache/lock/upstream/task behavior, distributed tracing where appropriate, and alerts tied to SLOs. |
| P2-05 | P2 | Testing | The repository contains tests, but release gates are incomplete. | `backend/tests` contains approximately 70 Python files, while no `.github/workflows` files were found. Prior focused tests passed, but the full suite and real Redis/Docker deployment were not validated here. | Add CI stages for lint/type checks, unit/integration tests, migration upgrade from blank DB, Compose config, image build, and a Redis/Postgres smoke environment. |
| P2-06 | P2 | API design | The API surface is broad and contains overlapping responsibilities across domain services and legacy paths. | The backend exposes many routers and compatibility mounts; the supplied audit includes empty payloads and timeouts across watchlists, recommendations, alerts, community, and events. | Generate an OpenAPI inventory from the running application, designate supported/v1 endpoints, mark deprecated routes, and remove or isolate dead/legacy paths. |
| P3-01 | P3 | Documentation | The existing `PRODUCTION_READINESS_REVIEW.md` is stale relative to the current checkout. | It is dated 2026-09-19 and reports issues that have since changed, while not covering the current CORS, secret-mount, Compose healthcheck, and endpoint-audit evidence. | Use this dated review as historical context only. Keep the current review and update it after each release gate. |

## What is working

- Docker Engine and Docker Compose are installed and responsive.
- Both local and production Compose files render successfully when required variables are supplied.
- Production worker queues are separated into live/news, fundamentals, and ML/data-pipeline workloads.
- Redis-backed single-flight and dispatch deduplication protections exist in the market, fundamentals, startup warmup, daily workflow, and news refresh paths.
- The production image uses a pinned Python base image and a hash-locked requirements file.
- The production Compose file uses a one-shot migration service instead of relying on the API container to run migrations.
- Focused OHLCV/stock-service tests previously passed, but this does not replace a full release validation.

## Changes implemented after this review

- Production Compose was reduced to `redis`, `migrate`, `app`, `celery-worker`, and `celery-beat`.
- Nginx, external Docker networks, external volumes, legacy profiles, and host Firebase bind mounts were removed.
- Compose now uses ordinary named volumes and injects service connection variables into each container.
- The Docker image's bundled model artifacts are no longer hidden by a broad `/app/models` volume.
- Local Postgres healthcheck credentials are now interpolated from the service environment.
- API CORS now uses `settings.CORS_ORIGINS`; production rejects wildcard and localhost origins.
- A backend CI workflow was added for Python compilation, focused tests, and Compose validation.
- The deleted tracked `backend/requirements.lock` was restored so the Dockerfile can perform its hash-locked installation.
- Scraper runs now have a single-writer lock, atomic JSON logs, staged Parquet output, and last-known-good publication semantics.
- Readiness now includes ML model state, while liveness remains independent of dependency health.
- Trusted host validation is enabled and production configuration rejects wildcard/localhost hosts.

## Release gates

The following gates should be green before production deployment:

1. **Security/configuration:** explicit CORS, rotated external credentials, no service-account files in Git or images, production secret preflight, trusted-host/ingress contract.
2. **Database:** one Alembic head, blank-database upgrade, upgrade from a representative existing database, rollback policy, and backup/restore rehearsal.
3. **Runtime:** all endpoint-audit 500s and timeouts explained or fixed; forecast, news, events, alerts, watchlists, portfolio, and community smoke tests pass with seeded data.

Implemented in the current remediation pass:
- Request correlation IDs are generated or propagated by application middleware and returned as `X-Request-ID`, including application-error responses.
- Portfolio update requests return a domain 404 when the transaction does not exist instead of attempting response serialization on `None`.
- Celery mode now fails explicitly when a task is not dispatchable; it does not silently execute work in the API process.
- Historical stock and ETF reads use the maintained OHLCV files and no longer perform request-time historical PSX fetches.
- Recommendation detail and target/stop routes consume the published recommendation snapshot instead of recomputing provider-dependent signals in the API process.
- Sector performance no longer falls back to a request-time PSX screener call; sector enrichment remains an ingestion responsibility.
- Scheduled daily, market-refresh, fundamentals, and news-ingestion jobs now fail closed when Redis coordination is unavailable; they do not run uncoordinated scraper work.
- Daily pipeline dispatch clears its Redis deduplication key if Celery enqueue fails.
4. **Data pipeline:** one active scraper owner, atomic generation publication, stale-data behavior, partial-failure behavior, upstream 403/429 behavior, and replay safety tested.
5. **Operations:** CI build/push/scan, Compose preflight, health/readiness checks, queue-depth/freshness alerts, structured logs, and deployment/rollback runbooks.
6. **Performance:** load tests for cache hits, cache misses, lock contention, portfolio calculations, WebSocket fan-out, and Celery backlog recovery.

## Recommended implementation order

### Immediate

1. Fix CORS and the local Postgres healthcheck.
2. Resolve the Firebase secret provisioning path and rotate the credential if exposure is possible.
3. Re-run endpoint smoke tests with seeded Postgres, Redis, Celery, and model artifacts; fix all 500s first.
4. Add CI and make Compose validation, migrations, tests, and image build mandatory gates.

### Next

1. Add atomic scraper generation publication and single-owner enforcement.
2. Complete Celery idempotency, retry, dead-letter, and result-retention policies.
3. Implement readiness semantics for model, Redis, database, and Celery dependencies.
4. Add production telemetry and SLO-based alerts.

### Before broad user rollout

1. Run a representative load test and failure-injection test.
2. Exercise backup restore and deployment rollback.
3. Freeze and version the OpenAPI contract.
4. Perform a separate formal security assessment after the credential and CORS blockers are resolved.
