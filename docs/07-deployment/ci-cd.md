# CI/CD Pipeline

## Overview

The project uses GitHub Actions for automated continuous integration, testing, Docker image packaging, and deployment to **Oracle Cloud Infrastructure (OCI)**.

**Primary Deployment Workflow:** `.github/workflows/deploy-oracle.yml`  
**Automated CI PR Validation:** `.github/workflows/backend-ci.yml`

## Pipeline Triggers
- Push to `main` branch
- Pull Requests to `main`
- Manual trigger (`workflow_dispatch`)

## Pipeline Stages

### Stage 1: Automated Testing & Validation (`test`)
Runs on: `ubuntu-latest`  
Timeout: 30 minutes

| Step | Action | Description |
|---|---|---|
| 1. Python Environment Setup | Python 3.11 with pip cache | Installs backend dependencies from `requirements.txt` |
| 2. Bytecode Compilation | `python -m compileall -q backend/app` | Validates Python syntax across all 25 domain modules |
| 3. Alembic Graph Integrity | `alembic heads` | Asserts exactly 1 linear migration head |
| 4. Pytest Test Suite | `pytest tests/unit/` | Runs all unit and schema validation tests |
| 5. Compose Syntax Validation | `docker compose -f docker-compose.production.yml config` | Validates production container topology |

### Stage 2: Multi-Platform Image Packaging (`build-and-push`)
Runs on: `ubuntu-latest`  
Target Architecture: `linux/arm64` (Native for Oracle Ampere A1)

| Step | Action | Description |
|---|---|---|
| 1. QEMU & Docker Buildx | Multi-arch emulation | Configures native ARM64 container build |
| 2. GHCR Authentication | `ghcr.io` Login | Authenticates using scoped `GITHUB_TOKEN` (`packages: write`) |
| 3. Build & Publish Image | `docker buildx build --platform linux/arm64` | Publishes `ghcr.io/iahmedd-k/basarat-backend:<commit_sha>` |

### Stage 3: Remote Oracle VM Cutover (`deploy`)
Target Host: `https://api.basarat.live` (`193.123.84.223`, Oracle Cloud Infrastructure)  
Environment: `oracle-production`

| Step | Action | Description |
|---|---|---|
| 1. Secure SSH Connection | SSH Key Auth | Authenticates with `ORACLE_HOST` using `ORACLE_SSH_PRIVATE_KEY` |
| 2. GHCR Pull on Host | `docker pull` | Pulls immutable SHA-tagged ARM64 container image |
| 3. Database Migration | `alembic upgrade head` | Runs one-off database migration container (`basarat-migrate-1`) |
| 4. Fleet Restart | `docker compose up -d` | Restarts API (`basarat-app-1`), Celery worker, and Celery beat |
| 5. Health Probe Verification | `https://api.basarat.live/health` & `/api/v1/health/ready` | Polls readiness probe until status is healthy |

## Security & Secrets Management
- **No Secrets in Code**: Environment secrets (`ORACLE_SSH_PRIVATE_KEY`, `CLOUD_DATABASE_URL`, `SECRET_KEY`) are managed via GitHub Actions Secrets and runtime `.env`.
- **Immutable Container Tagging**: Every build is tagged with the exact 40-character Git Commit SHA; mutable `:latest` tags are restricted.
- **Role Isolation**: Celery workers run with worker-only queue bindings; API runs unprivileged.
