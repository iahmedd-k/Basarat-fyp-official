# Local Development Setup Guide — Basarat

## 1. Prerequisites & System Requirements

Ensure the following runtimes and tools are installed:

- **Python:** Version `3.11.x` (Recommended: `3.11.9`).
- **Node.js:** Version `18.x` or `20.x` LTS with `npm`.
- **Docker & Docker Compose:** Docker Desktop (Windows/macOS) or Docker Engine + Compose v2 (Linux).
- **Git:** For source control.
- **OpenSSL / Terminal:** For generating secrets.

---

## 2. Step-by-Step Backend Setup

### Step 2.1: Clone the Repository & Navigate to Backend
```bash
git clone https://github.com/iahmedd-k/Basarat-fyp-official.git
cd Basarat-fyp-official/backend
```

### Step 2.2: Create and Activate a Python Virtual Environment
```bash
# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Linux / macOS (Bash/Zsh)
python3 -m venv venv
source venv/bin/activate
```

### Step 2.3: Install Backend Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-test.txt
```

### Step 2.4: Configure Environment Variables
Copy the example environment template and configure required secrets:
```bash
cp .env.example .env
```

Generate a secure 32-character secret key and set it in `.env`:
```bash
# Generate secret key
openssl rand -hex 32
```
Edit `backend/.env` and update:
```ini
PROJECT_NAME=Basarat
ENVIRONMENT=development
DEBUG=true
SECRET_KEY=your_generated_32_character_hex_secret_here

DATABASE_URL=postgresql+asyncpg://ahmed:adminadmin@localhost:5432/basarat
DATABASE_URL_SYNC=postgresql+psycopg2://ahmed:adminadmin@localhost:5432/basarat
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
```

---

## 3. Starting Local Database & Redis (Docker Compose)

Start PostgreSQL 16 and Redis 7 in detached mode:
```bash
# Inside backend/ directory
docker compose up -d db redis
```

Verify that both containers are healthy:
```bash
docker compose ps
```

---

## 4. Database Migrations (Alembic)

Apply all schema migrations to create tables and indexes:
```bash
# Ensure virtualenv is active
alembic upgrade head
```

To verify the current migration state:
```bash
alembic current
```

---

## 5. Running the Backend Services

### 5.1 Run the FastAPI Application Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
The API is now live at:
- **API Base:** `http://localhost:8000/api/v1`
- **Interactive Swagger Docs:** `http://localhost:8000/docs`
- **ReDoc Documentation:** `http://localhost:8000/redoc`

### 5.2 Run Celery Worker (In a Separate Terminal)
```bash
# Ensure virtualenv is active
celery -A app.celery_app worker --loglevel=info --concurrency=2
```

### 5.3 Run Celery Beat Scheduler (In a Separate Terminal)
```bash
# Ensure virtualenv is active
celery -A app.celery_app beat --loglevel=info
```

---

## 6. Frontend Setup (React + Vite)

### Step 6.1: Navigate to Frontend & Install Dependencies
Open a new terminal:
```bash
cd Basarat-fyp-official/frontend
npm install
```

### Step 6.2: Configure Frontend Environment Variables
```bash
cp .env.example .env
```
Ensure `VITE_API_URL` points to your local backend:
```ini
VITE_API_URL=http://localhost:8000/api/v1
```

### Step 6.3: Start Frontend Dev Server
```bash
npm run dev
```
The frontend web application is now accessible at `http://localhost:5173`.

---

## 7. Running Tests & Quality Checks

### 7.1 Backend Test Suite (Pytest)
Run all unit, API, integration, and security tests:
```bash
# Inside backend/ directory with venv active
pytest
```

Run specific test modules:
```bash
# Run API endpoint tests
pytest tests/api/

# Run security & authentication tests
pytest tests/security/

# Run unit tests
pytest tests/unit/
```

### 7.2 Linting & Code Formatting
```bash
# Backend linting with Ruff
ruff check .

# Frontend linting with Oxlint
cd ../frontend
npx oxlint
```
