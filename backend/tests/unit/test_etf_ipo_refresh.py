from datetime import date
from types import SimpleNamespace

import pytest

from app.tasks import refresh_etf_ipo


def test_parse_psx_etf_symbols_filters_psx_etf_sector():
    html = """
    <table>
      <tr><th>Symbol</th><th>Sector</th></tr>
      <tr><td>MIIETF</td><td>0837</td></tr>
      <tr><td>OGDC</td><td>0820</td></tr>
      <tr><td>UBLPEtf</td><td>0837</td></tr>
    </table>
    """

    assert refresh_etf_ipo.parse_psx_etf_symbols(html) == ["MIIETF", "UBLPETF"]


def test_parse_psx_etf_symbols_rejects_missing_source_data():
    with pytest.raises(ValueError, match="no ETFs"):
        refresh_etf_ipo.parse_psx_etf_symbols(
            "<table><tr><th>Symbol</th><th>Sector</th></tr></table>"
        )


def test_parse_psx_ipo_dates_parses_official_columns_and_empty_table():
    html = """
    <h1>IPO DATES</h1>
    <table>
      <tr><th>Start Date</th><th>End Date</th><th>Security Code</th>
          <th>Security Name</th></tr>
      <tr><td>14-Oct-2026</td><td>15-Oct-2026</td><td>GTECH</td>
          <td>Green Technology Solutions Limited</td></tr>
    </table>
    """

    assert refresh_etf_ipo.parse_psx_ipo_dates(html) == [
        {
            "symbol": "GTECH",
            "company_name": "Green Technology Solutions Limited",
            "subscription_start": date(2026, 10, 14),
            "subscription_end": date(2026, 10, 15),
        }
    ]
    assert refresh_etf_ipo.parse_psx_ipo_dates(
        "<table><tr><th>Start Date</th><th>End Date</th>"
        "<th>Security Code</th><th>Security Name</th></tr></table>"
    ) == []


@pytest.mark.asyncio
async def test_persist_commits_before_invalidating_redis(monkeypatch):
    events = []
    etf = SimpleNamespace(symbol="MIIETF", is_active=False)
    ipo = SimpleNamespace(
        symbol="GTECH",
        company_name="Old Name",
        status="UPCOMING",
        public_subscription_start=None,
        public_subscription_end=None,
    )

    class Result:
        def __init__(self, rows):
            self.rows = rows

        def scalars(self):
            return self

        def all(self):
            return self.rows

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def execute(self, statement):
            entity = statement.column_descriptions[0]["entity"]
            return Result([etf] if entity.__name__ == "ETF" else [ipo])

        async def commit(self):
            events.append("commit")

    async def invalidate(pattern):
        events.append(("invalidate", pattern))

    monkeypatch.setattr(refresh_etf_ipo, "async_session_factory", FakeSession)
    monkeypatch.setattr(refresh_etf_ipo, "cache_invalidate_pattern", invalidate)

    result = await refresh_etf_ipo._persist_catalogs(
        ["MIIETF"],
        [
            {
                "symbol": "GTECH",
                "company_name": "Green Technology Solutions Limited",
                "subscription_start": date(2026, 10, 14),
                "subscription_end": date(2026, 10, 15),
            }
        ],
    )

    assert etf.is_active is True
    assert ipo.company_name == "Green Technology Solutions Limited"
    assert result == {"etfs_updated": 1, "ipos_updated": 1}
    assert events[0] == "commit"
    assert all(event[0] == "invalidate" for event in events[1:])


def test_celery_schedule_refreshes_during_market_day_window():
    from app.celery_app import celery

    schedule = celery.conf.beat_schedule["refresh-etf-ipo-catalogs"]["schedule"]
    assert schedule.minute == {10}
    assert schedule.hour == {9, 16}
    assert schedule.day_of_week == {1, 2, 3, 4, 5}
