"""SECP official source — regulatory / company filings.

Public page: https://www.secp.gov.pk/media-center/press-releases/

NOTE: SECP does not expose a structured news feed.  This adapter scrapes
the public news/notices page.  If SECP explicitly disallows scraping in the
future, this adapter should be disabled.
"""

import logging
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from app.services.news_pipeline.base import NormalizedArticle

log = logging.getLogger(__name__)

_BASE = "https://www.secp.gov.pk"
_NEWS_URL = f"{_BASE}/media-center/press-releases/"


def _parse_date(text: str | None) -> datetime | None:
    if not text:
        return None
    for fmt in ("%d-%b-%Y", "%d %b %Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text.strip(), fmt)
        except ValueError:
            continue
    return None


def fetch_articles(limit: int = 50) -> list[NormalizedArticle]:
    articles: list[NormalizedArticle] = []
    try:
        resp = httpx.get(_NEWS_URL, timeout=15, follow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        items = soup.select(".news-item, .list-item, article, .card")[:limit]
        for item in items:
            link_el = item.find("a")
            title = (link_el.get_text(strip=True) if link_el else item.get_text(strip=True))[:500]
            href = link_el.get("href", "") if link_el else ""
            url = href if href.startswith("http") else f"{_BASE}{href}" if href else _NEWS_URL
            date_el = item.find(class_=lambda c: c and ("date" in c.lower() if c else False))
            date_text = date_el.get_text(strip=True) if date_el else None
            summary_el = item.find("p") or item.find(class_=lambda c: c and ("desc" in c.lower() if c else False))
            summary = summary_el.get_text(strip=True) if summary_el else None

            if not title:
                continue

            articles.append(
                NormalizedArticle(
                    title=title,
                    url=url,
                    source="SECP",
                    source_key="secp",
                    source_type="official",
                    published_at=_parse_date(date_text),
                    summary=summary[:500] if summary else None,
                )
            )
    except Exception as exc:
        log.warning("SECP source fetch failed: %s", exc)

    return articles
