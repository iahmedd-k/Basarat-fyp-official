# Backend Production-Readiness Review

**Scope:** backend only. The `frontend/` directory was not read or changed.  
**Review date:** 2026-09-19  
**Verdict:** **DO NOT RELEASE** to production or hand off as a production-ready API.

## Evidence and limits

This was a source/configuration review of the current backend working tree. I found 124 declared HTTP route decorators; 9 are in `app/api/v1/portfolio_routes/` but are not imported or mounted by `app/main.py`, leaving 115 exposed HTTP routes. Runtime test execution was attempted but is not a valid release signal: the host has no usable `python`/`pytest` on PATH and the committed `backend/venv/Scripts/python.exe` could not be started (`Access is denied`). No backend code was changed.

The working tree was already dirty before the review, including edits to API/configuration files, a newly added assistant module/migration, and deleted evaluation scripts. Therefore this report assesses the files currently present, not a known immutable release candidate.

## Release blockers

| ID | Finding | Evidence | Impact / required disposition |
|---|---|---|---|
| B1 | The Alembic revision graph has two heads. | `c3...` and `d4...` both descend from `b2...`; `f6... -> c3...` and `e5... -> d4...`, while the assistant migration extends only the former. | `alembic upgrade head` is ambiguous; schema deployment cannot be safely automated. Create and test a merge migration; require `alembic heads` = one head and `alembic upgrade head` on a blank DB. |
| B2 | Monte Carlo is non-functional in its worker. | `app/tasks/risk_tasks.py` imports nonexistent `app.core.config.settings`, and nonexistent `Portfolio` / `PortfolioHolding` models; the actual model is `PortfolioTransaction`. | `POST /risk/monte-carlo` can return 202 then every task fails/retries. Reimplement it against the transaction model and test submit/poll/ownership/failure paths. |
| B3 | Password-reset user flow cannot complete. | `AuthService.forgot_password` creates only a hash and has a TODO for email delivery; raw token is never returned or sent. | A real user cannot obtain a reset token. Integrate an async transactional email provider, template, URL allowlist, delivery failure monitoring, and end-to-end test. |
| B4 | Three registered task modules are placeholders. | `scrape_market.run`, `compute_sentiment.run`, and `evaluate_alert_rules.run` contain only `pass`. | Any caller of these named tasks gets false-success with no business work. Remove registrations or implement/test them; do not schedule/advertise the functions until then. |
| B5 | Database schema governance is unsafe. | API lifespan calls `Base.metadata.create_all()` on every application start. | It can conceal missing migrations and races with Alembic. Production must run migrations as a one-shot deployment job; remove automatic DDL from app startup. |
| B6 | Deployment composition is development-grade and exposes state services. | Compose runs Uvicorn with `--reload`, bind-mounts the source tree, and publishes PostgreSQL/Redis to the host; database password is a literal `adminadmin`. | Not production deployable. Use an immutable image, production process manager/workers, secret manager, network-private DB/Redis, TLS/authenticated Redis, and no reload. |

## High-priority production gaps

