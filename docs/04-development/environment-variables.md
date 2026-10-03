# Environment Variables

## Core Configuration

| Variable | Required | Purpose | Default | Sensitive |
|----------|----------|---------|---------|-----------|
| `PROJECT_NAME` | No | Application name | `Basarat` | No |
| `ENVIRONMENT` | No | Runtime environment | `development` | No |
| `DEBUG` | No | Debug mode | `false` | No |
| `SECRET_KEY` | **Yes** | JWT signing key (32+ chars) | — | **Yes** |
| `ALGORITHM` | No | JWT algorithm | `HS256` | No |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | Access token lifetime | `30` | No |
| `REFRESH_TOKEN_EXPIRE_DAYS` | No | Refresh token lifetime | `7` | No |

## Database

| Variable | Required | Purpose | Default | Sensitive |
|----------|----------|---------|---------|-----------|
| `DATABASE_URL` | Yes | Async PostgreSQL URL | `postgresql+asyncpg://...localhost...` | **Yes** |
| `DATABASE_URL_SYNC` | No | Sync PostgreSQL URL (auto-derived) | — | **Yes** |
| `CLOUD_DATABASE_URL` | Prod | Production database URL | — | **Yes** |
| `POSTGRES_USER` | Docker | Docker Compose DB user | `basarat` | No |
| `POSTGRES_PASSWORD` | Docker | Docker Compose DB password | — | **Yes** |
| `POSTGRES_DB` | Docker | Docker Compose DB name | `basarat` | No |

## Redis & Cache

| Variable | Required | Purpose | Default | Sensitive |
|----------|----------|---------|---------|-----------|
| `REDIS_URL` | No | Redis connection URL | `redis://localhost:6379/0` | **Yes** |
| `CLOUD_REDIS_URL` | Prod | Production Redis URL | — | **Yes** |
| `REDIS_ENABLED` | No | Enable Redis | `true` | No |
| `CACHE_TTL_SECONDS` | No | Default cache TTL | `300` | No |

## Celery

| Variable | Required | Purpose | Default | Sensitive |
|----------|----------|---------|---------|-----------|
| `USE_CELERY` | No | Enable Celery | `true` | No |
| `CELERY_BROKER_URL` | No | Celery broker URL | `redis://localhost:6379/1` | **Yes** |
| `CELERY_RESULT_BACKEND` | No | Celery result backend | `redis://localhost:6379/2` | **Yes** |

## External Services

| Variable | Required | Purpose | Default | Sensitive |
|----------|----------|---------|---------|-----------|
| `GROQ_API_KEY` | No | Groq LLM API key | — | **Yes** |
| `GROQ_BASE_URL` | No | Groq API base URL | `https://api.groq.com/openai/v1` | No |
| `GROQ_MODEL` | No | Primary LLM model | `openai/gpt-oss-20b` | No |
| `GROQ_FALLBACK_MODEL` | No | Fallback LLM model | `qwen/qwen3.8-27b` | No |
| `HF_API_TOKEN` | No | HuggingFace API token | — | **Yes** |
| `SENDGRID_API_KEY` | No | SendGrid email API key | — | **Yes** |
| `SENDGRID_FROM_EMAIL` | No | Sender email address | — | No |
| `CLOUDINARY_CLOUD_NAME` | No | Cloudinary cloud name | — | No |
| `CLOUDINARY_API_KEY` | No | Cloudinary API key | — | **Yes** |
| `CLOUDINARY_API_SECRET` | No | Cloudinary API secret | — | **Yes** |

## OAuth

| Variable | Required | Purpose | Default | Sensitive |
|----------|----------|---------|---------|-----------|
| `GOOGLE_CLIENT_ID` | No | Google OAuth client ID | — | No |
| `GOOGLE_CLIENT_SECRET` | No | Google OAuth secret | — | **Yes** |
| `APPLE_CLIENT_ID` | No | Apple service/bundle ID | — | No |
| `APPLE_TEAM_ID` | No | Apple team ID | — | No |
| `APPLE_KEY_ID` | No | Apple key ID | — | No |

## Firebase

| Variable | Required | Purpose | Default | Sensitive |
|----------|----------|---------|---------|-----------|
| `FIREBASE_ENABLED` | No | Enable FCM push | `false` | No |
| `FIREBASE_CREDENTIALS_PATH` | If enabled | Firebase service account JSON | — | **Yes** |
| `FIREBASE_PROJECT_ID` | If enabled | Firebase project ID | — | No |

## SMTP (Legacy/Alternative to SendGrid)

| Variable | Required | Purpose | Default | Sensitive |
|----------|----------|---------|---------|-----------|
| `SMTP_HOST` | No | SMTP server host | — | No |
| `SMTP_PORT` | No | SMTP port | `465` | No |
| `SMTP_USERNAME` | No | SMTP username | — | No |
| `SMTP_PASSWORD` | No | SMTP password | — | **Yes** |
| `SMTP_FROM_EMAIL` | No | Sender email | — | No |
| `PASSWORD_RESET_URL` | No | Deep link template | `basarat://reset-password?token={token}` | No |

## ML Configuration

| Variable | Required | Purpose | Default | Sensitive |
|----------|----------|---------|---------|-----------|
| `GRU_MODEL_PATH` | No | ML model artifacts path | `models/gru_v1` | No |
| `TRAINING_LOOKBACK_YEARS` | No | Training data window | `5` | No |
| `WINDOW_SIZE` | No | Feature window size | `30` | No |
| `LABEL_THRESHOLD` | No | Direction label threshold | `0.01` | No |

## Market Data

| Variable | Required | Purpose | Default | Sensitive |
|----------|----------|---------|---------|-----------|
| `MARKET_SESSION_REFRESH_SECONDS` | No | Quote refresh interval | `60` | No |
| `MARKET_QUOTES_TTL_SECONDS` | No | Redis quote TTL | `90` | No |
| `MARKET_CIRCUIT_BREAKER_SECONDS` | No | Scrape pause on PSX error | `900` | No |
| `NEWS_INGESTION_INTERVAL_MARKET` | No | News interval during market | `1800` | No |
