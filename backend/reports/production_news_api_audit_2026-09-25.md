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

The focused News API suite passes **4/4**. Both commits deployed successfully through GitHub Actions: `9761a0d` (run `36133478456`) and `6c92cf1` (run `36134525168`).

Post-deployment, all **26 public GET operations** across Market, Stocks, Shariah, and News returned the expected status and valid JSON. Their required top-level response fields were present. The two protected sentiment routes returned their expected 401 responses without credentials. Representative filters returned valid responses, including quote symbols/sector/search/sort/order, stock range/indicators, News row/symbol/sentiment/source/source-type/event/search, and stock-News sentiment/source-type/event filters.

Final News checks: the public feed reports **282** articles and traverses **282/282 unique IDs in 6 pages**; OGDC stock News reports **36** articles and traverses **36/36 unique IDs in 8 pages**. Both final pages have `has_more=false` and no cursor. A unique no-match search returns zero items and `total=0`; malformed cursors return 400; the stock sentiment filter returns 200 and all returned items match the requested sentiment. Article detail includes all required identifiers, title, URL, source fields, and timestamps.

Live data remains incomplete in optional fields: 8 of the first 50 News articles have no symbol tags and 9 have no sentiment; the sample SYS article names the company in its title but has no symbol association. The full quote set still contains **560/560** records but is stale (`2026-09-24T23:55:11+05:00`), all 560 OHLC values are null, 75 have zero volume, and one current price is null. HBL history remains stale at `2026-09-18` (7 days old), and HBL annual/quarterly fundamentals remain absent (`data_status=partial`). The official Shariah snapshot is stale, based on accounts as of `2025-12-31` and effective from `2026-05-25`. All 8 configured News sources currently report healthy.

The News refresh POST was not invoked because it queues background ingestion against external sources. No create/update/delete operation is documented for these four public modules.
