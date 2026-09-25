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

## Production-readiness follow-up — 2026-09-25

The product owner confirmed purification is **dividend income × rate** and confirmed that the organization has a PSX redistribution license. The first code follow-up was committed and deployed earlier in this work. This addendum records the subsequent source-data integration and current verification.

- Added the official PSX KMI-30 recomposition/screening snapshot from notice PSX/N-610 dated 2026-05-15. It lists the 30 constituents effective 2026-05-25 and screening ratios calculated from company accounts as of 2025-12-31. Source: [PSX notice](https://dps.psx.com.pk/download/attachment/277332-1.pdf).
- Public KMI-30, single-symbol screening, and criteria payloads now carry the source URL, accounts-as-of date, effective date, and a stale-data indicator. Unavailable source fields remain null; the notice's N/A values for MEBL are retained.
- The API preserves PSX's published final Shariah status and exposes the individual ratio checks separately. It identifies PSX exceptions for OGDC and HUBC rather than making those threshold ratios look like ordinary pass/fail outcomes.
- Purification uses the official PSX income ratio as the provisional rate where PSX marks the source rate available. It multiplies this by `dividend_income`, reports the exact result and source date, and warns that the rate is provisional. MEBL has no published income ratio in the notice, so its purification route remains unavailable.
- The source ratios are almost nine months old on the audit date and are correctly reported as stale. This is an explicitly dated last-known official dataset, not a claim that the companies have been screened against newer accounts.

Local verification: **21/21** tests passed in `tests/api/test_shariah_api.py`; changed Python modules passed `py_compile`; the JSON snapshot contains exactly 30 tickers; `git diff --check` passed. The test coverage checks anonymous access, source dates and URL, OGDC's 6.62% provisional rate and PKR 993 calculation for PKR 15,000 dividend income, and MEBL's unavailable rate.

The remaining publication step is to push this source-data integration and then confirm that GitHub deployment completed before repeating the anonymous production smoke checks. Do not describe this new snapshot as live on AWS until that check succeeds.

Security follow-up: an earlier live-test script revision included an inline test-account password. The working-tree script no longer contains it, but prior Git revisions retain it. No credential was read or used during this work. If that password was valid anywhere, disable or rotate the account and treat the value as exposed; consider history cleanup after rotation.
