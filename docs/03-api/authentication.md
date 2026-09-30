# Authentication & Session Architecture — Basarat

## 1. Authentication Overview

Basarat implements a hybrid **Self-Contained JWT with Database-Backed Revocation and Rotation** authentication system:

- **Access Tokens:** Signed HMAC-SHA256 (`HS256`) JSON Web Tokens with a **30-minute lifetime**, carrying the user ID (`sub`), token type (`type="access"`), and the user's current token version (`tv`).
- **Refresh Tokens:** Long-lived (**7 days**) signed JWTs (`type="refresh"`), tracked in the `refresh_tokens` PostgreSQL table by a unique UUID `jti` for explicit revocation and rotation.
- **Immediate Revocation:** The system enforces an atomic integer `User.token_version` check on every authenticated request. Incrementing this counter immediately and globally invalidates all outstanding access JWTs across all active client devices.
- **Social OAuth:** Federated identity support for Google OAuth 2.0 and Apple Sign-In.
- **3-Step Password Reset:** High-security password recovery using 6-digit SHA-256 hashed OTPs, time-limited JWT grant tokens, and anti-enumeration protection.

---

## 2. JWT Payload Specifications

### 2.1 Access Token Payload
```json
{
  "sub": "b2f6c8d1-4e9a-4c28-98e1-567890abcdef",
  "type": "access",
  "jti": "a1b2c3d4e5f678901234567890abcdef",
  "tv": 3,
  "exp": 1727694600
}
```
- `sub`: Unique UUID string of the authenticated user.
- `type`: Must equal `"access"`. Tokens with any other type are rejected by `get_token_payload`.
- `jti`: Unique token identifier.
- `tv`: Token version number matching `User.token_version` in the database.
- `exp`: Unix expiration timestamp (Current time + `ACCESS_TOKEN_EXPIRE_MINUTES`).

### 2.2 Refresh Token Payload
```json
{
  "sub": "b2f6c8d1-4e9a-4c28-98e1-567890abcdef",
  "type": "refresh",
  "jti": "f9e8d7c6b5a432109876543210fedcba",
  "exp": 1728299400
}
```

### 2.3 Password Reset Grant Token Payload
```json
{
  "sub": "b2f6c8d1-4e9a-4c28-98e1-567890abcdef",
  "email": "investor@example.pk",
  "type": "password_reset_grant",
  "jti": "1234567890abcdef1234567890abcdef",
  "exp": 1727693700
}
```

---

## 3. Core Authentication Flows

### 3.1 User Registration & Email OTP Verification

```mermaid
sequenceDiagram
    autonumber
    actor User as User / Client
    participant API as FastAPI Router (/auth)
    participant AuthSvc as AuthService
    participant DB as PostgreSQL
    participant Mail as SendGrid / SMTP

    User->>API: POST /auth/signup {email, password, full_name}
    API->>AuthSvc: signup(email, password, full_name)
    AuthSvc->>DB: Check if email exists
    alt Email already exists & verified
        AuthSvc-->>User: Generic Success Message (Anti-Enumeration)
    else New Registration
        AuthSvc->>DB: Insert User (is_verified=False, bcrypt hash)
        AuthSvc->>AuthSvc: Generate 6-digit OTP (e.g. 849201)
        AuthSvc->>DB: Save SHA-256(OTP) in email_verification_tokens (10m TTL)
        AuthSvc->>Mail: Send Verification Email with OTP
        AuthSvc-->>User: {"message": "Account created. Please check your email for the verification code."}
    end

    User->>API: POST /auth/verify-email {email, code: "849201"}
    API->>AuthSvc: verify_email(email, code)
    AuthSvc->>DB: Validate SHA-256(code) & expires_at & used=False
    AuthSvc->>DB: Set User.is_verified=True, mark token used=True
    AuthSvc->>DB: Create RefreshToken record
    AuthSvc->>AuthSvc: Issue Access JWT + Refresh JWT
    AuthSvc-->>User: {"access_token": "...", "refresh_token": "...", "user": {...}}
```

---

### 3.2 Standard Login & Refresh Token Rotation

