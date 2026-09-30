# Deployment Architecture & Runbook — Basarat

## 1. Target Deployment Architecture

Basarat is engineered to deploy across both self-hosted Linux container hosts (AWS EC2 / Ubuntu LTS) and containerized orchestration platforms using **Docker** and **Docker Compose**.

```mermaid
flowchart TD
    subgraph Host["Production Host (AWS EC2 / Ubuntu 22.04 LTS)"]
        subgraph MigrationJob["1. Pre-Flight Migration Service"]
            Migrate["basarat-migrate Container<br/>(alembic upgrade head)"]
        end

        subgraph CoreServices["2. Core Container Services (depends_on: migrate success)"]
            APIApp["basarat-api Container<br/>(Uvicorn ASGI Server :8000)"]
            Worker["basarat-celery-worker Container<br/>(Celery Distributed Worker)"]
            Beat["basarat-celery-beat Container<br/>(Celery Beat Cron Daemon)"]
        end

        subgraph Volumes["Persistent Host Volumes"]
            VolMarket["market-data (/app/data/raw/ohlcv)"]
            VolFeatures["feature-data (/app/data/features)"]
            VolGRU["gru-candidates (/app/models/gru_candidate)"]
            VolXGB["xgb-candidates (/app/models/xgb_candidate)"]
            VolBeat["beat-state (/var/lib/celery)"]
            VolReports["training-reports (/app/data/reports)"]
        end
    end

    subgraph ManagedCloud["Managed Cloud Data Layer"]
        CloudPostgres[(Supabase / RDS PostgreSQL 16)]
        CloudRedis[(Upstash / Managed Redis 7)]
    end

    Migrate -->|Alembic Sync DDL| CloudPostgres
    MigrationJob -->|Exit 0| CoreServices

    APIApp <-->|Async Queries (asyncpg)| CloudPostgres
    APIApp <-->|Cache & PubSub Bus| CloudRedis
    Worker <-->|Task Broker & Backend| CloudRedis
    Worker -->|Sync Queries (psycopg2)| CloudPostgres
    Beat -->|Publishes Scheduled Crons| CloudRedis

    APIApp --- VolMarket
    APIApp --- VolFeatures
    Worker --- VolMarket
    Worker --- VolFeatures
    Worker --- VolGRU
    Worker --- VolXGB
    Worker --- VolReports
    Beat --- VolBeat
```

---

## 2. Production Composition (`docker-compose.production.yml`)

The production deployment manifest defines four coordinated services:

### 2.1 Service 1: `migrate` (One-Shot Schema Migration)
- **Image:** `basarat-backend:latest`
- **Command:** `alembic upgrade head`
- **Restart Policy:** `"no"`
- **Behavior:** Executes all pending database schema migrations before starting web or worker containers. All downstream services declare `depends_on: { migrate: { condition: service_completed_successfully } }`.

### 2.2 Service 2: `app` (FastAPI Web Server)
- **Command:** `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1`
- **Ports:** Bound to host port `8000:8000`.
- **Restart Policy:** `unless-stopped`
- **Health Probe:** `/api/v1/health` and `/health`.

### 2.3 Service 3: `celery-worker` (Async Task Worker)
- **Command:** `celery -A app.celery_app worker --loglevel=info --concurrency=1 --max-tasks-per-child=1`
- **Memory Guard:** `--max-tasks-per-child=1` recycles worker sub-processes after heavy ML retraining and Pandas calculations to prevent memory leaks.

### 2.4 Service 4: `celery-beat` (Cron Scheduler Daemon)
- **Command:** `celery -A app.celery_app beat --loglevel=info --schedule=/var/lib/celery/celerybeat-schedule`
- **State Persistence:** Preserves beat cron schedules in named volume `beat-state`.

---

## 3. Production Deployment Step-by-Step Runbook

### Step 1: Provision Host & Ensure Prerequisites
On the target EC2 Linux instance:
```bash
sudo apt update && sudo apt install -y docker.io docker-compose-v2 rsync curl
sudo usermod -aG docker $USER
```

### Step 2: Configure Production Environment Variables
Create `/opt/basarat/backend/.env`:
```ini
PROJECT_NAME=Basarat
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=generate_64_character_hex_secret_here

CLOUD_DATABASE_URL=postgresql+asyncpg://user:pass@ep-cool-pool.us-east-2.aws.neon.tech/basarat?sslmode=require
DATABASE_URL=postgresql+asyncpg://user:pass@ep-cool-pool.us-east-2.aws.neon.tech/basarat?sslmode=require
REDIS_URL=rediss://default:password@upstash-redis-endpoint:6379/0
CELERY_BROKER_URL=rediss://default:password@upstash-redis-endpoint:6379/0?ssl_cert_reqs=required
CELERY_RESULT_BACKEND=rediss://default:password@upstash-redis-endpoint:6379/0?ssl_cert_reqs=required

CORS_ORIGINS=["https://app.basarat.pk","https://basarat.pk"]
GROQ_API_KEY=gsk_your_groq_production_key
GROQ_MODEL=qwen/qwen3.8-27b
SENDGRID_API_KEY=SG.your_sendgrid_key
SENDGRID_FROM_EMAIL=auth@basarat.pk
```

### Step 3: Build and Deploy the Container Stack
```bash
cd /opt/basarat/backend
docker compose -f docker-compose.production.yml config --quiet
docker compose -f docker-compose.production.yml up -d --build
```

### Step 4: Verify Deployment Health
```bash
# Verify container states
docker compose -f docker-compose.production.yml ps

# Verify API health endpoint (retry up to 12 times with 5s delay)
curl --fail http://127.0.0.1:8000/api/v1/health
```

---

## 4. Rollback & Disaster Recovery Procedures

If a deployment fails the health check probe:

```bash
# 1. Inspect failed container logs
docker compose -f docker-compose.production.yml logs --tail 100 app
docker compose -f docker-compose.production.yml logs --tail 100 migrate

# 2. Rollback to previous Docker image tag
docker tag basarat-backend:previous basarat-backend:latest
docker compose -f docker-compose.production.yml up -d

# 3. Rollback database migration if needed (Alembic step-down)
docker run --rm --env-file .env basarat-backend:latest alembic downgrade -1
```