| ID | Finding | Evidence / consequence |
|---|---|---|
| H1 | Health/readiness contract is inconsistent. | `/api/v1/health` performs DB, Redis, worker and beat checks but is a 200 response even when degraded; `/api/v1/ready` always returns `{"status":"ready"}`. The documented `/health/ready` is not mounted. Split liveness/readiness and return an unhealthy status when dependencies needed for traffic are unavailable. |
| H2 | API documentation does not match the deployed routing. | Docs describe `/`, `/health/ready`, `/market/sector-heatmap`, `/risk/cvar`, holdings CRUD, WebSocket market live, community share, and assistant quick prompts, but these are missing or different. Several actual endpoints are undocumented (assistant conversation mutation, admin community, news status/sources, alert listing). Generate/validate OpenAPI as the contract before client handoff. |
| H3 | Nine portfolio route implementations are unreachable. | `portfolio_routes/{transactions,summary,prices}.py` declare routes but `main.py` never includes their routers. | Do not hand those endpoints to clients; decide one portfolio API, remove dead routes or mount it deliberately, and test backward compatibility. |
| H4 | Push notifications are a stub. | `NotificationService.send_push_notification` returns `True` and bulk returns input count without contacting Firebase. | Delivery metrics and alerting are fictitious. Implement Firebase credentials/lifecycle/error handling and device-token invalidation, or disable push claims. |
| H5 | Rate-limit identity trusts an unvalidated `X-Forwarded-For`. | `core/rate_limiter.py` uses the first header value from any caller. | Clients can spoof identity/bypass per-IP throttles unless a trusted proxy strips/sets the header. Configure proxy middleware and trust only known proxy hops. |
| H6 | No release observability/edge controls found. | No structured JSON logging with request IDs, metrics/traces, exception reporting, trusted-host/HTTPS middleware, or health alerting configuration. | Add request correlation, redacted structured logs, metrics, tracing, alerting, ingress TLS/HSTS/host policy, and runbooks. |
| H7 | Async job reliability policy is incomplete. | `task_acks_late=True` is global, but no demonstrated idempotency keys/deduplication, worker-lost rejection, result expiry, queue routing, TLS/auth, or operational retry/DLQ policy. | Redelivery can duplicate writes/notifications; result store can grow without bound. Define task-specific idempotency and retention, queues, alerts, and recovery policy. |
| H8 | Scheduled workflow has correctness/operability risks. | Beat schedules each stage at 02:00–05:00 independently instead of scheduling the defined daily chain; a run can overlap the next stage or a prior run. Weekly orchestrator blocks inside a task with `.get()`, risking starvation/deadlock at low worker concurrency. Candidate GRU task reads `metadata.json` before ensuring/creating the candidate directory/file. | Use a single chain trigger with overlap locking, worker-concurrency tests, and nonblocking Celery canvases. Exercise failure/retry/recovery. |
| H9 | CORS and configuration defaults are not production-safe enough. | Missing production `CORS_ORIGINS` silently enables localhost origins; environment allows unknown fields; DB defaults embed credentials. | Require explicit environment/profile, fail fast on non-production secrets/endpoints, validate URLs/origins, and remove credential defaults. |

## Endpoint inventory and release assessment

Legend: **R** = registered/mounted; **A** = authenticated; **Adm** = admin-authorized; **X** = release-blocked by an identified defect; **U** = unmounted (not externally callable). “Source-reviewed” does **not** mean runtime-verified.

### System and authentication

| Endpoint | Assessment |
|---|---|
| `GET /api/v1/` | R, public; contract/documentation mismatch (root is version-prefixed). |
| `GET /api/v1/ready` | R, public; **X** false readiness—always ready. |
| `GET /api/v1/health` | R, public; source-reviewed; degraded result does not express HTTP readiness failure. |
| `POST /api/v1/auth/signup` | R, rate limited; source-reviewed. Validate duplicate/race, verification/abuse and transactional commit E2E before release. |
| `POST /api/v1/auth/login` | R, rate limited; source-reviewed. No account-lockout/MFA/audit control found. |
| `POST /api/v1/auth/refresh` | R, rate limited; refresh rotation/reuse revocation implemented; runtime concurrency/replay test required. |
| `POST /api/v1/auth/logout` | R, public by design, rate limited; source-reviewed. |
| `POST /api/v1/auth/forgot-password` | R, rate limited; **X** reset token is never delivered. |
| `POST /api/v1/auth/change-password` | R, A, rate limited; source-reviewed; verify all-session revocation E2E. |
| `POST /api/v1/auth/reset-password` | R, rate limited; **X** unreachable through normal user flow. |
| `GET /api/v1/users/me` | R, A; source-reviewed. |
| `PATCH /api/v1/users/me` | R, A; source-reviewed. |
| `PATCH /api/v1/users/me/risk-profile` | R, A; source-reviewed. |
| `PATCH /api/v1/users/me/notification-preferences` | R, A; source-reviewed. |
| `GET /api/v1/users/risk-profile/sectors` | R, public route in source (no auth dependency); assess whether disclosure is intentional. |
| `POST /api/v1/devices/register` | R, A; source-reviewed; **X** downstream push service is stubbed. |

