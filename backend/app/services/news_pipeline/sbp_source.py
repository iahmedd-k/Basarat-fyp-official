"""SBP official source — monetary policy, interest rates, FX data.

robots.txt: https://www.sbp.org.pk/robots.txt  (returned 403)
Public page: https://www.sbp.org.pk (publications / press releases)

NOTE: SBP returned 403 for robots.txt, which may indicate restricted access.
This adapter only accesses publicly visible press-release pages.  If SBP
explicitly blocks automated access, this adapter should be disabled.
"""

import logging
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from app.services.news_pipeline.base import NormalizedArticle

log = logging.getLogger(__name__)

_BASE = "https://www.sbp.org.pk"
_PRESS_URL = f"{_BASE}/press-release"
_NEWS_URL = f"https://archive.sbp.org.pk/press/{datetime.now().year}/index2.asp"


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
    for url in (_PRESS_URL, _NEWS_URL):
        try:
            resp = httpx.get(url, timeout=15, follow_redirects=True)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")

            items = soup.select("li a, .news-item a, table tbody tr")[:limit]
            for item in items:
                if item.name == "a":
                    title = item.get_text(strip=True)[:500]
                    href = item.get("href", "")
                else:
                    cols = item.find_all("td")
                    if len(cols) < 2:
                        continue
                    title = cols[1].get_text(strip=True)[:500] if cols[1] else ""
                    a = cols[1].find("a") if cols[1] else None
                    href = a.get("href", "") if a else ""

                if not title or len(title) < 5:
                    continue

                full_url = href if href.startswith("http") else f"{_BASE}{href}" if href else url

                date_el = item.find(class_=lambda c: c and ("date" in c.lower() if c else False)) if hasattr(item, "find") else None
                date_text = date_el.get_text(strip=True) if date_el else None

                articles.append(
                    NormalizedArticle(
                        title=title,
                        url=full_url,
                        source="SBP",
                        source_key="sbp",
                        source_type="official",
                        published_at=_parse_date(date_text),
                        summary=None,
                    )
                )
            if articles:
                break
        except Exception as exc:
            log.warning("SBP source fetch failed (%s): %s", url, exc)

    return articles[:limit]
