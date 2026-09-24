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

The first full-universe (`limit=1000`) request after `bfbb40c` returned 503 even though the 29 probes passed. Pagination isolated the response-validation failure to quote offset 485, a sparse/unclassified row; other 50-row pages tested returned 200. Follow-up commit `170afd9` normalizes missing symbol/name/sector/volume/market-cap metadata, permits null market values in the response schema, and makes sector/search filters safe for unclassified records. The focused suite passes **41/41** after this fix.

After `170afd9` deployed, all 29 route/input probes passed again with valid JSON. The offset-485 record and the full-universe request returned 200; all 560 quote items were serialized. `Habib` search returned `{symbol: "HBL", name: "Habib Bank"}`, and ascending sort by current price worked with unavailable prices placed last.

Post-fix data summary: all 560 quotes have null open/high/low values because the source feed supplies no OHLC; one quote (AAL) has null current/change values; zero rows fail arithmetic reconciliation when unavailable values are excluded; 75 rows still have zero volume; two zero market caps were converted to null; and the top-10 losers response contains no zero-volume rows. The quote snapshot itself is still marked stale, HBL history is still six days old, the HBL day range remains unavailable, and annual/quarterly fundamentals remain null. These are upstream refresh/source gaps and are correctly exposed as stale/null; the API cannot reconstruct true market prices or missing financial statements.

## Final deployment verification (2026-09-25)

Commits `eb8704f` and `289c01e` were pushed to `main`. The latter increments the fundamentals cache key so older ticker-only HBL profiles are not reused. After deployment, the same **29** Stocks/Market route and validation cases were run again against AWS. All 29 returned the expected HTTP status and valid JSON: valid requests returned 200; invalid range, period, symbol, sort, and bounds returned 422. The response keys were checked for all endpoint families. The entire quote endpoint returned **560 of 560** items.

The final quality pass confirmed:

- HBL overview and fundamentals now both return `Habib Bank Limited`; overview day range is `{low: 299.0, high: 312.05}`.
- All 560 quotes still have unavailable OHLC values; the API returns null instead of fabricated zeros. One quote has unavailable current price. There are no arithmetic mismatches among available price/change values.
- Zero-volume rows remain in the full market quote universe, but none appears in the top-10 losers endpoint.
- The quote snapshot remains marked stale. HBL history/indicators still use the 2026-09-18 data point (six days old at verification time).
- HBL annual and quarterly fundamentals remain null and the response remains explicitly `partial`; the upstream source does not provide those statement sets.

Final focused backend regression suite: **43 passed** (`tests/api/test_stocks_api.py`, `tests/api/test_market_api.py`, `tests/unit/test_market_service.py`, `tests/unit/test_stock_search.py`). The final production pass covers every documented public Stocks and Market GET operation plus representative valid filters and validation failures. No POST operation is documented for these public modules in the OpenAPI spec.

## Production-readiness follow-up — 2026-09-25

- Replaced the Market Pulse page's hard-coded quote/index lists and generated sparklines with public Market API requests for quotes, indices, sentiment, and index constituents. Gainers, losers, active-volume sorting, search, and index filters now operate on API records.
- Stale OHLCV snapshots now trigger an incremental fetch from the last stored bar and a sorted/deduplicated merge. If the PSX history source fails, the last known bars are retained and their existing `is_stale`/age metadata continues to expose the gap. Missing optional bar columns serialize as null rather than raising.
- Added quote and index freshness indicators, stale-constituent suppression for KMI-30 badges, explicit errors/loading/empty states, and null-aware numeric rendering. Stock detail shows only fields present in the API and no longer presents placeholder charts/financial data as if available.
- Frontend production configuration still requires `VITE_API_URL` ending in `/api/v1`. The local frontend env file has no such setting and the repository has no frontend build/deploy workflow, so the page intentionally shows a configuration error in production until the web host/build environment supplies the API URL. Development falls back to localhost.
- Validation: **45** Stocks/Market tests passed across API, market service, stock search, and OHLCV refresh suites; `npm run build` passed. `npm run lint` passed with existing warnings in `News_Seciton.jsx` and `Stockperview.jsx`; the changed Market Pulse file introduced no lint warnings.

The AWS API continues to expose source freshness; quote/history staleness and unavailable financial fundamentals remain upstream data-quality limitations. This follow-up improves frontend behavior but does not eliminate missing source records, and the frontend is not production-connected until its build environment configures `VITE_API_URL`.

### AWS check after commit `7bf683b`

- `GET /stocks/HBL/price-history?range=1W` returned 200 with `as_of_date=2026-09-18`, `data_age_days=6`, and `is_stale=true` at the 2026-09-25 check. A direct, unauthenticated query to the configured PSX history source for HBL returned `PSXNotFoundError`; stale bars were preserved and correctly marked rather than replaced with invented data.
- The OHLCV code path and regression tests are deployed, but the history source currently cannot refresh HBL. A functioning licensed historical-data source is required before history can be considered current.