### Market, stock, forecast, recommendation

| Endpoint | Assessment |
|---|---|
| `GET /api/v1/market/indices` | R, A; source-reviewed. |
| `GET /api/v1/market/indices/kse-100` | R, A; source-reviewed. |
| `GET /api/v1/market/indices/kse-30` | R, A; source-reviewed. |
| `GET /api/v1/market/indices/kmi-30` | R, A; source-reviewed. |
| `GET /api/v1/market/gainers` | R, A; source-reviewed. |
| `GET /api/v1/market/losers` | R, A; source-reviewed. |
| `GET /api/v1/market/volume-spikes` | R, A; source-reviewed. |
| `GET /api/v1/market/sentiment-overview` | R, A; source-reviewed. |
| `GET /api/v1/stocks/search` | R, A, rate limited; source-reviewed. |
| `GET /api/v1/stocks/{symbol}/overview` | R, A, rate limited; source-reviewed. |
| `GET /api/v1/stocks/{symbol}/price-history` | R, A, rate limited; source-reviewed. |
| `GET /api/v1/stocks/{symbol}/technical-indicators` | R, A, rate limited; source-reviewed. |
| `GET /api/v1/stocks/{symbol}/fundamentals` | R, A, rate limited; source-reviewed. |
| `GET /api/v1/forecast/{symbol}` | R, A; source-reviewed. Requires model/data availability, latency/load, probability calibration, and prediction-write idempotency tests before release. |
| `GET /api/v1/forecast/{symbol}/history` | R, A; source-reviewed; history is not scoped to user and always reports horizon `1D`; confirm product/privacy contract. |
| `GET /api/v1/recommendations` | R, A; source-reviewed. |
| `GET /api/v1/recommendations/engine-weights` | R, A; source-reviewed. |
| `POST /api/v1/recommendations/engine-weights` | R, A; source-reviewed; confirm this is admin-only if it changes shared model behavior. |
| `GET /api/v1/recommendations/{symbol}` | R, A; source-reviewed. |
| `GET /api/v1/recommendations/{symbol}/target-stop` | R, A; source-reviewed. |

### Portfolio, risk, alerts, notifications

| Endpoint | Assessment |
|---|---|
| `GET /api/v1/portfolio` | R, A; source-reviewed. |
| `GET /api/v1/portfolio/holdings` | R, A; source-reviewed. |
| `GET /api/v1/portfolio/holdings/{symbol}` | R, A; source-reviewed. |
| `GET /api/v1/portfolio/pnl` | R, A; source-reviewed. |
| `GET /api/v1/portfolio/allocation` | R, A; source-reviewed. |
| `GET /api/v1/portfolio/performance` | R, A; incomplete: underlying time-series calculation currently returns an empty list. |
| `GET /api/v1/portfolio/transactions` | R, A; source-reviewed. |
| `GET /api/v1/portfolio/transactions/{transaction_id}` | R, A; source-reviewed. |
| `POST /api/v1/portfolio/transactions` | R, A; source-reviewed. Require idempotency/duplicate-submission test. |
| `PATCH /api/v1/portfolio/transactions/{transaction_id}` | R, A; source-reviewed. |
| `DELETE /api/v1/portfolio/transactions/{transaction_id}` | R, A; source-reviewed. |
| `GET /api/v1/risk/var` | R, A, rate limited; source-reviewed. |
| `POST /api/v1/risk/monte-carlo` | R, A, rate limited; **X** accepted task will fail (B2). |
| `GET /api/v1/risk/monte-carlo/{task_id}` | R, A, rate limited; **X** dependent on failed task; ownership only checked on SUCCESS. |
| `GET /api/v1/risk/stress-test` | R, A, rate limited; source-reviewed. |
| `GET /api/v1/alerts/rules` | R, A; source-reviewed. |
| `POST /api/v1/alerts/rules` | R, A; source-reviewed. |
| `PATCH /api/v1/alerts/rules/{rule_id}` | R, A; source-reviewed. |
| `DELETE /api/v1/alerts/rules/{rule_id}` | R, A; source-reviewed. |
| `GET /api/v1/alerts` | R, A; source-reviewed. |
| `PATCH /api/v1/alerts/{alert_id}/read` | R, A; source-reviewed. |
| `GET /api/v1/notifications` | R, A; source-reviewed. |
| `PATCH /api/v1/notifications/{notification_id}/read` | R, A; source-reviewed. |

