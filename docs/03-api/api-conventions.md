# API Design Conventions & Standards — Basarat

## 1. Route & URI Naming Conventions

Basarat adheres to RESTful resource-oriented URL conventions:

- **Plural Resource Nouns:** Collections use plural lowercase nouns (`/api/v1/stocks`, `/api/v1/watchlists`, `/api/v1/portfolio/transactions`, `/api/v1/alerts/rules`).
- **Kebab-Case Path Segments:** Multi-word URI path segments use lowercase kebab-case (`/technical-indicators`, `/engine-weights`, `/completed-trade`, `/investment-profile`).
- **Entity Sub-Resources:** Hierarchical child resources are nested under parent identifiers (`/api/v1/watchlists/{watchlist_id}/items/{symbol}`, `/api/v1/community/posts/{post_id}/comments`).
- **Action Verbs on Special Operations:** When an operation does not cleanly map to a CRUD verb, a trailing action verb is used (`/toggle/{symbol}`, `/regenerate`, `/restore`, `/refresh`).

---

## 2. HTTP Method Semantics

| HTTP Verb | Semantic Purpose | Idempotent | Safe | Typical Response Codes |
|---|---|---|---|---|
| **`GET`** | Read-only resource retrieval or search query. | **Yes** | **Yes** | `200 OK`, `404 Not Found` |
| **`POST`** | Create a new entity, initiate an action, or submit login credentials. | **No** | **No** | `200 OK`, `201 Created`, `202 Accepted` |
| **`PATCH`** | Partial modification of an existing entity. | **No** | **No** | `200 OK`, `400 Bad Request`, `404 Not Found` |
| **`PUT`** | Complete replacement of a resource (or mounted as alias). | **Yes** | **No** | `200 OK`, `400 Bad Request` |
| **`DELETE`** | Remove or soft-delete a resource. | **Yes** | **No** | `200 OK`, `204 No Content`, `404 Not Found` |

---

## 3. Identifiers, Timestamps & Numeric Precision

### 3.1 Entity Identifiers
- **UUID Strings (36 chars):** Primary keys for users, transactions, watchlists, alerts, posts, and conversations are standard lowercase UUIDv4 strings (e.g., `b2f6c8d1-4e9a-4c28-98e1-567890abcdef`).
- **Stock Ticker Symbols:** Equities and ETFs use uppercase PSX ticker strings (e.g., `ENGRO`, `LUCK`, `OGDC`, `UBL`).
- **Sequential Integers:** Used internally for prediction audit records and market hours configurations (`predictions.id: int`).

### 3.2 Timestamps & Timezones
- **Format:** ISO-8601 format with explicit timezone offsets (`2026-09-30T18:00:00+05:00` or `2026-09-30T13:00:00Z`).
- **Database Storage:** Stored as PostgreSQL `TIMESTAMP WITH TIME ZONE` using server-side `func.now()`.
- **System Timezone:** Core market scheduling evaluates against Pakistan Standard Time (`Asia/Karachi`, UTC+5).

### 3.3 Numeric & Monetary Precision
- **Share Quantities:** Stored with 4 decimal places (`Numeric(18, 4)`) to accommodate fractional positions.
- **Execution Prices & Rupee Balances:** Stored with 4 decimal places (`Numeric(18, 4)`) to avoid rounding loss during ACB calculations; formatted to 2 decimal places for user display.
- **Ratios & Probabilities:** Model probabilities and sentiment scores use floating-point numbers between `0.0` and `1.0` (or `-1.0` to `+1.0`).

---

## 4. Casing Conventions Across Subsystems

> [!NOTE]
> To support both Python backend standards and JavaScript/mobile frontend ecosystems:
> - **Core API Modules (Auth, Portfolio, Market, Forecast):** Request and response fields use standard Python `snake_case` (e.g. `access_token`, `stock_symbol`, `added_price`, `unrealized_pnl`).
> - **Community Module:** Schemas support automatic camelCase aliases for seamless mobile React/TypeScript integration (e.g. `likeCount`, `commentCount`, `createdAt`, `authorId`).

---

## 5. Standard Query Parameters

| Parameter Name | Type | Default | Description |
|---|---|---|---|
| `limit` | `int` | `20` (max `100`) | Maximum number of records to return per page. |
| `offset` | `int` | `0` | Number of records to skip (offset pagination). |
| `before` / `cursor`| `datetime` / `str` | `None` | Fetch items created strictly before this timestamp (cursor pagination). |
| `symbol` / `symbols`| `str` | `None` | Single ticker symbol or comma-separated list (`"ENGRO,LUCK"`). |
| `period` | `str` | `"1M"` | Timeframe window (`"1D"`, `"1W"`, `"1M"`, `"3M"`, `"6M"`, `"1Y"`, `"ALL"`). |
| `search` / `q` | `str` | `None` | Free-text search query string. |
