from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.news import NewsArticle


class NewsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_articles(self, limit: int = 20, offset: int = 0) -> list[NewsArticle]:
        result = await self.db.execute(
            select(NewsArticle)
            .order_by(NewsArticle.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_article_by_id(self, article_id: str) -> NewsArticle | None:
        result = await self.db.execute(
            select(NewsArticle).where(NewsArticle.id == article_id)
        )
        return result.scalars().first()
