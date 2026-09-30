# Authorization & Access Control Specification — Basarat

## 1. Access Control Model & Roles

Basarat implements a hybrid **Role-Based Access Control (RBAC)** and **Resource-Based Ownership Access Control (OBAC)** model.

### 1.1 Actor Roles
1. **Anonymous / Public User (`GUEST`):** Unauthenticated caller. Can read market summaries, stock overviews, technical indicators, fundamentals, Shariah screening, and ETF/IPO catalogs.
2. **Authenticated User (`USER`):** Active registered user with valid Bearer JWT. Can manage their personal watchlists, portfolio transactions, alert rules, AI chat conversations, and post/comment in the community.
3. **Resource Owner (`OWNER`):** Authenticated user who created a specific entity (e.g. author of a community post, owner of a portfolio transaction). Has exclusive permissions to edit or delete that resource.
4. **Administrator (`ADMIN`):** Privileged user with `User.is_admin == True`. Can access administrative moderation queues, delete any post/comment, restore auto-hidden content, inspect system metrics, and perform CRUD operations on ETF/IPO directories.

---

## 2. Resource Authorization Matrix

| Resource / Action | Anonymous (`GUEST`) | Authenticated (`USER`) | Resource Owner (`OWNER`) | Administrator (`ADMIN`) | Enforcement Mechanism |
|---|---|---|---|---|---|
| **Market Data & Indices (Read)** | **Allowed** | **Allowed** | **Allowed** | **Allowed** | Public Route |
| **Stock Fundamentals & Technicals (Read)**| **Allowed** | **Allowed** | **Allowed** | **Allowed** | Public Route |
| **Shariah Screening & Purification (Read)**| **Allowed** | **Allowed** | **Allowed** | **Allowed** | Public Route |
| **ETFs & IPOs Catalog (Read)** | **Allowed** | **Allowed** | **Allowed** | **Allowed** | Public Route |
| **ETFs & IPOs Management (Create/Update)**| Denied (401) | Denied (403) | N/A | **Allowed** | `get_current_admin` Dependency |
| **User Profile (`GET /users/me`)** | Denied (401) | **Allowed** (Self) | **Allowed** (Self) | **Allowed** (Self) | `get_current_user` Dependency |
| **Watchlists (Create / View / Modify)** | Denied (401) | Denied (404/403)| **Allowed** | **Allowed** (Self) | SQL Filter (`user_id == current_user.id`) |
| **Portfolio Transactions (Create / View)**| Denied (401) | Denied (404/403)| **Allowed** | **Allowed** (Self) | SQL Filter (`user_id == current_user.id`) |
| **Portfolio Risk & Monte Carlo (Execute)**| Denied (401) | **Allowed** (Self) | **Allowed** (Self) | **Allowed** (Self) | SQL Filter on User Holdings |
| **ML Directional Forecasts (Read)** | Denied (401) | **Allowed** | **Allowed** | **Allowed** | `get_current_user` Dependency |
| **Stock Recommendations (Read / Weights)**| Denied (401) | **Allowed** | **Allowed** | **Allowed** | `get_current_user` Dependency |
| **AI Assistant Conversations (Chat)** | Denied (401) | Denied (404/403)| **Allowed** | **Allowed** (Self) | SQL Filter (`user_id == current_user.id`) |
| **Community Feed & Public Posts (Read)** | Denied (401) | **Allowed** | **Allowed** | **Allowed** | `get_current_user` Dependency |
| **Community Post (Create / Like / Comment)**| Denied (401) | **Allowed** | **Allowed** | **Allowed** | `get_current_user` Dependency |
| **Community Post (Edit / Delete)** | Denied (401) | Denied (403) | **Allowed** | **Allowed** (Admin Delete) | Service Author ID Check |
| **Community Content Reporting (Submit)** | Denied (401) | **Allowed** | **Allowed** | **Allowed** | `get_current_user` Dependency |
| **Admin Moderation Queue (Review/Act)** | Denied (401) | Denied (403) | Denied (403) | **Allowed** | `get_current_admin` Dependency |

---

## 3. Implementation of Ownership & Authorization Checks

### 3.1 Database-Level Ownership Enforcement (OBAC)
Resource ownership is enforced at the database query level in service and repository classes. Queries for user-owned assets explicitly include `where(Entity.user_id == current_user.id)`:

```python
# Example from WatchlistService (app/services/watchlist_service.py)
result = await self.db.execute(
    select(Watchlist).where(
        Watchlist.id == watchlist_id,
        Watchlist.user_id == current_user.id  # Strict ownership constraint
    )
)
watchlist = result.scalars().first()
if not watchlist:
    raise NotFoundError("Watchlist not found")  # Returns 404 to avoid leaking existence
```

### 3.2 Administrative Authorization Dependency
Admin-only routes use FastAPI's dependency injection to verify administrative claims before handler execution:

```python
# app/core/authorization.py
async def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_admin:
        raise ForbiddenError("Admin privileges required")
    return current_user
```

---

## 4. Authorization Failure Behaviors & Status Codes

1. **Missing or Expired Token:** Returns **HTTP 401 Unauthorized** with code `UNAUTHORIZED`.
2. **Revoked Token (`token_version` mismatch):** Returns **HTTP 401 Unauthorized** with message `"Token has been revoked. Please log in again."`.
3. **Insufficient Privileges (Non-Admin calling Admin route):** Returns **HTTP 403 Forbidden** with code `FORBIDDEN` and message `"Admin privileges required"`.
4. **Attempting to Access Unowned Entity (Watchlist, Conversation, Portfolio):** Returns **HTTP 404 Not Found** with code `NOT_FOUND` (deliberately masking existence to prevent ID harvesting).
5. **Attempting to Modify Another User's Post/Comment:** Returns **HTTP 403 Forbidden** or **HTTP 404 Not Found**.
