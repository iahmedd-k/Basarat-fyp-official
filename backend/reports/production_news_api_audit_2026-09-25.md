# Production News API Audit — 2026-09-25

**Target:** `http://16.16.26.247:8000`
**Scope:** Deployed OpenAPI read-only audit of News routes and News filters. The public OpenAPI exposes GET operations for Markets, Stocks, Shariah, and News; those modules have no CRUD write operations. `POST /api/v1/news/refresh` is a background ingestion trigger, not CRUD, and was not invoked because it queues work against external sources. Two sentiment routes adjacent to News require authentication and returned the expected 401 without credentials.

## Baseline findings

- Public Market, Stocks, Shariah, and News GET route families were reachable and returned valid JSON for representative valid requests. KMI-30 returned 30 constituents; News sources returned 8 configured sources; News and stock-News feeds returned real titled articles with source and URL fields.
- `GET /api/v1/news?limit=1` returned one article but `total=0`. Filtered News feeds also returned `total=0` despite returning matching items.
- The `q` text-search parameter was ignored. A unique no-match search returned exactly the same first three article IDs as an unfiltered request.
- Invalid News cursors were silently ignored: `cursor=not-valid` returned the first page with HTTP 200.
- `GET /api/v1/stocks/OGDC/news?sentiment=bullish` returned HTTP 503 when an item had a missing/null sentiment object.
- The stock-News route accepted `cursor` but did not use it and always returned `next_cursor=null`, `has_more=false`.
- `NewsService` produced a next cursor for every nonempty page, even if there was no following page; consequently `has_more` could be incorrectly true at the end of pagination.
- Full traversal stopped after 51 items although the feed reported 282 total: cursor predicates compared only `published_at`, so the 231 records with no publication date were never reachable.
- The sample article detail had a real title, source, URL, summary, publication time, and created time, but its `symbols` list was empty even though the title named Systems Limited (SYS). This is an existing-row tagging gap; the optional list is schema-valid, but stock association is incomplete for this article.

## Fixes in this change

- Return the actual filtered article count from the News feed and stock-News endpoints.
- Emit a pagination cursor only when another page exists.
- Use `created_at` as the stable cursor/sort timestamp when `published_at` is missing, so every stored article remains reachable.
- Apply the documented `q` parameter to article title and summary searches.
- Reject malformed cursors with HTTP 400 instead of restarting at page one.
- Use the shared cursor-aware News query for stock-News filtering and pagination, preventing the null-sentiment 503.
- Add regression tests for public News access, totals, cursor pagination, text search, malformed cursors, and missing sentiment.

## Data limitations

Previously completed production audits document stale Market quotes/history, unavailable source OHLC and fundamentals, and a dated/stale official Shariah snapshot. Those fields remain null or marked stale rather than fabricated. The SYS-tagging gap above also needs a historical tag backfill; these public modules expose no mutation route for that operation.

## Verification

Pending deployment and post-deployment live retest.
