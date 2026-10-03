# ADR-002: JWT Authentication with Refresh Token Rotation

## Status
Accepted / Implemented

## Context
The system needs stateless authentication for a mobile client that supports session persistence, token refresh, and security against token theft.

## Decision
JWT-based authentication with:
- HS256-signed access tokens (30 min expiry)
- Rotating refresh tokens (7 day expiry) stored in database
- Refresh token rotation: each use issues a new token pair; old token is revoked
- Reuse detection: reusing a revoked refresh token invalidates all user sessions
- bcrypt password hashing with salt
- OAuth integration (Google, Apple) alongside email/password

## Alternatives
- **Session-based auth**: Not suitable for mobile-first API
- **OAuth-only**: Would exclude email/password users
- **Clerk/Auth0**: Third-party dependency with potential cost

## Consequences
- Stateless access token verification (no DB hit for most requests)
- Refresh token rotation provides defense against token theft
- Access tokens remain valid until expiry even after password change
- Database stores refresh tokens (RefreshToken model with revoked flag)

## Current Implementation
- Token creation/decoding: `app/core/security.py`
- Auth dependencies: `app/core/authorization.py`
- Auth service: `app/services/auth_service.py`
- Routes: `app/api/v1/auth.py`
