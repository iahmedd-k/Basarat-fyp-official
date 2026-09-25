# Basarat API Quality & Route Audit Report
**Timestamp:** 2026-09-25T19:21:16.616255+00:00  
**Target URL:** `http://16.16.26.247:8000`  
**Total Tested:** 17  
**Pass Rate:** 17/17  

## Detailed Results Table

| Module | Method | Endpoint | HTTP Status | Latency | Grade | Data Summary / Anomalies |
| :--- | :---: | :--- | :---: | :---: | :---: | :--- |
| System | `GET` | `/` | 200 | 498.64ms | **DEGRADED (C)** | message=Basarat API, version=v1, status=online, openapi_url=/api/v1/openapi.json<br/>[!] Critical key missing or null: 'name' |
| System | `GET` | `/health` | 200 | 170.42ms | **DEGRADED (C)** | status=ok<br/>[!] Critical key missing or null: 'services' |
| System | `GET` | `/health/ready` | 200 | 3948.38ms | **ADEQUATE (B)** | status=healthy, services: dict[5] |
| System | `GET` | `/openapi.json` | 200 | 1576.16ms | **RICH (A+)** | openapi=3.1.0, info: dict[2], paths: dict[107], components: dict[2], tags: list[20] |
| Market | `GET` | `/market/indices` | 200 | 617.38ms | **ADEQUATE (B)** | indices: list[18], as_of=None, is_stale=True |
| Market | `GET` | `/market/indices/kse-100` | 200 | 891.02ms | **DEGRADED (C)** | index=KSE-100, code=KSE100, shariah_compliant=None, constituents: list[100], as_of=None, is_stale=True<br/>[!] Critical key missing or null: 'change_pct' |
| Market | `GET` | `/market/indices/kse-30` | 200 | 616.71ms | **ADEQUATE (B)** | index=KSE-30, code=KSE30, shariah_compliant=None, constituents: list[30], as_of=None, is_stale=True |
| Market | `GET` | `/market/indices/kmi-30` | 200 | 625.0ms | **ADEQUATE (B)** | index=KMI-30, code=KMI30, shariah_compliant=True, constituents: list[30], as_of=None, is_stale=True |
| Market | `GET` | `/market/gainers` | 200 | 761.8ms | **RICH (A+)** | gainers: list[5], as_of=2026-09-24T18:55:..., is_stale=True |
| Market | `GET` | `/market/losers` | 200 | 750.17ms | **RICH (A+)** | losers: list[5], as_of=2026-09-24T18:55:..., is_stale=True |
| Market | `GET` | `/market/volume-spikes` | 200 | 748.44ms | **RICH (A+)** | volume_spikes: list[5], as_of=2026-09-24T18:55:..., is_stale=True |
| Market | `GET` | `/market/sentiment-overview` | 200 | 756.65ms | **RICH (A+)** | market_mood=strongly_bearish, advancing=99, declining=350, unchanged=36, advance_decline_ratio=0.28, gainers_pct=20.4 (+5 more keys) |
| Market | `GET` | `/market/status` | 404 | 180.5ms | **DEGRADED (C)** | detail=Not Found<br/>[!] Critical key missing or null: 'is_open' |
| Shariah | `GET` | `/shariah/kmi30` | 200 | 172.03ms | **RICH (A+)** | index=KMI-30, total_constituents=30, as_of=2025-12-31T00:00:00Z, is_stale=True, effective_from=2026-05-25T00:00:00Z, source_url=https://dps.psx.c... (+1 more keys) |
| Shariah | `GET` | `/shariah/universe` | 200 | 1073.93ms | **DEGRADED (C)** | symbol=UNIVERSE, screening_available=False, is_shariah_compliant=None, overall_score=None, screening_method=None, screened_at=None (+10 more keys) |
| Shariah | `GET` | `/shariah/OGDC` | 200 | 922.08ms | **DEGRADED (C)** | symbol=OGDC, screening_available=True, is_shariah_compliant=True, overall_score=None, screening_method=PSX KMI-30 screen..., screened_at=2025-12-31T00:00:00 (+10 more keys)<br/>[!] Critical key missing or null: 'compliance_status' |
| Shariah | `GET` | `/shariah/OGDC/purification` | 200 | 918.03ms | **RICH (A+)** | symbol=OGDC, dividend_income=1000.0, purification_amount=66.2, purification_rate=0.0662, notes=Using the PSX scr..., data_as_of=2025-12-31T00:00:00Z (+3 more keys) |