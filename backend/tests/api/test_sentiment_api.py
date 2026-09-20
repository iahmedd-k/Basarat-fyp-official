import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.news import NewsArticle
from app.models.sentiment import SentimentResult, SentimentAggregate
from app.models.stock import Stock
from app.models.user import User
from app.core.security import create_access_token


@pytest_asyncio.fixture
async def auth_headers(db_session: AsyncSession):
    """Create a test user and return auth headers."""
    from sqlalchemy import select

    user = User(
        id=uuid4().hex,
        email=f"test_{uuid4().hex[:8]}@example.com",
        username=f"user_{uuid4().hex[:8]}",
        hashed_password="hashed",
        is_active=True,
    )
    db_session.add(user)
    
    # Add test stocks if not already present
    test_stocks = [
        ("stock-hbl", "HBL", "Habib Bank Limited", "Banking"),
        ("stock-ogdc", "OGDC", "Oil & Gas Development Company", "Oil & Gas"),
        ("stock-luck", "LUCK", "Lucky Cement", "Cement"),
    ]
    for sid, sym, name, sec in test_stocks:
        existing = await db_session.execute(select(Stock).where(Stock.symbol == sym))
        if not existing.scalars().first():
            db_session.add(Stock(id=sid, symbol=sym, name=name, sector=sec))
    
    await db_session.flush()
    
    token = create_access_token({"sub": user.id})
    return {"Authorization": f"Bearer {token}"}, user.id


@pytest_asyncio.fixture
async def sample_news_with_sentiment(db_session: AsyncSession):
    """Create sample news articles with sentiment."""
    # Create news articles
    articles = [
        NewsArticle(
            id=uuid4().hex,
            title="HBL Reports Strong Quarterly Earnings",
            url="https://example.com/hbl-earnings-1",
            source="Business Recorder",
            source_type="financial_media",
            summary="HBL reported profit growth of 25% YoY",
            symbols='["HBL"]',
            company_names='["Habib Bank Limited"]',
            sector="Banking",
            sentiment_label="positive",
            sentiment_score=0.85,
            published_at=datetime.utcnow() - timedelta(days=2),
        ),
        NewsArticle(
            id=uuid4().hex,
            title="OGDC Faces Production Challenges",
            url="https://example.com/ogdc-production",
            source="Dawn Business",
            source_type="financial_media",
            summary="Oil & Gas Development Company reports lower output",
            symbols='["OGDC"]',
            company_names='["Oil & Gas Development Company"]',
            sector="Oil & Gas",
            sentiment_label="negative",
            sentiment_score=-0.65,
            published_at=datetime.utcnow() - timedelta(days=5),
        ),
        NewsArticle(
            id=uuid4().hex,
            title="LUCK Cement Expands Capacity",
            url="https://example.com/luck-expansion",
            source="PSX",
            source_type="official",
            summary="Lucky Cement announces new plant",
            symbols='["LUCK"]',
            company_names='["Lucky Cement"]',
            sector="Cement",
            sentiment_label="positive",
            sentiment_score=0.72,
            published_at=datetime.utcnow() - timedelta(days=1),
        ),
    ]
    
    for article in articles:
        db_session.add(article)
    
    await db_session.flush()
    
    # Create sentiment results
    sentiment_results = [
        SentimentResult(
            id=uuid4().hex,
            news_article_id=articles[0].id,
            symbol="HBL",
            model_name="finbert_api",
            label="positive",
            score=0.85,
            positive_score=0.90,
            neutral_score=0.05,
            negative_score=0.05,
        ),
        SentimentResult(
            id=uuid4().hex,
            news_article_id=articles[1].id,
            symbol="OGDC",
            model_name="finbert_api",
            label="negative",
            score=-0.65,
            positive_score=0.10,
            neutral_score=0.25,
            negative_score=0.65,
        ),
        SentimentResult(
            id=uuid4().hex,
            news_article_id=articles[2].id,
            symbol="LUCK",
            model_name="finbert_api",
            label="positive",
            score=0.72,
            positive_score=0.80,
            neutral_score=0.15,
            negative_score=0.05,
        ),
    ]
    
    for sr in sentiment_results:
        db_session.add(sr)
    
    # Create sentiment aggregate
    aggregate = SentimentAggregate(
        id=uuid4().hex,
        symbol="HBL",
        period="7D",
        period_start=datetime.utcnow() - timedelta(days=7),
        period_end=datetime.utcnow(),
        overall_score=0.85,
        label="positive",
        article_count=1,
        positive_ratio=1.0,
        neutral_ratio=0.0,
        negative_ratio=0.0,
        trend="improving",
        daily_scores='[{"date": "2026-09-15", "score": 0.85, "count": 1}]',
        source_breakdown='{"news": 1}',
    )
    db_session.add(aggregate)
    
    await db_session.flush()
    
    return articles


