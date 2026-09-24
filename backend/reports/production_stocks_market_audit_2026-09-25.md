# Production Stocks and Market API Audit

**Target:** `http://16.16.26.247:8000`
**Run date:** 2026-09-25 (Asia/Karachi)
**Scope:** Public Stocks and Market API operations only. All production calls were read-only `GET` requests; the module exposes no `POST` operations in its live OpenAPI document. No PEM key or seed credentials were read or used.

## Executive result

The deployed Swagger UI and OpenAPI document were reachable. All 16 documented Stocks and Market operations returned HTTP 200 for representative valid requests, and their success payloads were valid JSON with the response structures expected by the local schemas. Search, range, indicator, pagination, symbol, sector, and supported sorting filters were exercised. Invalid basic ranges and numeric bounds returned 422.

The API is functional, but the production data is not fully production-ready: market quotes are stale; every quote has zero OHLC values; HBL history/indicators are six days old; company-name search does not find Habib Bank; and invalid symbol/sort inputs are handled incorrectly. The report identifies which issues were corrected in the workspace and which need upstream data work. Workspace changes have **not** been deployed to AWS, so production behavior remains unchanged until deployment.

## Endpoint results

| Module | Endpoint | Valid request result | Response structure / check |
|---|---|---:|---|
| Stocks | `GET /api/v1/stocks/search?q=HBL&limit=3` | 200 | `{results: [...]}`; HBL returned |
| Stocks | `GET /api/v1/stocks/{symbol}/overview` | 200 | Required overview keys present; HBL day range was null |
| Stocks | `GET /api/v1/stocks/{symbol}/price-history?range=1D` | 200 | `{symbol, range, bars, as_of_date, data_age_days, is_stale}` |
| Stocks | `GET /api/v1/stocks/{symbol}/technical-indicators` | 200 | Structured summary, signal counts, and series |
| Stocks | `GET /api/v1/stocks/{symbol}/fundamentals` | 200 | Structured profile, ratios, limits, dividends, announcements, and status |
| Market | `GET /api/v1/market/sectors/performance` | 200 | Sector aggregates and totals |
| Market | `GET /api/v1/market/indices` | 200 | KSE-100, KSE-30, KMI-30 index records |
| Market | `GET /api/v1/market/indices/kse-100` | 200 | Index metadata and constituent records |
| Market | `GET /api/v1/market/indices/kse-30` | 200 | Index metadata and constituent records |
| Market | `GET /api/v1/market/indices/kmi-30` | 200 | Index metadata, Shariah flag, and constituents |
| Market | `GET /api/v1/market/gainers?limit=5` | 200 | Gainers list and freshness metadata |
| Market | `GET /api/v1/market/losers?limit=5` | 200 | Losers list and freshness metadata |
| Market | `GET /api/v1/market/volume-spikes?limit=5` | 200 | Volume spike list and freshness metadata |
| Market | `GET /api/v1/market/sentiment-overview` | 200 | Mood, breadth counts, sectors, and top movers |
| Market | `GET /api/v1/market/quotes?limit=5` | 200 | Paginated quote object with totals and freshness |
| Market | `GET /api/v1/market/all-stocks?limit=5` | 200 | Alias returned the same quote response structure |

All successful responses were valid JSON. The production OpenAPI document is served from `/api/v1/openapi.json`; the default `/openapi.json` path returned 404, while the provided `/docs` URL worked.

## Input and filter checks

| Case | Production result | Assessment |
|---|---:|---|
| Search `q=HBL`, `limit=3` | 200 | Works |
| Search `q=Habib`, `limit=3` | 200, empty results | Company-name lookup is incomplete (see data findings) |
| Empty query | 422 | Correct validation |
| Search limit 101 | 422 | Correct validation |
| Price range `5Y` | 422 | Correct validation |
| Indicator period 0 | 422 | Correct validation |
| Invalid stock symbol `!!!` | 503 | Incorrect; malformed input is reported as service outage |
| Quote pagination `limit=5&offset=2` | 200 | Works |
| Quote symbol filter `HBL,OGDC` | 200 | Returned both requested symbols |
| Sector filter `Bank` | 200 | Substring match returned 56 bank-related-sector records |
| Search filter `HBL` | 200 | Returned HBL and ticker substring CHBL, consistent with substring semantics |
| Sort by `current`, order `asc` | 200 | Works |
| Invalid sort field and order | 200 | Incorrect; unsupported values are silently accepted |
| Quote limit 0 | 422 | Correct validation |

## Data-quality findings

