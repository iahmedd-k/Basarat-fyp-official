# Basarat API Quality & Route Audit Report
**Timestamp:** 2026-09-25T19:25:29.131295+00:00  
**Target URL:** `http://16.16.26.247:8000`  
**Total Tested:** 36  
**Pass Rate:** 35/36  

## Detailed Results Table

| Module | Method | Endpoint | HTTP Status | Latency | Grade | Data Summary / Anomalies |
| :--- | :---: | :--- | :---: | :---: | :---: | :--- |
| Market | `GET` | `/market/indices` | 200 | 786.23ms | **ADEQUATE (B)** | indices: list[18], as_of=None, is_stale=True |
| Market | `GET` | `/market/indices/kse-100` | 200 | 784.91ms | **DEGRADED (C)** | index=KSE-100, code=KSE100, shariah_compliant=None, constituents: list[100], as_of=None, is_stale=True<br/>[!] Critical key missing or null: 'change_pct' |
| Market | `GET` | `/market/indices/kse-30` | 200 | 613.85ms | **ADEQUATE (B)** | index=KSE-30, code=KSE30, shariah_compliant=None, constituents: list[30], as_of=None, is_stale=True |
| Market | `GET` | `/market/indices/kmi-30` | 200 | 614.9ms | **ADEQUATE (B)** | index=KMI-30, code=KMI30, shariah_compliant=True, constituents: list[30], as_of=None, is_stale=True |
| Market | `GET` | `/market/gainers` | 200 | 749.82ms | **RICH (A+)** | gainers: list[5], as_of=2026-09-24T18:55:..., is_stale=True |
| Market | `GET` | `/market/losers` | 200 | 738.5ms | **RICH (A+)** | losers: list[5], as_of=2026-09-24T18:55:..., is_stale=True |
| Market | `GET` | `/market/volume-spikes` | 200 | 738.48ms | **RICH (A+)** | volume_spikes: list[5], as_of=2026-09-24T18:55:..., is_stale=True |
| Market | `GET` | `/market/sentiment-overview` | 200 | 740.27ms | **RICH (A+)** | market_mood=strongly_bearish, advancing=99, declining=350, unchanged=36, advance_decline_ratio=0.28, gainers_pct=20.4 (+5 more keys) |
| Market | `GET` | `/market/status` | 404 | 174.08ms | **DEGRADED (C)** | detail=Not Found<br/>[!] Critical key missing or null: 'is_open' |
| Stocks | `GET` | `/stocks/search` | 200 | 1037.81ms | **ADEQUATE (B)** | results: list[1] |
| Stocks | `GET` | `/stocks/search` | 200 | 2841.43ms | **ADEQUATE (B)** | results: list[5] |
| Stocks | `GET` | `/stocks/OGDC/overview` | 200 | 3108.95ms | **ADEQUATE (B)** | symbol=OGDC, name=Ogdcl, sector=OIL & GAS EXPLORA..., current_price=316.23, ltp=316.23, ldcp=319.53 (+11 more keys) |
| Stocks | `GET` | `/stocks/OGDC/price-history` | 200 | 173.59ms | **RICH (A+)** | symbol=OGDC, range=1M, bars: list[19], as_of_date=2026-09-18, data_age_days=7, is_stale=True |
| Stocks | `GET` | `/stocks/OGDC/price-history` | 200 | 348.47ms | **RICH (A+)** | symbol=OGDC, range=1Y, bars: list[246], as_of_date=2026-09-18, data_age_days=7, is_stale=True |
| Stocks | `GET` | `/stocks/OGDC/technical-indicators` | 200 | 481.28ms | **RICH (A+)** | symbol=OGDC, period=14, as_of_date=2026-09-18, data_age_days=7, is_stale=True, overall_signal=BEARISH (+4 more keys) |
| Stocks | `GET` | `/stocks/OGDC/fundamentals` | 503 | 758.82ms | **DEGRADED (C)** | success=False, error: dict[2]<br/>[!] Critical key missing or null: 'symbol'; Critical key missing or null: 'pe_ratio' |
| Stocks | `GET` | `/stocks/OGDC/news` | 200 | 1635.82ms | **ADEQUATE (B)** | items: list[20], next_cursor=2026-08-17T06:53:..., has_more=True, row=news, last_updated_at=2026-09-25T11:30:..., empty_reason=None (+1 more keys) |
| Stocks | `GET` | `/stocks/SYS/overview` | 200 | 3276.95ms | **ADEQUATE (B)** | symbol=SYS, name=Systems Limited, sector=TECHNOLOGY & COMM..., current_price=119.47, ltp=119.47, ldcp=121.69 (+11 more keys) |
| Stocks | `GET` | `/stocks/SYS/price-history` | 200 | 173.06ms | **RICH (A+)** | symbol=SYS, range=1M, bars: list[19], as_of_date=2026-09-18, data_age_days=7, is_stale=True |
| Stocks | `GET` | `/stocks/SYS/price-history` | 200 | 347.79ms | **RICH (A+)** | symbol=SYS, range=1Y, bars: list[246], as_of_date=2026-09-18, data_age_days=7, is_stale=True |
| Stocks | `GET` | `/stocks/SYS/technical-indicators` | 200 | 483.01ms | **RICH (A+)** | symbol=SYS, period=14, as_of_date=2026-09-18, data_age_days=7, is_stale=True, overall_signal=NEUTRAL (+4 more keys) |
| Stocks | `GET` | `/stocks/SYS/fundamentals` | 503 | 765.86ms | **DEGRADED (C)** | success=False, error: dict[2]<br/>[!] Critical key missing or null: 'symbol'; Critical key missing or null: 'pe_ratio' |
| Stocks | `GET` | `/stocks/SYS/news` | 200 | 1471.97ms | **ADEQUATE (B)** | items: list[20], next_cursor=2026-05-25T08:33:..., has_more=True, row=news, last_updated_at=2026-09-25T11:30:..., empty_reason=None (+1 more keys) |
| Stocks | `GET` | `/stocks/HUBC/overview` | 200 | 3272.08ms | **ADEQUATE (B)** | symbol=HUBC, name=Hub Power, sector=POWER GENERATION ..., current_price=202.59, ltp=202.59, ldcp=205.56 (+11 more keys) |
| Stocks | `GET` | `/stocks/HUBC/price-history` | 200 | 171.04ms | **RICH (A+)** | symbol=HUBC, range=1M, bars: list[19], as_of_date=2026-09-18, data_age_days=7, is_stale=True |
| Stocks | `GET` | `/stocks/HUBC/price-history` | 200 | 350.05ms | **RICH (A+)** | symbol=HUBC, range=1Y, bars: list[246], as_of_date=2026-09-18, data_age_days=7, is_stale=True |
| Stocks | `GET` | `/stocks/HUBC/technical-indicators` | 200 | 478.85ms | **RICH (A+)** | symbol=HUBC, period=14, as_of_date=2026-09-18, data_age_days=7, is_stale=True, overall_signal=NEUTRAL (+4 more keys) |
| Stocks | `GET` | `/stocks/HUBC/fundamentals` | 503 | 755.59ms | **DEGRADED (C)** | success=False, error: dict[2]<br/>[!] Critical key missing or null: 'symbol'; Critical key missing or null: 'pe_ratio' |
| Stocks | `GET` | `/stocks/HUBC/news` | 200 | 1334.72ms | **ADEQUATE (B)** | items: list[0], next_cursor=None, has_more=False, row=news, last_updated_at=2026-09-25T11:30:..., empty_reason=no_results (+1 more keys) |
| News | `GET` | `/news` | 200 | 2325.52ms | **ADEQUATE (B)** | items: list[10], next_cursor=2026-09-25T11:00:..., has_more=True, row=news, last_updated_at=2026-09-25T11:30:..., empty_reason=None (+1 more keys) |
| News | `GET` | `/news/status` | 404 | 1040.19ms | **DEGRADED (C)** | success=False, error: dict[2]<br/>[!] Critical key missing or null: 'pipeline_status'; Critical key missing or null: 'total_articles_indexed' |
| News | `GET` | `/news/sources` | 200 | 1434.5ms | **ADEQUATE (B)** | sources: list[8] |
| Shariah | `GET` | `/shariah/kmi30` | 200 | 2396.28ms | **RICH (A+)** | index=KMI-30, total_constituents=30, as_of=2025-12-31T00:00:00Z, is_stale=True, effective_from=2026-05-25T00:00:00Z, source_url=https://dps.psx.c... (+1 more keys) |
| Shariah | `GET` | `/shariah/universe` | 200 | 1608.81ms | **DEGRADED (C)** | symbol=UNIVERSE, screening_available=False, is_shariah_compliant=None, overall_score=None, screening_method=None, screened_at=None (+10 more keys) |
| Shariah | `GET` | `/shariah/OGDC` | 200 | 925.81ms | **DEGRADED (C)** | symbol=OGDC, screening_available=True, is_shariah_compliant=True, overall_score=None, screening_method=PSX KMI-30 screen..., screened_at=2025-12-31T00:00:00 (+10 more keys)<br/>[!] Critical key missing or null: 'compliance_status' |
| Shariah | `GET` | `/shariah/OGDC/purification` | 200 | 918.18ms | **RICH (A+)** | symbol=OGDC, dividend_income=1000.0, purification_amount=66.2, purification_rate=0.0662, notes=Using the PSX scr..., data_as_of=2025-12-31T00:00:00Z (+3 more keys) |