```mermaid
sequenceDiagram
    autonumber
    actor User as Client App
    participant API as FastAPI Router (/auth)
    participant AuthSvc as AuthService
    participant DB as PostgreSQL

    User->>API: POST /auth/login {email, password}
    API->>AuthSvc: login(email, password)
    AuthSvc->>DB: Fetch User by email
    AuthSvc->>AuthSvc: Verify bcrypt password hash
    AuthSvc->>DB: Insert new RefreshToken (jti=uuid)
    AuthSvc->>AuthSvc: Create Access JWT (tv=User.token_version)
    AuthSvc-->>User: 200 OK {"access_token": "...", "refresh_token": "..."}

    Note over User,DB: Later, when Access Token expires (30 mins)...

    User->>API: POST /auth/refresh {refresh_token}
    API->>AuthSvc: refresh_token(token_string)
    AuthSvc->>AuthSvc: Decode JWT & verify type="refresh"
    AuthSvc->>DB: SELECT RefreshToken WHERE jti=payload.jti AND revoked=False
    alt Token Revoked or Not Found
        AuthSvc-->>User: 401 Unauthorized ("Invalid or revoked refresh token")
    else Valid Refresh Token
        AuthSvc->>DB: UPDATE RefreshToken SET revoked=True, revoked_at=now()
        AuthSvc->>DB: INSERT new RefreshToken (new_jti)
        AuthSvc->>AuthSvc: Create new Access Token + new Refresh Token
        AuthSvc-->>User: 200 OK {"access_token": "...", "refresh_token": "..."}
    end
```

---

### 3.3 3-Step Secure Password Reset Flow

```mermaid
sequenceDiagram
    autonumber
    actor User as User
    participant API as FastAPI Router
    participant AuthSvc as AuthService
    participant DB as PostgreSQL
    participant Mail as SendGrid / SMTP

    Note over User,Mail: Step 1 — Request Reset OTP
    User->>API: POST /auth/forgot-password {email}
    API->>AuthSvc: forgot_password(email)
    AuthSvc->>DB: Find user by email
    opt User Found
        AuthSvc->>AuthSvc: Generate 6-digit OTP (e.g. 529143)
        AuthSvc->>DB: Insert SHA-256(OTP) into password_reset_tokens (10m expiry)
        AuthSvc->>Mail: Send Password Reset Code Email
    end
    AuthSvc-->>User: Generic Success Message (No email existence leak)

    Note over User,Mail: Step 2 — Verify OTP & Obtain Grant Token
    User->>API: POST /auth/verify-reset-code {email, code: "529143"}
    API->>AuthSvc: verify_reset_code(email, code)
    AuthSvc->>DB: Check SHA-256(code), expires_at, used=False
    AuthSvc->>DB: Mark token used=True
    AuthSvc->>AuthSvc: Generate signed reset_token (type="password_reset_grant", 15m expiry)
    AuthSvc-->>User: 200 OK {"reset_token": "eyJhbGci...", "message": "Code verified"}

    Note over User,Mail: Step 3 — Submit New Password with Grant Token
    User->>API: POST /auth/reset-password {reset_token, new_password}
    API->>AuthSvc: reset_password_with_token(reset_token, new_password)
    AuthSvc->>AuthSvc: Decode reset_token & verify type="password_reset_grant"
    AuthSvc->>DB: UPDATE User SET hashed_password=bcrypt(new_password), token_version=token_version + 1
    AuthSvc->>DB: UPDATE RefreshToken SET revoked=True WHERE user_id=user.id
    AuthSvc-->>User: 200 OK {"message": "Password reset successfully. Please log in with your new password."}
```

---

## 4. Immediate Session Invalidation Mechanism (`token_version`)

To prevent compromised or stale access tokens from accessing protected resources:

1. The `users` table holds a column `token_version: int` (default 0).
2. The authentication dependency [get_current_user](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/core/authorization.py#L26-L49) extracts `tv` from the token payload:
   ```python
   user = await db.get(User, user_id)
   if int(payload.get("tv", 0)) != int(user.token_version):
       raise UnauthorizedError("Token has been revoked. Please log in again.")
   ```
3. When a user logs out (`POST /auth/logout`), changes password (`POST /auth/change-password`), or resets password (`POST /auth/reset-password`), `User.token_version` is atomically incremented by `1`.
4. All existing access tokens immediately fail subsequent requests with HTTP 401.

---

## 5. Third-Party Identity Federation (Google & Apple)

- **Google OAuth (`POST /auth/google`):** Verifies the Google ID token using `google-auth` / Google's public keys. If valid, retrieves the user by `oauth_id` or creates a verified user record and issues Basarat JWTs.
- **Apple OAuth (`POST /auth/apple`):** Decodes Apple's identity token, verifies the cryptographic signature with Apple's JSON Web Key Set (JWKS), and issues Basarat JWTs.
- **Clerk Webhooks (`POST /webhooks/clerk`):** Implements HMAC-SHA256 signature verification via `svix` using `CLERK_WEBHOOK_SECRET` for synchronization with external Clerk authentication directories.
