"""News ingestion pipeline — orchestrates the full flow.

INGEST → VALIDATE/CLEAN → DEDUPLICATE → SYMBOL TAG → EVENT CLASSIFY → SENTIMENT → IMPACT SCORE → SAVE

Each stage is a separate function for testability.
Source failures are isolated — one source failing does not stop others.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news import NewsArticle, NewsArticleSymbol, NewsSourceState
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
from app.services.news_pipeline import mettis_source
from app.services.news_pipeline import ogra_source
from app.services.news_pipeline import fbr_mof_source
from app.services.news_pipeline.base import NormalizedArticle

log = logging.getLogger(__name__)

# All source adapters in execution order
_SOURCE_ADAPTERS = [
    ("PSX", psx_source.fetch_articles),
    ("SECP", secp_source.fetch_articles),
    ("SBP", sbp_source.fetch_articles),
    ("OGRA", ogra_source.fetch_articles),
    ("FBR/MoF", fbr_mof_source.fetch_articles),
    ("Business Recorder", br_source.fetch_articles),
    ("Dawn Business", dawn_source.fetch_articles),
    ("Mettis Global", mettis_source.fetch_articles),
]

# Sources that should get FinBERT sentiment (news sources only)
_SENTIMENT_SOURCES = {"business_recorder", "dawn", "mettis"}

# Official sources that get NO sentiment dot (except PSX results with EPS rule)
_NO_SENTIMENT_SOURCES = {"psx", "secp", "sbp", "ogra", "fbr/mof"}


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


async def _save_source_health(db: AsyncSession, results: list[IngestResult]) -> None:
    """Persist each adapter's latest run result for the source-health endpoint."""
    now = datetime.now(timezone.utc)
    keys = {
        "PSX": "psx", "SECP": "secp", "SBP": "sbp", "OGRA": "ogra",
        "FBR/MoF": "fbr_mof", "Business Recorder": "business_recorder",
        "Dawn Business": "dawn", "Mettis Global": "mettis",
    }
    try:
        existing_result = await db.execute(select(NewsSourceState))
        states = {state.source_key: state for state in existing_result.scalars().all()}
        for item in results:
            key = keys.get(item.source)
            if not key:
                continue
            state = states.get(key)
            if state is None:
                state = NewsSourceState(source_key=key, consecutive_failures=0, last_new_count=0, healthy=False)
                db.add(state)
            state.last_run_at = now
            state.last_new_count = int(item.articles_inserted or 0)
            state.last_error = (str(item.error)[:4000] if item.error else None)
            if item.error:
                state.consecutive_failures = (state.consecutive_failures or 0) + 1
                state.healthy = False
            else:
                state.last_success_at = now
                state.consecutive_failures = 0
                state.healthy = True
        await db.commit()
    except Exception:
        await db.rollback()
        log.exception("Could not persist news source health")


def _clean_article(raw: NormalizedArticle) -> dict | None:
    """Validate and clean a normalized article."""
    title = (raw.title or "").strip()
    url = (raw.url or "").strip()
    external_url = (raw.external_url or "").strip() if raw.external_url else None

    if not title or not url or len(title) < 5:
        return None

    # Validate external_url is http/https
    if external_url and not external_url.startswith(("http://", "https://")):
        external_url = None

    return {
        "title": title[:500],
        "url": url[:1000],
        "external_url": external_url[:1000] if external_url else None,
        "source": raw.source,
        "source_key": raw.source_key,
        "source_type": raw.source_type,
        "external_id": raw.external_id,
        "summary": (raw.summary or "")[:500] if raw.summary else None,
        "published_at": raw.published_at,
        "published_at_estimated": raw.published_at_estimated,
        "event_type": raw.event_type,
        "symbols": raw.symbols or [],
        "company_names": raw.company_names or [],
        "metadata": raw.metadata or {},
    }


