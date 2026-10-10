# Deployment

## Target Environment
Oracle Cloud Infrastructure (OCI) Ubuntu Virtual Machine (`193.123.84.223`) serving production traffic via `https://api.basarat.live` with automated SSL and reverse proxying to Docker Compose containers.

- **Production API Gateway**: `https://api.basarat.live`
- **Interactive Swagger Documentation**: `https://api.basarat.live/docs`
- **Interactive Architecture Topology**: `https://api.basarat.live/architecture`
- **ReDoc Specification**: `https://api.basarat.live/redoc`

---

## Deployment Architecture

```
GitHub Push (main) ──► GitHub Actions CI/CD Pipeline
  │
  ├── 1. Automated Test Execution (pytest 627-test suite)
  ├── 2. Build Multi-Platform ARM64 Docker Image
  ├── 3. Publish to GitHub Container Registry (ghcr.io/iahmedd-k/basarat-backend:<sha>)
  └── 4. SSH Remote Trigger to Oracle VM
        ├── Pull Latest Docker Image
        ├── Execute Database Migrations (alembic upgrade head)
        ├── Launch / Restart API (basarat-app-1)
        ├── Restart Background Workers (basarat-celery-worker-1, basarat-celery-beat-1)
        └── Verify System Health Probes (/health & /api/v1/health/ready)
```

---

## Production Stack & Container Services

| Container Name | Base Image / Command | Exposed Ports | Health Status |
| :--- | :--- | :---: | :---: |
| `basarat-app-1` | `ghcr.io/iahmedd-k/basarat-backend:<sha>` (`uvicorn app.main:app --host 0.0.0.0 --port 8000`) | `8000:8000` | Healthy (Polls `/health`) |
| `basarat-celery-worker-1` | `ghcr.io/iahmedd-k/basarat-backend:<sha>` (`celery -A app.celery_app worker`) | Internal | Healthy |
| `basarat-celery-beat-1` | `ghcr.io/iahmedd-k/basarat-backend:<sha>` (`celery -A app.celery_app beat`) | Internal | Healthy |
| `basarat-migrate-1` | `ghcr.io/iahmedd-k/basarat-backend:<sha>` (`alembic upgrade head`) | N/A | Exited `0` (One-off migration) |
| `basarat-redis-1` | `redis:7-alpine` | `6379:6379` | Healthy |

---

## Remote Access & Management

```bash
# SSH into production Oracle VM
ssh -i "d:\FYP\OrcaleSecrets\ssh-key-2026-10-03.key" ubuntu@193.123.84.223

# Check container status
docker ps

# Inspect API logs in real-time
docker logs -f basarat-app-1

# Inspect Celery worker & periodic task logs
docker logs -f basarat-celery-worker-1
docker logs -f basarat-celery-beat-1
```

---

## Health & Readiness Endpoints

- **Liveness Probe**: `GET https://api.basarat.live/health` $\to$ `{"status": "ok"}`
- **Readiness Probe**: `GET https://api.basarat.live/api/v1/health/ready` $\to$ Checks DB connection, Redis ping, Celery worker heartbeat, Celery beat scheduler, and ML model loaded states.
