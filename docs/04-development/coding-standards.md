# Coding Standards

> **Note:** These conventions are inferred from the existing codebase.

## Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Files | snake_case | `auth_service.py` |
| Classes | PascalCase | `AuthService`, `CommunityPost` |
| Functions | snake_case | `get_current_user()` |
| Variables | snake_case | `user_id`, `access_token` |
| Constants | UPPER_CASE | `MAX_FILE_SIZE_MB`, `PROTOCOL_VERSION` |
| Environment vars | UPPER_CASE | `DATABASE_URL`, `SECRET_KEY` |

## Module Organization

```
app/
  api/v1/          # Route handlers (thin controllers)
  core/            # Configuration, security, exceptions, middleware
  db/              # Database engine and session management
  models/          # SQLAlchemy ORM models
  schemas/         # Pydantic request/response schemas
  services/        # Business logic (injected into routes)
  repository/      # Data access layer (partially used)
  tasks/           # Celery background tasks
  ml/              # Machine learning serving and training
  data/            # Static data files and scrapers
  cache/           # Redis client wrapper
  ws/              # WebSocket (empty, logic in services)
  jobs/            # Maintenance jobs (token cleanup)
```

## Router Patterns

```python
router = APIRouter()

def _get_service(db: AsyncSession = Depends(get_db)) -> SomeService:
    return SomeService(db)

@router.get("/resource")
async def list_resources(service: SomeService = Depends(_get_service)):
    return await service.list()
```

## Service Patterns

Services accept a database session in constructor and contain business logic:

```python
class SomeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data) -> result:
        # Business logic here
```

## Async/Sync Patterns

- API routes: Always `async`
- Services: `async` methods for DB operations
- Celery tasks: Synchronous (use sync DB engine)
- Redis: Both async and sync clients available

## Error Handling Style

- Routes catch and re-raise known exceptions
- Unexpected errors wrapped in `ServiceUnavailableError`
- All routes log exceptions with `log.exception()`
- Service methods raise domain-specific exceptions

## Import Conventions

```python
# Standard library
import logging
from datetime import datetime

# Third-party
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

# Local application
from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.services.auth_service import AuthService
```