async def _save_article_batch(db: AsyncSession, articles: list[dict]) -> int:
    """Save a batch of articles with link table entries. Falls back to row-by-row on failure."""
    inserted = 0

    # Try batch insert first
    try:
        db_articles = []
        for article in articles:
            db_article = NewsArticle(
                title=article["title"],
                url=article["url"],
                external_url=article.get("external_url"),
                source=article.get("source"),
                source_key=article.get("source_key"),
                source_type=article.get("source_type"),
                external_id=article.get("external_id"),
                summary=article.get("summary"),
                content_hash=article.get("content_hash"),
                symbols=json.dumps(article.get("symbols", [])),
                company_names=json.dumps(article.get("company_names", [])),
                sector=None,
                event_type=article.get("event_type"),
                sentiment_label=article.get("sentiment_label"),
                sentiment_score=article.get("sentiment_score"),
                sentiment_method=article.get("sentiment_method"),
                sentiment_status=article.get("sentiment_status"),
                impact_score=article.get("impact_score"),
                published_at=article.get("published_at"),
                published_at_estimated=article.get("published_at_estimated", False),
            )
            db_articles.append(db_article)

        db.add_all(db_articles)
        await db.flush()  # Get IDs

        # Create link table entries
        for db_article, article in zip(db_articles, articles):
            for symbol in article.get("symbols", []):
                if symbol:
                    link = NewsArticleSymbol(
                        article_id=db_article.id,
                        symbol=symbol.upper().strip(),
                    )
                    db.add(link)

        await db.commit()
        inserted = len(db_articles)
        log.info("Batch saved %d articles", inserted)
        return inserted

    except Exception as exc:
        await db.rollback()
        log.warning("Batch commit failed, falling back to row-by-row: %s", exc)

    # Fallback: row-by-row
    for article in articles:
        try:
            db_article = NewsArticle(
                title=article["title"],
                url=article["url"],
                external_url=article.get("external_url"),
                source=article.get("source"),
                source_key=article.get("source_key"),
                source_type=article.get("source_type"),
                external_id=article.get("external_id"),
                summary=article.get("summary"),
                content_hash=article.get("content_hash"),
                symbols=json.dumps(article.get("symbols", [])),
                company_names=json.dumps(article.get("company_names", [])),
                sector=None,
                event_type=article.get("event_type"),
                sentiment_label=article.get("sentiment_label"),
                sentiment_score=article.get("sentiment_score"),
                sentiment_method=article.get("sentiment_method"),
                sentiment_status=article.get("sentiment_status"),
                impact_score=article.get("impact_score"),
                published_at=article.get("published_at"),
                published_at_estimated=article.get("published_at_estimated", False),
            )
            db.add(db_article)
            await db.flush()

            # Link table entries
            for symbol in article.get("symbols", []):
                if symbol:
                    link = NewsArticleSymbol(
                        article_id=db_article.id,
                        symbol=symbol.upper().strip(),
                    )
                    db.add(link)

            await db.commit()
            inserted += 1
        except Exception as exc:
            await db.rollback()
            log.warning("Failed to insert article row-by-row: %s", exc)

    return inserted


