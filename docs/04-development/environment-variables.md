# Environment Variables Reference

This document provides a comprehensive dictionary of all runtime environment variables accepted and validated by `app/core/config.py` (Pydantic `Settings`).

---

## 1. Core Server & Security Settings

| Variable | Required | Type | Default | Description |
|---|---|---|---|---|
| `PROJECT_NAME` | No | `str` | `Basarat` | Application brand name displayed in logs and documentation. |
| `ENVIRONMENT` | No | `str` | `development` | Runtime environment: `development`, `staging`, `production`. |
| `DEBUG` | No | `bool` | `false` | Enables verbose tracebacks and Swagger UI. Must be `false` in production. |
| `SECRET_KEY` | **Yes** | `str` | — | Cryptographic secret for signing JWT tokens (min 32 characters). |
| `ALGORITHM` | No | `str` | `HS256` | JWT signature algorithm. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | `int` | `60` | JWT Access token expiration lifetime in minutes. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | No | `int` | `7` | JWT Refresh token validity window in days. |
| `CORS_ORIGINS` | No | `list[str]` | `["http://localhost:3000","http://localhost:8080"]` | Allowed CORS origins. In production, wildcard `*` and `localhost` are rejected. |
| `ALLOWED_HOSTS` | No | `list[str]` | `["localhost","127.0.0.1"]` | Allowed HTTP `Host` header values validated by `TrustedHostMiddleware`. |

---

## 2. Database & Data Stores

| Variable | Required | Type | Default | Description |
|---|---|---|---|---|
| `DATABASE_URL` | **Yes** | `str` | `postgresql+asyncpg://basarat:password@localhost:5432/basarat` | Primary asynchronous PostgreSQL connection URL. |
| `DATABASE_URL_SYNC` | No | `str` | Auto-derived from `DATABASE_URL` (`postgresql+psycopg2://...`) | Synchronous connection string utilized by Celery workers & Alembic. |
| `CLOUD_DATABASE_URL` | Prod | `str` | — | Cloud-hosted database URL (e.g., Supabase / Managed Cloud PostgreSQL). |
| `POSTGRES_USER` | Docker | `str` | `basarat` | PostgreSQL username for local Docker Compose instance. |
| `POSTGRES_PASSWORD` | Docker | `str` | — | PostgreSQL password for local Docker Compose instance. |
| `POSTGRES_DB` | Docker | `str` | `basarat` | PostgreSQL database name for local Docker Compose instance. |

---

## 3. Redis & Caching Tier

| Variable | Required | Type | Default | Description |
|---|---|---|---|---|
| `REDIS_URL` | No | `str` | `redis://localhost:6379/0` | Primary Redis connection URI for application caching. |
| `CLOUD_REDIS_URL` | Prod | `str` | — | Managed cloud Redis connection URI (e.g. Upstash). |
| `REDIS_ENABLED` | No | `bool` | `true` | Toggle Redis caching layer. |
| `CACHE_TTL_SECONDS` | No | `int` | `300` | Default application cache TTL in seconds. |

---

## 4. Celery Distributed Task Processing

| Variable | Required | Type | Default | Description |
|---|---|---|---|---|
| `USE_CELERY` | No | `bool` | `true` | When `true`, dispatches background jobs via Celery worker queue. |
| `CELERY_BROKER_URL` | No | `str` | `redis://localhost:6379/1` | Redis database URI dedicated to Celery message broker. |
| `CELERY_RESULT_BACKEND` | No | `str` | `redis://localhost:6379/2` | Redis database URI dedicated to Celery task execution results. |

---

## 5. AI, ML & NLP Integrations

| Variable | Required | Type | Default | Description |
|---|---|---|---|---|
| `GROQ_API_KEY` | No | `str` | — | API authentication key for Groq Cloud LLM acceleration. |
| `GROQ_BASE_URL` | No | `str` | `https://api.groq.com/openai/v1` | OpenAI-compatible endpoint URL for Groq. |
| `GROQ_MODEL` | No | `str` | `llama-3.3-70b-versatile` | Primary large language model for AI Copilot chat. |
| `GROQ_FALLBACK_MODEL` | No | `str` | `llama-3.1-8b-instant` | Fallback model in case of primary model rate limiting. |
| `HF_API_TOKEN` | No | `str` | — | HuggingFace API token for FinBERT financial sentiment inference. |
| `GRU_MODEL_PATH` | No | `str` | `models/production/v3` | Local filesystem path to trained GRU model artifacts. |

---

## 6. External Messaging & Storage Services

| Variable | Required | Type | Default | Description |
|---|---|---|---|---|
| `SENDGRID_API_KEY` | No | `str` | — | SendGrid API key for transactional email and OTP dispatch. |
| `SENDGRID_FROM_EMAIL` | No | `str` | `noreply@basarat.com` | Verified sender email address for system emails. |
| `CLOUDINARY_CLOUD_NAME` | No | `str` | — | Cloudinary cloud account name. |
| `CLOUDINARY_API_KEY` | No | `str` | — | Cloudinary API access key for image management. |
| `CLOUDINARY_API_SECRET` | No | `str` | — | Cloudinary secret access key. |
| `FIREBASE_ENABLED` | No | `bool` | `false` | Enable Firebase Cloud Messaging for push notifications. |
| `FIREBASE_CREDENTIALS_PATH` | No | `str` | — | Filesystem path to Firebase Admin SDK service account JSON. |

---

## 7. Market Scraping & Pipeline Timing

| Variable | Required | Type | Default | Description |
|---|---|---|---|---|
| `MARKET_SESSION_REFRESH_SECONDS` | No | `int` | `60` | Interval between intraday live market quote snapshots. |
| `MARKET_QUOTES_TTL_SECONDS` | No | `int` | `90` | Cache retention TTL for live market quote lists in Redis. |
| `MARKET_CIRCUIT_BREAKER_SECONDS` | No | `int` | `900` | Circuit breaker pause duration upon upstream PSX 403/429 HTTP status. |
| `NEWS_INGESTION_INTERVAL_MARKET` | No | `int` | `1800` | News scrape interval during market hours (30 minutes). |
