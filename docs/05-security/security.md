# Security Overview

## Implemented Controls

### Authentication
- JWT-based access tokens (HS256, 30 min expiry)
- Rotating refresh tokens stored in database (7 day expiry)
- bcrypt password hashing with salt
- Email OTP verification for signup
- 3-step password reset with OTP + grant token
- OAuth integration (Google, Apple) with ID token verification
- Session revocation on password change

### Authorization
- Role-based: `user` and `admin` roles via `is_admin` flag
- Resource ownership enforcement in services (portfolio, watchlists, conversations)
- Admin-only endpoints for ETF/IPO CRUD and community moderation
- `get_current_user`, `get_current_admin`, `require_roles()` dependencies

### Rate Limiting
- SlowAPI per-user/IP rate limiting on auth endpoints (3-15 req/min)
- Nginx-level rate limiting (20 req/s burst 50, 20 concurrent connections)
- Trusted proxy IP support for X-Forwarded-For extraction

### Input Validation
- Pydantic v2 schema validation on all API inputs
- File upload validation: MIME type whitelist, 5MB size limit (Cloudinary)
- SQL injection protection via SQLAlchemy parameterized queries

### Secret Management
- Environment variables for all secrets (never hardcoded)
- Production validation: rejects placeholder SECRET_KEY values
- Production validation: rejects localhost database/Redis URLs
- Production validation: rejects DEBUG=true
- `.gitignore` excludes `.env` files and credential JSON

### Container Security
- Non-root user (UID 1000) in production Docker containers
- Minimal base image (python:3.11.9-slim-bookworm)
- Pinned dependencies with hash verification (`requirements.lock`)

### Error Information Disclosure
- Global exception handler masks internal errors
- Generic error messages for unhandled exceptions
- Account enumeration prevention on password reset

## Partial Controls

### CORS
- Development: `allow_origins=["*"]` (permissive)
- Production: Validated to exclude localhost origins
- **Gap:** Middleware uses `allow_origins=["*"]` directly in code regardless of config

### Refresh Token Security
- Tokens stored in DB with revocation tracking
- Reuse detection invalidates all sessions
- **Gap:** No absolute session limit per user (could accumulate refresh tokens)

## Missing / Recommended Controls

| Control | Status | Recommendation |
|---------|--------|---------------|
| HTTPS enforcement | Not in app (Nginx handles) | Ensure TLS termination at Nginx/ALB |
| CSRF protection | Not applicable (API-only, no cookies) | N/A for Bearer token auth |
| Content Security Policy | Not applicable (no web frontend served) | N/A |
| Access token blacklist | Not implemented | Consider Redis-based blacklist for logout |
| Password complexity rules | Partial (min length in Pydantic) | Add complexity requirements |
| Account lockout | Not implemented | Lock after N failed login attempts |
| Audit logging | Partial (exception logging) | Add structured audit trail |
| Dependency vulnerability scanning | Not identified | Add Dependabot or pip-audit |
| API key rotation for external services | Manual | Document rotation procedure |
