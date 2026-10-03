# Deployment

## Target Environment
AWS EC2 instance running Docker containers.

## Deployment Architecture

```
GitHub Push (main) -> GitHub Actions CI/CD
  -> Test (pytest) -> Build Docker Image -> Push to AWS ECR
  -> Self-hosted Runner on EC2 -> Blue-Green Deploy
    -> Pull Image -> Run Migrations -> Start New Container
    -> Health Check -> Switch Nginx Proxy -> Stabilize
    -> Update Worker/Beat -> Ready Verification
```

## Backend Deployment

### Production Stack
- **API**: Uvicorn with 1 worker (`uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1`)
- **Worker**: Celery worker (`celery -A app.celery_app worker --concurrency=1 --max-tasks-per-child=1`)
- **Beat**: Celery Beat scheduler
- **Proxy**: Nginx reverse proxy (port 8000)
- **Database**: Supabase PostgreSQL (managed)
- **Redis**: Upstash Redis (managed) + local Redis (for Celery broker/pub-sub)

### Deployment Process
1. Push to `main` branch triggers GitHub Actions
2. CI runs tests (`tests/api` + `tests/unit`)
3. Docker image built and pushed to ECR (tagged with Git SHA)
4. Self-hosted runner downloads deployment bundle
5. `deploy-api.sh` executes blue-green deployment:
   - Runs `alembic upgrade head` via migrate container
   - Starts new API container on inactive slot
   - Verifies `/health` endpoint
   - Switches Nginx upstream
   - Verifies `/health` through proxy
   - Waits 60s stabilization
   - Updates worker and beat containers
   - Verifies `/health/ready`
   - Removes old API container

### Rollback
```bash
bash /opt/basarat/deploy/ec2/deploy-api.sh --rollback
```
Restores the previous API container and Nginx routing.

## Database Migrations
- Executed as a separate Docker container before API deployment
- Command: `alembic upgrade head`
- Uses `CLOUD_DATABASE_URL` for production

## Health Checks
- **Liveness**: `GET /health` -> `{"status": "ok"}`
- **Readiness**: `GET /health/ready` -> Checks DB, Redis, Celery Worker, Celery Beat
- Docker HEALTHCHECK: Polls `/health` every 30s
