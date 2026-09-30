# ADR-003: High-Performance Asynchronous API Framework (FastAPI)

## Status
**Accepted / Implemented**

## Context
The backend requires a modern, high-throughput framework capable of handling:
- Over 140+ REST API endpoints.
- Concurrent WebSocket quote streaming.
- Server-Sent Events (SSE) for real-time LLM token generation.
- Automated OpenAPI / Swagger documentation generation for frontend contract validation.
- Strict data typing and validation on complex financial schemas.

## Decision
Adopt **FastAPI** running on the **Uvicorn** ASGI server with **Pydantic v2** for schema validation.

Key design points:
1. **Asynchronous Request Handlers (`async def`):** Non-blocking I/O throughout all API endpoints, allowing thousands of concurrent idle or streaming connections.
2. **Pydantic v2 Core Engine:** Written in Rust, providing up to 5x faster serialization and validation for large market data and portfolio quote arrays.
3. **Lifespan Management:** Centralized startup and shutdown hooks in `app/main.py` to load ML artifacts, connect Redis pub/sub listeners, and safely dispose of database connection pools.

## Alternatives Considered
- **Django / Django REST Framework:** Rejected due to heavyweight ORM overhead, traditional synchronous WSGI defaults, and clunky WebSocket (Channels) integration.
- **Flask:** Rejected due to lack of native asynchronous primitives, lack of built-in OpenAPI generation, and manual validation boilerplate.
- **Node.js / Express or NestJS:** Considered, but Python was mandatory for native TensorFlow, Scikit-Learn, and XGBoost machine learning model serving and data science pipelines.

## Consequences
- **Positive:** Exceptional I/O concurrency; native WebSocket and SSE support; automatic interactive documentation (`/docs` and `/redoc`); unified Python ecosystem for both web APIs and ML serving.
- **Negative / Trade-off:** Developers must avoid blocking CPU-bound operations in `async def` route handlers (offloading them to Celery or threadpools).

## Current Implementation
- Application definition and lifespan in [app/main.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/main.py).
- Router modules in [app/api/v1/](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/api/v1/).
- Pydantic schemas in [app/schemas/](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/schemas/).
