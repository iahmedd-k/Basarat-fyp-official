from datetime import date

from fastapi import APIRouter, Depends, Query

from app.core.authorization import get_current_user
from app.core.exceptions import ServiceUnavailableError
from app.models.user import User
from app.schemas.auth import EventResponse, EventsCalendarResponse

router = APIRouter()


@router.get(
    "/events/calendar",
    response_model=EventsCalendarResponse,
    summary="Get events calendar (earnings, dividends, SBP)",
)
async def get_events_calendar(
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    user: User = Depends(get_current_user),
):
    try:
        return EventsCalendarResponse(events=[])
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to fetch events calendar: {exc}")
