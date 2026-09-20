"""PSX official source — fetches company announcements from dps.psx.com.pk.

Request contract (captured from Chrome DevTools):
- POST https://dps.psx.com.pk/announcements
- Form fields: type (C=Companies, E=PSX Notices, etc.), symbol, query, date_from, date_to, count, offset
- Returns HTML table fragment with rows: date/time, symbol, company, title, document links
- Document PDFs: https://dps.psx.com.pk/download/document/{id}.pdf
"""

import logging
import re
import time
from datetime import datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.core.config import get_settings
from app.services.news_pipeline.base import NormalizedArticle, SourceChangedError, SourceDisabledError

log = logging.getLogger(__name__)

_BASE = "https://dps.psx.com.pk"
_ANNOUNCEMENTS_URL = f"{_BASE}/announcements"
_DOWNLOAD_BASE = f"{_BASE}/download/document/"

# Announcement type codes
_TYPE_COMPANIES = "C"      # Companies Announcements
_TYPE_PSX_NOTICES = "E"    # PSX Notices
_TYPE_CDC = "CDC"          # CDC Notices
_TYPE_SECP = "SECP"        # SECP Notices
_TYPE_NCCPL = "NCCPL"      # NCCPL Notices

_PKT_TZ = "Asia/Karachi"

# Circuit breaker state
_psx_consecutive_failures = 0
_psx_circuit_open_until = 0
_PSX_MAX_FAILURES = 5
_PSX_CIRCUIT_TIMEOUT = 1800  # 30 minutes
_psx_last_request_time = 0
_PSX_MIN_INTERVAL = 2.0  # seconds

_USER_AGENT = "Basarat/1.0 (+https://basarat.pk; marketdatarequest@psx.com.pk)"


def _circuit_check() -> None:
    """Check and update circuit breaker state."""
    global _psx_circuit_open_until
    now = time.time()
    if _psx_circuit_open_until and now < _psx_circuit_open_until:
        raise SourceDisabledError("PSX circuit breaker open")
    if _psx_circuit_open_until and now >= _psx_circuit_open_until:
        log.info("PSX circuit breaker reset")
        _psx_circuit_open_until = 0


def _record_failure() -> None:
    """Record a failure and potentially open the circuit breaker."""
    global _psx_consecutive_failures, _psx_circuit_open_until
    _psx_consecutive_failures += 1
    if _psx_consecutive_failures >= _PSX_MAX_FAILURES:
        _psx_circuit_open_until = time.time() + _PSX_CIRCUIT_TIMEOUT
        log.error("PSX circuit breaker opened after %d consecutive failures", _psx_consecutive_failures)


def _record_success() -> None:
    """Record a successful request."""
    global _psx_consecutive_failures
    _psx_consecutive_failures = 0


def _rate_limit() -> None:
    """Enforce minimum interval between PSX requests."""
    global _psx_last_request_time
    now = time.time()
    elapsed = now - _psx_last_request_time
    if elapsed < _PSX_MIN_INTERVAL:
        time.sleep(_PSX_MIN_INTERVAL - elapsed)
    _psx_last_request_time = time.time()


def _parse_pkt_datetime(date_str: str | None, time_str: str | None) -> tuple[datetime | None, bool]:
    """Parse PKT date/time strings to UTC datetime. Returns (datetime, estimated)."""
    if not date_str:
        return None, True

    date_str = date_str.strip()
    time_str = (time_str or "00:00").strip()

    # Try to parse date and time
    for date_fmt in ("%d-%b-%Y", "%d %b %Y", "%Y-%m-%d", "%d/%m/%Y"):
        for time_fmt in ("%H:%M", "%I:%M %p", "%H:%M:%S"):
            try:
                dt_str = f"{date_str} {time_str}"
                fmt = f"{date_fmt} {time_fmt}"
                dt = datetime.strptime(dt_str, fmt)
                # Assume PKT (UTC+5, no DST)
                from datetime import timezone, timedelta
                pkt = timezone(timedelta(hours=5))
                dt = dt.replace(tzinfo=pkt)
                # Convert to UTC
                return dt.astimezone(timezone.utc), False
            except ValueError:
                continue

    # If parsing fails, use current time
    log.warning("Failed to parse PSX date/time: %s %s", date_str, time_str)
    return datetime.now().astimezone(timezone.utc), True