class TestSentimentStock:
    """Tests for per-stock sentiment endpoint."""

    async def test_get_sentiment_with_data(self, client: AsyncClient, auth_headers, sample_news_with_sentiment):
        headers, user_id = auth_headers
        
        resp = await client.get("/api/v1/sentiment/HBL", headers=headers)
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "HBL"
        assert "score" in data
        assert "label" in data
        assert "article_count" in data

    async def test_get_sentiment_invalid_symbol(self, client: AsyncClient, auth_headers):
        headers, user_id = auth_headers
        
        resp = await client.get("/api/v1/sentiment/INVALID", headers=headers)
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "INVALID"
        assert data["article_count"] == 0
        assert data["label"] == "neutral"

    async def test_get_sentiment_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/sentiment/HBL")
        assert resp.status_code in (401, 403)

    async def test_get_sentiment_custom_days(self, client: AsyncClient, auth_headers):
        headers, user_id = auth_headers
        
        resp = await client.get("/api/v1/sentiment/HBL?days=30", headers=headers)
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "HBL"


class TestSentimentHistory:
    """Tests for sentiment history endpoint."""

    async def test_get_sentiment_history(self, client: AsyncClient, auth_headers, sample_news_with_sentiment):
        headers, user_id = auth_headers
        
        resp = await client.get("/api/v1/sentiment/HBL/history?period=1W", headers=headers)
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "HBL"
        assert data["period"] == "1W"
        assert "data" in data
        assert isinstance(data["data"], list)

    async def test_get_sentiment_history_empty(self, client: AsyncClient, auth_headers):
        headers, user_id = auth_headers
        
        resp = await client.get("/api/v1/sentiment/INVALID/history", headers=headers)
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "INVALID"
        assert data["data"] == []

    async def test_get_sentiment_history_invalid_period(self, client: AsyncClient, auth_headers):
        headers, user_id = auth_headers
        
        resp = await client.get("/api/v1/sentiment/HBL/history?period=INVALID", headers=headers)
        
        assert resp.status_code == 422

    async def test_get_sentiment_history_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/sentiment/HBL/history")
        assert resp.status_code in (401, 403)


class TestSentimentNews:
    """Tests for sentiment news endpoint."""

    async def test_get_sentiment_news(self, client: AsyncClient, auth_headers, sample_news_with_sentiment):
        headers, user_id = auth_headers
        
        resp = await client.get("/api/v1/sentiment/HBL/news", headers=headers)
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "HBL"
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "limit" in data
        assert isinstance(data["items"], list)
        
        if data["items"]:
            item = data["items"][0]
            assert "id" in item
            assert "title" in item
            assert "sentiment" in item

    async def test_get_sentiment_news_pagination(self, client: AsyncClient, auth_headers, sample_news_with_sentiment):
        headers, user_id = auth_headers
        
        resp = await client.get("/api/v1/sentiment/HBL/news?page=1&limit=5", headers=headers)
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["limit"] == 5

    async def test_get_sentiment_news_filter_by_sentiment(self, client: AsyncClient, auth_headers, sample_news_with_sentiment):
        headers, user_id = auth_headers
        
        resp = await client.get("/api/v1/sentiment/HBL/news?sentiment=POSITIVE", headers=headers)
        
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["sentiment"] == "positive"

    async def test_get_sentiment_news_filter_by_date(self, client: AsyncClient, auth_headers, sample_news_with_sentiment):
        headers, user_id = auth_headers
        
        from_date = (datetime.utcnow() - timedelta(days=3)).isoformat()[:10]
        resp = await client.get(f"/api/v1/sentiment/HBL/news?from_date={from_date}", headers=headers)
        
        assert resp.status_code == 200
        data = resp.json()

    async def test_get_sentiment_news_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/sentiment/HBL/news")
        assert resp.status_code in (401, 403)

    async def test_get_sentiment_news_invalid_sentiment(self, client: AsyncClient, auth_headers):
        headers, user_id = auth_headers
        
        resp = await client.get("/api/v1/sentiment/HBL/news?sentiment=INVALID", headers=headers)
        
        assert resp.status_code == 422


class TestMarketSentiment:
    """Tests for market sentiment endpoint."""

    async def test_get_market_sentiment(self, client: AsyncClient, auth_headers):
        headers, user_id = auth_headers
        
        resp = await client.get("/api/v1/sentiment/market-overview", headers=headers)
        
        assert resp.status_code == 200
        data = resp.json()
        assert "score" in data
        assert "label" in data
        assert "article_count" in data

    async def test_get_market_sentiment_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/sentiment/market-overview")
        assert resp.status_code in (401, 403)


# Need to import datetime and timedelta
from datetime import datetime, timedelta