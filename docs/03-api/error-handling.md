# Error Handling

## Exception Hierarchy

All custom exceptions inherit from `AppError` (defined in `app/core/exceptions.py`):

| Exception Class | HTTP Code | Error Code | Default Message |
|----------------|-----------|------------|-----------------|
| `AppError` | 500 | `INTERNAL_ERROR` | Internal server error |
| `BadRequestError` | 400 | `BAD_REQUEST` | Bad request |
| `UnauthorizedError` | 401 | `UNAUTHORIZED` | Not authenticated |
| `ForbiddenError` | 403 | `FORBIDDEN` | Not enough permissions |
| `NotFoundError` | 404 | `NOT_FOUND` | Resource not found |
| `ConflictError` | 409 | `CONFLICT` | Resource already exists |
| `ValidationFailedError` | 422 | `VALIDATION_FAILED` | Validation failed |
| `ServiceUnavailableError` | 503 | `SERVICE_UNAVAILABLE` | Service unavailable |
| `CommunityError` | varies | `COMMUNITY_ERROR` | Community request failed |

## Global Exception Handlers

Three exception handlers registered in `register_error_handlers()`:

1. **CommunityError handler** (most specific):
   ```json
   {"error": "CODE", "message": "detail", "field": "optional_field"}
   ```

2. **AppError handler** (standard errors):
   ```json
   {"success": false, "error": {"code": "ERROR_CODE", "message": "Human-readable message"}}
   ```

3. **Unhandled Exception handler** (catch-all):
   ```json
   {"success": false, "error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred"}}
   ```

## Error Handling Patterns

### Route-Level Error Handling
Routes catch known exceptions and re-raise them, wrapping unexpected errors in `ServiceUnavailableError`:

```python
try:
    return await service.login(email=data.email, password=data.password)
except (UnauthorizedError, ValidationFailedError, RateLimitExceeded):
    raise
except Exception as e:
    log.exception("Login failed")
    raise ServiceUnavailableError("Login failed")
```

### Rate Limit Errors
SlowAPI raises `RateLimitExceeded`, handled by the default `_rate_limit_exceeded_handler`.

### Validation Errors
Pydantic validation errors return 422 with field-level error details (FastAPI default behavior).

## Inconsistencies Noted

1. **Dual error formats**: Standard API uses `{"success": false, "error": {...}}` while Community module uses `{"error": "CODE", "message": "..."}`. This is by design for different client contracts but may confuse consumers.

2. **Exception logging**: Most routes log exceptions with `log.exception()` before wrapping, which is good. However, the global unhandled exception handler does not log the exception (potential gap for debugging).
