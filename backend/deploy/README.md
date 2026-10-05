# Production Deployment Specifications (Oracle Cloud Infrastructure)

This directory documents the production deployment architecture for the Basarat backend on **Oracle Cloud Infrastructure (OCI)**.

---

## 1. Active Production Topology

The production stack runs on an **Oracle Cloud Ampere A1 ARM64 Ubuntu VM (`193.123.84.223`)** using **Docker Compose v2**.

```
Client (Android Mobile / Web)
     │
     ▼ (Port 8000)
FastAPI Application Container (`basarat-app-1`)
     │
     ├── In-Memory Store: Redis 7 Container (`basarat-redis-1`)
     ├── Asynchronous Tasks: Celery Worker Container (`basarat-celery-worker-1`)
     ├── Periodic Scheduler: Celery Beat Container (`basarat-celery-beat-1`)
     ├── Cloud Database: Managed PostgreSQL 16
     └── Cloud AI: Groq Cloud (Llama 3.3 70B) & HuggingFace FinBERT
```

> **Direct Port Binding**: The FastAPI application container runs Uvicorn ASGI directly bound to host port `8000:8000`. No external Nginx reverse proxy layer is deployed on the host.

---

## 2. Core Deployment Files

| File | Purpose |
|---|---|
| [`docker-compose.production.yml`](file:///d:/FYP/Basarat-fyp-official/backend/docker-compose.production.yml) | Production multi-container orchestration definition |
| [`dockerfile`](file:///d:/FYP/Basarat-fyp-official/backend/dockerfile) | Multi-stage Dockerfile packaging FastAPI and ML models (`models/production/v3/`) |
| [`.github/workflows/deploy-oracle.yml`](file:///d:/FYP/Basarat-fyp-official/.github/workflows/deploy-oracle.yml) | Automated CI/CD workflow pushing ARM64 container to GHCR and triggering SSH deploy |
| [`docs/07-deployment/oracle-deployment.md`](file:///d:/FYP/Basarat-fyp-official/docs/07-deployment/oracle-deployment.md) | Step-by-step production runbook and VM preparation guide |

---

## 3. Archived Scripts (`deploy/archive/`)

Legacy deployment configurations from earlier AWS EC2 and Nginx setups have been organized into [`deploy/archive/`](file:///d:/FYP/Basarat-fyp-official/backend/deploy/archive/):
- `deploy/archive/ec2/`: Previous AWS EC2 blue-green bash deployment scripts.
- `deploy/archive/nginx/`: Previous Nginx reverse proxy and logrotate templates.
