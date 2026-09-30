# Operations Troubleshooting Guide — Basarat

This guide provides practical diagnosis and resolution steps for common operational and runtime issues in the Basarat platform.

---

## 1. Application Startup & Configuration Failures

### 1.1 "SECRET_KEY must be set to a strong random value"
- **Symptoms:** Container `basarat-api` exits immediately upon startup (Exit code 1).
- **Possible Cause:** `SECRET_KEY` in `.env` is empty or set to a development placeholder (e.g. `secret`, `change-me-in-production`).
- **How to Diagnose:** Inspect container startup logs: `docker compose logs app`.
- **Resolution:** Generate a 32+ byte cryptographic secret and update `.env`:
  ```bash
  openssl rand -hex 32
  ```

### 1.2 "CORS_ORIGINS must be an explicit allowlist outside development"
- **Symptoms:** API fails to start when `ENVIRONMENT` is set to `staging` or `production`.
- **Possible Cause:** `CORS_ORIGINS` contains `["*"]` or is empty.
- **How to Diagnose:** Check logs for `ValueError: CORS_ORIGINS must be an explicit allowlist outside development`.
- **Resolution:** Update `.env` with specific client domains:
  ```ini
  CORS_ORIGINS=["https://app.basarat.pk","https://basarat.pk"]
  ```

---

## 2. Database & Migration Failures

### 2.1 "Multiple head revisions are present for given argument 'head'"
- **Symptoms:** `alembic upgrade head` fails with `CommandError: Multiple head revisions are present`.
- **Possible Cause:** Divergent migration branches created concurrently by different developers.
- **How to Diagnose:** Run `alembic heads` to view active branches.
- **Resolution:** Apply the merge migration `alembic/versions/h8i9j0k1l2m3_merge_schema_heads.py` or generate a new merge:
  ```bash
  alembic merge heads -m "merge divergent branches"
  alembic upgrade head
  ```

### 2.2 PostgreSQL Connection Refused / Pool Timeout
- **Symptoms:** API returns HTTP 500 `Internal Server Error`; logs show `asyncpg.exceptions.CannotConnectNowError` or `TimeoutError QueuePool limit of size 5 overflow 10 reached`.
- **Possible Cause:** PostgreSQL container is down, database credentials expired, or connection pool exhausted by long-running transactions.
- **How to Diagnose:**
  1. Test direct database connection: `pg_isready -h localhost -p 5432 -U postgres`.
  2. Inspect active connections in PostgreSQL:
     ```sql
     SELECT count(*), state FROM pg_stat_activity GROUP BY state;
     ```
- **Resolution:** Restart database container or increase pool limits in [base.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/db/base.py) (`pool_size=20, max_overflow=10`).

---

## 3. Background Worker & Celery Failures

### 3.1 Celery Worker Out-Of-Memory (OOM Killed)
- **Symptoms:** Container `basarat-celery-worker` exits with code 137 during weekly model retraining or heavy Monte Carlo jobs.
- **Possible Cause:** Deep learning models and large Pandas dataframes accumulate in memory across task iterations.
- **How to Diagnose:** Check Docker exit state: `docker inspect -f '{{.State.OOMKilled}}' basarat-celery-worker`.
- **Resolution:** Ensure Celery worker runs with `--max-tasks-per-child=1` in `docker-compose.production.yml` to recycle worker child processes after task completion.

### 3.2 Scheduled Crons Not Executing
- **Symptoms:** Daily 18:00 PKT pipeline or 5-minute alert evaluations do not trigger.
- **Possible Cause:** `basarat-celery-beat` is not running, or clock drift exists between containers.
- **How to Diagnose:**
  1. Check beat container status: `docker compose ps celery-beat`.
  2. Inspect Celery Beat logs: `docker compose logs --tail 50 celery-beat`.
- **Resolution:** Restart `celery-beat` and verify host system time is synchronized with NTP (`timedatectl`).

---

## 4. Market Ingestion & External Service Errors

### 4.1 Upstream PSX Scraper Circuit Breaker Active
- **Symptoms:** Market quotes stop updating; logs show `Circuit breaker active for next 900s`.
- **Possible Cause:** Upstream PSX exchange portal returned HTTP 429 Too Many Requests or HTTP 403 Forbidden.
- **How to Diagnose:** Query `GET /api/v1/news/sources` or inspect worker logs for `PSX rate limit hit`.
- **Resolution:** The circuit breaker will automatically reset after 15 minutes (`MARKET_CIRCUIT_BREAKER_SECONDS=900`). To manually reset, flush Redis key `del market:scraper:circuit_breaker`.

### 4.2 Groq LLM Assistant Downtime or Rate Limit
- **Symptoms:** AI Assistant returns `"AI assistant is currently experiencing high demand"`.
- **Possible Cause:** Groq free-tier rate limits reached, or configured model identifier (`GROQ_MODEL`) was deprecated by provider.
- **How to Diagnose:** Test Groq key directly using curl:
  ```bash
  curl https://api.groq.com/openai/v1/models -H "Authorization: Bearer $GROQ_API_KEY"
  ```
- **Resolution:** Switch to fallback model in `.env`:
  ```ini
  GROQ_MODEL=qwen/qwen3.8-27b
  ```

---

## 5. Client Connectivity & WebSocket Issues

### 5.1 WebSocket Connection Immediately Closes
- **Symptoms:** Browser console reports `WebSocket connection to 'wss://.../ws/market' failed: WebSocket is closed before the connection is established`.
- **Possible Cause:** Reverse proxy (Nginx) is not configured to upgrade HTTP connections to WebSockets.
- **How to Diagnose:** Check Nginx configuration for `Upgrade` and `Connection` headers.
- **Resolution:** Add standard WebSocket upgrade directives to Nginx site config:
  ```nginx
  location /api/v1/ws/ {
      proxy_pass http://127.0.0.1:8000;
      proxy_http_version 1.1;
      proxy_set_header Upgrade $http_upgrade;
      proxy_set_header Connection "Upgrade";
      proxy_read_timeout 86400s;
  }
  ```
