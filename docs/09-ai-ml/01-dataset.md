# Dataset Documentation

## 1. Dataset Overview

The Basarat AI/ML predictive system is trained and evaluated on historical daily market data from the **Pakistan Stock Exchange (PSX)** spanning from **March 2020 through October 2026** (6.5+ years of continuous trading history). The primary dataset encompasses high-frequency daily Open, High, Low, Close, and Volume (OHLCV) records for the most liquid equities listed on the exchange.

---

## 2. Universe Definition & Coverage

### 2.1 Broad PSX Universe (100 Equities)
The primary predictive universe comprises **100 actively traded equities** meeting minimum liquidity criteria (daily trading activity on $>85\%$ of market sessions and average daily turnover $> PKR 5,000,000$). This universe represents $>85\%$ of the total market capitalization and trading volume of the PSX.

### 2.2 Core 15 Liquid Benchmark Universe
For high-conviction benchmarking and evaluation, a core subset of **15 heavyweight equities** representing $>60\%$ of KSE-100 index movement is monitored:

| Sector | Ticker Symbols | Sector Description |
|---|---|---|
| **Oil & Gas Exploration** | `OGDC`, `PPL`, `MARI` | Upstream petroleum producers driving index weight |
| **Fertilizers** | `ENGROH`, `FFC`, `EFERT` | Agricultural chemicals & conglomerates |
| **Commercial Banking** | `MCB`, `HBL`, `UBL`, `MEBL` | Top private and Islamic commercial banks |
| **Cement** | `LUCK`, `DGKC` | Infrastructure and construction leaders |
| **Technology & IT** | `SYS`, `TRG` | Export-oriented IT consulting and tech venture |
| **Power Generation** | `HUBC` | Primary independent power producer (IPP) |
| **Oil Marketing (OMC)** | `PSO` | National petroleum marketing enterprise |

---

## 3. Data Schema & Raw Attributes

The raw tabular dataset is persisted in Apache Parquet format (`data/features/features_daily.parquet`) and contains the following base attributes per trading session:

| Column Name | Data Type | Unit / Format | Description |
|---|---|---|---|
| `date` | `datetime64[ns]` | `YYYY-MM-DD` | PSX trading session date |
| `symbol` | `string` | Ticker (e.g. `OGDC`) | Unique equity symbol identifier |
| `open` | `float64` | PKR (Pakistani Rupee) | Opening market price |
| `high` | `float64` | PKR | Session intraday maximum price |
| `low` | `float64` | PKR | Session intraday minimum price |
| `close` | `float64` | PKR | Official closing price at session settlement |
| `volume` | `float64` | Number of Shares | Total shares transacted during the session |
| `daily_pct_change`| `float64` | Ratio ($\pm 0.075$) | Single-day percentage return: $(Close_t - Close_{t-1})/Close_{t-1}$ |
| `index_return_5d` | `float64` | Ratio | Rolling 5-day return of the KSE-100 benchmark index |
| `index_return_20d`| `float64` | Ratio | Rolling 20-day return of the KSE-100 benchmark index |

---

## 4. Dataset Scale & Volume Metrics

```
+-------------------------------------------------------------------------------+
|                            DATASET SUMMARY METRICS                            |
+-------------------------------------------------------------------------------+
|  Total Calendar Span          |  2020-03-12 to 2026-10-02 (6.5+ Years)        |
|  Total Daily Observations     |  151,484 Normalized Rows                      |
|  Total Tracked Symbols        |  100 Listed PSX Equities                      |
|  Trading Sessions Tracked     |  ~1,620 PSX Trading Days                      |
|  Average Daily Data Points    |  100 Symbols * 5 OHLCV + Indicators           |
|  Storage Footprint (Parquet)  |  ~42.8 MB (Snappy compressed columnar)        |
|  News Corpus Articles         |  >35,000 Articles (BR, Dawn, Mettis, SBP)     |
+-------------------------------------------------------------------------------+
```

---

## 5. Market Calendar & Trading Session Rules

The dataset accounts for the unique multi-session schedule of the Pakistan Stock Exchange:
- **Monday – Thursday**: Single continuous trading session: `09:15 PKT` to `15:30 PKT` (Market close).
- **Friday (Split Session)**:
  - Morning Session: `09:00 PKT` to `12:00 PKT`
  - Jummah Intermission: `12:00 PKT` to `14:30 PKT` (Market closed)
  - Afternoon Session: `14:30 PKT` to `16:30 PKT` (Market close)
- **PSX Circuit Limits**: Equities are constrained by a statutory daily price fluctuation band of **$\pm 7.5\%$ or PKR 1.00** (whichever is greater) from the previous closing price.
