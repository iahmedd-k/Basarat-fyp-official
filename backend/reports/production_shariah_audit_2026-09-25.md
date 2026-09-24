# Production Shariah API Audit — 2026-09-25

Target: `http://16.16.26.247:8000/api/v1`

## Scope and baseline

Inspected the deployed OpenAPI routes and the local implementation. The public Shariah module documents four GET operations and no POST operations:

| Route | Purpose |
|---|---|
| `GET /shariah/kmi30` | KMI-30 constituent list |
| `GET /shariah/{symbol}` | Compliance screening |
| `GET /shariah/{symbol}/criteria` | Screening criteria breakdown |
| `GET /shariah/{symbol}/purification` | Purification calculation using `holding_qty` and `holding_value` |

Before deployment, all four route families returned 401 without credentials. Valid, invalid, and unknown-symbol cases were initially blocked by authentication.

## Fixes deployed

Commits `58350d2` and `19e2a18` were pushed to `main` and deployed.

- Removed authentication dependencies from all four Shariah GET route families. Rate limits remain active (30/minute for KMI-30; 60/minute for symbol endpoints).
- Added symbol path validation (1–15 characters, starting with a letter or digit; letters, digits, periods, and hyphens thereafter).
- Removed the default rule that treated unknown/unclassified stocks as compliant with invented debt and interest ratios. Responses now mark screening unavailable, compliance null, and criterion values/results null.
- Purification now returns 404 when no screening exists and 422 for securities that are screened non-compliant. This avoids returning a 100% charge against the entire holding value for HBL.
- Conventional/non-compliant classifications no longer invent debt and interest ratios; those criteria are null when the source values are absent.

## Production retest

After the final deployment, **13/13** anonymous endpoint, input-validation, and data-shape checks returned the expected status and valid JSON:

| Case | Result |
|---|---:|
| KMI-30 | 200; `total_constituents=30`, 30 returned |
| OGDC screening | 200; compliant, sector/method/date fields populated |
| HBL screening | 200; non-compliant based on conventional banking classification; unavailable ratio/score is null |
| Unknown symbol screening | 200; `screening_available=false`, compliance null |
| Invalid symbol | 422 |
| OGDC criteria | 200; six named criteria with thresholds, values, pass flags, and descriptions |
| HBL criteria | 200; known business criterion fails; unavailable financial ratios are null |
| Unknown symbol criteria | 200; all six values and pass flags are null |
| OGDC purification (`qty=100`, `value=15000`) | 200; amount 180 at 1.2% |
| HBL purification | 422; unavailable for a non-compliant screen |
| Unknown symbol purification | 404; no default purification rate |
| Zero quantity / negative value | 422 each |

The final focused test suite passed **18/18**: `tests/api/test_shariah_api.py`.

## Remaining data-quality limitations

- The response’s `overall_score` is the debt ratio (for OGDC it is `0.021`), not a normalized overall score. That field name can mislead consumers.
- `KMI30_PROFILES` supplies static sector, debt-ratio, and purification-rate values for enrichment. The public KMI-30 payload has no `as_of`/staleness field for those screening ratios; their currentness and authoritative source could not be confirmed in this endpoint audit. Treat those ratios as unverified until a dated authoritative screening feed is connected.
- The purification response applies the rate to the supplied `holding_value`; changing `holding_qty` while holding `holding_value` constant does not change the amount. The API text refers to “dividend/holding value,” leaving the intended financial basis ambiguous. Confirm the product’s intended basis before using the result for real-world charitable calculations.
- The live KMI-30 constituent payload was structurally valid and contained 30 records. This audit did not independently reconcile the full constituent roster or ratios against an authoritative dated PSX/Meezan publication.

These items need a product-approved data source/definition; this audit intentionally did not invent dates, ratios, or religious determinations.
