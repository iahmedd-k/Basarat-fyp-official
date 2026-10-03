# ADR-003: FastAPI as API Framework

## Status
Accepted / Implemented

## Context
The system requires a high-performance Python web framework with async support, automatic OpenAPI documentation, and dependency injection.

## Decision
FastAPI was selected for native async/await, automatic OpenAPI/Swagger docs, Pydantic v2 validation, dependency injection, and WebSocket support.

## Alternatives
- **Django REST Framework**: Heavier, sync-first
- **Flask**: No built-in async, no automatic API docs
- **Starlette**: Lower-level; FastAPI adds validation and DI

## Consequences
- High performance with async I/O
- Self-documenting API with 16 tagged endpoint groups
- Type-safe request handling via Pydantic schemas
- WebSocket support for live market streaming

## Current Implementation
- Application: `app/main.py`
- Routes: `app/api/v1/` (22 modules)
- Schemas: `app/schemas/` (12 modules)
