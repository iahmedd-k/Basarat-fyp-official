# PSX library probe results

Tested locally on 2026-10-01, 05:58–06:12 Asia/Karachi, before the market opened. No app source files or application dependencies were changed. Live trading quotes cannot be verified outside market hours; these observations are network fetches of the latest available session data.

## `psx-dps` 0.1.0

- Forced market-watch request returned **495 rows**.
- KSE-100 constituents returned **100 rows**.
- HBL EOD returned **22 rows** for Sep 1–30, with Sep 30 as the latest date.
- HBL intraday returned **682 ticks**; its latest tick was Sep 30 at 10:47 PKT, not Oct 1.
- `history_by_date("2026-09-30")` returned **617 unique symbols** with open/high/low/close/volume present on every row, no duplicate symbols, and all **100/100** symbols in this project’s frozen KSE-100 universe. It also returned 594 rows for 2025-10-01 and 780 rows for 2021-10-01, including HBL.
- No structured fundamentals method was present.

**Best result:** one daily request produced OHLCV for all response symbols and covered the project’s full KSE-100 analysis universe on the tested date. This is a much better shape for the daily update and historical backfill than fetching each symbol/month separately. Validate the endpoint over a longer date range before loading the full historical database.

## `psxdata` 1.2.0

- `symbols()` returned **1,028** instruments with symbol, name, sector name, and ETF/debt/GEM flags.
- HBL quote and HBL daily history returned data; HBL history had 22 rows through Sep 30 and OHLCV fields.
- The history call logged **one OHLC constraint warning** and a date-order warning; the returned dates were descending (Sep 30 first, Sep 1 last). Sort and validate before persistence.
- Its cached screener had **747 rows** and 11 fields. `market_cap` was missing for 671 rows (**89.83%**), `free_float` for 662 (**88.62%**), and sector for 53 (**7.10%**). HBL’s sector in quote output was a numeric code (`807`), not a display name.
- `fundamentals("HBL")` and the unfiltered financial-reports call both returned **zero parsed rows**. The client has no `dividends()` method.

**Assessment:** useful for symbol metadata, quotes, screener fields, and OHLCV experiments, but its tested output is not complete/clean enough to fill all permanent reference and fundamental fields without additional parsing and validation.

## `psx-feed` 0.0.1b1

- `tickers()` failed with **HTTP 404**.
- One HBL September-history call returned **zero rows** without raising an error.
- Its public exports are only `stocks()` and `tickers()` (plus the module/data reader); no live quote or fundamentals API was present.
- Inspected code makes up to six month requests concurrently and does not specify request timeouts or call `raise_for_status()` in the download path.

**Assessment:** not suitable as the production primary or fallback based on this probe. PyPI currently identifies the release as a pre-release.

## Coverage of the requested permanent fields

- Symbol/name/sector and some screener values: partially available from `psxdata`; listing/profile fields such as website and business description were not returned by the tested symbol schema.
- Daily OHLCV: `psx-dps.history_by_date()` returned the strongest all-symbol result in this test. Validate each returned date and reconcile missing symbols before marking a pipeline run complete.
- RSI, MACD, moving averages, and Bollinger Bands: derive from validated persisted daily closes; none of the three needs to be the indicator source.
- P/E and dividend yield: present in the screener snapshot, with source/definition/freshness validation still needed.
- EPS, revenue, profits, assets/liabilities, shares, detailed ratios: not returned as structured financial values in these probes. `psxdata.fundamentals()` describes filings, and yielded zero rows in this run.
- Declared dividend amount, ex-date, book closure, and payment date: none of the clients exposed a structured dividend endpoint in the tested API.
- Recommendations, forecasts, and risk metrics: calculate using this project's stored prices/fundamentals and models; these libraries are not a source for them.

## Recommended next step

Use `psx-dps` as the first candidate for the live whole-market snapshot and daily all-symbol OHLCV request. Persist validated EOD rows to PostgreSQL and use Redis as a cache. Keep refresh work serialized and obey the client cache/rate controls. Do not claim the full fundamentals/dividend dataset is covered: none of these three sources supplied it in this local test. A trading-hours run is still required to confirm that returned quotes actually change during the session.

## Probe environment

- Python 3.13.7 on Windows.
- `psx-dps` was installed in its own temporary virtual environment from Git commit `350301cfbd9c19ee2827a0309d01a7959d7431f0`.
- `psxdata` and `psx-feed` packages were imported from temporary target directories, using already installed system data/HTTP dependencies; no global packages were installed or upgraded. The full dependency install was not completed because the pandas/PyArrow downloads were very slow.
- Probe scripts and compact results are in this temporary folder. No historical bulk download was started.
