"""PSX official source — scrapes material information / corporate announcements.

robots.txt: https://www.psx.com.pk/robots.txt
  User-agent: *
  Disallow:            (empty — all paths allowed)

Public page: https://www.psx.com.pk/psx/announcement/financial-announcements
"""

import logging
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from app.services.news_pipeline.base import NormalizedArticle

log = logging.getLogger(__name__)

_BASE = "https://www.psx.com.pk"
_ANNOUNCEMENTS_URL = f"{_BASE}/psx/announcement/financial-announcements"


def _parse_date(text: str | None) -> datetime | None:
    if not text:
        return None
    for fmt in ("%d-%b-%Y", "%d %b %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text.strip(), fmt)
        except ValueError:
            continue
    return None


def fetch_articles(limit: int = 50) -> list[NormalizedArticle]:
    """Fetch recent PSX financial announcements."""
    articles: list[NormalizedArticle] = []
    try:
        resp = httpx.get(_ANNOUNCEMENTS_URL, timeout=15, follow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        rows = soup.select("table tbody tr")[:limit]
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 3:
                continue

            title_el = cols[1].find("a")
            title = (title_el.get_text(strip=True) if title_el else cols[1].get_text(strip=True)) or ""
            href = title_el.get("href", "") if title_el else ""
            url = href if href.startswith("http") else f"{_BASE}{href}" if href else _ANNOUNCEMENTS_URL
            date_text = cols[0].get_text(strip=True) if cols else None
            summary = cols[2].get_text(strip=True) if len(cols) > 2 else None

            if not title:
                continue

            articles.append(
                NormalizedArticle(
                    title=title,
                    url=url,
                    source="PSX",
                    source_type="official",
                    published_at=_parse_date(date_text),
                    summary=summary[:500] if summary else None,
                )
            )
    except Exception as exc:
        log.warning("PSX source fetch failed: %s", exc)

    return articles
