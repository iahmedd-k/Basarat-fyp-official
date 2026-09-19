import json
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news import NewsArticle, NewsArticleSymbol
from app.models.user import User

log = logging.getLogger(__name__)


class NewsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_articles(
        self,
        limit: int = 20,
        cursor: Optional[str] = None,
        symbol: Optional[str] = None,
        sentiment: Optional[str] = None,
        source: Optional[str] = None,
        event_type: Optional[str] = None,
        source_type: Optional[str] = None,
        row: str = "news",
        user_id: Optional[str] = None,
    ) -> tuple[list[NewsArticle], int, Optional[str]]:
        """Get articles with cursor pagination.

        Args:
            limit: Max items per page (1-50)
            cursor: Opaque cursor from previous page (published_at|id)
            symbol: Filter by PSX symbol
            sentiment: Filter by sentiment label
            source: Filter by source name
            event_type: Filter by event type
            source_type: Filter by source_type (official|news)
            row: "news" or "portfolio"
            user_id: Required for portfolio row

        Returns:
            (articles, total_count, next_cursor)
        """
        # Base query
        query = select(NewsArticle)
        count_query = select(func.count(NewsArticle.id))
        conditions = []

        # Row filtering
        if row == "portfolio":
            if not user_id:
                return [], 0, None
            # Get user's symbols and filter via link table
            user_symbols = await self._get_user_symbols(user_id)
            if not user_symbols:
                return [], 0, None  # no_holdings

            # Join with link table
            query = query.join(NewsArticleSymbol, NewsArticle.id == NewsArticleSymbol.article_id)
            count_query = count_query.join(NewsArticleSymbol, NewsArticle.id == NewsArticleSymbol.article_id)
            conditions.append(NewsArticleSymbol.symbol.in_(user_symbols))

        # Filters
        if symbol:
            conditions.append(NewsArticleSymbol.symbol == symbol.upper())
        if sentiment:
            conditions.append(NewsArticle.sentiment_label == sentiment.lower())
        if source:
            conditions.append(NewsArticle.source == source)
        if event_type:
            conditions.append(NewsArticle.event_type == event_type)
        if source_type:
            conditions.append(NewsArticle.source_type == source_type)

        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Cursor pagination: published_at DESC, id DESC
        if cursor:
            try:
                cursor_published_at_str, cursor_id = cursor.split("|", 1)
                cursor_published_at = datetime.fromisoformat(cursor_published_at_str)
                # For DESC order: we want items OLDER than cursor
                query = query.where(
                    or_(
                        NewsArticle.published_at < cursor_published_at,
                        and_(
                            NewsArticle.published_at == cursor_published_at,
                            NewsArticle.id < cursor_id,
                        ),
                    )
                )
            except (ValueError, IndexError):
                log.warning("Invalid cursor format: %s", cursor)
                pass

        query = query.order_by(NewsArticle.published_at.desc(), NewsArticle.id.desc())
        query = query.limit(limit + 1)  # +1 to check has_more

        result = await self.db.execute(query)
        articles = list(result.scalars().all())

        has_more = len(articles) > limit
        if has_more:
            articles = articles[:limit]

        next_cursor = None
        if articles:
            last = articles[-1]
            if last.published_at:
                next_cursor = f"{last.published_at.isoformat()}|{last.id}"

        return articles, total, next_cursor

    async def get_article_by_id(self, article_id: str) -> Optional[NewsArticle]:
        result = await self.db.execute(
            select(NewsArticle).where(NewsArticle.id == article_id)
        )
        return result.scalars().first()

    async def _get_user_symbols(self, user_id: str) -> list[str]:
        """Get symbols from user's portfolio holdings."""
        # Use the existing portfolio/holdings table through a function
        # Find the existing get_user_symbols function or query holdings
        try:
            # Try to find portfolio holdings
            from app.repository.portfolio_repository import PortfolioRepository
            repo = PortfolioRepository(self.db)
            holdings = await repo.get_holdings(user_id)
            return [h.symbol.upper() for h in holdings if h.quantity > 0]
        except Exception as exc:
            log.warning("Failed to get user symbols via PortfolioRepository: %s", exc)

        # Fallback: query transactions directly
        try:
            from app.models.portfolio import PortfolioTransaction, TransactionType
            result = await self.db.execute(
                select(PortfolioTransaction.symbol, func.sum(PortfolioTransaction.quantity))
                .where(
                    PortfolioTransaction.user_id == user_id,
                    PortfolioTransaction.transaction_type.in_([TransactionType.BUY, TransactionType.SELL]),
                )
                .group_by(PortfolioTransaction.symbol)
                .having(func.sum(PortfolioTransaction.quantity) > 0)
            )
            return [row[0].upper() for row in result.all()]
        except Exception as exc:
            log.warning("Failed to get user symbols via transactions: %s", exc)
            return []

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

    def to_response(self, article: NewsArticle) -> dict:
        """Convert NewsArticle to API response dict."""
        symbols = self.parse_symbols(article.symbols)
        company_names = self.parse_company_names(article.company_names)

        return {
            "id": article.id,
            "title": article.title,
            "url": article.url,
            "external_url": article.external_url,
            "source": {
                "key": article.source_key or "",
                "name": article.source or "",
                "type": article.source_type or "news",
            },
            "is_official": article.source_type == "official",
            "summary": article.summary,
            "symbols": [
                {"symbol": sym, "name": name}
                for sym, name in zip(symbols, company_names)
            ],
            "event_type": article.event_type,
            "sentiment": None if article.sentiment_label is None else {
                "label": article.sentiment_label,
                "score": float(article.sentiment_score) if article.sentiment_score else None,
                "method": article.sentiment_method,
            },
            "impact_score": article.impact_score,
            "published_at": article.published_at.isoformat() if article.published_at else None,
            "created_at": article.created_at.isoformat() if article.created_at else "",
        }