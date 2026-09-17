# News & Events Pipeline — Module 8

### Trade Recommendation & Assistance System for PSX

**Version:** 1.0 | **Module:** 8 (News & Events Intelligence) | **Status:** Development/FYP

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Source Adapters](#3-source-adapters)
4. [Pipeline Steps](#4-pipeline-steps)
5. [Market-Aware Scheduling](#5-market-aware-scheduling)
6. [API Endpoints](#6-api-endpoints)
7. [Database Schema](#7-database-schema)
8. [Impact Score Methodology](#8-impact-score-methodology)
9. [Sentiment Analysis](#9-sentiment-analysis)
10. [Limitations & Legal Considerations](#10-limitations--legal-considerations)
11. [Configuration](#11-configuration)
12. [Testing](#12-testing)

---

## 1. Overview

The News & Events Pipeline collects, processes, and stores financial news from PSX-relevant sources, providing:

- **Multi-source ingestion** from 5 curated sources (PSX, SECP, SBP, Business Recorder, Dawn Business)
- **Deduplication** via SHA-256 content hashing
- **Symbol tagging** — automatic matching of articles to PSX-listed stocks
- **Event classification** — rule-based categorization into 10 event types
- **Sentiment analysis** — FinBERT-powered positive/negative/neutral scoring
- **Impact scoring** — deterministic 0–100 score based on source, event, symbol specificity, sentiment, and recency
- **Market-aware scheduling** — automatic ingestion during PSX market hours only
- **Manual refresh** — user-triggered refresh with cooldown protection

**Key design principle:** `GET /news` reads from database only (never scrapes). `POST /news/refresh` triggers the full pipeline.

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Source Adapters (5)                          │
│  PSX · SECP · SBP · Business Recorder · Dawn Business           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                    NormalizedArticle (base dataclass)
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Pipeline Orchestrator                         │
│  pipeline.py → run_pipeline()                                   │
│                                                                 │
│  Step 1: Fetch from all source adapters                         │
│  Step 2: Dedup via SHA-256 hash (title + URL)                   │
│  Step 3: Symbol tagging (alias map from stocks table)           │
│  Step 4: Event classification (rule-based)                      │
│  Step 5: Sentiment scoring (reuse existing FinBERT service)     │
│  Step 6: Impact scoring (deterministic 0–100)                   │
│  Step 7: Persist to PostgreSQL                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  PostgreSQL                                                      │
│  news_articles (deduped, tagged, scored)                         │
│  market_events (extracted from high-impact articles)             │
└─────────────────────────────────────────────────────────────────┘
```

**File structure:**
```
app/services/news_pipeline/
├── __init__.py              # Package init, PipelineResult
├── base.py                  # NormalizedArticle dataclass + NewsSource protocol
├── psx_source.py            # PSX filings adapter
├── secp_source.py           # SECP corporate filings adapter
├── sbp_source.py            # SBP monetary policy adapter
├── br_source.py             # Business Recorder adapter (sitemap-based)
├── dawn_source.py           # Dawn Business adapter (sitemap-based)
├── dedup.py                 # SHA-256 content hashing + normalisation
├── symbol_tagger.py         # Alias-map symbol matching
├── event_classifier.py      # Rule-based event type classification
├── impact_scorer.py         # Deterministic 0–100 impact scoring
├── market_schedule.py       # PKT timezone market hours logic
├── ingestion_state.py       # File-based last-ingestion tracker
└── pipeline.py              # Full ingestion orchestrator
```

---

## 3. Source Adapters

Each adapter implements the `NewsSource` protocol and returns a list of `NormalizedArticle` dataclass instances.

### 3.1 Source Protocol

```python
class NewsSource(Protocol):
    async def fetch(self, session: aiohttp.ClientSession) -> list[NormalizedArticle]: ...
    @property
    def source_name(self) -> str: ...
```

### 3.2 NormalizedArticle Base

```python
@dataclass
class NormalizedArticle:
    title: str
    url: str
    source: str
    summary: str | None
    published_at: datetime | None
    source_type: str  # psx/secp/sbp/financial_media/general_news
```

### 3.3 Source Details

| Source | File | Type | Fetch Strategy | Notes |
|---|---|---|---|---|
| PSX | `psx_source.py` | `psx` | Direct API calls | Official PSX filings. Highest source weight (30). |
| SECP | `secp_source.py` | `secp` | SECP eServices portal | Corporate announcements, dividend notices. Weight: 25. |
| SBP | `sbp_source.py` | `sbp` | SBP circulars/announcements | Monetary policy decisions, regulatory changes. Weight: 28. |
| Business Recorder | `br_source.py` | `financial_media` | Sitemap-based scraping | Financial news, market commentary. Weight: 18. |
| Dawn Business | `dawn_source.py` | `general_news` | Sitemap-based scraping | Business news, analysis. Weight: 15. |

**Source weights** (used in impact scoring, see §8):
- PSX: 30 (highest — official filings)
- SBP: 28 (regulatory authority)
- SECP: 25 (corporate filings)
- Business Recorder: 18 (financial media)
- Dawn Business: 15 (general news)

---

## 4. Pipeline Steps

### Step 1: Fetch from Sources

Each adapter fetches its latest articles and normalizes them to `NormalizedArticle`. All adapters run in parallel via `asyncio.gather()`.

### Step 2: Deduplication

**Method:** SHA-256 hash of normalized title + URL

```python
# dedup.py
normalise_url(url) → str    # Strip query params, trailing slashes, lowercase
normalise_title(title) → str # Lowercase, collapse whitespace, strip punctuation
compute_content_hash(title, url) → str # SHA-256 hex digest
```

**Why this works:**
- Same article from different sources will have the same title and similar URLs
- Normalisation removes noise (query params, capitalisation, punctuation)
- Content hash stored in `news_articles.content_hash` with unique constraint

### Step 3: Symbol Tagging

**Method:** Alias map loaded from `stocks` table + static aliases

```python
# symbol_tagger.py
alias_map = {
    "ogdc": "OGDC",
    "oil and gas development": "OGDC",
    "state bank": "SBP",
    # ... loaded from stocks table at startup
}

tag_symbols(article) → tuple[list[str], list[str]]
# Returns (matched_symbols, matched_company_names)
```

**Process:**
1. Load alias map from `stocks` table (symbol → symbol, name → symbol)
2. Merge with static aliases (common abbreviations, sector names)
3. Search article title + summary for matches
4. Return matched PSX symbols and company names

### Step 4: Event Classification

**Method:** Rule-based keyword matching

```python
# event_classifier.py
EVENT_TYPES = [
    "earnings",           # quarterly results, profit/loss
    "dividend",           # dividend announcements
    "corporate_action",   # splits, mergers, acquisitions
    "monetary_policy",    # SBP policy rate changes
    "regulatory_action",  # SECP regulations, compliance
    "market_commentary",  # analyst opinions, market outlook
    "interest_rate",      # interest rate changes (non-SBP)
    "inflation",          # CPI, inflation data
    "gdp",                # GDP growth, economic data
    "general_news",       # default fallback
]
```

**Priority rules:**
- `monetary_policy` takes precedence over `interest_rate`
- SBP source articles are excluded from `regulatory_action` rules
- Most specific match wins (e.g., "earnings" over "general_news")

### Step 5: Sentiment Scoring

**Reuse existing service:** `app/services/sentiment_service.py`

```python
# sentiment_service.py (existing)
score_text(text: str) → tuple[str, float]
# Returns (label, confidence) where label ∈ {"positive", "negative", "neutral"}
```

**What changes:**
- Previously: sentiment stored as single `sentiment` field
- Now: `sentiment_label` (for filtering) + `sentiment_score` (FinBERT confidence, 0.0–1.0)

### Step 6: Impact Scoring

**Method:** Deterministic 0–100 score (see §8 for full methodology)

```python
# impact_scorer.py
score_impact(article, matched_symbols, event_type, sentiment_label, sentiment_score) → int
# Returns integer 0–100
```

### Step 7: Persist

- Insert into `news_articles` table (skip if `content_hash` already exists)
- If `impact_score >= 40`, extract to `market_events` table
- Update ingestion state on successful commit

---

## 5. Market-Aware Scheduling

### PSX Trading Hours (PKT / UTC+5)

| Window | Time (PKT) | Ingestion Behaviour |
|---|---|---|
| **Pre-market** | Before 09:30 | Skipped — `status: "skipped_outside_hours"` |
| **Market hours** | 09:30–15:30 | Active — ingestion every 30 minutes |
| **Post-market** | 15:30–17:00 | Active — final digest of the day |
| **Closed** | After 17:00 | Skipped |
| **Weekends** | Saturday, Sunday | Skipped |

### Celery Beat Schedule

```
news-ingestion-market-aware: every 30 minutes during market hours
```

**Logic:**
1. Celery beat fires every 30 minutes
2. Task checks `is_market_open()` (from `market_schedule.py`)
3. If outside hours → `status: "skipped_outside_hours"`, returns immediately
4. If within hours → check `ingestion_state.py` for last successful run
5. If < 30 min since last run → skip (avoid duplicate work)
6. If ≥ 30 min or no previous run → execute full pipeline

### Manual Refresh

`POST /news/refresh` bypasses the Celery schedule but enforces a **5-minute cooldown**:

```json
// Successful refresh
{
  "status": "completed",
  "articles_ingested": 12,
  "duplicates_skipped": 3,
  "symbols_tagged": ["OGDC", "LUCK", "MCB"],
  "last_updated": "2026-09-16T10:35:00+05:00",
  "refresh_available": false,
  "next_refresh_at": "2026-09-16T10:40:00+05:00"
}

// Cooldown active
{
  "status": "cooldown",
  "refresh_available": false,
  "next_refresh_at": "2026-09-16T10:40:00+05:00",
  "last_updated": "2026-09-16T10:35:00+05:00"
}
```

---

## 6. API Endpoints

### GET /news

Database read only — never triggers scraping.

**Query parameters:**
| Parameter | Type | Description |
|---|---|---|
| `symbol` | string | Filter by PSX symbol (e.g., `OGDC`) |
| `sentiment` | string | Filter by sentiment label (`positive`, `negative`, `neutral`) |
| `source` | string | Filter by source name |
| `event_type` | string | Filter by event type (see §4 Step 4) |
| `page` | int | Page number (default: 1) |
| `limit` | int | Items per page (default: 20, max: 100) |

**Response shape:**
```json
{
  "items": [
    {
      "id": "abc123",
      "title": "OGDC reports strong quarterly earnings",
      "url": "https://brecorder.com/news/...",
      "source": "Business Recorder",
      "source_type": "financial_media",
      "summary": "...",
      "symbols": ["OGDC"],
      "company_names": ["Oil and Gas Development Company"],
      "event_type": "earnings",
      "sentiment_label": "positive",
      "sentiment_score": 0.91,
      "impact_score": 78,
      "published_at": "2026-09-16T10:30:00",
      "created_at": "2026-09-16T10:35:00"
    }
  ],
  "total": 150,
  "page": 1,
  "limit": 20,
  "has_more": true
}
```

### GET /news/{id}

Returns full article details including all fields above.

### POST /news/refresh

Triggers manual refresh with cooldown protection.

**Response:** See §5 Manual Refresh.

### GET /news/market-status

Returns current PKT time and market window.

```json
{
  "current_time": "2026-09-16T10:35:00+05:00",
  "market_status": "market_hours",
  "market_status_label": "Market is open",
  "next_closing": "2026-09-16T15:30:00+05:00",
  "is_weekend": false,
  "is_holiday": false
}
```

### GET /events/calendar

Returns events from `market_events` table (auto-populated from high-impact articles).

**Query parameters:**
| Parameter | Type | Description |
|---|---|---|
| `from` | date | Start date (inclusive) |
| `to` | date | End date (inclusive) |
| `event_type` | string | Filter by event type |
| `symbol` | string | Filter by PSX symbol |

---

## 7. Database Schema

### news_articles

| Column | Type | Notes |
|---|---|---|
| `id` | bigint (PK) | Auto-increment |
| `title` | text | Article headline |
| `source` | text | Human-readable source name |
| `source_type` | enum | `psx`/`secp`/`sbp`/`financial_media`/`general_news` |
| `summary` | text | Article summary (not full body — copyright) |
| `url` | text (unique) | Article URL |
| `content_hash` | text (unique) | SHA-256 of normalised title + URL |
| `published_at` | timestamp | When article was published |
| `created_at` | timestamp | When ingested |
| `updated_at` | timestamp | Last modified |
| `symbols` | jsonb | Matched PSX symbols (e.g., `["OGDC"]`) |
| `company_names` | jsonb | Matched company names |
| `sector` | text | Sector if all symbols share one |
| `event_type` | enum | Classified event type (10 types) |
| `sentiment_label` | enum | `positive`/`negative`/`neutral` |
| `sentiment_score` | float | FinBERT confidence (0.0–1.0) |
| `impact_score` | integer | Deterministic score 0–100 |

### market_events

| Column | Type | Notes |
|---|---|---|
| `id` | bigint (PK) | Auto-increment |
| `event_type` | enum | Same 10 types as news_articles |
| `symbol` | varchar (nullable) | Target PSX symbol |
| `title` | text | Event title |
| `description` | text | Event description |
| `event_date` | date | When event occurs/occurred |
| `event_time` | time (nullable) | Specific time if known |
| `source` | text | Human-readable source |
| `source_url` | text | Source article URL |
| `source_type` | enum | Same as news_articles |
| `sentiment_label` | enum | Sentiment if applicable |
| `sentiment_score` | float | Sentiment confidence |
| `impact_score` | integer | Impact score |
| `news_article_id` | bigint (FK, nullable) | Link to source article |
| `created_at` | timestamp | When created |
| `updated_at` | timestamp | Last modified |

**Indexing:**
- `news_articles`: composite index on `(symbols, published_at DESC)`, index on `source_type`, index on `event_type`, index on `sentiment_label`, index on `impact_score DESC`
- `market_events`: composite index on `(event_date, event_type)`, index on `symbol`

---

## 8. Impact Score Methodology

The impact score is a **deterministic, explainable** 0–100 integer. It is **not** a trading signal or prediction — it measures how likely an article is to matter to a PSX investor.

### Component Weights

| Component | Range | Weight | Rationale |
|---|---|---|---|
| **Source weight** | 0–30 | 30% | Official filings (PSX/SBP/SECP) more credible than media |
| **Event weight** | 0–25 | 25% | Earnings/dividend/monetary_policy > general_news |
| **Symbol specificity** | 0–20 | 20% | 1 specific symbol > multiple symbols > no symbols |
| **Sentiment strength** | 0–15 | 15% | Strong positive/negative > neutral |
| **Recency** | 0–10 | 10% | Within market hours > older |

### Source Weights

| Source | Score | Justification |
|---|---|---|
| PSX | 30 | Official exchange filings |
| SBP | 28 | Central bank regulatory decisions |
| SECP | 25 | Corporate regulator filings |
| Business Recorder | 18 | Established financial media |
| Dawn Business | 15 | General business news |

### Event Weights

| Event Type | Score | Justification |
|---|---|---|
| earnings | 25 | Direct company financials |
| dividend | 24 | Direct shareholder impact |
| monetary_policy | 23 | Market-wide rate impact |
| corporate_action | 20 | Splits, mergers, acquisitions |
| regulatory_action | 18 | Compliance changes |
| interest_rate | 16 | Economic indicator |
| inflation | 14 | Economic indicator |
| gdp | 12 | Economic indicator |
| market_commentary | 10 | Analyst opinions |
| general_news | 5 | Lowest priority |

### Symbol Specificity

| Scenario | Score | Example |
|---|---|---|
| 1 specific symbol | 20 | "OGDC reports earnings" |
| 2–3 symbols | 15 | "OGDC, PPL announce dividends" |
| 4+ symbols | 10 | "Banking sector earnings rise" |
| Sector reference | 5 | "Oil & gas sector outlook" |
| No symbol match | 0 | General market news |

### Sentiment Strength

| Score | Condition |
|---|---|
| 15 | FinBERT confidence ≥ 0.8 (strong positive/negative) |
| 10 | FinBERT confidence 0.5–0.8 |
| 5 | Neutral or low confidence |

### Recency

| Score | Condition |
|---|---|
| 10 | Published within current market hours |
| 7 | Published today (outside market hours) |
| 4 | Published within 3 days |
| 0 | Older than 3 days |

---

## 9. Sentiment Analysis

### FinBERT Integration

The pipeline reuses the existing `sentiment_service.py` which uses a FinBERT model via HuggingFace Inference API.

**Input:** Article title + summary (truncated to 512 tokens)
**Output:** `(label, confidence)` where:
- `label` ∈ `{"positive", "negative", "neutral"}`
- `confidence` ∈ `[0.0, 1.0]`

### Storage

- `sentiment_label`: Stored separately for efficient filtering (e.g., `WHERE sentiment_label = 'negative'`)
- `sentiment_score`: FinBERT confidence score for ranking and display

### Limitations

- FinBERT is trained on English financial text — may not handle Urdu/Arabic well
- Summaries (not full articles) are scored — context may be lost
- Confidence scores are model-internal, not externally calibrated
- Sentiment is per-article, not per-paragraph — mixed-sentiment articles get one label

---

## 10. Limitations & Legal Considerations

### Content Policy

- **Summaries only** — full article bodies are never stored (copyright protection)
- Articles link back to original sources via URL
- No paywall bypass — only publicly accessible content is scraped
- Respects `robots.txt` where applicable

### Source Limitations

| Source | Limitation |
|---|---|
| PSX | May not cover all listed companies equally |
| SECP | Corporate filings may lag announcement dates |
| SBP | Monetary policy announcements are infrequent |
| Business Recorder | Sitemap-based — may miss some articles |
| Dawn Business | Sitemap-based — may miss some articles |

### Technical Limitations

- **No real-time streaming** — ingestion is batch-based (30-min intervals)
- **No article dedup across languages** — same story in English/Urdu treated as different articles
- **Symbol tagging is keyword-based** — may miss articles using informal company references
- **Event classification is rule-based** — new event types require code changes
- **Impact score is heuristic** — not validated against market reaction data

### FYP Positioning

This is a **development/demo system**, not production trading infrastructure:
- Impact scores are for educational purposes only
- Not a substitute for professional financial analysis
- Users should verify information from original sources
- System does not provide investment advice

---

## 11. Configuration

### config.py Settings

| Setting | Default | Description |
|---|---|---|
| `NEWS_TIMEZONE` | `"Asia/Karachi"` | PKT timezone for market hours |
| `MARKET_OPEN_HOUR` | `9` | Market opens at 09:30 PKT |
| `MARKET_OPEN_MINUTE` | `30` | |
| `MARKET_CLOSE_HOUR` | `15` | Market closes at 15:30 PKT |
| `MARKET_CLOSE_MINUTE` | `30` | |
| `POST_MARKET_CLOSE_HOUR` | `17` | Post-market ends at 17:00 PKT |
| `POST_MARKET_CLOSE_MINUTE` | `0` | |
| `NEWS_INGESTION_INTERVAL_MINUTES` | `30` | Minutes between ingestion runs |
| `NEWS_REFRESH_COOLDOWN_MINUTES` | `5` | Cooldown for manual refresh |

### Environment Variables

All settings can be overridden via environment variables (e.g., `MARKET_OPEN_HOUR=10`).

---

## 12. Testing

### Test File

`tests/test_news_pipeline.py` — 46 tests covering all pipeline components.

### Test Coverage

| Component | Tests | What's Tested |
|---|---|---|
| Dedup | 8 | URL normalisation, title normalisation, content hash, duplicate detection |
| Symbol Tagger | 8 | Alias matching, case insensitivity, no-match handling |
| Event Classifier | 10 | Keyword matching, priority rules, fallback to general_news |
| Impact Scorer | 8 | Component weights, boundary conditions, source/event weights |
| Market Schedule | 6 | Market hours, post-market, closed, weekends, next window |
| Ingestion State | 6 | File-based state, update/check/reset |

### Running Tests

```bash
# All news pipeline tests
pytest tests/test_news_pipeline.py -v

# Specific component
pytest tests/test_news_pipeline.py -k "test_compute_content_hash" -v
```

---

## Appendix: File Reference

| File | Purpose |
|---|---|
| `app/services/news_pipeline/__init__.py` | Package init, exports |
| `app/services/news_pipeline/base.py` | `NormalizedArticle` dataclass, `NewsSource` protocol |
| `app/services/news_pipeline/psx_source.py` | PSX adapter |
| `app/services/news_pipeline/secp_source.py` | SECP adapter |
| `app/services/news_pipeline/sbp_source.py` | SBP adapter |
| `app/services/news_pipeline/br_source.py` | Business Recorder adapter |
| `app/services/news_pipeline/dawn_source.py` | Dawn Business adapter |
| `app/services/news_pipeline/dedup.py` | Content hashing |
| `app/services/news_pipeline/symbol_tagger.py` | Symbol matching |
| `app/services/news_pipeline/event_classifier.py` | Event classification |
| `app/services/news_pipeline/impact_scorer.py` | Impact scoring |
| `app/services/news_pipeline/market_schedule.py` | Market hours logic |
| `app/services/news_pipeline/ingestion_state.py` | State tracker |
| `app/services/news_pipeline/pipeline.py` | Orchestrator |
| `app/models/news.py` | `NewsArticle` SQLAlchemy model |
| `app/models/event.py` | `MarketEvent` SQLAlchemy model |
| `app/schemas/news.py` | Pydantic schemas |
| `app/api/v1/news.py` | News endpoints |
| `app/api/v1/events.py` | Events endpoints |
| `app/tasks/scrape_news.py` | Celery task |
| `tests/test_news_pipeline.py` | Test suite |
