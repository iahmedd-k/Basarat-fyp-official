import pytest
from httpx import AsyncClient
from datetime import date, timedelta
from app.models.event import MarketEvent

pytestmark = pytest.mark.asyncio


class TestEventsCalendarAPI:
    async def test_get_events_calendar_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/events/calendar")
        assert resp.status_code == 401

    async def test_get_events_calendar_empty(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/v1/events/calendar", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

    async def test_get_events_calendar_with_data(self, client: AsyncClient, auth_headers: dict, db_session):
        event = MarketEvent(
            event_type="earnings",
            event_date=date.today() + timedelta(days=5),
            title="OGDC Q3 Financial Results Announcement",
            symbol="OGDC",
            company_name="Oil & Gas Development Company Limited",
            description="Board of directors meeting for Q3 earnings.",
            source="PSX",
            source_url="https://dps.psx.com.pk",
        )
        db_session.add(event)
        await db_session.commit()

        resp = await client.get("/api/v1/events/calendar?symbol=OGDC", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert any(e["symbol"] == "OGDC" and e["event_type"] == "earnings" for e in data["items"])

    async def test_get_events_calendar_invalid_date_format(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/v1/events/calendar?from=not-a-date", headers=auth_headers)
        assert resp.status_code == 400
        data = resp.json()
        err_msg = data.get("error", {}).get("message", "") or data.get("detail", "")
        assert "Invalid 'from' date format" in err_msg

    async def test_get_events_calendar_invalid_range_from_after_to(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/v1/events/calendar?from=2026-12-31&to=2026-01-01", headers=auth_headers)
        assert resp.status_code == 400
        data = resp.json()
        err_msg = data.get("error", {}).get("message", "") or data.get("detail", "")
        assert "Start date ('from') cannot be after end date ('to')" in err_msg
