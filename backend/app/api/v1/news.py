from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.db.session import get_db
from app.models.news import NewsArticle
from app.models.user import User
from app.schemas.auth import NewsArticleResponse, NewsListResponse

router = APIRouter()


@router.get(
    "/news",
    response_model=NewsListResponse,
    summary="Get paginated news feed",
)
async def get_news(
    symbol: str | None = Query(None),
    sentiment: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        query = select(NewsArticle)

        if sentiment:
            if sentiment == "positive":
                query = query.where(NewsArticle.sentiment_score > 0.2)
            elif sentiment == "negative":
                query = query.where(NewsArticle.sentiment_score < -0.2)
            elif sentiment == "neutral":
                query = query.where(
                    NewsArticle.sentiment_score >= -0.2,
                    NewsArticle.sentiment_score <= 0.2,
                )

        count_result = await db.execute(select(func.count(NewsArticle.id)))
        total = count_result.scalar() or 0

        query = query.order_by(NewsArticle.created_at.desc())
        query = query.offset((page - 1) * limit).limit(limit)

        result = await db.execute(query)
        articles = result.scalars().all()

        items = [
            NewsArticleResponse(
                id=a.id,
                title=a.title,
                url=a.url,
                source=a.source,
                summary=a.summary,
                sentiment_score=float(a.sentiment_score) if a.sentiment_score else None,
                published_at=a.published_at.isoformat() if a.published_at else None,
                created_at=a.created_at.isoformat() if a.created_at else "",
            )
            for a in articles
        ]

        return NewsListResponse(
            articles=items,
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
        result = await db.execute(
            select(NewsArticle).where(NewsArticle.id == article_id)
        )
        article = result.scalars().first()
        if article is None:
            raise NotFoundError(f"News article '{article_id}' not found.")

        return NewsArticleResponse(
            id=article.id,
            title=article.title,
            url=article.url,
            source=article.source,
            summary=article.summary,
            sentiment_score=float(article.sentiment_score) if article.sentiment_score else None,
            published_at=article.published_at.isoformat() if article.published_at else None,
            created_at=article.created_at.isoformat() if article.created_at else "",
        )
    except NotFoundError:
        raise
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to fetch news article: {exc}")
