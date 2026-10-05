# Data Protection

## Sensitive Data Categories

| Category | Examples | Protection |
|----------|---------|------------|
| **Credentials** | Passwords, API keys | bcrypt hashing; env variables |
| **Authentication tokens** | JWT access/refresh tokens | HS256 signed; DB-stored refresh tokens |
| **PII** | Email, full name, avatar URL | Stored in DB; no encryption at rest |
| **Financial data** | Portfolio transactions, holdings | Stored in DB; ownership-based access |
| **Device tokens** | FCM tokens | Stored in DB; user-scoped access |

## Data at Rest

- **Database**: PostgreSQL with Supabase managed encryption (provider-managed)
- **Application-level encryption**: Not implemented for individual fields
- **File storage**: Cloudinary (third-party managed)
- **Model artifacts**: Stored on Docker volumes (not encrypted)

## Data in Transit

- **API**: HTTPS via Nginx TLS termination (production)
- **Database**: SSL connection to Supabase (`sslmode=require` auto-configured)
- **Redis**: TLS connection to Upstash (`rediss://` protocol)
- **External APIs**: HTTPS for Groq, HuggingFace, SendGrid, Cloudinary

## Secret Storage

- All secrets stored as environment variables
- `.env` file excluded from Git via `.gitignore`
- Docker Compose reads from `.env` file
- Production: Secrets in Oracle VM `~/basarat/.env` file (restricted permissions `600`)

> **Note:** Secrets are injected directly via GitHub Actions Secrets and runtime `.env`.

## Password Storage

- Algorithm: bcrypt with auto-generated salt
- Implementation: `app/core/security.py` -> `hash_password()`, `verify_password()`
- Raw passwords never stored or logged

## Token Security

- Access tokens: Short-lived (30 min), not stored server-side
- Refresh tokens: Stored in `refresh_tokens` table with `jti`, `revoked`, `expires_at`
- Email verification tokens: Stored hashed in `email_verification_tokens` table
- Password reset tokens: Stored hashed in `password_reset_tokens` table

## Log Security

- Global exception handler masks internal error details
- Application logs include request metadata but not request bodies
- **Gap:** No explicit PII scrubbing in log output
- **Gap:** Firebase credentials JSON file was found in the repository (should be in `.gitignore`)

## User Data Deletion

- No user account deletion endpoint identified in the current API
- Community posts support soft delete (`DELETED` status)
- Portfolio transactions can be deleted individually
- Watchlists cascade delete on user deletion (FK constraint)
