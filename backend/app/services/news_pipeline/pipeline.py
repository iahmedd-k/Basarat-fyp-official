"""News ingestion pipeline — orchestrates the full flow.

INGEST → VALIDATE → CLEAN → DEDUPLICATE → SYMBOL TAG → EVENT CLASSIFY → SENTIMENT → IMPACT SCORE → SAVE

Each stage is a separate function for testability.
Source failures are isolated — one source failing does not stop others.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news import NewsArticle
from app.schemas.news import IngestResult
from app.services.sentiment_service import score_text

from app.services.news_pipeline.dedup import compute_content_hash, is_duplicate
from app.services.news_pipeline.symbol_tagger import tag_articles, load_stock_symbols, _build_alias_map
from app.services.news_pipeline.event_classifier import classify_articles
from app.services.news_pipeline.impact_scorer import score_articles
from app.services.news_pipeline import ingestion_state

# Source adapter imports
from app.services.news_pipeline import psx_source
from app.services.news_pipeline import secp_source
from app.services.news_pipeline import sbp_source
from app.services.news_pipeline import br_source
from app.services.news_pipeline import dawn_source

log = logging.getLogger(__name__)

# All source adapters in execution order
_SOURCE_ADAPTERS = [
    ("PSX", psx_source.fetch_articles),
    ("SECP", secp_source.fetch_articles),
    ("SBP", sbp_source.fetch_articles),
    ("Business Recorder", br_source.fetch_articles),
    ("Dawn Business", dawn_source.fetch_articles),
]


@dataclass
class PipelineResult:
    """Structured result returned by run_pipeline."""
    sources: list[IngestResult] = field(default_factory=list)
    total_fetched: int = 0
    total_inserted: int = 0
    total_skipped_duplicate: int = 0
    total_symbol_tagged: int = 0
    total_sentiment_processed: int = 0
    events_created: int = 0
    errors: int = 0
    completed_at: str = ""


async def _load_existing_hashes(db: AsyncSession, limit: int = 10000) -> set[str]:
    """Load recent content hashes from DB for dedup."""
    result = await db.execute(
        select(NewsArticle.content_hash)
        .where(NewsArticle.content_hash.isnot(None))
        .order_by(NewsArticle.created_at.desc())
        .limit(limit)
    )
    return {row[0] for row in result.fetchall() if row[0]}


def _clean_article(raw: dict) -> dict | None:
    """Validate and clean a normalised article dict."""
    title = (raw.get("title") or "").strip()
    url = (raw.get("url") or "").strip()
    if not title or not url or len(title) < 5:
        return None
    return {
        "title": title[:500],
        "url": url[:1000],
        "source": raw.get("source", ""),
        "source_type": raw.get("source_type", ""),
        "summary": (raw.get("summary") or "")[:2000] or None,
        "published_at": raw.get("published_at"),
    }


async def run_pipeline(db: AsyncSession, limit_per_source: int = 50) -> PipelineResult:
    """Execute the full ingestion pipeline across all sources.

    Updates ingestion state on success. Returns structured PipelineResult.
    """
    result = PipelineResult()
    existing_hashes = await _load_existing_hashes(db)
    all_new_articles: list[dict] = []

    # ── Stage 1-3: FETCH + VALIDATE + CLEAN ──────────────────────────────
    for source_name, fetch_fn in _SOURCE_ADAPTERS:
        src_result = IngestResult(source=source_name)
        try:
            raw_articles = fetch_fn(limit=limit_per_source)
            src_result.articles_fetched = len(raw_articles)

            for raw in raw_articles:
                cleaned = _clean_article(raw.__dict__ if hasattr(raw, "__dict__") else raw)
                if cleaned is None:
                    continue

                # ── Stage 4: DEDUPLICATE ──────────────────────────────────
                content_hash = compute_content_hash(cleaned["title"], cleaned["url"])
                if is_duplicate(content_hash, existing_hashes):
                    src_result.articles_skipped_duplicate += 1
                    continue

                cleaned["content_hash"] = content_hash
                existing_hashes.add(content_hash)
                all_new_articles.append(cleaned)

            src_result.articles_inserted = len([
                a for a in all_new_articles if a.get("source") == source_name
            ])
        except Exception as exc:
            src_result.error = str(exc)
            log.warning("Source %s failed: %s", source_name, exc)

        result.sources.append(src_result)

    if not all_new_articles:
        log.info("No new articles to process")
        result.completed_at = datetime.now(timezone.utc).isoformat()
        return result

    # ── Stage 5: SYMBOL TAGGING ──────────────────────────────────────────
    try:
        all_new_articles = await tag_articles(db, all_new_articles)
        for r in result.sources:
            r.articles_symbol_tagged = sum(
                1 for a in all_new_articles
                if a.get("source") == r.source and a.get("symbols")
            )
    except Exception as exc:
        log.warning("Symbol tagging failed: %s", exc)

    # ── Stage 6: EVENT CLASSIFICATION ────────────────────────────────────
    try:
        all_new_articles = classify_articles(all_new_articles)
    except Exception as exc:
        log.warning("Event classification failed: %s", exc)

    # ── Stage 7: FINBERT SENTIMENT ───────────────────────────────────────
    try:
        for article in all_new_articles:
            text = f"{article['title']}. {article.get('summary') or ''}"
            sentiment = score_text(text)
            article["sentiment_label"] = sentiment["label"]
            article["sentiment_score"] = sentiment["score"]
    except Exception as exc:
        log.warning("Sentiment scoring failed: %s", exc)

    # ── Stage 8: IMPACT SCORING ──────────────────────────────────────────
    try:
        all_new_articles = score_articles(all_new_articles)
    except Exception as exc:
        log.warning("Impact scoring failed: %s", exc)

    # ── Stage 9: SAVE TO DATABASE ────────────────────────────────────────
    inserted_count = 0
    for article in all_new_articles:
        try:
            db_article = NewsArticle(
                title=article["title"],
                url=article["url"],
                source=article.get("source"),
                source_type=article.get("source_type"),
                summary=article.get("summary"),
                content_hash=article.get("content_hash"),
                symbols=json.dumps(article.get("symbols", [])),
                company_names=json.dumps(article.get("company_names", [])),
                sector=None,
                event_type=article.get("event_type"),
                sentiment_label=article.get("sentiment_label"),
                sentiment_score=article.get("sentiment_score"),
                impact_score=article.get("impact_score"),
                published_at=article.get("published_at"),
            )
            db.add(db_article)
            inserted_count += 1
        except Exception as exc:
            log.warning("Failed to stage article for insert: %s", exc)

    if inserted_count:
        try:
            await db.commit()
            # Update ingestion state on successful commit
            ingestion_state.set_last_ingestion_time()
            ingestion_state.increment_run_count()
        except Exception as exc:
            await db.rollback()
            log.warning("Batch commit failed: %s", exc)
            inserted_count = 0

    # Aggregate results
    result.total_fetched = sum(r.articles_fetched for r in result.sources)
    result.total_inserted = inserted_count
    result.total_skipped_duplicate = sum(r.articles_skipped_duplicate for r in result.sources)
    result.total_symbol_tagged = sum(r.articles_symbol_tagged for r in result.sources)
    result.total_sentiment_processed = inserted_count
    result.errors = sum(1 for r in result.sources if r.error)
    result.completed_at = datetime.now(timezone.utc).isoformat()

    log.info(
        "Pipeline complete: fetched=%d, inserted=%d, dedup_skipped=%d",
        result.total_fetched,
        result.total_inserted,
        result.total_skipped_duplicate,
    )

    return result