def _extract_doc_id(href: str) -> str | None:
    """Extract document ID from PDF download link."""
    match = re.search(r"/download/document/(\d+)\.pdf", href, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def _build_summary(symbol: str, company: str, title: str) -> str:
    """Build a short summary from structured fields for PSX company announcements."""
    parts = []
    if company and symbol:
        parts.append(f"{company} ({symbol})")
    elif company:
        parts.append(company)
    elif symbol:
        parts.append(symbol)
    if title:
        parts.append(title)
    return ": ".join(parts)


def _parse_announcement_rows(soup: BeautifulSoup, announcement_type: str) -> list[NormalizedArticle]:
    """Parse announcement table rows from HTML."""
    articles: list[NormalizedArticle] = []

    # Find the table - look for table with announcement data
    tables = soup.find_all("table")
    if not tables:
        return articles

    # Usually the last table contains the data
    table = tables[-1]
    rows = table.find_all("tr")

    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 4:
            continue

        try:
            # Column structure typically: Date, Time, Symbol, Company, Title, Documents
            # But we need to be flexible - find by header text if possible
            date_text = cols[0].get_text(strip=True) if len(cols) > 0 else None
            time_text = cols[1].get_text(strip=True) if len(cols) > 1 else None
            symbol = cols[2].get_text(strip=True).upper() if len(cols) > 2 else None
            company = cols[3].get_text(strip=True) if len(cols) > 3 else None
            title = cols[4].get_text(strip=True) if len(cols) > 4 else None

            # Find document links
            doc_links = []
            for col in cols:
                for link in col.find_all("a", href=True):
                    href = link["href"]
                    if "download/document/" in href:
                        doc_links.append(href)

            if not title or not symbol:
                continue

            # Parse date/time
            published_at, estimated = _parse_pkt_datetime(date_text, time_text)

            # Get primary document URL
            external_id = None
            external_url = None
            if doc_links:
                primary_href = doc_links[0]
                external_id = _extract_doc_id(primary_href)
                external_url = urljoin(_BASE, primary_href) if not primary_href.startswith("http") else primary_href

            # If no document link, use a generated dedupe key and the announcements page as URL
            if not external_url:
                external_url = _ANNOUNCEMENTS_URL

            # Build summary
            summary = _build_summary(symbol, company or "", title)

            # Determine event type from title
            event_type = None
            title_lower = title.lower()
            if any(kw in title_lower for kw in ["result", "earning", "quarterly", "half year", "annual", "profit", "loss"]):
                event_type = "results"
            elif any(kw in title_lower for kw in ["dividend", "entitlement", "bonus"]):
                event_type = "dividend"
            elif any(kw in title_lower for kw in ["board", "bod", "meeting"]):
                event_type = "board_meeting"
            elif any(kw in title_lower for kw in ["merger", "acquisition", "amalgam"]):
                event_type = "merger_acquisition"
            else:
                event_type = "company_notice"

            articles.append(NormalizedArticle(
                title=title[:500],
                url=external_url,
                source="PSX",
                source_key="psx",
                source_type="official",
                external_id=external_id,
                external_url=external_url,
                published_at=published_at,
                published_at_estimated=estimated,
                summary=summary[:500] if summary else None,
                symbols=[symbol],
                company_names=[company] if company else [],
                event_type=event_type,
                metadata={"announcement_type": announcement_type}
            ))

        except Exception as exc:
            log.warning("Failed to parse PSX row: %s", exc)
            continue

    return articles


def fetch_companies_announcements(limit: int = 50) -> list[NormalizedArticle]:
    """Fetch Companies Announcements (type C)."""
    return _fetch_announcements(_TYPE_COMPANIES, limit)


def fetch_psx_notices(limit: int = 50) -> list[NormalizedArticle]:
    """Fetch PSX Notices (type E) - no symbol, appear in News row only."""
    return _fetch_announcements(_TYPE_PSX_NOTICES, limit)


def _fetch_announcements(announcement_type: str, limit: int) -> list[NormalizedArticle]:
    """Fetch announcements of a specific type from dps.psx.com.pk."""
    settings = get_settings()

    # Check kill switch
    if not getattr(settings, "PSX_FETCH_ENABLED", True):
        log.info("PSX fetch disabled via config")
        return []

    _circuit_check()
    _rate_limit()

    articles: list[NormalizedArticle] = []

    try:
        # Prepare form data
        form_data = {
            "type": announcement_type,
            "count": min(limit, 100),
            "offset": 0,
        }

        # For incremental fetch, we don't filter by symbol - get all and let pipeline dedupe
        # Date range: last few days to catch any missed
        from datetime import datetime, timedelta
        date_from = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        form_data["date_from"] = date_from

        headers = {"User-Agent": _USER_AGENT}

        resp = httpx.post(
            _ANNOUNCEMENTS_URL,
            data=form_data,
            headers=headers,
            timeout=20.0,
            follow_redirects=True,
        )
        resp.raise_for_status()

        # Check for maintenance/empty responses
        if "maintenance" in resp.text.lower() or "captcha" in resp.text.lower():
            raise SourceChangedError("PSX returned maintenance/captcha page")

        soup = BeautifulSoup(resp.text, "html.parser")

        # Check if we got a valid table
        tables = soup.find_all("table")
        if not tables:
            raise SourceChangedError("PSX response has no tables - layout may have changed")

        articles = _parse_announcement_rows(soup, announcement_type)
        articles = articles[:limit]

        _record_success()
        log.info("PSX %s: fetched %d articles", announcement_type, len(articles))

    except SourceChangedError:
        _record_failure()
        raise
    except httpx.HTTPStatusError as exc:
        _record_failure()
        if exc.response.status_code == 429:
            log.warning("PSX rate limited (429)")
        elif exc.response.status_code >= 500:
            log.warning("PSX server error: %s", exc)
        else:
            log.warning("PSX HTTP error: %s", exc)
    except httpx.TimeoutException:
        _record_failure()
        log.warning("PSX request timeout")
    except Exception as exc:
        _record_failure()
        log.warning("PSX fetch failed: %s", exc)

    return articles


def fetch_articles(limit: int = 50) -> list[NormalizedArticle]:
    """Main entry point - fetch both Companies Announcements and PSX Notices."""
    settings = get_settings()

    # Check kill switch
    if not getattr(settings, "PSX_FETCH_ENABLED", True):
        log.info("PSX fetch disabled via config")
        return []

    max_pages = getattr(settings, "PSX_MAX_PAGES_PER_RUN", 5)
    all_articles: list[NormalizedArticle] = []

    # Fetch Companies Announcements (have symbols - for Portfolio row)
    for page in range(max_pages):
        articles = fetch_companies_announcements(limit=50)
        if not articles:
            break
        all_articles.extend(articles)
        if len(articles) < 50:
            break  # Last page
        # Could add offset here for pagination

    # Fetch PSX Notices (no symbols - for News row only)
    for page in range(max_pages):
        articles = fetch_psx_notices(limit=50)
        if not articles:
            break
        all_articles.extend(articles)
        if len(articles) < 50:
            break

    return all_articles[:limit]