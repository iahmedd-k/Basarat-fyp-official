# ADR-001: PostgreSQL as Primary Database

## Status
Accepted / Implemented

## Context
The system requires a relational database capable of handling complex queries, JSON columns, partial unique indexes, and financial transaction data with ACID compliance.

## Decision
PostgreSQL 16 was selected as the primary database, with:
- Local development via Docker (`postgres:16-alpine`)
- Production hosting on Supabase (managed PostgreSQL)
- Async access via asyncpg + SQLAlchemy 2.x
- Sync access via psycopg2 for Celery tasks and Alembic migrations

## Alternatives
- **SQLite**: Insufficient for concurrent access and production workloads
- **MySQL**: Lacks PostgreSQL's partial indexes and advanced JSON support
- **MongoDB**: Relational model better suits financial transaction data

## Consequences
- Strong ACID compliance for financial transactions
- Rich indexing (partial unique, composite) for complex constraints
- Supabase free-tier connection limits require conservative pooling (pool_size=3)
- Two database drivers needed (asyncpg for API, psycopg2 for sync tasks)

## Current Implementation
- Engine config: `app/db/base.py`
- URL handling: `app/core/database_urls.py`
- Session management: `app/db/session.py`
- Migrations: `alembic/` (19 migration files)
