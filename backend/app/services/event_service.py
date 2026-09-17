"""Event calendar service — ingestion and querying.

Ingests earnings, dividend, and SBP monetary policy events.
Normalises them into the MarketEvent model.
"""

import json
import logging
from datetime import date, datetime

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import MarketEvent
from app.models.news import NewsArticle

log = logging.getLogger(__name__)


async def upsert_event(
    db: AsyncSession,
    event_type: str,
    event_date: date,
    title: str,
    symbol: str | None = None,
    company_name: str | None = None,
    description: str | None = None,
    source: str | None = None,
    source_url: str | None = None,
    metadata: dict | None = None,
) -> MarketEvent:
    """Insert or update an event (dedup by type + date + symbol)."""
    existing = await db.execute(
        select(MarketEvent).where(
            and_(
                MarketEvent.event_type == event_type,
                MarketEvent.event_date == event_date,
                MarketEvent.symbol == symbol,
            )
        )
    )
    event = existing.scalars().first()

    if event:
        event.title = title
        event.description = description or event.description
        event.source = source or event.source
        event.source_url = source_url or event.source_url
        if metadata:
            event.metadata_json = json.dumps(metadata)
        event.updated_at = datetime.utcnow()
    else:
        event = MarketEvent(
            event_type=event_type,
            event_date=event_date,
            title=title,
            symbol=symbol,
            company_name=company_name,
            description=description,
            source=source,
            source_url=source_url,
            metadata_json=json.dumps(metadata) if metadata else None,
        )
        db.add(event)

    return event


async def get_events(
    db: AsyncSession,
    from_date: date | None = None,
    to_date: date | None = None,
    event_type: str | None = None,
    symbol: str | None = None,
) -> list[MarketEvent]:
    """Query events with optional filters."""
    query = select(MarketEvent)
    conditions = []
    if from_date:
        conditions.append(MarketEvent.event_date >= from_date)
    if to_date:
        conditions.append(MarketEvent.event_date <= to_date)
    if event_type:
        conditions.append(MarketEvent.event_type == event_type)
    if symbol:
        conditions.append(MarketEvent.symbol == symbol.upper())
    if conditions:
        query = query.where(and_(*conditions))
    query = query.order_by(MarketEvent.event_date.asc())

    result = await db.execute(query)
    return list(result.scalars().all())


async def extract_events_from_news(db: AsyncSession) -> int:
    """Scan recent news articles for event-like content and create calendar events.

    Looks for articles classified as earnings/dividend/interest_rate/monetary_policy
    that contain date references.
    """
    from app.services.news_pipeline.event_classifier import classify_event

    result = await db.execute(
        select(NewsArticle)
        .where(NewsArticle.event_type.in_(["earnings", "dividend", "interest_rate", "monetary_policy"]))
        .order_by(NewsArticle.published_at.desc())
        .limit(200)
    )
    articles = result.scalars().all()
    created = 0

    for article in articles:
        if not article.published_at:
            continue
        event_date = article.published_at.date()
        symbols = []
        if article.symbols:
            try:
                symbols = json.loads(article.symbols)
            except (json.JSONDecodeError, TypeError):
                pass

        if article.event_type in ("earnings", "dividend") and symbols:
            for sym in symbols[:3]:  # cap at 3 symbols per article
                await upsert_event(
                    db=db,
                    event_type=article.event_type,
                    event_date=event_date,
                    title=article.title[:500],
                    symbol=sym,
                    source=article.source,
                    source_url=article.url,
                )
                created += 1
        elif article.event_type in ("interest_rate", "monetary_policy"):
            await upsert_event(
                db=db,
                event_type="sbp_monetary_policy",
                event_date=event_date,
                title=article.title[:500],
                symbol=None,
                source=article.source,
                source_url=article.url,
            )
            created += 1

    if created:
        await db.commit()

    return created