### Sentiment, news, events, Shariah

| Endpoint | Assessment |
|---|---|
| `GET /api/v1/sentiment/{symbol}` | R, A; source-reviewed. |
| `GET /api/v1/sentiment/{symbol}/history` | R, A; source-reviewed. |
| `GET /api/v1/sentiment/{symbol}/news` | R, A; source-reviewed. |
| `GET /api/v1/sentiment/market-overview` | R, A; source-reviewed. |
| `GET /api/v1/news` | R, A; source-reviewed; uses a different error body (`HTTPException`) for validation than global contract. |
| `POST /api/v1/news/refresh` | R, A; source-reviewed; in-process background task is not durable—job is lost on restart and has no client job status. |
| `GET /api/v1/news/refresh/status` | R, A; source-reviewed. |
| `GET /api/v1/news/market-status` | R, A; source-reviewed. |
| `GET /api/v1/news/sources` | R, A; source-reviewed. |
| `GET /api/v1/news/{article_id}` | R, A; source-reviewed. |
| `GET /api/v1/stocks/{symbol}/news` | R, A; source-reviewed. |
| `GET /api/v1/events/calendar` | R, A; source-reviewed. |
| `GET /api/v1/shariah/kmi30` | R, A, rate limited; source-reviewed. |
| `GET /api/v1/shariah/{symbol}` | R, A, rate limited; source-reviewed. |
| `GET /api/v1/shariah/{symbol}/criteria` | R, A, rate limited; source-reviewed. |
| `GET /api/v1/shariah/{symbol}/purification` | R, A, rate limited; source-reviewed. |

### Community, assistant, administration

| Endpoint | Assessment |
|---|---|
| `POST /api/v1/community/posts` | R, A, rate limited; source-reviewed. |
| `GET /api/v1/community/feed` | R, A; source-reviewed. |
| `GET /api/v1/community/posts/{post_id}` | R, A; source-reviewed. |
| `PATCH /api/v1/community/posts/{post_id}` | R, A; source-reviewed. |
| `DELETE /api/v1/community/posts/{post_id}` | R, A; source-reviewed. |
| `POST /api/v1/community/posts/{post_id}/like` | R, A; source-reviewed. |
| `DELETE /api/v1/community/posts/{post_id}/like` | R, A; source-reviewed. |
| `POST /api/v1/community/posts/{post_id}/report` | R, A; source-reviewed. |
| `POST /api/v1/community/posts/{post_id}/comments` | R, A; source-reviewed. |
| `GET /api/v1/community/posts/{post_id}/comments` | R, A; source-reviewed. |
| `DELETE /api/v1/community/comments/{comment_id}` | R, A; source-reviewed. |
| `POST /api/v1/community/comments/{comment_id}/report` | R, A; source-reviewed. |
| `POST /api/v1/community/users/{user_id}/follow` | R, A; source-reviewed. |
| `DELETE /api/v1/community/users/{user_id}/follow` | R, A; source-reviewed. |
| `GET /api/v1/community/users/{user_id}/follow-status` | R, A; source-reviewed. |
| `GET /api/v1/community/users/{user_id}/followers` | R, A; source-reviewed. |
| `GET /api/v1/community/users/{user_id}/following` | R, A; source-reviewed. |
| `GET /api/v1/community/me` | R, A; source-reviewed. |
| `GET /api/v1/community/me/posts` | R, A; source-reviewed. |
| `GET /api/v1/community/users/{user_id}` | R, A; source-reviewed. |
| `GET /api/v1/community/users/{user_id}/posts` | R, A; source-reviewed. |
| `GET /api/v1/community/notifications` | R, A; source-reviewed. |
| `GET /api/v1/community/notifications/unread-count` | R, A; source-reviewed. |
| `POST /api/v1/community/notifications/{notification_id}/read` | R, A; source-reviewed. |
| `POST /api/v1/community/notifications/read-all` | R, A; source-reviewed. |
| `POST /api/v1/assistant/chat` | R, A, 30/minute; source-reviewed. LLM provider safety, timeouts, cost caps, data-retention and prompt-injection evaluation are required before production. |
| `GET /api/v1/assistant/conversations` | R, A; source-reviewed. |
| `POST /api/v1/assistant/conversations` | R, A; source-reviewed. |
| `GET /api/v1/assistant/conversations/{conversation_id}` | R, A; source-reviewed. |
| `PATCH /api/v1/assistant/conversations/{conversation_id}` | R, A; source-reviewed. |
| `DELETE /api/v1/assistant/conversations/{conversation_id}` | R, A; source-reviewed. |
| `POST /api/v1/assistant/conversations/{conversation_id}/regenerate` | R, A; source-reviewed; apply the same LLM safeguards. |
| `GET /api/v1/admin/community/reports` | R, Adm; source-reviewed. |
| `PATCH /api/v1/admin/community/reports/{report_id}` | R, Adm; source-reviewed. |
| `GET /api/v1/admin/community/posts/{post_id}` | R, Adm; source-reviewed. |
| `POST /api/v1/admin/community/posts/{post_id}/restore` | R, Adm; source-reviewed. |
| `DELETE /api/v1/admin/community/posts/{post_id}` | R, Adm; source-reviewed. |
| `POST /api/v1/admin/community/posts/{post_id}/remove` | R, Adm; source-reviewed. |
| `DELETE /api/v1/admin/community/comments/{comment_id}` | R, Adm; source-reviewed. |
| `GET /api/v1/admin/community/moderation-actions` | R, Adm; source-reviewed. |

