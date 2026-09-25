# Basarat API Quality & Route Audit Report
**Timestamp:** 2026-09-25T19:40:36.870367+00:00  
**Target URL:** `http://16.16.26.247:8000`  
**Total Tested:** 38  
**Pass Rate:** 38/38  

## Detailed Results Table

| Module | Method | Endpoint | HTTP Status | Latency | Grade | Data Summary / Anomalies |
| :--- | :---: | :--- | :---: | :---: | :---: | :--- |
| Market | `GET` | `/market/sectors/performance` | 200 | 2233.58ms | **RICH (A+)** | sectors: list[37], total_sectors=37, total_companies=560, classified_companies=548, unclassified_companies=12, as_of=2026-09-24T18:55:... (+1 more keys) |
| Market | `GET` | `/market/indices` | 200 | 621.59ms | **RICH (A+)** | indices: list[18], as_of=None, is_stale=True |
| Market | `GET` | `/market/indices/kse-100` | 200 | 800.61ms | **RICH (A+)** | index=KSE-100, code=KSE100, shariah_compliant=None, constituents: list[100], as_of=None, is_stale=True |
| Market | `GET` | `/market/indices/kse-30` | 200 | 619.39ms | **RICH (A+)** | index=KSE-30, code=KSE30, shariah_compliant=None, constituents: list[30], as_of=None, is_stale=True |
| Market | `GET` | `/market/indices/kmi-30` | 200 | 659.49ms | **RICH (A+)** | index=KMI-30, code=KMI30, shariah_compliant=True, constituents: list[30], as_of=None, is_stale=True |
| Market | `GET` | `/market/gainers` | 200 | 745.15ms | **RICH (A+)** | gainers: list[5], as_of=2026-09-24T18:55:..., is_stale=True |
| Market | `GET` | `/market/losers` | 200 | 760.83ms | **RICH (A+)** | losers: list[5], as_of=2026-09-24T18:55:..., is_stale=True |
| Market | `GET` | `/market/volume-spikes` | 200 | 744.59ms | **RICH (A+)** | volume_spikes: list[5], as_of=2026-09-24T18:55:..., is_stale=True |
| Market | `GET` | `/market/sentiment-overview` | 200 | 746.91ms | **RICH (A+)** | market_mood=strongly_bearish, advancing=99, declining=350, unchanged=36, advance_decline_ratio=0.28, gainers_pct=20.4 (+5 more keys) |
| Market | `GET` | `/market/quotes` | 200 | 862.3ms | **RICH (A+)** | stocks: list[10], total=560, limit=10, offset=0, filtered=False, as_of=2026-09-24T18:55:... (+1 more keys) |
| Stocks | `GET` | `/stocks/search` | 200 | 2631.95ms | **ADEQUATE (B)** | results: list[1] |
| Stocks | `GET` | `/stocks/search` | 200 | 3503.83ms | **ADEQUATE (B)** | results: list[5] |
| Stocks | `GET` | `/stocks/OGDC/overview` | 200 | 3723.08ms | **RICH (A+)** | symbol=OGDC, name=Ogdcl, sector=OIL & GAS EXPLORA..., current_price=316.23, ltp=316.23, ldcp=319.53 (+11 more keys) |
| Stocks | `GET` | `/stocks/OGDC/price-history` | 200 | 623.34ms | **RICH (A+)** | symbol=OGDC, range=1M, bars: list[19], as_of_date=2026-09-18, data_age_days=7, is_stale=True |
| Stocks | `GET` | `/stocks/OGDC/price-history` | 200 | 1014.06ms | **RICH (A+)** | symbol=OGDC, range=1Y, bars: list[246], as_of_date=2026-09-18, data_age_days=7, is_stale=True |
| Stocks | `GET` | `/stocks/OGDC/technical-indicators` | 200 | 319.36ms | **RICH (A+)** | symbol=OGDC, period=14, as_of_date=2026-09-18, data_age_days=7, is_stale=True, overall_signal=BEARISH (+4 more keys) |
| Stocks | `GET` | `/stocks/OGDC/fundamentals` | 200 | 6784.42ms | **RICH (A+)** | symbol=OGDC, data_status=partial, data_message=Some company fund..., company_profile: dict[8], equity_profile: dict[5], financials_annual=None (+11 more keys) |
| Stocks | `GET` | `/stocks/OGDC/news` | 200 | 2516.36ms | **RICH (A+)** | items: list[20], next_cursor=2026-08-17T06:53:..., has_more=True, row=news, last_updated_at=2026-09-25T11:30:..., empty_reason=None (+1 more keys) |
| Stocks | `GET` | `/stocks/SYS/overview` | 200 | 3882.28ms | **RICH (A+)** | symbol=SYS, name=Systems Limited, sector=TECHNOLOGY & COMM..., current_price=119.47, ltp=119.47, ldcp=121.69 (+11 more keys) |
| Stocks | `GET` | `/stocks/SYS/price-history` | 200 | 628.67ms | **RICH (A+)** | symbol=SYS, range=1M, bars: list[19], as_of_date=2026-09-18, data_age_days=7, is_stale=True |
| Stocks | `GET` | `/stocks/SYS/price-history` | 200 | 1162.55ms | **RICH (A+)** | symbol=SYS, range=1Y, bars: list[246], as_of_date=2026-09-18, data_age_days=7, is_stale=True |
| Stocks | `GET` | `/stocks/SYS/technical-indicators` | 200 | 488.71ms | **RICH (A+)** | symbol=SYS, period=14, as_of_date=2026-09-18, data_age_days=7, is_stale=True, overall_signal=NEUTRAL (+4 more keys) |
| Stocks | `GET` | `/stocks/SYS/fundamentals` | 200 | 5057.3ms | **RICH (A+)** | symbol=SYS, data_status=partial, data_message=Some company fund..., company_profile: dict[8], equity_profile: dict[5], financials_annual=None (+11 more keys) |
| Stocks | `GET` | `/stocks/SYS/news` | 200 | 1638.36ms | **RICH (A+)** | items: list[20], next_cursor=2026-05-25T08:33:..., has_more=True, row=news, last_updated_at=2026-09-25T11:30:..., empty_reason=None (+1 more keys) |
| Stocks | `GET` | `/stocks/HUBC/overview` | 200 | 3868.28ms | **RICH (A+)** | symbol=HUBC, name=Hub Power, sector=POWER GENERATION ..., current_price=202.59, ltp=202.59, ldcp=205.56 (+11 more keys) |
| Stocks | `GET` | `/stocks/HUBC/price-history` | 200 | 802.92ms | **RICH (A+)** | symbol=HUBC, range=1M, bars: list[19], as_of_date=2026-09-18, data_age_days=7, is_stale=True |
| Stocks | `GET` | `/stocks/HUBC/price-history` | 200 | 1023.12ms | **RICH (A+)** | symbol=HUBC, range=1Y, bars: list[246], as_of_date=2026-09-18, data_age_days=7, is_stale=True |
| Stocks | `GET` | `/stocks/HUBC/technical-indicators` | 200 | 347.65ms | **RICH (A+)** | symbol=HUBC, period=14, as_of_date=2026-09-18, data_age_days=7, is_stale=True, overall_signal=NEUTRAL (+4 more keys) |
| Stocks | `GET` | `/stocks/HUBC/fundamentals` | 200 | 5165.14ms | **RICH (A+)** | symbol=HUBC, data_status=partial, data_message=Some company fund..., company_profile: dict[8], equity_profile: dict[5], financials_annual=None (+11 more keys) |
| Stocks | `GET` | `/stocks/HUBC/news` | 200 | 1349.47ms | **RICH (A+)** | items: list[0], next_cursor=None, has_more=False, row=news, last_updated_at=2026-09-25T11:30:..., empty_reason=no_results (+1 more keys) |
| News | `GET` | `/news` | 200 | 1828.37ms | **RICH (A+)** | items: list[10], next_cursor=2026-09-25T11:00:..., has_more=True, row=news, last_updated_at=2026-09-25T11:30:..., empty_reason=None (+1 more keys) |
| News | `GET` | `/news/refresh/status` | 200 | 336.29ms | **RICH (A+)** | state=failed, last_success_at=2026-09-25T11:30:..., new_articles=7 |
| News | `GET` | `/news/market-status` | 200 | 1168.46ms | **RICH (A+)** | timezone=Asia/Karachi, current_time_pkt=2026-09-26T00:40:..., status=closed, is_weekend=True, is_holiday=False, ingestion_allowed=False (+4 more keys) |
| News | `GET` | `/news/sources` | 200 | 1043.22ms | **ADEQUATE (B)** | sources: list[8] |
| Shariah | `GET` | `/shariah/kmi30` | 200 | 170.24ms | **RICH (A+)** | index=KMI-30, total_constituents=30, as_of=2025-12-31T00:00:00Z, is_stale=True, effective_from=2026-05-25T00:00:00Z, source_url=https://dps.psx.c... (+1 more keys) |
| Shariah | `GET` | `/shariah/OGDC` | 200 | 1045.94ms | **RICH (A+)** | symbol=OGDC, screening_available=True, is_shariah_compliant=True, overall_score=None, screening_method=PSX KMI-30 screen..., screened_at=2025-12-31T00:00:00 (+10 more keys) |
| Shariah | `GET` | `/shariah/OGDC/criteria` | 200 | 921.08ms | **RICH (A+)** | symbol=OGDC, screening_available=True, is_shariah_compliant=True, criteria: list[6], data_as_of=2025-12-31T00:00:00Z, data_is_stale=True (+1 more keys) |
| Shariah | `GET` | `/shariah/OGDC/purification` | 200 | 919.38ms | **RICH (A+)** | symbol=OGDC, dividend_income=1000.0, purification_amount=66.2, purification_rate=0.0662, notes=Using the PSX scr..., data_as_of=2025-12-31T00:00:00Z (+3 more keys) |