# Configuration & Environment Management — Basarat

## 1. Configuration Architecture

Basarat manages application settings through **Pydantic v2 `BaseSettings`** in [app/core/config.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/core/config.py). Configuration is loaded in the following priority order:

1. System Environment Variables (Highest priority).
2. `.env` file located in the application root directory (`backend/.env`).
3. Default values defined in the `Settings` class definition (Lowest priority).

---

## 2. Configuration Differences Across Environments

| Configuration Key | Development | Testing (`pytest`) | Staging | Production |
|---|---|---|---|---|
| `ENVIRONMENT` | `"development"` | `"test"` | `"staging"` | `"production"` |
| `DEBUG` | `True` | `False` | `False` (Enforced) | `False` (Enforced) |
| `SECRET_KEY` | Dev Hex Key | Static Test Secret Key | 32+ char strong random hex | 64+ char cryptographically generated hex |
| `CORS_ORIGINS` | `["*"]` (Wildcard allowed) | `["*"]` | Explicit domain list (No `*`) | Explicit domain list (No `*`) |
| `DATABASE_URL` | Local PostgreSQL (localhost:5432) | Ephemeral / Test PostgreSQL | Managed Cloud DB (SSL enabled) | Managed Cloud DB (SSL enabled) |
| `REDIS_URL` | Local Redis (localhost:6379/0) | Mock Redis / Test Redis | Managed Upstash Redis (TLS) | Managed Upstash Redis (TLS) |
| `USE_CELERY` | `True` / `False` | `False` (In-process mock) | `True` | `True` |
| `FIREBASE_ENABLED`| `False` | `False` | `False` / `True` | `True` (with valid service account) |
| `SENDGRID_API_KEY`| Optional / Empty | Mocked | Real Staging Key | Verified Production API Key |
| `GROQ_MODEL` | `"openai/gpt-oss-20b"` | Mocked / Fast model | `"qwen/qwen3.8-27b"` | `"qwen/qwen3.8-27b"` |

---

## 3. Dangerous Production Misconfigurations (Startup Blockers)

To prevent security oversights from reaching production, `Settings.__init__` executes strict startup validation assertions:

### 3.1 Insecure `SECRET_KEY` Check
If `SECRET_KEY` matches known placeholder strings (`"change-me-in-production"`, `"secret"`, `"changeme"`, `"your-secret-key"`, `"dev-secret"`), application startup crashes immediately with:
```text
ValueError: SECRET_KEY must be set to a strong random value (32+ chars) in production. Generate with: openssl rand -hex 32
```

### 3.2 Wildcard CORS Disallowance
If `ENVIRONMENT` is `"staging"` or `"production"` and `CORS_ORIGINS` contains wildcard `*` or is empty, startup halts:
```text
ValueError: CORS_ORIGINS must be an explicit allowlist outside development (no '*')
```

### 3.3 Default Database Credential Check
If `ENVIRONMENT` is `"staging"` or `"production"` and `DATABASE_URL` contains development credentials (e.g., `postgres:postgres@` or `adminadmin`), startup halts:
```text
ValueError: DATABASE_URL must not use development credentials outside development
```

### 3.4 Debug Mode Prohibition
If `ENVIRONMENT` is outside `"development"` and `DEBUG` is `True`, startup halts:
```text
ValueError: DEBUG must be false outside development
```

---

## 4. Production Configuration Template (`backend/.env.production`)

```ini
# Production System Configuration
PROJECT_NAME=Basarat
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=e83a9f71c42b08d591e4a6f72c0d8b1395e7a4f62c0d8b1395e7a4f62c0d8b13
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Explicit Domain Allowlist (No Wildcards)
CORS_ORIGINS=["https://app.basarat.pk","https://basarat.pk"]
TRUSTED_PROXY_IPS=["127.0.0.1","172.31.0.0/16"]

# Managed Database (Supabase / Neon / RDS)
DATABASE_URL=postgresql+asyncpg://basarat_prod:EncryptedPassword123!@ep-db.us-east-2.aws.neon.tech/basarat?sslmode=require
DATABASE_URL_SYNC=postgresql+psycopg2://basarat_prod:EncryptedPassword123!@ep-db.us-east-2.aws.neon.tech/basarat?sslmode=require

# Managed Cache & Broker (Upstash / ElastiCache)
REDIS_URL=rediss://default:UpstashToken123@endpoint.upstash.io:6379/0
CELERY_BROKER_URL=rediss://default:UpstashToken123@endpoint.upstash.io:6379/0?ssl_cert_reqs=required
CELERY_RESULT_BACKEND=rediss://default:UpstashToken123@endpoint.upstash.io:6379/0?ssl_cert_reqs=required
USE_CELERY=true

# AI & NLP Cloud Credentials
GROQ_API_KEY=gsk_live_production_key_here
GROQ_MODEL=qwen/qwen3.8-27b
HF_API_TOKEN=hf_live_token_here

# Transactional Email (SendGrid)
SENDGRID_API_KEY=SG.live_production_sendgrid_key_here
SENDGRID_FROM_EMAIL=auth@basarat.pk
PASSWORD_RESET_URL=https://app.basarat.pk/reset-password?token={token}

# Media Cloud Storage
CLOUDINARY_CLOUD_NAME=basarat-prod
CLOUDINARY_API_KEY=123456789012345
CLOUDINARY_API_SECRET=live_cloudinary_secret_here

# Mobile Push Notifications (FCM)
FIREBASE_ENABLED=true
FIREBASE_CREDENTIALS_PATH=/opt/basarat/secrets/firebase-service-account.json
FIREBASE_PROJECT_ID=basarat-production
```
