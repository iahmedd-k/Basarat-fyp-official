# Environment Variables & Configuration Reference — Basarat

## 1. Complete Environment Variable Matrix

This table catalogs all configuration variables parsed by `app.core.config.Settings`:

| Variable | Required | Purpose | Default Value | Sensitive | Used By |
|---|---|---|---|---|---|
| `PROJECT_NAME` | No | Display name of the application | `"Basarat"` | No | `main.py`, `email_service.py` |
| `API_V1_PREFIX` | No | URL prefix for versioned endpoints | `"/api/v1"` | No | `main.py`, all routers |
| `ENVIRONMENT` | No | Deployment tier (`development`, `staging`, `production`, `test`) | `"development"` | No | `main.py`, `config.py` |
| `DEBUG` | No | Enable verbose debug output (Must be `false` in production) | `False` | No | `main.py`, `config.py` |
| `SECRET_KEY` | **Yes** | 32+ character key used to sign and verify all JWT tokens | *None* | **Yes** | `security.py`, `authorization.py` |
| `ALGORITHM` | No | JWT cryptographic signing algorithm | `"HS256"` | No | `security.py` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | Expiration duration for access tokens | `30` | No | `security.py`, `auth_service.py` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | No | Expiration duration for refresh tokens | `7` | No | `security.py`, `auth_service.py` |
| `CORS_ORIGINS` | No | Allowed frontend origin list (JSON array; e.g. `["https://app.basarat.pk"]`) | `["*"]` | No | `main.py` |
| `TRUSTED_PROXY_IPS` | No | Whitelist of trusted upstream reverse proxy IP addresses | `[]` | No | `rate_limiter.py` |
| `DATABASE_URL` | **Yes** | Primary asynchronous PostgreSQL connection URL (`asyncpg`) | `postgresql+asyncpg://postgres:postgres@localhost:5432/basarat` | **Yes** | `base.py`, `session.py` |
| `DATABASE_URL_SYNC` | No | Synchronous PostgreSQL connection URL (`psycopg2`) for Alembic/Celery | Derived from `DATABASE_URL` | **Yes** | `database_urls.py`, `alembic` |
| `REDIS_URL` | No | Redis connection URL for query caching and live quote bus (DB 0) | `"redis://localhost:6379/0"` | **Yes** | `redis.py`, `market_live_bus.py` |
| `REDIS_ENABLED` | No | Master toggle for Redis caching | `True` | No | `redis_client.py` |
| `CACHE_TTL_SECONDS` | No | Default Time-To-Live for cached API query responses | `300` | No | `market_service.py`, `redis.py` |
| `USE_CELERY` | No | Toggle distributed Celery execution vs in-process task mode | `True` | No | `main.py`, `task_runner.py` |
| `CELERY_BROKER_URL` | No | Redis broker URL for task queues (DB 1) | `"redis://localhost:6379/1"` | **Yes** | `celery_app.py` |
| `CELERY_RESULT_BACKEND` | No | Redis backend URL for storing async task results (DB 2) | `"redis://localhost:6379/2"` | **Yes** | `celery_app.py` |
| `CLOUDINARY_CLOUD_NAME` | No | Cloudinary account name for community image hosting | `""` | No | `cloudinary_service.py` |
| `CLOUDINARY_API_KEY` | No | Cloudinary API Key | `""` | **Yes** | `cloudinary_service.py` |
| `CLOUDINARY_API_SECRET` | No | Cloudinary API Secret | `""` | **Yes** | `cloudinary_service.py` |
| `GROQ_API_KEY` | No | API Key for Groq Cloud LLM inference | `""` | **Yes** | `groq_client.py`, `assistant_service.py` |
| `GROQ_BASE_URL` | No | Groq API base URL endpoint | `"https://api.groq.com/openai/v1"` | No | `groq_client.py` |
| `GROQ_MODEL` | No | Primary LLM model identifier | `"openai/gpt-oss-20b"` | No | `groq_client.py`, `assistant_service.py` |
| `GROQ_FALLBACK_MODEL` | No | Fallback LLM model identifier if primary model is unavailable | `"qwen/qwen3.8-27b"` | No | `groq_client.py`, `assistant_service.py` |
| `HF_API_TOKEN` | No | HuggingFace API Token for FinBERT financial sentiment inference | `""` | **Yes** | `sentiment_service.py`, `sentiment_tasks.py` |
| `GOOGLE_CLIENT_ID` | No | Google Cloud OAuth 2.0 Web Client ID | `""` | No | `auth_service.py` |
| `GOOGLE_CLIENT_SECRET` | No | Google Cloud OAuth 2.0 Client Secret | `""` | **Yes** | `auth_service.py` |
| `APPLE_CLIENT_ID` | No | Apple Developer Service ID (e.g. `pk.basarat.app`) | `""` | No | `auth_service.py` |
| `APPLE_TEAM_ID` | No | Apple Developer Team ID | `""` | No | `auth_service.py` |
| `APPLE_KEY_ID` | No | Apple Sign-In Private Key ID | `""` | No | `auth_service.py` |
| `CLERK_WEBHOOK_SECRET` | No | HMAC Secret for validating Clerk authentication webhooks | `""` | **Yes** | `webhooks.py` |
| `SENDGRID_API_KEY` | No | API Key for SendGrid transactional email delivery | `""` | **Yes** | `email_service.py` |
| `SENDGRID_FROM_EMAIL` | No | Verified sender email address in SendGrid | `""` | No | `email_service.py` |
| `SMTP_HOST` | No | SMTP Server Hostname for transactional emails | `""` | No | `email_service.py` |
| `SMTP_PORT` | No | SMTP Port (default: `465` SSL / `587` TLS) | `465` | No | `email_service.py` |
| `SMTP_USERNAME` | No | SMTP authentication username | `""` | No | `email_service.py` |
| `SMTP_PASSWORD` | No | SMTP authentication password | `""` | **Yes** | `email_service.py` |
| `SMTP_FROM_EMAIL` | No | From email address for SMTP mailer | `""` | No | `email_service.py` |
| `SMTP_USE_TLS` | No | Use TLS encryption for SMTP connections | `True` | No | `email_service.py` |
| `PASSWORD_RESET_URL` | No | Base deep-link URL for password recovery links | `"basarat://reset-password?token={token}"` | No | `email_service.py` |
| `EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES`| No | Expiration time for signup 6-digit OTPs | `10` | No | `auth_service.py`, `email_service.py` |
| `PASSWORD_RESET_TOKEN_EXPIRE_MINUTES`| No | Expiration time for password-reset 6-digit OTPs | `10` | No | `auth_service.py` |
| `PASSWORD_RESET_GRANT_EXPIRE_MINUTES`| No | Expiration time for Step 2 JWT grant tokens | `15` | No | `auth_service.py`, `security.py` |
| `FIREBASE_ENABLED` | No | Master toggle for Firebase Cloud Messaging push notifications | `False` | No | `push_notifications.py` |
| `FIREBASE_CREDENTIALS_PATH` | No | Absolute path to Google Service Account JSON file | `""` | **Yes** | `push_notifications.py` |
| `FIREBASE_PROJECT_ID` | No | Google Firebase Project ID string | `""` | No | `push_notifications.py` |
| `GRU_MODEL_PATH` | No | Directory path to Attention-BiGRU model weights | `"models/gru_v1"` | No | `model_loader.py` |
| `NEWS_TIMEZONE` | No | Timezone for market scheduling and news windows | `"Asia/Karachi"` | No | `celery_app.py`, `scrape_news.py` |
| `MARKET_SESSION_REFRESH_SECONDS` | No | Celery cadence for scraping live quotes during trading hours | `60` | No | `celery_app.py`, `refresh_market_cache.py` |
| `MARKET_QUOTES_TTL_SECONDS` | No | Redis key TTL for live quote snapshots | `90` | No | `market_service.py`, `refresh_market_cache.py` |
| `MARKET_LIVE_PUBSUB_CHANNEL` | No | Redis Pub/Sub channel for live quote broadcasts | `"market:quotes:live"` | No | `market_live_bus.py`, `refresh_market_cache.py` |
| `MARKET_CIRCUIT_BREAKER_SECONDS` | No | Pause duration after receiving HTTP 429/403 from PSX | `900` (15 mins) | No | `market_service.py`, `refresh_market_cache.py` |
| `MAX_FILE_SIZE_MB` | No | Maximum allowed file upload size for community attachments | `10` | No | `community_service.py` |

---

## 2. Configuration Analysis & Discrepancy Findings

1. **Production Validation Rules:** `Settings.__init__` enforces that `SECRET_KEY` cannot be a default placeholder (e.g. `change-me-in-production`, `secret`), that `DEBUG` must be `False` in staging/production, and that `CORS_ORIGINS` must not contain wildcard `*` outside development.
2. **Synchronous URL Automatic Derivation:** If `DATABASE_URL_SYNC` is not explicitly declared, the system automatically converts `postgresql+asyncpg://` to `postgresql+psycopg2://` via [database_urls.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/core/database_urls.py).
3. **Optional Cloud Variables in `.env.example`:**
   - `AWS_ENDPOINT_URL_S3`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `NEON_AI_GATEWAY_TOKEN` are present in `.env.example` as optional cloud storage/gateway extensions but are not required for core API startup.