async def run_pipeline(db: AsyncSession, limit_per_source: int = 50) -> PipelineResult:
    """Execute the full ingestion pipeline across all sources.

    Updates ingestion state on success. Returns structured PipelineResult.
    """
    ingestion_state.mark_ingestion_started()
    result = PipelineResult()
    existing_hashes = await _load_existing_hashes(db)
    all_new_articles: list[dict] = []

    # ── Stage 1-3: FETCH + VALIDATE + CLEAN ──────────────────────────────
    for source_name, fetch_fn in _SOURCE_ADAPTERS:
        src_result = IngestResult(source=source_name)
        try:
            source_article_count = len(all_new_articles)
            raw_articles = fetch_fn(limit=limit_per_source)
            src_result.articles_fetched = len(raw_articles)

            for raw in raw_articles:
                cleaned = _clean_article(raw)
                if cleaned is None:
                    continue

                # ── Stage 4: DEDUPLICATE ──────────────────────────────────
                content_hash = compute_content_hash(cleaned["title"], cleaned["url"])
                if is_duplicate(content_hash, existing_hashes):
                    src_result.articles_skipped_duplicate += 1
                    continue

                cleaned["content_hash"] = content_hash
                existing_hashes.add(content_hash)

                # Preserve source-specific fields for saving
                cleaned["source"] = raw.source
                cleaned["source_key"] = raw.source_key
                cleaned["source_type"] = raw.source_type
                cleaned["external_id"] = raw.external_id
                cleaned["external_url"] = raw.external_url
                cleaned["published_at_estimated"] = raw.published_at_estimated
                cleaned["event_type"] = raw.event_type
                cleaned["symbols"] = raw.symbols
                cleaned["company_names"] = raw.company_names

                all_new_articles.append(cleaned)

            src_result.articles_inserted = len(all_new_articles) - source_article_count
        except Exception as exc:
            src_result.error = str(exc)
            log.warning("Source %s failed: %s", source_name, exc)

        result.sources.append(src_result)

    if not all_new_articles:
        log.info("No new articles to process")
        await _save_source_health(db, result.sources)
        ingestion_state.mark_ingestion_completed(0)
        ingestion_state.increment_run_count()
        result.completed_at = datetime.now(timezone.utc).isoformat()
        return result

    # ── Stage 5: SYMBOL TAGGING ──────────────────────────────────────────
    # PSX company announcements already have symbols from the fetcher
    # For other sources, apply regex tagging
    try:
        # Split articles: those with symbols (PSX) vs those without
        articles_with_symbols = [a for a in all_new_articles if a.get("symbols")]
        articles_without_symbols = [a for a in all_new_articles if not a.get("symbols")]

        if articles_without_symbols:
            tagged = await tag_articles(db, articles_without_symbols)
            # Merge back
            all_new_articles = articles_with_symbols + tagged
        else:
            all_new_articles = articles_with_symbols

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

    # ── Stage 7: SENTIMENT (FinBERT for news sources only) ───────────────
    try:
        for article in all_new_articles:
            source_key = (article.get("source_key") or "").lower()

            # Skip sentiment for official sources (no dot)
            if source_key in _NO_SENTIMENT_SOURCES:
                article["sentiment_label"] = None
                article["sentiment_score"] = None
                article["sentiment_method"] = "none"
                article["sentiment_status"] = "skipped"
                continue

            # Only news sources get FinBERT
            if source_key in _SENTIMENT_SOURCES:
                text = f"{article['title']}. {article.get('summary') or ''}"
                text = text[:1500]  # Truncate to ~512 tokens

                # Try FinBERT with retry
                sentiment = None
                for attempt in range(3):
                    try:
                        sentiment = score_text(text)
                        if sentiment and sentiment.get("score") is not None:
                            break
                    except Exception:
                        if attempt == 2:
                            raise
                        import asyncio
                        await asyncio.sleep(2 ** attempt)

                if sentiment and sentiment.get("score") is not None:
                    score = sentiment["score"]
                    label = sentiment["label"]
                    # Apply confidence threshold
                    min_conf = 0.6
                    if abs(score) < min_conf:
                        label = "neutral"
                        score = 0.0

                    article["sentiment_label"] = label  # bullish|bearish|neutral
                    article["sentiment_score"] = round(score, 4)
                    article["sentiment_method"] = "finbert"
                    article["sentiment_status"] = "ok"
                else:
                    article["sentiment_label"] = None
                    article["sentiment_score"] = None
                    article["sentiment_method"] = "finbert"
                    article["sentiment_status"] = "failed"
            else:
                article["sentiment_label"] = None
                article["sentiment_score"] = None
                article["sentiment_method"] = "none"
                article["sentiment_status"] = "skipped"

    except Exception as exc:
        log.warning("Sentiment scoring failed: %s", exc)
        # Mark all as failed
        for article in all_new_articles:
            if article.get("sentiment_status") != "skipped":
                article["sentiment_label"] = None
                article["sentiment_score"] = None
                article["sentiment_method"] = "finbert"
                article["sentiment_status"] = "failed"

    # ── Stage 8: IMPACT SCORING ──────────────────────────────────────────
    try:
        all_new_articles = score_articles(all_new_articles)
    except Exception as exc:
        log.warning("Impact scoring failed: %s", exc)

    # ── Stage 9: SAVE TO DATABASE ────────────────────────────────────────
    inserted_count = await _save_article_batch(db, all_new_articles)

    # Record completion even when all fetched items were duplicates or no new
    # items could be saved, so refresh polling does not keep stale state.
    ingestion_state.mark_ingestion_completed(inserted_count)
    ingestion_state.increment_run_count()

    # Update per-source counts
    for r in result.sources:
        r.articles_inserted = sum(
            1 for a in all_new_articles if a.get("source") == r.source
        )
    await _save_source_health(db, result.sources)

    # Aggregate results
    result.total_fetched = sum(r.articles_fetched for r in result.sources)
    result.total_inserted = inserted_count
    result.total_skipped_duplicate = sum(r.articles_skipped_duplicate for r in result.sources)
    result.total_symbol_tagged = sum(r.articles_symbol_tagged for r in result.sources)
    result.total_sentiment_processed = sum(
        1 for a in all_new_articles
        if a.get("sentiment_status") == "ok"
    )
    result.errors = sum(1 for r in result.sources if r.error)
    result.completed_at = datetime.now(timezone.utc).isoformat()

    log.info(
        "Pipeline complete: fetched=%d, inserted=%d, dedup_skipped=%d, sentiment_ok=%d",
        result.total_fetched,
        result.total_inserted,
        result.total_skipped_duplicate,
        result.total_sentiment_processed,
    )

    return result
