from datetime import date
import logging

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import AppError, BadRequestError, ServiceUnavailableError
from app.core.rate_limiter import limiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.news import EventResponse, EventsCalendarResponse
from app.services.event_service import get_events

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/events/calendar",
    response_model=EventsCalendarResponse,
    summary="Get events calendar (earnings, dividends, SBP)",
)
@limiter.limit("60/minute")
async def get_events_calendar(
    request: Request,
    from_date: str | None = Query(None, alias="from", description="Start date (YYYY-MM-DD)"),
    to_date: str | None = Query(None, alias="to", description="End date (YYYY-MM-DD)"),
    event_type: str | None = Query(None, description="Filter by event type (earnings, dividend, sbp_monetary_policy)"),
    symbol: str | None = Query(None, description="Filter by PSX stock symbol (e.g. OGDC)"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve financial events calendar with multi-criteria filtering."""
    try:
        fd = None
        if from_date:
            try:
                fd = date.fromisoformat(from_date.strip())
            except ValueError:
                raise BadRequestError(f"Invalid 'from' date format '{from_date}'. Expected YYYY-MM-DD.")

        td = None
        if to_date:
            try:
                td = date.fromisoformat(to_date.strip())
            except ValueError:
                raise BadRequestError(f"Invalid 'to' date format '{to_date}'. Expected YYYY-MM-DD.")

        sym = symbol.strip().upper() if symbol else None
        etype = event_type.strip().lower() if event_type else None

        events = await get_events(db, from_date=fd, to_date=td, event_type=etype, symbol=sym)

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
    except AppError:
        raise
    except Exception as exc:
        logger.exception("Failed to fetch events calendar")
        raise ServiceUnavailableError(f"Failed to fetch events calendar: {exc}")
