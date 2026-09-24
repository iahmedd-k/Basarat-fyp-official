# Feature contract

This contract belongs only to the isolated `psx_disclosure_v1` experiment. Column order is defined in `common.py` and saved beside every trained model. It does not describe or modify the current serving model.

## Shared target

At each stock/date observation, calculate close-to-close return from the current observed session to the exact fifth session on the union of PSX dates in the OHLCV archive. Require positive traded volume and an actual close at both endpoints. Subtract the median return of the other stocks with valid endpoints on that date. Rank the excess returns within that date: bottom 30% = class 0 `avoid`, middle 40% = class 1 `neutral`, top 30% = class 2 `buy`. This is relative performance, not probability that the absolute price rises.

## XGBoost feature order

XGBoost receives 29 cross-sectional percentile ranks, two unranked macro changes, and ten unranked disclosure inputs (41 total). Rank transforms are calculated by date over available stock rows. Macro and disclosure features are never cross-sectionally ranked.

### Ranked technical/market features (29)

| Input | Definition before cross-sectional rank |
|---|---|
| `dist_52w_high_csrank` | Close / trailing 252-observation high minus one; at least 50 observations |
| `mom_12m_1m_csrank` | 252-observation return minus 21-observation return |
| `ret_1d_csrank`, `ret_3d_csrank`, `ret_5d_csrank`, `ret_10d_csrank`, `ret_20d_csrank` | Close return over that many observed bars |
| `amihud_illiquidity_csrank` | `log1p(abs(ret_1d)/(close*volume + 0.001)*1e8)` |
| `is_lower_circuit_csrank` | Flag for one-bar return at or below -7.4% |
| `volatility_10d_csrank`, `volatility_20d_csrank`, `volatility_60d_csrank` | Rolling standard deviation of log returns, with stated minimum observations in code |
| `norm_atr14_csrank` | 14-bar average true range / close |
| `hl_range_csrank` | (high - low) / close |
| `co_range_csrank` | (close - open) / open |
| `dist_sma20_csrank`, `dist_sma50_csrank` | Close / simple moving average minus one |
| `dist_ema12_csrank`, `dist_ema26_csrank` | Close / exponential moving average minus one |
| `bb_pct_b_csrank` | Position of close between 20-bar Bollinger bands |
| `bb_width_csrank` | Bollinger band width / middle band |
| `rsi_norm_csrank` | (14-bar RSI - 50) / 50 |
| `macd_norm_csrank`, `macd_hist_norm_csrank` | MACD line/histogram divided by close |
| `volume_zscore_20_csrank` | 20-bar volume z-score |
| `vol_growth_5d_csrank`, `vol_growth_20d_csrank` | Volume percentage change over five/twenty observed bars |
| `rel_to_index_5d_csrank`, `rel_to_index_20d_csrank` | Stock return minus market median compounded return over the horizon |

### Unranked macro features (2)

- `policy_rate_chg_20d`: change in the as-of joined policy rate across 20 union-calendar sessions. The available macro source uses effective dates; it does not supply announcement timestamps, so this is a conservative effective-date join.
- `pkr_usd_ret_20d`: percentage change in as-of joined PKR/USD rate across 20 union-calendar sessions.

If macro history is absent, these remain missing for XGBoost. Do not fabricate values or rank the same market-wide series across symbols.

### Unranked disclosure features (10)

| Input | Definition |
|---|---|
| `evt_results_published` | Result/financial statement notice becomes available on this session; board agenda notices “to consider” results do not count as published results |
| `evt_dividend_announced` | Dividend/payout notice becomes available; a board agenda to consider it does not count as a declaration |
| `evt_bonus_or_rights` | Bonus or rights issue notice becomes available |
| `evt_board_meeting_notice` | Board meeting notice becomes available |
| `evt_material_info` | Other title-rule material information notice becomes available |
| `evt_count_5s` | Unique notices in the current and prior four market sessions |
| `sessions_since_results` | Market sessions since latest known results notice, capped at 252; 252 when no result is known in the covered history |
| `sessions_to_board_meeting` | Sessions to nearest future meeting date from a notice published by the feature cutoff; missing if unknown |
| `dividend_yield` | Explicit cash dividend per share / current close; face-value percentage is converted only with explicit face value; expires at ex-date or after 60 sessions |
| `eps_delta_over_price` | (current EPS - comparable prior EPS) / current close; requires populated comparable period and reporting basis; expires at the next results notice or after 126 sessions |

XGBoost supports missing numerical disclosures natively. Its two variants use identical covered rows: the baseline uses the 31 core inputs; the event model uses all 41 inputs.

## GRU feature order

The GRU uses 36 stationary price/market features, then 11 disclosure features (47 total). A sample is a sequence of 45 observed bars ending at the prediction date; sequence calendar span must not exceed 90 days. The target is still five union-calendar sessions ahead. Only train rows fit medians and the `StandardScaler`.

### Stationary core features (36)

`dist_sma20`, `dist_sma50`, `dist_ema12`, `dist_ema26`, `bb_pct_b`, `bb_width`, `norm_atr14`, `hl_range`, `co_range`, `rsi_norm`, `macd_norm`, `macd_hist_norm`, `log_return`, `ret_1d`, `ret_2d`, `ret_3d`, `ret_5d`, `ret_10d`, `ret_20d`, `volatility_10d`, `volatility_20d`, `volatility_30d`, `volatility_60d`, `volume_zscore_20`, `volume_change_5d`, `volume_change_10d`, `volume_change_20d`, `market_breadth_20d`, `rel_to_index_5d`, `rel_to_index_10d`, `rel_to_index_20d`, `index_return_5d`, `index_return_10d`, `index_return_20d`, `policy_rate_chg_20d`, `pkr_usd_ret_20d`.

### GRU disclosure inputs (11)

The five arrival flags are the same as XGBoost. The remaining inputs are `sessions_since_results`, `sessions_to_board_meeting`, `dividend_yield`, `eps_delta_over_price`, `dividend_parsed`, and `eps_parsed`. The final two are availability masks so the model can distinguish an unreported number from a measured zero. Sparse continuous values are imputed with train-only medians before scaling.

## Known data caveats

- “Observed bars” used for technical indicators can span more calendar time for illiquid/suspended stocks. The five-session target itself is calendar-aligned through the union PSX date set.
- The source OHLCV is not confirmed corporate-action adjusted. Returns and labels can be corrupted by bonus issues, splits, rights issues and ex-dividend adjustments.
- A current-constituent universe is not survivorship-free. Use delisted and removed securities if available.
- Events are not assigned from a model sentiment score. Current event labels are conservative title rules; event archive completeness is independently declared and required.
