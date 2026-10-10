# Error Handling & Validation

Basarat implements a unified, predictable error and validation response contract across all API endpoints.

---

## 1. Exception Hierarchy

All domain and business exceptions inherit from `AppError` ([app/core/exceptions.py](file:///d:/FYP/Basarat-fyp-official/backend/app/core/exceptions.py)):

| Exception Class | HTTP Status | Error Code | Default Detail | Typical Trigger |
| :--- | :---: | :--- | :--- | :--- |
| `AppError` | `500` | `INTERNAL_ERROR` | Internal server error | Unhandled application error base |
| `BadRequestError` | `400` | `BAD_REQUEST` | Bad request | Inverted dates (`from > to`), invalid types |
| `UnauthorizedError` | `401` | `UNAUTHORIZED` | Not authenticated | Missing or expired JWT Bearer token |
| `ForbiddenError` | `403` | `FORBIDDEN` | Not enough permissions | Accessing another user's private resources |
| `NotFoundError` | `404` | `NOT_FOUND` | Resource not found | Symbol not in universe, unknown alert/event |
| `ConflictError` | `409` | `CONFLICT` | Resource already exists | Duplicate active alerts, existing watchlist items |
| `ValidationFailedError` | `422` | `VALIDATION_FAILED` | Validation failed | Cross-field schema rule failure |
| `ServiceUnavailableError`| `503` | `SERVICE_UNAVAILABLE`| Service unavailable | Downstream model or external network unreachable |
| `CommunityError` | `400` / `422` | `COMMUNITY_ERROR` | Community request failed | Specific community feed contracts |

---

## 2. Standardized JSON Error Response Contracts

### Standard API Error Envelope (All Domain Endpoints)

All errors return `success: false` along with an explicit `error` object and an `X-Request-ID` HTTP header for distributed tracing:

```json
{
  "success": false,
  "error": {
    "code": "BAD_REQUEST",
    "message": "Start date ('from') cannot be after end date ('to')."
  }
}
```

### Schema & Validation Errors (HTTP 422)

When request payloads, path parameters, or query strings fail Pydantic or FastAPI validation, `RequestValidationError` formats the error with specific field locations and details:

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Input should be greater than 0",
    "field": "body.shares",
    "details": [
      {
        "loc": ["body", "shares"],
        "msg": "Input should be greater than 0",
        "type": "greater_than"
      }
    ]
  }
}
```

### Community Contract Envelope

Community endpoints support custom extra parameters (e.g. rate-limiting cooldowns):

```json
{
  "error": "POST_RATE_LIMIT",
  "message": "You can only post once every 60 seconds",
  "field": "content",
  "retryAfterSeconds": 45
}
```

---

## 3. Global Exception Handlers

FastAPI registers 5 global handlers in `register_error_handlers(app)`:

1. **`CommunityError`**: Formats community domain errors into the mobile client contract and attaches `X-Request-ID`.
2. **`RequestValidationError`**: Catches Pydantic schema validation failures, extracts root field names, and renders standard 422 JSON.
3. **`StarletteHTTPException`**: Catches standard HTTP exceptions (404, 405, 429, 503) and maps them to canonical uppercase error codes (`NOT_FOUND`, `RATE_LIMIT_EXCEEDED`, etc.).
4. **`AppError`**: Catches any explicit application exception and renders the exact `status_code`, `code`, and `detail`.
5. **`Exception` (Catch-All)**: Catches unexpected crashes, logs internal errors securely, and returns a sanitized HTTP 500 without leaking database schemas or stack traces.

---

## 4. Request Tracing (`X-Request-ID`)

Every incoming request passes through `RequestContextMiddleware`:
- Checks incoming `X-Request-ID` header or generates a new `UUID4` hexadecimal identifier.
- Injects `request.state.request_id` into route handlers.
- Appends `X-Request-ID: <id>` to all HTTP response headers (successes and errors alike).
