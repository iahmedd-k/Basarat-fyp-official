from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user, get_optional_current_user
from app.core.config import get_settings
from app.core.exceptions import BadRequestError, NotFoundError, ServiceUnavailableError, AppError
from app.core.rate_limiter import limiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.news import (
    NewsArticleResponse,
    NewsListResponse,
    NewsRefreshResponse,
    NewsRefreshStatusResponse,
    SourceHealthResponse,
    SourcesResponse,
)
from app.services.news_service import NewsService
from app.services.news_pipeline import ingestion_state
from app.services.news_pipeline.market_schedule import (
    market_status,
    next_ingestion_window,
)

router = APIRouter()


def _encode_cursor(published_at: datetime, article_id: str) -> str:
    """Encode cursor as published_at|id."""
    return f"{published_at.isoformat()}|{article_id}"


@router.get(
    "/news",
    response_model=NewsListResponse,
    summary="Get paginated news feed with cursor pagination",
)
@limiter.limit("60/minute")
async def get_news(
    request: Request,
    row: str = Query("news", description="Row type: 'news' or 'portfolio'"),
    symbol: Optional[str] = Query(None, description="Filter by PSX symbol"),
    sentiment: Optional[str] = Query(None, description="Filter by sentiment: bullish|bearish|neutral"),
    source: Optional[str] = Query(None, description="Filter by source name"),
    source_type: Optional[str] = Query(None, description="Filter by source_type: official|news"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    q: Optional[str] = Query(None, description="Text search (max 100 chars)", max_length=100),
    limit: int = Query(20, ge=1, le=50),
    cursor: Optional[str] = Query(None, description="Opaque cursor from previous page"),
    user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        if row not in ("news", "portfolio"):
            raise BadRequestError("row must be 'news' or 'portfolio'")
        if source_type and source_type not in ("official", "news"):
            raise BadRequestError("source_type must be 'official' or 'news'")
        if sentiment and sentiment not in ("bullish", "bearish", "neutral"):
            raise BadRequestError("sentiment must be 'bullish', 'bearish', or 'neutral'")

        user_id = user.id if (user and row == "portfolio") else None
        empty_reason = None

        if row == "portfolio":
            if not user:
                return NewsListResponse(
                    items=[],
                    next_cursor=None,
                    has_more=False,
                    row="portfolio",
                    last_updated_at=None,
                    empty_reason="unauthenticated",
                )
            from app.services.psx_announcement_service import PSXAnnouncementService
            psx_svc = PSXAnnouncementService(db)
            items, empty_reason = await psx_svc.get_portfolio_announcements(user_id=user_id, limit=limit)
            next_cursor = None
        else:
            svc = NewsService(db)
            articles, total, next_cursor = await svc.get_articles(
                limit=limit,
                cursor=cursor,
                symbol=symbol,
                sentiment=sentiment,
                source=source,
                event_type=event_type,
                source_type=source_type,
                row=row,
                user_id=user_id,
            )
            items = [svc.to_response(a) for a in articles]
            if not items:
                empty_reason = "no_results"

        # The feed's last-updated time is the latest visible article, while
        # /news/refresh/status continues to report the last ingestion attempt.
        last_updated = None
        if row == "news":
            from app.models.news import NewsArticle
            latest = await db.execute(select(NewsArticle.created_at).order_by(NewsArticle.created_at.desc()).limit(1))
            last_updated = latest.scalar_one_or_none()

        return NewsListResponse(
            items=[NewsArticleResponse(**item) for item in items],
            next_cursor=next_cursor,
            has_more=next_cursor is not None,
            row=row,
            last_updated_at=last_updated.isoformat() if last_updated else None,
            empty_reason=empty_reason,
        )
    except AppError:
        raise
    except Exception as exc:
        import logging
        logging.getLogger(__name__).exception("Get news failed: %s", exc)
        raise ServiceUnavailableError(f"Failed to fetch news: {exc}")


@router.post(
    "/news/refresh",
    response_model=NewsRefreshResponse,
    summary="Manually refresh news feed (async, cooldown-protected)",
)
@limiter.limit("5/minute")
async def refresh_news(
    request: Request,
    force: bool = Query(False, description="Admin only: bypass cooldown"),
    user: Optional[User] = Depends(get_optional_current_user),
):
    """Trigger a manual news ingestion with cooldown protection.

    - If last ingestion was within NEWS_REFRESH_COOLDOWN (5 min), returns cooldown status.
    - Manual refresh IGNORES market hours (user-initiated, works any time).
    - force=true (admin only) bypasses cooldown.
    - Returns immediately with status; runs pipeline in background.
    """
    settings = get_settings()
    last_run = ingestion_state.get_last_ingestion_time()
    now = datetime.now(timezone.utc)
    m_status = await market_status()

    # Check admin for force
    is_admin = getattr(user, "is_admin", False) if user else False

    # ── Check 1: Cooldown ────────────────────────────────────────────────
    if last_run and not (force and is_admin):
        elapsed = (now - last_run).total_seconds()
        if elapsed < settings.NEWS_REFRESH_COOLDOWN:
            remaining = int(settings.NEWS_REFRESH_COOLDOWN - elapsed)
            return NewsRefreshResponse(
                status="cooldown",
                last_updated=last_run.isoformat(),
                refresh_available=False,
                next_refresh_at=(last_run.timestamp() + settings.NEWS_REFRESH_COOLDOWN),
                retry_after_seconds=remaining,
                market_status=m_status,
            )

    # API replicas only enqueue work; the Celery worker owns source fetches.
    current = ingestion_state.get_ingestion_status()
    if current["state"] in {"queued", "running"}:
        return NewsRefreshResponse(
            status="already_running",
            last_updated=last_run.isoformat() if last_run else None,
            refresh_available=False,
            market_status=m_status,
        )

    try:
        from app.tasks.scrape_news import run as news_ingestion_task
        ingestion_state.mark_ingestion_queued()
        news_ingestion_task.apply_async(kwargs={"force": True, "limit_per_source": 50})
    except Exception as exc:
        ingestion_state.mark_ingestion_failed(str(exc))
        raise ServiceUnavailableError("Could not queue news refresh") from exc

    return NewsRefreshResponse(
        status="started",
        last_updated=now.isoformat(),
        refresh_available=True,
        next_refresh_at=None,
        market_status=m_status,
    )


@router.get(
    "/news/refresh/status",
    response_model=NewsRefreshStatusResponse,
    summary="Get refresh job status for polling",
)
@limiter.limit("60/minute")
async def refresh_status(
    request: Request,
):
    """Get current refresh job status for client polling after pull-to-refresh."""
    state = ingestion_state.get_ingestion_status()
    return NewsRefreshStatusResponse(
        **state,
    )


@router.get(
    "/news/market-status",
    summary="Get current market schedule and ingestion status",
)
@limiter.limit("60/minute")
async def get_market_status_endpoint(
    request: Request,
):
    """Return current PKT time, market window, and next ingestion window."""
    return await market_status()


REGISTERED_SOURCES = [
    {"key": "psx", "name": "PSX Official Announcements", "type": "official"},
    {"key": "secp", "name": "SECP Regulatory Notices", "type": "official"},
    {"key": "sbp", "name": "State Bank of Pakistan", "type": "official"},
    {"key": "ogra", "name": "OGRA Petroleum & Gas", "type": "official"},
    {"key": "fbr_mof", "name": "FBR & Ministry of Finance", "type": "official"},
    {"key": "business_recorder", "name": "Business Recorder", "type": "news"},
    {"key": "dawn", "name": "Dawn Business", "type": "news"},
    {"key": "mettis", "name": "Mettis Global", "type": "news"},
]


@router.get(
    "/news/sources",
    response_model=SourcesResponse,
    summary="Get per-source health status (admin/ops)",
)
@limiter.limit("30/minute")
async def get_sources(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Per-source health status for all configured data sources."""
    from app.models.news import NewsSourceState
    result = await db.execute(select(NewsSourceState).order_by(NewsSourceState.source_key))
    db_sources = {s.source_key: s for s in result.scalars().all()}

    source_list = []
    for reg in REGISTERED_SOURCES:
        s = db_sources.get(reg["key"])
        if s:
            source_list.append(SourceHealthResponse(
                key=s.source_key,
                name=reg["name"],
                type=reg["type"],
                last_success_at=s.last_success_at.isoformat() if s.last_success_at else None,
                last_error=s.last_error,
                consecutive_failures=s.consecutive_failures,
                healthy=s.healthy,
            ))
        else:
            source_list.append(SourceHealthResponse(
                key=reg["key"],
                name=reg["name"],
                type=reg["type"],
                last_success_at=None,
                last_error="No ingestion status recorded yet.",
                consecutive_failures=0,
                healthy=False,
            ))

    return SourcesResponse(sources=source_list)


@router.get(
    "/news/{article_id}",
    response_model=NewsArticleResponse,
    summary="Get a single news article",
)
@limiter.limit("60/minute")
async def get_news_article(
    request: Request,
    article_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        svc = NewsService(db)
        article = await svc.get_article_by_id(article_id)
        if article is None:
            raise NotFoundError(f"News article '{article_id}' not found.")
        return NewsArticleResponse(**svc.to_response(article))
    except NotFoundError:
        raise
    except Exception as exc:
        import logging
        logging.getLogger(__name__).exception("Get news article failed: %s", exc)
        raise ServiceUnavailableError(f"Failed to fetch news article: {exc}")


@router.get(
    "/stocks/{symbol}/news",
    response_model=NewsListResponse,
    summary="Get news for a specific stock (stock page News tab)",
)
@limiter.limit("60/minute")
async def get_stock_news(
    request: Request,
    symbol: str,
    sentiment: Optional[str] = Query(None, description="Filter by sentiment: bullish|bearish|neutral"),
    source_type: Optional[str] = Query(None, description="Filter by source_type: official|news"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    limit: int = Query(20, ge=1, le=50),
    cursor: Optional[str] = Query(None, description="Opaque cursor from previous page"),
    db: AsyncSession = Depends(get_db),
):
    """Stock page News tab - retrieves live official announcements from PSX with Redis cache & DB fallback."""
    try:
        if source_type and source_type not in ("official", "news"):
            raise HTTPException(status_code=400, detail="source_type must be 'official' or 'news'")
        if sentiment and sentiment not in ("bullish", "bearish", "neutral"):
            raise HTTPException(status_code=400, detail="sentiment must be 'bullish', 'bearish', or 'neutral'")

        from app.services.psx_announcement_service import PSXAnnouncementService
        psx_svc = PSXAnnouncementService(db)
        items = await psx_svc.get_stock_announcements(symbol=symbol.upper(), limit=limit)

        # Apply optional filters
        if sentiment:
            items = [item for item in items if item.get("sentiment", {}).get("label") == sentiment.lower()]
        if event_type:
            items = [item for item in items if item.get("event_type") == event_type]
        if source_type:
            items = [item for item in items if item.get("source", {}).get("type") == source_type]

        return NewsListResponse(
            items=[NewsArticleResponse(**item) for item in items],
            next_cursor=None,
            has_more=False,
            row="news",
            last_updated_at=ingestion_state.get_last_ingestion_time().isoformat() if ingestion_state.get_last_ingestion_time() else None,
            empty_reason="no_results" if not items else None,
        )
    except HTTPException:
        raise
    except Exception as exc:
        import logging
        logging.getLogger(__name__).exception("Get stock news failed: %s", exc)
        raise ServiceUnavailableError(f"Failed to fetch stock news: {exc}")
