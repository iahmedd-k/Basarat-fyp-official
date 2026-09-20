"""Sentiment Repository - Database access for sentiment data."""

from datetime import date, datetime
from typing import Literal

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news import NewsArticle
from app.models.sentiment import SentimentAggregate, SentimentResult
from app.models.stock import Stock


class SentimentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── News Articles ──────────────────────────────────────────────────────────

    async def get_news_article(self, article_id: str) -> NewsArticle | None:
        result = await self.db.execute(
            select(NewsArticle).where(NewsArticle.id == article_id)
        )
        return result.scalars().first()

    async def get_news_by_external_id(self, source: str, external_id: str) -> NewsArticle | None:
        result = await self.db.execute(
            select(NewsArticle).where(
                NewsArticle.source == source,
                NewsArticle.url.like(f"%{external_id}%"),
            )
        )
        return result.scalars().first()

    async def create_news_article(
        self,
        title: str,
        url: str,
        source: str,
        source_type: str | None,
        summary: str | None,
        content_hash: str | None,
        symbols: list[str] | None,
        company_names: list[str] | None,
        sector: str | None,
        event_type: str | None,
        published_at: datetime | None,
    ) -> NewsArticle:
        import json

        article = NewsArticle(
            title=title,
            url=url,
            source=source,
            source_type=source_type,
            summary=summary,
            content_hash=content_hash,
            symbols=json.dumps(symbols) if symbols else None,
            company_names=json.dumps(company_names) if company_names else None,
            sector=sector,
            event_type=event_type,
            published_at=published_at,
        )
        self.db.add(article)
        await self.db.flush()
        await self.db.refresh(article)
        return article

    async def get_recent_news(
        self,
        symbol: str | None = None,
        days: int = 365,
        limit: int = 100,
        page: int = 1,
    ) -> tuple[list[NewsArticle], int]:
        from datetime import timezone, timedelta
        from sqlalchemy import or_
        from app.models.news import NewsArticleSymbol

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = (
            select(NewsArticle)
            .where(
                or_(
                    NewsArticle.published_at >= cutoff,
                    NewsArticle.published_at.is_(None),
                )
            )
            .order_by(NewsArticle.published_at.desc().nulls_last(), NewsArticle.created_at.desc())
        )
        if symbol:
            sym_clean = symbol.strip().upper()
            sym_subq = select(NewsArticleSymbol.article_id).where(NewsArticleSymbol.symbol == sym_clean)
            stmt = stmt.where(
                or_(
                    NewsArticle.id.in_(sym_subq),
                    NewsArticle.symbols.ilike(f'%"{sym_clean}"%'),
                    NewsArticle.symbols.ilike(f'%{sym_clean}%'),
                    NewsArticle.title.ilike(f'%{sym_clean}%'),
                )
            )

        count_stmt = select(func.count(NewsArticle.id)).where(stmt.whereclause)
        total = await self.db.scalar(count_stmt) or 0

        stmt = stmt.offset((page - 1) * limit).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    # ── Sentiment Results ──────────────────────────────────────────────────────

    async def create_sentiment_result(
        self,
        news_article_id: str,
        symbol: str,
        model_name: str,
        label: str,
        score: float,
        positive_score: float | None = None,
        neutral_score: float | None = None,
        negative_score: float | None = None,
    ) -> SentimentResult:
        result = SentimentResult(
            news_article_id=news_article_id,
            symbol=symbol.upper(),
            model_name=model_name,
            label=label,
            score=score,
            positive_score=positive_score,
            neutral_score=neutral_score,
            negative_score=negative_score,
        )
        self.db.add(result)
        await self.db.flush()
        await self.db.refresh(result)
        return result

    async def get_sentiment_results_for_symbol(
        self,
        symbol: str,
        days: int = 7,
        limit: int = 100,
    ) -> list[SentimentResult]:
        from datetime import timedelta

        cutoff = datetime.utcnow() - timedelta(days=days)
        result = await self.db.execute(
            select(SentimentResult)
            .where(
                SentimentResult.symbol == symbol.upper(),
                SentimentResult.created_at >= cutoff,
            )
            .order_by(desc(SentimentResult.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_latest_sentiment_for_symbol(self, symbol: str) -> SentimentResult | None:
        result = await self.db.execute(
            select(SentimentResult)
            .where(SentimentResult.symbol == symbol.upper())
            .order_by(desc(SentimentResult.created_at))
            .limit(1)
        )
        return result.scalars().first()

    # ── Sentiment Aggregates ───────────────────────────────────────────────────

    async def upsert_sentiment_aggregate(
        self,
        symbol: str,
        period: str,
        period_start: datetime,
        period_end: datetime,
        overall_score: float,
        label: str,
        article_count: int,
        positive_ratio: float | None = None,
        neutral_ratio: float | None = None,
        negative_ratio: float | None = None,
        trend: str | None = None,
        daily_scores: str | None = None,
        source_breakdown: str | None = None,
    ) -> SentimentAggregate:
        # Check if exists
        result = await self.db.execute(
            select(SentimentAggregate).where(
                SentimentAggregate.symbol == symbol.upper(),
                SentimentAggregate.period == period,
                SentimentAggregate.period_end == period_end,
            )
        )
        agg = result.scalars().first()

        if agg:
            agg.overall_score = overall_score
            agg.label = label
            agg.article_count = article_count
            agg.positive_ratio = positive_ratio
            agg.neutral_ratio = neutral_ratio
            agg.negative_ratio = negative_ratio
            agg.trend = trend
            agg.daily_scores = daily_scores
            agg.source_breakdown = source_breakdown
            agg.computed_at = datetime.utcnow()
        else:
            agg = SentimentAggregate(
                symbol=symbol.upper(),
                period=period,
                period_start=period_start,
                period_end=period_end,
                overall_score=overall_score,
                label=label,
                article_count=article_count,
                positive_ratio=positive_ratio,
                neutral_ratio=neutral_ratio,
                negative_ratio=negative_ratio,
                trend=trend,
                daily_scores=daily_scores,
                source_breakdown=source_breakdown,
            )
            self.db.add(agg)

        await self.db.flush()
        await self.db.refresh(agg)
        return agg

    async def get_sentiment_aggregate(
        self,
        symbol: str,
        period: str,
    ) -> SentimentAggregate | None:
        result = await self.db.execute(
            select(SentimentAggregate)
            .where(
                SentimentAggregate.symbol == symbol.upper(),
                SentimentAggregate.period == period,
            )
            .order_by(desc(SentimentAggregate.period_end))
            .limit(1)
        )
        return result.scalars().first()

    async def get_sentiment_history(
        self,
        symbol: str,
        period: Literal["1D", "1W", "1M", "3M", "6M", "1Y"] = "1M",
        limit: int = 100,
    ) -> list[SentimentAggregate]:
        result = await self.db.execute(
            select(SentimentAggregate)
            .where(
                SentimentAggregate.symbol == symbol.upper(),
                SentimentAggregate.period == period,
            )
            .order_by(desc(SentimentAggregate.period_end))
            .limit(limit)
        )
        return list(result.scalars().all())

    # ── Stock Info ─────────────────────────────────────────────────────────────

    async def get_stock(self, symbol: str) -> Stock | None:
        result = await self.db.execute(
            select(Stock).where(Stock.symbol == symbol.upper())
        )
        return result.scalars().first()