# API Conventions

## Route Naming
- RESTful resource-based naming: `/resource` for collections, `/resource/{id}` for items
- Nested resources: `/community/posts/{id}/comments`
- Actions: `/community/posts/{id}/like`, `/auth/forgot-password`

## HTTP Methods
| Method | Usage |
|--------|-------|
| GET | Retrieve resources |
| POST | Create resources, trigger actions |
| PUT | Full update of resources |
| PATCH | Not commonly used (PUT used instead) |
| DELETE | Remove resources |

## Resource Naming
- Plural nouns for collections: `/stocks`, `/users`, `/watchlist`
- Kebab-case for multi-word paths: `/auth/forgot-password`, `/auth/verify-email`

## IDs
- UUID hex strings (32 characters) for most entities
- Auto-increment integers for `predictions`, `model_registry`, `training_runs`

## Timestamps
- ISO 8601 format with timezone
- Server-side: `func.now()` for database defaults
- Most models use `datetime(timezone=True)` columns

## Pagination
- Cursor-based: `cursor` + `limit` parameters (community posts, notifications)
- Offset-based: `offset` + `limit` parameters (some endpoints)
- Default limit varies by endpoint

## Authentication Convention
- Bearer token in Authorization header: `Authorization: Bearer <access_token>`
- Optional auth: `get_optional_current_user` dependency (returns None for anonymous)

## Content Type
- Request/Response: `application/json`
- File uploads: `multipart/form-data` (community post images)

## Naming Conventions (Code)
- Python snake_case for all variables, functions, and file names
- PascalCase for Pydantic models and SQLAlchemy models
- UPPER_CASE for constants and environment variables
