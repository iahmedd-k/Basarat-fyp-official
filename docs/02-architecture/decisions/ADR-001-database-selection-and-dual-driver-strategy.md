# ADR-001: PostgreSQL Relational Database & Dual-Driver Strategy

## Status
**Accepted / Implemented**

## Context
Basarat requires a robust, ACID-compliant database capable of storing complex relational financial entities (users, portfolios, transactions, watchlists, community posts, audit logs) and handling concurrent asynchronous API requests alongside heavy synchronous background analytics (Celery jobs, daily ML feature generation, Alembic migrations).

Python database drivers present a challenge: asynchronous web frameworks like FastAPI thrive on `asyncpg` for non-blocking I/O, whereas task runners like Celery and migration tools like Alembic run synchronously and require standard DB-API drivers like `psycopg2`.

## Decision
1. Adopt **PostgreSQL 16** as the central relational datastore.
2. Use **SQLAlchemy 2.0** as the unified ORM with declarative mapping across the entire system.
3. Implement a **Dual-Driver Configuration**:
   - Primary `DATABASE_URL` uses `postgresql+asyncpg://...` for the FastAPI web server.
   - Derived `DATABASE_URL_SYNC` uses `postgresql+psycopg2://...` for Alembic migrations and synchronous Celery task workers.
   - Derive the synchronous URL automatically in [database_urls.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/core/database_urls.py) if omitted from environment variables.

## Alternatives Considered
- **MongoDB / NoSQL:** Rejected due to lack of strict relational constraints, foreign keys, and complex ACID transaction guarantees needed for financial portfolios and transaction ledgers.
- **Single Synchronous Driver (psycopg2 for all):** Rejected because blocking I/O would degrade FastAPI concurrency and WebSocket connection scaling.
- **Single Asynchronous Driver (asyncpg for Celery/Alembic):** Rejected because Celery tasks and Alembic's core runner operate synchronously, and forcing `async_to_sync` bridges introduces deadlocks and connection pooling fragility.

## Consequences
- **Positive:** Maximum API throughput and concurrency using `asyncpg`; completely stable Alembic migrations and Celery tasks using `psycopg2`.
- **Negative / Trade-off:** Developers must be mindful when writing database access code (using `AsyncSession` in API routes and standard synchronous sessions in standalone Celery worker tasks).

## Current Implementation
- Configured in [app/core/config.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/core/config.py) and [app/core/database_urls.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/core/database_urls.py).
- Async engine in [app/db/base.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/db/base.py) and session dependency in [app/db/session.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/db/session.py).