### Declared but unreachable routes (not part of the live API)

| Endpoint | Assessment |
|---|---|
| `GET /api/v1/prices/{symbol}` | U — router not included in `main.py`. |
| `POST /api/v1/prices/bulk` | U — router not included in `main.py`. |
| `GET /api/v1/portfolio/summary` | U — router not included in `main.py`. |
| `GET /api/v1/portfolio/holdings/{symbol}` (alternate implementation) | U — router not included; duplicates an exposed route. |
| `POST /api/v1/portfolio/transactions` (alternate implementation) | U — router not included; conflicts with exposed contract. |
| `GET /api/v1/portfolio/transactions` (alternate implementation) | U — router not included; conflicts with exposed contract. |
| `GET /api/v1/portfolio/transactions/{transaction_id}` (alternate implementation) | U — router not included; conflicts with exposed contract. |
| `PUT /api/v1/portfolio/transactions/{transaction_id}` | U — router not included; exposed API uses PATCH. |
| `DELETE /api/v1/portfolio/transactions/{transaction_id}` (alternate implementation) | U — router not included; conflicts with exposed contract. |

## Mandatory gate before client handoff

1. Freeze a clean release branch and resolve the migration heads.
2. Fix B1–B6 and add regression tests specifically reproducing each issue.
3. Stand up ephemeral PostgreSQL and Redis in CI; run `alembic upgrade head`, all unit/API/integration tests, and a clean-start smoke test.
4. Generate an OpenAPI snapshot from the running app, reconcile it with the client contract, and contract-test every row above including 401/403/404/409/422/429/5xx behavior.
5. Test complete user flows: signup/login/refresh/logout; recover password by delivered email; device registration plus real push; transaction lifecycle/P&L; news refresh/restart; Monte Carlo submit/poll/access control; community moderation; assistant ownership/safety.
6. Deploy a staging stack with production-equivalent secrets, TLS ingress, database/Redis isolation, Celery worker/beat monitoring, alerting, backup/restore, load tests, and a rollback rehearsal.

Only after all six gates pass should this API be provided to web or Android teams as a stable production contract.
