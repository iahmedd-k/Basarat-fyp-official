# CI/CD & Deployment Automation — Basarat

## 1. Existing CI/CD Pipeline (`.github/workflows/deploy-ec2.yml`)

The repository includes an active automated continuous deployment workflow targeting a self-hosted AWS EC2 deployment runner.

```mermaid
sequenceDiagram
    autonumber
    actor Dev as Developer
    participant Git as GitHub (main branch)
    participant Runner as Self-Hosted EC2 Runner
    participant Host as /opt/basarat/ Filesystem
    participant Docker as Docker Engine & Compose
    participant Health as Health Probe (curl :8000/health)

    Dev->>Git: git push origin main
    Git->>Runner: Trigger "Deploy to Basarat EC2"
    Runner->>Runner: Check out main branch
    Runner->>Host: rsync application files (exclude .git, .env)
    Runner->>Docker: Verify Docker Compose & Buildx versions
    Runner->>Docker: docker compose -f docker-compose.production.yml up -d --build
    Docker->>Docker: Run alembic migration container -> Start API, Worker, Beat
    Runner->>Health: curl --fail --retry 12 --retry-delay 5 http://127.0.0.1:8000/health
    alt Health Check Passes
        Health-->>Runner: 200 OK
        Runner-->>Git: Workflow Success (Exit 0)
    else Health Check Fails
        Health-->>Runner: Failure / Timeout
        Runner->>Docker: docker inspect (State, OOMKilled, ExitCode)
        Runner-->>Git: Workflow Failure (Exit 1)
    end
```

---

## 2. Workflow Stage Breakdown

### 2.1 Trigger & Concurrency Controls
- **Triggers:** Automatic execution on `push` to `main` branch, or manual trigger via `workflow_dispatch`.
- **Concurrency Group:** `concurrency: { group: basarat-production, cancel-in-progress: false }` ensures that deployments do not overlap or corrupt in-flight migrations.

### 2.2 Execution Steps
1. **Source Synchronization:** Uses `rsync` to synchronize repository files to `/opt/basarat/`, safely preserving the host's existing `/opt/basarat/backend/.env` file.
2. **Tooling Verification:** Checks and automatically downloads verified binaries for Docker Compose (`v5.5.0`) and Docker Buildx (`v0.37.1`) with SHA-256 checksum verification.
3. **Configuration Sanity Check:** Verifies `/opt/basarat/backend/.env` exists and injects runtime model parameters (`GROQ_MODEL=qwen/qwen3.8-27b`).
4. **Stack Build & Startup:** Executes `docker compose -f docker-compose.production.yml up -d --build --parallel 1`.
5. **Automated Health Check Verification:** Executes up to 12 automated HTTP health probe retries (5-second intervals) against `http://127.0.0.1:8000/health`.
6. **Failure Diagnosis:** If the probe fails, inspects container exit states, restarts, and `OOMKilled` flags for immediate debugging before failing the workflow.

---

## 3. Recommended Multi-Stage Enterprise CI/CD Pipeline

The current workflow focuses primarily on deployment (`CD`). To establish full enterprise test automation, the following multi-stage CI pipeline is recommended:

```mermaid
flowchart LR
    subgraph CI["1. Continuous Integration (GitHub-Hosted Runner)"]
        Lint["Lint & Format<br/>(Ruff & Oxlint)"]
        Test["Automated Tests<br/>(Pytest on Postgres/Redis Services)"]
        Build["Docker Image Build<br/>(Buildx Cache)"]
    end

    subgraph CD["2. Continuous Deployment (Self-Hosted Runner)"]
        DeployStaging["Deploy to Staging"]
        SmokeTest["Staging Smoke Test"]
        DeployProd["Promote to Production"]
    end

    Lint --> Test --> Build --> DeployStaging --> SmokeTest --> DeployProd
```

### Recommended `.github/workflows/ci.yml` Structure:
```yaml
name: Continuous Integration & Automated Tests

on:
  pull_request:
    branches: [main, develop]
  push:
    branches: [develop]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: password
          POSTGRES_DB: basarat_test
        ports: ["5432:5432"]
        options: >-
          --health-cmd pg_isready
          --health-interval 5s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7-alpine
        ports: ["6379:6379"]
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Install Dependencies
        run: |
          pip install -r backend/requirements.txt
          pip install -r backend/requirements-test.txt

      - name: Run Ruff Linter
        run: ruff check backend/

      - name: Run Alembic Migrations
        run: |
          cd backend
          alembic upgrade head
        env:
          DATABASE_URL_SYNC: postgresql+psycopg2://postgres:password@localhost:5432/basarat_test

      - name: Run Pytest Suite
        run: |
          cd backend
          pytest
        env:
          SECRET_KEY: test_secret_key_minimum_32_characters_long_12345
          DATABASE_URL: postgresql+asyncpg://postgres:password@localhost:5432/basarat_test
          REDIS_URL: redis://localhost:6379/0
          USE_CELERY: false
```
