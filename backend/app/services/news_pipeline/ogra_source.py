"""OGRA (Oil & Gas Regulatory Authority) source — official.

robots.txt: https://www.ogra.org.pk/robots.txt
RSS: Check for RSS/Atom feed; fallback to news page.
Public page: https://www.ogra.org.pk/notifications/
"""

import logging
import re
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from app.services.news_pipeline.base import NormalizedArticle

log = logging.getLogger(__name__)

_BASE = "https://www.ogra.org.pk"
_NOTIFICATIONS_URL = f"{_BASE}/notifications/"

# Keywords to identify fuel price notifications and relevant notices
_OGRA_KEYWORDS = {
    "fuel", "petrol", "diesel", "kerosene", "lpg", "cng",
    "price", "revision", "notification", "gas", "tariff",
    "petroleum", "oil", "energy", "pricing",
}


def _parse_date(text: str | None) -> datetime | None:
    if not text:
        return None
    for fmt in ("%d-%b-%Y", "%d %b %Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text.strip(), fmt)
        except ValueError:
            continue
    return None


def _is_relevant(title: str, summary: str | None) -> bool:
    text = f"{title} {summary or ''}".lower()
    return any(kw in text for kw in _OGRA_KEYWORDS)


def fetch_articles(limit: int = 50) -> list[NormalizedArticle]:
    articles: list[NormalizedArticle] = []

    settings = get_settings()
    if not getattr(settings, "OGRA_FETCH_ENABLED", True):
        return []

    try:
        # Try RSS first if available
        rss_url = f"{_BASE}/feed/"
        resp = httpx.get(rss_url, timeout=10, follow_redirects=True)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "xml")
            items = soup.find_all("item")
        else:
            items = []
            resp = httpx.get(_NOTIFICATIONS_URL, timeout=15, follow_redirects=True)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            # Try to find notification items
            items = soup.find_all("article") or soup.find_all("div", class_=re.compile(r"notification|notice|item"))

        for item in items[:limit]:
            if item.name == "item":  # RSS
                title_el = item.find("title")
                link_el = item.find("link")
                pub_date_el = item.find("pubDate")
                desc_el = item.find("description")

                title = title_el.get_text(strip=True) if title_el else ""
                url = link_el.get_text(strip=True) if link_el else ""
                pub_date = _parse_date(pub_date_el.get_text(strip=True) if pub_date_el else None)
                summary = desc_el.get_text(strip=True)[:500] if desc_el else None
            else:  # HTML
                title_el = item.find("a") or item.find("h3") or item.find("h4")
                title = title_el.get_text(strip=True) if title_el else item.get_text(strip=True)[:500]
                href = title_el.get("href", "") if title_el and title_el.name == "a" else ""
                url = urljoin(_BASE, href) if href else _NOTIFICATIONS_URL
                date_el = item.find(class_=re.compile(r"date|time"))
                pub_date = _parse_date(date_el.get_text(strip=True) if date_el else None)
                summary_el = item.find("p") or item.find(class_=re.compile(r"desc|summary|excerpt"))
                summary = summary_el.get_text(strip=True)[:500] if summary_el else None

            if not title or len(title) < 5:
                continue

            if not _is_relevant(title, summary):
                continue

            articles.append(
                NormalizedArticle(
                    title=title[:500],
                    url=url,
                    source="OGRA",
                    source_key="ogra",
                    source_type="official",
                    published_at=pub_date,
                    summary=summary,
                    event_type="fuel_price" if any(kw in f"{title} {summary or ''}".lower() for kw in ["fuel", "petrol", "diesel", "price", "revision"]) else "regulatory",
                    metadata={},
                )
            )
            if len(articles) >= limit:
                break

    except Exception as exc:
        log.warning("OGRA fetch failed: %s", exc)

    return articles[:limit]


from app.core.config import get_settings
from urllib.parse import urljoin