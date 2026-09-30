# Logging Architecture & Standards — Basarat

## 1. Logging Architecture & Implementation

Basarat uses Python's standard `logging` library configured centrally in [app/core/logging.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/core/logging.py) and initialized during application lifespan startup ([app/main.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/main.py#L57)).

### Log Configuration
- **Standard Formatting:** `"%(asctime)s [%(levelname)s] %(name)s: %(message)s"`
- **Log Destination:** Standard Output (`stdout` / `stderr`), allowing container runtimes (Docker / Kubernetes) and log collectors to capture streams natively.
- **Log Levels:**
  - `DEBUG`: Verbose query and calculation details (Active only when `DEBUG=True`).
  - `INFO`: Normal operational milestones (Model loading, task completions, authentication events).
  - `WARNING`: Recoverable anomalies (Redis connection retries, upstream rate limit circuit breakers).
  - `ERROR`: Subsystem failures, external API downtime, unhandled request exceptions.
  - `CRITICAL`: Fatal database disconnects, startup validation failures.

---

## 2. Sensitive Data Redaction & Logging Rules

> [!CAUTION]
> The following security rules are strictly enforced across all log statements:

1. **Never Log User Passwords or OTPs:** Plaintext passwords, bcrypt hashes, and 6-digit verification OTPs must never be passed to logger statements.
2. **Never Log Full Authorization Tokens:** Bearer JWT access tokens and refresh tokens must not appear in logs. If needed for debugging, log only the first 8 characters (`token[:8] + "..."`).
3. **Never Log Third-Party Cloud Secrets:** `SECRET_KEY`, `GROQ_API_KEY`, `SENDGRID_API_KEY`, and database connection strings containing passwords must never be output to standard logs.
4. **Mask Credit & Account Identifiers:** User email addresses should be logged in normalized or masked format where practical in production.

---

## 3. Recommended Structured JSON Logging Format

To facilitate log indexing in Grafana Loki, AWS CloudWatch, or Datadog, structured JSON logging with distributed request correlation IDs is recommended:

```json
{
  "timestamp": "2026-09-30T09:15:30.124Z",
  "level": "INFO",
  "logger": "app.services.portfolio_service",
  "request_id": "c8b4f120-7e9a-4c28-98e1-567890abcdef",
  "user_id": "b2f6c8d1-4e9a-4c28-98e1-567890abcdef",
  "action": "CREATE_TRANSACTION",
  "symbol": "ENGRO",
  "quantity": 100.0,
  "execution_time_ms": 14.8,
  "message": "Successfully recorded BUY transaction for user"
}
```
