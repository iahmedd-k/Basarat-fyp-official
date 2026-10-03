# Test Cases

## Authentication Test Cases

### TC-001 — Successful User Registration
- **Module:** Auth
- **Scenario:** Register with valid email, password, and full name
- **Input:** `{email: "test@example.com", password: "StrongPass123!", full_name: "Test User"}`
- **Expected Result:** 201 Created, verification email sent
- **Priority:** Critical
- **Status:** Implemented (`test_auth_api.py`)

### TC-002 — Duplicate Email Registration
- **Module:** Auth
- **Scenario:** Register with already-used email
- **Input:** `{email: "existing@example.com", password: "Pass123!", full_name: "User"}`
- **Expected Result:** 409 Conflict
- **Priority:** Critical
- **Status:** Implemented

### TC-003 — Login with Valid Credentials
- **Module:** Auth
- **Scenario:** Login with correct email/password after verification
- **Expected Result:** 200 OK with access_token and refresh_token
- **Priority:** Critical
- **Status:** Implemented

### TC-004 — Login with Invalid Password
- **Module:** Auth
- **Scenario:** Login with wrong password
- **Expected Result:** 401 Unauthorized
- **Priority:** Critical
- **Status:** Implemented

### TC-005 — Token Refresh
- **Module:** Auth
- **Scenario:** Exchange valid refresh token for new token pair
- **Expected Result:** 200 OK with new access_token and refresh_token
- **Priority:** Critical
- **Status:** Implemented

### TC-006 — Reuse Revoked Refresh Token
- **Module:** Auth
- **Scenario:** Attempt to use a previously-used refresh token
- **Expected Result:** 401 Unauthorized; all sessions invalidated
- **Priority:** Critical
- **Status:** Implemented

## Authorization Test Cases

### TC-007 — Access Protected Endpoint Without Token
- **Module:** Authorization
- **Scenario:** Call `/portfolio` without Authorization header
- **Expected Result:** 401 Unauthorized
- **Priority:** High
- **Status:** Implemented (`test_authorization.py`)

### TC-008 — Access Admin Endpoint as Regular User
- **Module:** Authorization
- **Scenario:** Call admin community endpoint as non-admin user
- **Expected Result:** 403 Forbidden
- **Priority:** High
- **Status:** Implemented

### TC-009 — Access Another User's Portfolio
- **Module:** Authorization
- **Scenario:** Attempt to read another user's portfolio transactions
- **Expected Result:** Empty result (ownership filter)
- **Priority:** High
- **Status:** Implemented

## Portfolio Test Cases

### TC-010 — Add Buy Transaction
- **Module:** Portfolio
- **Scenario:** Record a stock purchase
- **Expected Result:** 201 Created with transaction details
- **Priority:** High
- **Status:** Implemented (`test_portfolio_api.py`)

### TC-011 — Sell More Than Owned
- **Module:** Portfolio
- **Scenario:** Attempt to sell more shares than held
- **Expected Result:** 400 Bad Request
- **Priority:** High
- **Status:** Implemented

## Market Data Test Cases

### TC-012 — Get Market Summary
- **Module:** Market
- **Scenario:** Request PSX market summary
- **Expected Result:** 200 OK with indices, gainers, losers
- **Priority:** High
- **Status:** Implemented (`test_market_api.py`)

## Forecast Test Cases

### TC-013 — Get Stock Prediction
- **Module:** Forecast
- **Scenario:** Request prediction for a valid PSX symbol
- **Expected Result:** 200 OK with direction, probabilities
- **Priority:** High
- **Status:** Implemented (`test_forecast_api.py`)

### TC-014 — Get Prediction for Invalid Symbol
- **Module:** Forecast
- **Scenario:** Request prediction for non-existent symbol
- **Expected Result:** 404 Not Found
- **Priority:** Medium
- **Status:** Implemented

## Community Test Cases

### TC-015 — Create Stock Discussion Post
- **Module:** Community
- **Scenario:** Create a STOCK type post with valid symbol
- **Expected Result:** 201 Created
- **Priority:** High
- **Status:** Requires verification

### TC-016 — Report Abusive Post
- **Module:** Community
- **Scenario:** Report a post with ABUSIVE reason
- **Expected Result:** 201 Created; report_count incremented
- **Priority:** Medium
- **Status:** Requires verification

## Negative Test Cases

### TC-017 — Malformed JSON Request
- **Module:** General
- **Scenario:** Send invalid JSON body
- **Expected Result:** 422 Validation error
- **Priority:** Medium
- **Status:** Handled by FastAPI/Pydantic

### TC-018 — Expired Access Token
- **Module:** Auth
- **Scenario:** Use an expired JWT access token
- **Expected Result:** 401 Unauthorized
- **Priority:** Critical
- **Status:** Implemented

### TC-019 — Rate Limit Exceeded
- **Module:** Auth
- **Scenario:** Send 6 login requests in 1 minute (limit is 5)
- **Expected Result:** 429 Too Many Requests
- **Priority:** High
- **Status:** Requires verification
