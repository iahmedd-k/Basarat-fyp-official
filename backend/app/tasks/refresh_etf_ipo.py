"""Refresh PSX ETF and IPO catalogs during configured market hours."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import date, datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select

from app.celery_app import celery
from app.core.redis import cache_invalidate_pattern, get_sync_redis_client
from app.db.session import async_session_factory
from app.models.etf import ETF
from app.models.ipo import IPO

log = logging.getLogger(__name__)

PSX_SCREENER_URL = "https://dps.psx.com.pk/screener"
PSX_EIPO_URL = "https://eipo.psx.com.pk/EIPO/home/index"
LOCK_KEY = "jobs:etf-ipo-refresh:lock"
PKT = ZoneInfo("Asia/Karachi")
ETF_CACHE_PATTERNS = ("etf:list:v1:*", "etf:detail:v1:*")
IPO_CACHE_PATTERNS = (
    "ipo:list:v1:*",
    "ipo:detail:v1:*",
    "ipo:calendar:v1",
    "ipo:performance:v1",
)


def _table_rows(
    table: BeautifulSoup,
    required_headers: tuple[str, ...],
) -> tuple[dict[str, int], list[list[str]]]:
    headers = [
        cell.get_text(" ", strip=True).casefold()
        for cell in table.find_all("th")
    ]
    if not headers or any(header not in headers for header in required_headers):
        raise ValueError(f"PSX table is missing expected columns: {required_headers}")

    header_indexes = {header: headers.index(header) for header in required_headers}
    rows = [
        [cell.get_text(" ", strip=True) for cell in row.find_all(["td", "th"])]
        for row in table.find_all("tr")
        if row.find("td")
    ]
    return header_indexes, rows


def parse_psx_etf_symbols(html: str) -> list[str]:
    """Return ETF symbols identified by PSX screener sector code 0837."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        raise ValueError("PSX screener response contains no table")

    indexes, rows = _table_rows(table, ("symbol", "sector"))
    symbols = []
    for row in rows:
        if len(row) <= max(indexes.values()):
            continue
        symbol = row[indexes["symbol"]].strip().upper()
        sector = row[indexes["sector"]].strip()
        if sector == "0837" and re.fullmatch(r"[A-Z0-9.]{1,20}", symbol):
            symbols.append(symbol)

    if not symbols:
        raise ValueError("PSX screener returned no ETFs in sector 0837")
    return sorted(set(symbols))


def _parse_psx_date(value: str) -> date:
    for date_format in ("%d-%b-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(value.strip(), date_format).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognized PSX eIPO date: {value!r}")


def parse_psx_ipo_dates(html: str) -> list[dict[str, object]]:
    """Parse the official PSX eIPO page's public subscription date table."""
    soup = BeautifulSoup(html, "html.parser")
    table = next(
        (
            candidate
            for candidate in soup.find_all("table")
            if all(
                header in [
                    cell.get_text(" ", strip=True).casefold()
                    for cell in candidate.find_all("th")
                ]
                for header in ("start date", "end date", "security code", "security name")
            )
        ),
        None,
    )
    if table is None:
        raise ValueError("PSX eIPO response contains no IPO Dates table")

    indexes, rows = _table_rows(
        table,
        ("start date", "end date", "security code", "security name"),
    )
    ipos: list[dict[str, object]] = []
    for row in rows:
        if len(row) <= max(indexes.values()):
            raise ValueError("PSX eIPO table contains an incomplete row")

        symbol = row[indexes["security code"]].strip().upper()
        company_name = row[indexes["security name"]].strip()
        if not re.fullmatch(r"[A-Z0-9.]{1,20}", symbol) or not company_name:
            raise ValueError("PSX eIPO table contains an invalid security identity")

        ipos.append(
            {
                "symbol": symbol,
                "company_name": company_name,
                "subscription_start": _parse_psx_date(row[indexes["start date"]]),
                "subscription_end": _parse_psx_date(row[indexes["end date"]]),
            }
        )
    return ipos


async def _fetch_official_catalogs() -> tuple[list[str], list[dict[str, object]]]:
    headers = {"User-Agent": "Basarat/1.0 (+https://basarat.pk)"}
    async with httpx.AsyncClient(
        timeout=20.0,
        follow_redirects=True,
        headers=headers,
    ) as client:
        etf_response, ipo_response = await asyncio.gather(
            client.get(PSX_SCREENER_URL),
            client.get(PSX_EIPO_URL),
        )
    etf_response.raise_for_status()
    ipo_response.raise_for_status()
    return (
        parse_psx_etf_symbols(etf_response.text),
        parse_psx_ipo_dates(ipo_response.text),
    )


def _ipo_status(start: date, end: date, today: date) -> str:
    if today < start:
        return "UPCOMING"
    if today <= end:
        return "OPEN_FOR_PUBLIC_SUBSCRIPTION"
    return "CLOSED"


