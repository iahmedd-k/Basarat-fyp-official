# ADR-006: Hybrid Financial Sentiment Analysis Pipeline

## Status
**Accepted / Implemented**

## Context
Market sentiment from financial news, corporate earnings disclosures, and regulatory filings is a critical input for quantitative equity recommendations and investor insights. However, general-purpose NLP models (e.g. standard BERT or VADER) misclassify domain-specific financial terminology (e.g., "debt liabilities increased" is negative in finance but neutral in general text; "bearish trend broken" is positive).

Furthermore, relying solely on an external cloud NLP API creates a single point of failure if API tokens expire or rate limits are reached.

## Decision
Implement a **Hybrid, Two-Tier Financial Sentiment Pipeline**:

1. **Tier 1 (Primary Model): FinBERT via HuggingFace Inference API:**
   - Model: `ProsusAI/finbert` (a BERT model fine-tuned on the Financial PhraseBank dataset).
   - Ingests article headlines and summaries, returning three probability scores: `positive`, `negative`, and `neutral`.
   - Normalizes output into a unified continuous polarity score from `-1.0` (Strongly Bearish) to `+1.0` (Strongly Bullish).
2. **Tier 2 (Resilient Fallback): Financial Lexicon & EPS Heuristics:**
   - If `HF_API_TOKEN` is unconfigured, network timeouts occur, or the API returns HTTP 503/429, the system automatically falls back to an internal financial rule engine.
   - Evaluates quarterly Earnings Per Share (EPS) growth, dividend payout declarations, and financial keywords (`profit`, `loss`, `dividend`, `default`, `growth`).
3. **Content Deduplication & Rolling Aggregation:**
   - Compute SHA-256 `content_hash` on incoming articles to reject duplicates.
   - Pre-compute rolling sentiment aggregates across 1D, 1W, 1M, 3M, 6M, and 1Y periods stored in `sentiment_aggregates` for instant UI dashboard rendering.

## Alternatives Considered
- **VADER / TextBlob:** Rejected due to high error rates on financial reports and corporate disclosure terminology.
- **Self-Hosting FinBERT PyTorch Container:** Considered, but required dedicated GPU hardware (increasing cloud hosting costs). Using HuggingFace's managed inference API with local heuristic fallback proved optimal for cost and performance.

## Consequences
- **Positive:** High sentiment accuracy from FinBERT; 100% operational uptime due to automatic heuristic fallback; zero duplicate article processing.
- **Negative / Trade-off:** Cloud inference latency is subject to external network conditions (handled asynchronously by background Celery tasks).

## Current Implementation
- Ingestion and scoring tasks in [app/tasks/scrape_news.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/tasks/scrape_news.py) and [app/tasks/sentiment_tasks.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/tasks/sentiment_tasks.py).
- Domain logic in [app/services/sentiment_service.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/services/sentiment_service.py).
