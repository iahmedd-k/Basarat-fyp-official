# SBP Policy Rate Data

## File
`sbp_rate.csv` — columns: `effective_date`, `policy_rate`

## Purpose
This file is **manually maintained**. It holds the State Bank of Pakistan (SBP)
Monetary Policy Committee (MPC) policy rate decisions, which change roughly
6–8 times per year.

## How to Update
After each MPC announcement, add a row with the effective date and the new rate.
Source: [sbp.org.pk Monetary Policy Statements](https://www.sbp.org.pk/monetarypolicy/default.asp)
or [tradingeconomics.com/pakistan/interest-rate](https://tradingeconomics.com/pakistan/interest-rate).

## Known Gaps
- The 2018–2023 hiking/cutting cycle is **not fully dated** (only the starting
  rate of 6.25 is present). Fill these in manually when time permits.
- Some dates in mid-2025 are missing. Will be updated after SBP confirms exact
  effective dates.

## Usage in Pipeline
Joined onto the daily OHLCV timeline via `pandas.merge_asof` (forward-fill) in
`app/data/features/macro_features.py`. The most recent known rate is attached to
each trading date.
