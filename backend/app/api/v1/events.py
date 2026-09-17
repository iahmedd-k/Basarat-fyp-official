from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import ServiceUnavailableError
from app.db.session import get_db
from app.models.user import User
from app.schemas.news import EventResponse, EventsCalendarResponse
from app.services.event_service import get_events

router = APIRouter()


@router.get(
    "/events/calendar",
    response_model=EventsCalendarResponse,
    summary="Get events calendar (earnings, dividends, SBP)",
)
async def get_events_calendar(
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    event_type: str | None = Query(None, description="Filter by event type"),
    symbol: str | None = Query(None, description="Filter by PSX symbol"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        fd = date.fromisoformat(from_date) if from_date else None
        td = date.fromisoformat(to_date) if to_date else None

        events = await get_events(db, from_date=fd, to_date=td, event_type=event_type, symbol=symbol)

        items = [
            EventResponse(
                id=e.id,
                event_type=e.event_type,
                symbol=e.symbol,
                company_name=e.company_name,
                event_date=e.event_date.isoformat(),
                title=e.title,
                description=e.description,
                source=e.source,
                source_url=e.source_url,
            )
            for e in events
        ]

        return EventsCalendarResponse(items=items, total=len(items))
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to fetch events calendar: {exc}")
