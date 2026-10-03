# Authorization

## Role Model

The system uses a simple two-role model:

| Role | Determined By | Privileges |
|------|--------------|------------|
| **User** | Default for all registered users | Access own resources, community participation |
| **Admin** | `users.is_admin = True` | All user privileges + moderation, ETF/IPO CRUD |

## Authorization Dependencies

| Dependency | Location | Purpose |
|-----------|----------|---------|
| `get_current_user` | `app/core/authorization.py` | Requires valid access token; returns User |
| `get_optional_current_user` | `app/core/authorization.py` | Returns User or None (no auth required) |
| `get_current_admin` | `app/core/authorization.py` | Requires `is_admin=True` |
| `require_roles(*roles)` | `app/core/authorization.py` | Factory for role-based checks |

## Authorization Matrix

| Resource | Anonymous | Authenticated User | Owner | Admin |
|----------|-----------|-------------------|-------|-------|
| Market data | Read | Read | — | Read |
| Stock detail | Read | Read | — | Read |
| News/Events | Read | Read | — | Read |
| Sentiment | Read | Read | — | Read |
| Shariah | Read | Read | — | Read |
| Recommendations | Read | Read | — | Read |
| Portfolio | — | — | CRUD | — |
| Watchlists | — | — | CRUD | — |
| Alerts | — | — | CRUD | — |
| Notifications | — | — | Read/Update | — |
| Community posts | Read | Create | Edit/Delete own | Delete any |
| Community comments | Read | Create | Delete own | Delete any |
| Community follow | — | Follow/Unfollow | — | — |
| Community reports | — | Create | — | Review/Dismiss |
| AI Assistant | — | — | CRUD own conversations | — |
| Devices (FCM) | — | — | Register/Remove own | — |
| ETFs | Read | Read | — | CRUD |
| IPOs | Read | Read | — | CRUD |
| Health endpoints | Read | Read | — | Read |

## Ownership Enforcement

Ownership is enforced at the service layer by filtering queries with `user_id`:

- **Portfolio**: Transactions filtered by `user_id` in all queries
- **Watchlists**: Cascade delete via foreign key; queries filter by `user_id`
- **Alerts**: Filtered by `user_id`
- **AI Conversations**: Filtered by `user_id` in `get_conversation()`
- **Community posts**: Author can delete own posts; admin can delete any
- **Devices**: Filtered by `user_id`
