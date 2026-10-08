from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.dialects import postgresql

from app.repository.sentiment_repository import SentimentRepository
from app.services.news_service import NewsService


def _where_sql(statement) -> str:
    return " ".join(
        str(criterion.compile(dialect=postgresql.dialect()))
        for criterion in statement._where_criteria
    ).lower()


@pytest.mark.asyncio
async def test_news_service_symbol_filter_uses_link_table_only():
    db = AsyncMock()
    articles_result = Mock()
    articles_result.scalars.return_value.all.return_value = []
    db.execute.return_value = articles_result

    await NewsService(db).get_articles(symbol="ogdc")

    assert len(db.execute.await_args_list) == 1
    articles_where = _where_sql(db.execute.await_args_list[0].args[0])
    assert "news_article_symbols" in articles_where
    assert "news_articles.symbols" not in articles_where
    assert "ilike" not in articles_where


@pytest.mark.asyncio
async def test_news_service_portfolio_filter_uses_link_table_only(monkeypatch):
    db = AsyncMock()
    articles_result = Mock()
    articles_result.scalars.return_value.all.return_value = []
    db.execute.return_value = articles_result

    async def user_symbols(_service, _user_id):
        return ["OGDC", "LUCK"]

    monkeypatch.setattr(NewsService, "_get_user_symbols", user_symbols)

    await NewsService(db).get_articles(row="portfolio", user_id="user-1")

    assert len(db.execute.await_args_list) == 1
    articles_where = _where_sql(db.execute.await_args_list[0].args[0])
    assert "news_article_symbols" in articles_where
    assert "news_articles.symbols" not in articles_where
    assert "ilike" not in articles_where


@pytest.mark.asyncio
async def test_recent_sentiment_news_symbol_filter_uses_link_table_only():
    db = AsyncMock()
    db.scalar.return_value = 0
    articles_result = Mock()
    articles_result.scalars.return_value.all.return_value = []
    db.execute.return_value = articles_result

    await SentimentRepository(db).get_recent_news(symbol="ogdc")

    count_where = _where_sql(db.scalar.await_args.args[0])
    articles_where = _where_sql(db.execute.await_args.args[0])
    for where_clause in (count_where, articles_where):
        assert "news_article_symbols" in where_clause
        assert "news_articles.symbols" not in where_clause
        assert "news_articles.title" not in where_clause