async def _persist_catalogs(
    etf_symbols: list[str],
    ipo_dates: list[dict[str, object]],
) -> dict[str, int]:
    async with async_session_factory() as db:
        etf_result = await db.execute(select(ETF))
        etfs_by_symbol = {row.symbol.upper(): row for row in etf_result.scalars().all()}
        ipo_result = await db.execute(select(IPO))
        ipos_by_symbol = {row.symbol.upper(): row for row in ipo_result.scalars().all()}

        etf_updated = 0
        for symbol in etf_symbols:
            etf = etfs_by_symbol.get(symbol)
            if etf is None:
                log.warning(
                    "PSX screener found ETF %s without the additional fund metadata "
                    "required by the ETF catalog; leaving it uninserted",
                    symbol,
                )
                continue
            if not etf.is_active:
                etf.is_active = True
                etf_updated += 1

        today = datetime.now(PKT).date()
        ipo_updated = 0
        for item in ipo_dates:
            symbol = str(item["symbol"])
            start = item["subscription_start"]
            end = item["subscription_end"]
            if not isinstance(start, date) or not isinstance(end, date):
                raise TypeError(f"Invalid subscription dates for PSX IPO {symbol}")
            if end < start:
                raise ValueError(f"PSX IPO {symbol} ends before its start date")

            ipo = ipos_by_symbol.get(symbol)
            if ipo is None:
                ipo = IPO(
                    symbol=symbol,
                    company_name=str(item["company_name"]),
                    sector="Not specified by PSX eIPO",
                    status=_ipo_status(start, end, today),
                    is_shariah_compliant=False,
                )
                db.add(ipo)
                ipos_by_symbol[symbol] = ipo
                ipo_updated += 1
                continue

            changed = (
                ipo.company_name != item["company_name"]
                or ipo.public_subscription_start != start
                or ipo.public_subscription_end != end
            )
            ipo.company_name = str(item["company_name"])
            ipo.public_subscription_start = start
            ipo.public_subscription_end = end
            if ipo.status != "LISTED":
                ipo.status = _ipo_status(start, end, today)
            if changed:
                ipo_updated += 1

        await db.commit()

    # Commit first so a cache miss can only repopulate from persisted data.
    for pattern in (*ETF_CACHE_PATTERNS, *IPO_CACHE_PATTERNS):
        await cache_invalidate_pattern(pattern)

    return {"etfs_updated": etf_updated, "ipos_updated": ipo_updated}


async def _refresh_during_market_hours() -> dict[str, object]:
    from app.services.news_pipeline.market_schedule import is_market_hours
    from app.db.session import async_session_factory
    from app.services.ipo_service import IPOService

    if not await is_market_hours():
        return {"status": "skipped", "reason": "outside_market_hours"}

    etf_symbols, ipo_dates = await _fetch_official_catalogs()
    counts = await _persist_catalogs(etf_symbols, ipo_dates)

    # Precompute IPO calendar and performance after catalog updates
    try:
        async with async_session_factory() as db:
            ipo_service = IPOService(db)
            await ipo_service.precompute_calendar()
            await ipo_service.precompute_performance()
    except Exception as exc:
        log.warning("Failed to precompute IPO calendar/performance: %s", exc)

    result = {
        "status": "completed",
        "etf_symbols_seen": len(etf_symbols),
        "ipo_dates_seen": len(ipo_dates),
        **counts,
    }
    log.info("PSX ETF/IPO catalog refresh completed: %s", result)
    return result


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _release_lock(client, token: str) -> None:
    client.eval(
        "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end",
        1,
        LOCK_KEY,
        token,
    )


@celery.task(
    name="app.tasks.refresh_etf_ipo.refresh_etf_ipo_catalogs",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    acks_late=True,
)
def refresh_etf_ipo_catalogs(self):
    client = get_sync_redis_client()
    if client is None:
        log.error("Skipping ETF/IPO refresh because Redis is unavailable")
        return {"status": "blocked", "reason": "redis_unavailable"}

    token = uuid4().hex
    try:
        if not client.set(LOCK_KEY, token, nx=True, ex=1800):
            log.info("Skipping ETF/IPO refresh; another refresh is already running")
            return {"status": "skipped", "reason": "already_running"}
    except Exception as exc:
        log.exception("Could not acquire ETF/IPO refresh lock")
        raise self.retry(exc=exc)

    try:
        return _run_async(_refresh_during_market_hours())
    except Exception as exc:
        log.exception("PSX ETF/IPO catalog refresh failed")
        raise self.retry(exc=exc)
    finally:
        try:
            _release_lock(client, token)
        except Exception:
            log.exception("Could not release ETF/IPO refresh lock")
