# Logging

## Logging Implementation

### Library
Python standard `logging` module.

### Configuration
Defined in `app/core/logging.py`:

```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
```

### Log Levels
- `INFO`: Default level for application logs
- `WARNING`: Suppressed for `uvicorn.access` and `sqlalchemy.engine`
- `ERROR`: Service failures, external API errors
- `EXCEPTION`: Route-level error handling with stack traces

### Log Destinations
- **stdout**: Primary output (captured by Docker)
- **Docker**: JSON-file driver with 10MB max size, 3 files rotation

### Log Categories

| Category | Logger | Content |
|----------|--------|---------|
| Request handling | `uvicorn.access` | HTTP request logs (suppressed to WARNING) |
| Database | `sqlalchemy.engine` | SQL queries (suppressed to WARNING) |
| Authentication | `app.api.v1.auth` | Login/signup failures |
| External APIs | `app.services.groq_client` | Groq API errors and retries |
| Background tasks | `app.tasks.*` | Task execution logs |
| Cache | `app.core.redis` | Redis connection errors |
| ML | `app.ml.serving.*` | Model loading, inference |
| WebSocket | `app.services.websocket_manager` | Connection lifecycle |

### Security Considerations

- **Good**: Global exception handler masks internal error details
- **Good**: Route handlers log exceptions server-side before returning generic errors
- **Gap**: No explicit PII filtering in log output
- **Gap**: No structured JSON logging for machine parsing
- **Gap**: No log aggregation or centralized storage
