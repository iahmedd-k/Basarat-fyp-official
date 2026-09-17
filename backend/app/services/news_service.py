import json
from datetime import datetime

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news import NewsArticle


class NewsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_articles(
        self,
        limit: int = 20,
        offset: int = 0,
        symbol: str | None = None,
        sentiment: str | None = None,
        source: str | None = None,
        event_type: str | None = None,
    ) -> tuple[list[NewsArticle], int]:
        query = select(NewsArticle)
        count_query = select(func.count(NewsArticle.id))
        conditions = []

        if symbol:
            # JSON array search — symbols stored as '["OGDC","PPL"]'
            conditions.append(NewsArticle.symbols.contains(f'"{symbol.upper()}"'))
        if sentiment:
            conditions.append(NewsArticle.sentiment_label == sentiment.lower())
        if source:
            conditions.append(NewsArticle.source == source)
        if event_type:
            conditions.append(NewsArticle.event_type == event_type)

        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        query = query.order_by(NewsArticle.created_at.desc())
        query = query.offset(offset).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def get_article_by_id(self, article_id: str) -> NewsArticle | None:
        result = await self.db.execute(
            select(NewsArticle).where(NewsArticle.id == article_id)
        )
        return result.scalars().first()

    @staticmethod
    def parse_symbols(raw: str | None) -> list[str]:
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    @staticmethod
    def parse_company_names(raw: str | None) -> list[str]:
        return NewsService.parse_symbols(raw)  # same format
