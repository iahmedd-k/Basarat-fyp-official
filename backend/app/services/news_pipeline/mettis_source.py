"""Mettis Global source — financial media.

robots.txt: https://mettisglobal.news/robots.txt
RSS: https://mettisglobal.news/feed/
"""

import logging
from datetime import datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.services.news_pipeline.base import NormalizedArticle

log = logging.getLogger(__name__)

_BASE = "https://mettisglobal.news"
_RSS_URL = f"{_BASE}/feed/"

# Keywords to filter for Pakistan finance relevance
_PAK_KEYWORDS = {
    "psx", "kse", "karachi stock", "pakistan", "sbp", "secp",
    "rupee", "pkr", "imf", "oil", "cement", "bank", "earnings",
    "dividend", "fertilizer", "textile", "telecom", "energy",
    "power", "gas", "oil and gas", "ogdc", "ssgc", "ubl", "hbl",
    "mcb", "abl", "nbp", "fml", "efert", "engro", "luck",
    "acpl", "dgkc", "fccl", "fatima", "fauji",
    "k electric", "kel", "hubco", "hub power", "lotte",
    "prl", "nrl", "byco", "attock", "mari", "ppl",
    "circular debt", "interest rate", "block order",
    "foreign buying", "foreign selling", "institutional",
    "earnings surprise", "monetary policy",
    "budget", "tax", "fbr", "fuel", "ogra",
}


def _parse_rfc822_date(text: str | None) -> datetime | None:
    if not text:
        return None
    for fmt in (
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            try:
                return datetime.strptime(text.strip(), fmt)
            except ValueError:
                continue
    return None


def _is_pakistan_finance(title: str, url: str) -> bool:
    text = f"{title} {url}".lower()
    return any(kw in text for kw in _PAK_KEYWORDS)


def fetch_articles(limit: int = 50) -> list[NormalizedArticle]:
    articles: list[NormalizedArticle] = []

    settings = get_settings()
    if not getattr(settings, "METTIS_FETCH_ENABLED", True):
        return []

    try:
        resp = httpx.get(_RSS_URL, timeout=15, follow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "xml")

        for item in soup.find_all("item")[:limit * 3]:
            title_el = item.find("title")
            link_el = item.find("link")
            pub_date_el = item.find("pubDate")
            desc_el = item.find("description") or item.find("summary")

            title = title_el.get_text(strip=True) if title_el else ""
            url = link_el.get_text(strip=True) if link_el else ""
            pub_date = _parse_rfc822_date(pub_date_el.get_text(strip=True) if pub_date_el else None)

            # Clean description for summary
            summary = None
            if desc_el:
                desc_soup = BeautifulSoup(desc_el.get_text(), "html.parser")
                summary = desc_soup.get_text(strip=True)[:500]

            if not title or not url:
                continue

            if not _is_pakistan_finance(title, url):
                continue

            articles.append(
                NormalizedArticle(
                    title=title[:500],
                    url=url,
                    source="Mettis Global",
                    source_key="mettis",
                    source_type="news",
                    published_at=pub_date,
                    summary=summary,
                    metadata={},
                )
            )
            if len(articles) >= limit:
                break

    except Exception as exc:
        log.warning("Mettis Global fetch failed: %s", exc)

    return articles[:limit]


# Need to import get_settings
from app.core.config import get_settings