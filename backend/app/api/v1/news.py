from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.db.session import get_db
from app.models.user import User
from app.schemas.news import NewsArticleResponse, NewsListResponse, NewsRefreshResponse
from app.services.news_service import NewsService
from app.services.news_pipeline import ingestion_state
from app.services.news_pipeline.market_schedule import (
    is_ingestion_allowed,
    market_status,
    next_ingestion_window,
)

router = APIRouter()


def _to_response(article, svc: NewsService) -> NewsArticleResponse:
    return NewsArticleResponse(
        id=article.id,
        title=article.title,
        url=article.url,
        source=article.source,
        source_type=article.source_type,
        summary=article.summary,
        symbols=svc.parse_symbols(article.symbols),
        company_names=svc.parse_company_names(article.company_names),
        sector=article.sector,
        event_type=article.event_type,
        sentiment_label=article.sentiment_label,
        sentiment_score=float(article.sentiment_score) if article.sentiment_score else None,
        impact_score=article.impact_score,
        published_at=article.published_at.isoformat() if article.published_at else None,
        created_at=article.created_at.isoformat() if article.created_at else "",
    )


@router.get(
    "/news",
    response_model=NewsListResponse,
    summary="Get paginated news feed with filtering",
)
async def get_news(
    symbol: str | None = Query(None, description="Filter by PSX symbol"),
    sentiment: str | None = Query(None, description="positive|negative|neutral"),
    source: str | None = Query(None, description="Filter by source name"),
    event_type: str | None = Query(None, description="Filter by event type"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        svc = NewsService(db)
        offset = (page - 1) * limit
        articles, total = await svc.get_articles(
            limit=limit,
            offset=offset,
            symbol=symbol,
            sentiment=sentiment,
            source=source,
            event_type=event_type,
        )

        items = [_to_response(a, svc) for a in articles]

        return NewsListResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
            has_more=(page * limit) < total,
        )
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to fetch news: {exc}")


@router.get(
    "/news/{article_id}",
    response_model=NewsArticleResponse,
    summary="Get a single news article",
)
async def get_news_article(
    article_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        svc = NewsService(db)
        article = await svc.get_article_by_id(article_id)
        if article is None:
            raise NotFoundError(f"News article '{article_id}' not found.")
        return _to_response(article, svc)
    except NotFoundError:
        raise
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to fetch news article: {exc}")


@router.post(
    "/news/refresh",
    response_model=NewsRefreshResponse,
    summary="Manually refresh news feed (cooldown-protected)",
)
async def refresh_news(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a manual news ingestion with cooldown protection.

    - If last ingestion was within NEWS_REFRESH_COOLDOWN (5 min), returns cached status.
    - If outside market hours and post-market, returns without scraping.
    - Otherwise runs the full pipeline (same as the scheduled task).
    """
    settings = get_settings()
    last_run = ingestion_state.get_last_ingestion_time()
    now = datetime.now(timezone.utc)
    m_status = market_status()

    # ── Check 1: Cooldown ────────────────────────────────────────────────
    if last_run:
        elapsed = (now - last_run).total_seconds()
        if elapsed < settings.NEWS_REFRESH_COOLDOWN:
            remaining = int(settings.NEWS_REFRESH_COOLDOWN - elapsed)
            next_at = last_run.timestamp() + settings.NEWS_REFRESH_COOLDOWN
            return NewsRefreshResponse(
                status="skipped_cooldown",
                last_updated=last_run.isoformat(),
                refresh_available=False,
                next_refresh_at=datetime.fromtimestamp(next_at, tz=timezone.utc).isoformat(),
                market_status=m_status,
            )

    # ── Check 2: Market hours gate ───────────────────────────────────────
    if not is_ingestion_allowed():
        nxt = next_ingestion_window()
        return NewsRefreshResponse(
            status="skipped_outside_hours",
            last_updated=last_run.isoformat() if last_run else None,
            refresh_available=False,
            next_refresh_at=nxt.isoformat() if nxt else None,
            market_status=m_status,
        )

    # ── Run the pipeline (same as Celery task) ───────────────────────────
    from app.services.news_pipeline.pipeline import run_pipeline
    from app.services.event_service import extract_events_from_news

    try:
        pipeline_result = await run_pipeline(db, limit_per_source=50)

        # Extract events
        events_created = 0
        if pipeline_result.total_inserted > 0:
            events_created = await extract_events_from_news(db)

        return NewsRefreshResponse(
            status="completed",
            last_updated=pipeline_result.completed_at,
            refresh_available=True,
            next_refresh_at=None,
            articles_inserted=pipeline_result.total_inserted,
            market_status=m_status,
        )
    except Exception as exc:
        raise ServiceUnavailableError(f"News refresh failed: {exc}")


@router.get(
    "/news/market-status",
    summary="Get current market schedule and ingestion status",
)
async def get_market_status(user: User = Depends(get_current_user)):
    """Return current PKT time, market window, and next ingestion window."""
    return market_status()
