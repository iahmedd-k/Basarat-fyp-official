# ADR-007: Scraper Data Staging and Atomic Publication Boundary

## Status
Accepted

## Context
During high market volatility or network rate-limiting (PSX HTTP 403 / 429), partial scraper runs could corrupt or truncate model-input parquet files if written directly in-place. If an ingestion cycle failed halfway, downstream ML feature generation and prediction jobs would ingest partial datasets or fail outright.

## Decision
1. **Isolated Run Staging**: Scraper output is staged in an isolated timestamped directory (`/data/staging/run_<timestamp>/`).
2. **Atomic Publication Boundary**: A scrape generation is promoted to the production dataset (`/data/production/`) **only if 100% of symbols are successfully scraped or verified as non-trading**.
3. **Preservation of Last-Known-Good Generation**: In the event of network disruption, rate limits, or partial failures, the staging run is aborted and the previous verified dataset remains active without interruption.
4. **Single-Writer Lock**: Redis-backed distributed locks (`lock:scraper:daily_close`) guarantee that only one writer process can execute the daily ingestion pipeline at any given moment.

## Consequences
- **Positive**: Zero downtime or corrupted model-input files due to partial network failures. Downstream ML inference is guaranteed clean data.
- **Positive**: Prevents race conditions and multiple concurrent scraping runs.
- **Negative**: Requires temporary additional disk space to store staged parquet partitions prior to promotion.
