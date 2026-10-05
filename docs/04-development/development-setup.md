# Development Setup

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11.9 | Runtime |
| Docker Desktop | Latest | Containers for PostgreSQL, Redis |
| Git | Latest | Version control |
| pip | Latest | Package management |

## Quick Start with Docker Compose

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd Basarat-fyp-official/backend
   ```

2. **Create environment file:**
   ```bash
   cp .env.example .env
   # Edit .env and set required values:
   # - SECRET_KEY (generate with: openssl rand -hex 32)
   # - POSTGRES_PASSWORD (any local-only password)
   ```

3. **Start all services:**
   ```bash
   docker compose up --build -d
   ```
   This starts: API (port 8000), Celery Worker, Celery Beat, PostgreSQL (port 5432), Redis (port 6379).

4. **Run database migrations:**
   ```bash
   docker compose exec app alembic upgrade head
   ```

5. **Access the API:**
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc
   - Health: http://localhost:8000/health

## Local Development (without Docker)

1. **Create virtual environment:**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   source .venv/bin/activate  # Linux/Mac
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Start PostgreSQL and Redis locally** (or via Docker):
   ```bash
   docker run -d --name pg -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:16-alpine
   docker run -d --name redis -p 6379:6379 redis:7-alpine
   ```

4. **Run migrations:**
   ```bash
   alembic upgrade head
   ```

5. **Start the API server:**
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

6. **Start Celery worker (separate terminal):**
   ```bash
   celery -A app.celery_app worker --loglevel=info
   ```

7. **Start Celery Beat (separate terminal):**
   ```bash
   celery -A app.celery_app beat --loglevel=info
   ```

## Running Tests

```bash
# All tests
python -m pytest

# API tests only
python -m pytest tests/api -q

# Unit tests only
python -m pytest tests/unit -q

# With specific markers
python -m pytest -m unit
python -m pytest -m api
```

## Seed Data & Demo Credentials

For local development, API testing, and live FYP demonstrations, use the pre-configured verified credentials:

| Role | Email | Username | Password | Status & Fixtures |
|---|---|---|---|---|
| **Admin** | `admin@basarat.pk` | `admin_master` | `TestPassword12345!` | `is_admin=True`, `is_verified=True` |
| **Demo User 1** | `trader1@basarat.pk` | `trader_one` | `TestPassword12345!` | `is_verified=True`, Pre-seeded portfolio (`SYS`, `OGDC`, `HUBC`, `ENGRO`, `MEBL`) |
| **Demo User 2** | `trader2@basarat.pk` | `trader_two` | `TestPassword12345!` | `is_verified=True`, Community testing user |

### Running Seed Scripts

```bash
# Seed all demo users and sample portfolio fixtures (Recommended)
python -m scripts.seed_demo_users

# Seed only the administrator user
python scripts/seed_admin.py

# Initialize database tables and relations
python scripts/init_db_tables.py
```

