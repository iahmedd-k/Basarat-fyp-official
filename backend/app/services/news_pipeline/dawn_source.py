"""Dawn Business source — financial media.

robots.txt: https://www.dawn.com/robots.txt
  Disallows: /archive/*, /search, /obituary, */print
  Sitemap:   https://www.dawn.com/feeds/sitemap

Strategy: Parse the sitemap XML for recent articles, then filter
for Pakistan/business/finance relevance.
"""

import logging
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from app.services.news_pipeline.base import NormalizedArticle

log = logging.getLogger(__name__)

_SITEMAP_URL = "https://www.dawn.com/feeds/sitemap"
_BASE = "https://www.dawn.com"

_BUSINESS_KEYWORDS = {
    "psx", "kse", "karachi stock", "pakistan", "sbp", "secp",
    "rupee", "pkr", "imf", "oil", "cement", "bank", "earnings",
    "dividend", "market", "stock", "trading", "invest",
    "economy", "gdp", "inflation", "interest rate", "monetary",
    "fiscal", "budget", "tax", "revenue", "profit", "loss",
    "business", "finance", "corporate", "company", "sector",
    "circular debt", "block order", "foreign buying",
    "foreign selling", "institutional", "interest rate",
    "monetary", "earnings",
}


def _parse_iso_date(text: str | None) -> datetime | None:
    if not text:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.fromisoformat(text.strip())
        except ValueError:
            continue
    return None


def _is_business_relevant(title: str, url: str) -> bool:
    text = f"{title} {url}".lower()
    return any(kw in text for kw in _BUSINESS_KEYWORDS)


def fetch_articles(limit: int = 50) -> list[NormalizedArticle]:
    articles: list[NormalizedArticle] = []

    # Strategy 1: sitemap
    try:
        resp = httpx.get(_SITEMAP_URL, timeout=15, follow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "xml")

        for url_el in soup.find_all("url")[:limit * 3]:
            loc = url_el.find("loc")
            lastmod = url_el.find("lastmod")
            news_title_el = url_el.find("news:title") or url_el.find("title")

            if not loc:
                continue

            url = loc.get_text(strip=True)
            title = news_title_el.get_text(strip=True) if news_title_el else url.split("/")[-1].replace("-", " ").title()
            pub_date = _parse_iso_date(lastmod.get_text(strip=True) if lastmod else None)

            # Skip archived / non-business articles
            if "/archive/" in url or "/obituary" in url:
                continue

            if _is_business_relevant(title, url):
                articles.append(
                    NormalizedArticle(
                        title=title,
                        url=url,
                        source="Dawn Business",
                        source_key="dawn",
                        source_type="news",
                        published_at=pub_date,
                        summary=None,
                    )
                )
                if len(articles) >= limit:
                    break
    except Exception as exc:
        log.warning("Dawn sitemap fetch failed: %s", exc)

    return articles[:limit]
