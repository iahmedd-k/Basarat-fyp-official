# ADR-002: JWT Authentication, Token Versioning & 3-Step Password Reset

## Status
**Accepted / Implemented**

## Context
A financial intelligence platform requires strict authentication, immediate session revocation upon password changes or suspicious activity, rotation of refresh tokens, and a resilient password recovery flow that does not expose reset tokens in URL query strings or allow email enumeration.

Standard stateless JWTs suffer from the limitation that issued access tokens cannot be revoked before their expiration time without maintaining a distributed token blacklist.

## Decision
1. **Short-Lived Access JWTs:** 30-minute expiration signed with HMAC-SHA256 (`HS256`).
2. **Token Versioning Revocation Pattern:**
   - Add an integer column `token_version` to the `users` table (default 0).
   - Embed a claim `tv: user.token_version` into every issued access JWT.
   - On authentication verification (`get_current_user`), check whether `payload["tv"] == user.token_version`.
   - On logout, password change, or password reset, increment `User.token_version += 1`. This immediately and globally invalidates all outstanding access JWTs across all client devices.
3. **Database-Backed Refresh Token Rotation:** Store refresh token UUIDs (`jti`) in a dedicated `refresh_tokens` table. Mark tokens as revoked upon every refresh call and issue a new pair.
4. **3-Step OTP-Based Password Reset:**
   - **Step 1 (`POST /auth/forgot-password`):** Generates a random 6-digit OTP, stores its SHA-256 hash in `password_reset_tokens` (10m expiry), and sends it via transactional email. Returns a generic success message regardless of email existence (anti-enumeration).
   - **Step 2 (`POST /auth/verify-reset-code`):** Validates the 6-digit OTP and returns a short-lived (15m) signed JWT `reset_token` grant (`type="password_reset_grant"`).
   - **Step 3 (`POST /auth/reset-password`):** Consumes the grant token, sets the new password, and increments `token_version`.

## Alternatives Considered
- **Pure Stateless JWT without Revocation:** Rejected due to unacceptable security risk where a compromised access token remains valid for its full lifetime after password change.
- **Redis Blocklist for Revoked Tokens:** Considered, but requires storing millions of tokens in Redis with TTLs and creates a hard dependency on Redis for every authenticated REST request.
- **Traditional URL-Token Password Reset Link:** Kept as secondary fallback, but 6-digit OTP flow was prioritized for seamless mobile and desktop application integration.

## Consequences
- **Positive:** Immediate revocation capability; zero email enumeration risk; full audit trail of issued refresh tokens; robust against token replay attacks.
- **Negative / Trade-off:** `get_current_user` performs a fast primary-key query on `User` to verify `token_version` on each authenticated request.

## Current Implementation
- Security utilities in [app/core/security.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/core/security.py).
- Auth dependency in [app/core/authorization.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/core/authorization.py).
- Full service logic in [app/services/auth_service.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/services/auth_service.py).