1. **Market quote freshness:** the 560-quote response was marked `is_stale: true`; `as_of` was `2026-09-24T18:55:11.935180+00:00`. This is a cached snapshot, not a current quote feed.
2. **OHLC values missing but serialized as zero:** all 560 quotes had `open=0`, `high=0`, and `low=0`. These values are not credible market highs/lows. The local service/schema fix now serializes unavailable OHLC values as `null` and allows nulls in the response model; it does not invent substitute prices.
3. **No-trade / incomplete rows:** 75 of 560 quotes had zero volume; one had `current=0` and `volume=0`; two had zero market capitalization. These may be valid inactive/no-trade records or incomplete upstream data and need source-level review.
4. **Price history and technical indicators are stale:** HBL `range=1D` returned five trading bars, which is consistent with a ten-calendar-day fetch window, but its latest bar was 2026-09-18 (age 6 days; `is_stale: true`). The indicator response used the same 2026-09-18 close and also reported age 6 / stale.
5. **Overview day range unavailable:** HBL overview returned `day_range.low=null` and `day_range.high=null`. The API is accurately signaling that it could not find values; the upstream OHLC/history feed needs repair.
6. **Company-name search is incomplete:** searching `HBL` returned `name: "HBL"`, and searching `Habib` returned an empty list. The production stock-name records/fallback are ticker-based, so the autocomplete cannot reliably search official company names.
7. **Fundamentals are partial:** HBL was marked `data_status: "partial"`; annual and quarterly financial statements were null. The response includes a message explicitly saying upstream fundamentals are missing and are not estimated.
8. **Outlier in losers list:** SWL was returned at LDCP 316.53/current 44.00 (−86.1%) with zero volume. The same audit found one arithmetic change mismatch: AAL had `current=0`, `ldcp=16`, and `change=0`, causing the mismatch. Workspace fixes now null unavailable current/change values and exclude zero-volume rows from movers, volume spikes, and market breadth. The SWL row will no longer appear as a mover unless it has a positive trading volume.

The API response models are structured and consistent at the top level. Optional null values in fundamentals, indicator summaries, and day ranges were schema-supported; those values were not replaced with estimates. KSE-100 `shariah_compliant: null` appears to be a not-applicable optional field, not a schema defect.

## Workspace fixes

- Malformed stock symbols now return 422 input-validation errors instead of 503 service-unavailable errors.
- Market quote sorting now validates `sort_by` against the supported five fields and `order` against `asc`/`desc`; invalid values now return 422.
- Unavailable OHLC and current quote values now serialize as null rather than false zero prices; corresponding change values are null when they cannot be computed. Valid positive values are preserved.
- Zero-volume/no-trade rows are excluded from gainers, losers, volume spikes, sentiment breadth, and sector mover statistics.
- The project’s known ticker aliases now support company-name autocomplete; `Habib` resolves to HBL and returns `Habib Bank` instead of an empty result/ticker-only label.
- Tests now reflect that these endpoints are public and cover bad sort inputs and zero-to-null quote normalization.

The live AWS app still returned 503 for an invalid symbol and 200 for invalid sort inputs during this audit because these workspace fixes are not deployed.

## Verification

Focused backend suite before deployment: **39 passed** (`tests/api/test_stocks_api.py`, `tests/api/test_market_api.py`, `tests/unit/test_market_service.py`, `tests/unit/test_stock_search.py`). The follow-up sparse-row regression suite passes **41 tests**.

Read-only production probes were saved as reproducible PowerShell runners in `backend/scripts/production_stocks_market_audit.ps1` and `backend/scripts/production_market_quality_summary.ps1`.

## Production follow-up

Deploy the workspace changes, then rerun the invalid-symbol/sort probes. Separately repair or refresh market quote and OHLC/history ingestion, reconcile stale price history and SWL's large price discontinuity, and populate canonical company names in the stock search index/database.

## Post-deployment retest

Commit `bfbb40c` was pushed to `main`, and production health returned 200. The same 29 route/input probes were rerun against the deployed app: **all 29 returned valid JSON**, with valid requests returning 200 and invalid symbol, sort, range, and bound requests returning 422. The previously invalid `Habib` search returned HBL.

The first full-universe (`limit=1000`) quote request after deployment returned 503 even though all 29 probes passed. Pagination isolated the response-validation failure to quote offset 485, a sparse/unclassified row; all other 50-row pages tested returned 200. A follow-up workspace fix normalizes missing symbol/name/sector/volume/market-cap metadata, permits null market values in the response schema, and keeps sector/search filters safe for unclassified records. That follow-up passes the full focused suite (**41 passed**) and is awaiting its deployment and production retest.
