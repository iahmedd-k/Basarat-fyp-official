PYTHON ?= python
COMPOSE ?= docker compose

.PHONY: help install install-test test test-all run compose-up compose-down monitoring-up monitoring-down

help:
	@echo "Basarat project commands:"
	@echo "  make install       Install backend runtime dependencies"
	@echo "  make install-test  Install runtime and test dependencies"
	@echo "  make test          Run backend unit tests (same scope as CI)"
	@echo "  make test-all      Run the complete backend test suite"
	@echo "  make run           Run the backend API with auto-reload"
	@echo "  make compose-up    Start the local Docker Compose stack"
	@echo "  make compose-down  Stop the local Docker Compose stack"
	@echo "  make monitoring-up Start the local stack with Prometheus and Grafana"
	@echo "  make monitoring-down Stop the local stack and monitoring services"

install:
	cd backend && $(PYTHON) -m pip install -r requirements.txt

install-test:
	cd backend && $(PYTHON) -m pip install -r requirements.txt pytest pytest-asyncio aiosqlite "xgboost>=2.0,<4"

test:
	cd backend && $(PYTHON) -m pytest tests/unit -q

test-all:
	cd backend && $(PYTHON) -m pytest -q

run:
	cd backend && $(PYTHON) -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

compose-up:
	cd backend && $(COMPOSE) up --build

compose-down:
	cd backend && $(COMPOSE) down

monitoring-up:
	cd backend && $(COMPOSE) -f docker-compose.yml -f docker-compose.monitoring.yml up --build -d

monitoring-down:
	cd backend && $(COMPOSE) -f docker-compose.yml -f docker-compose.monitoring.yml down
