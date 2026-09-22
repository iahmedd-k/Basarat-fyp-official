"""Business Recorder source — financial media.

robots.txt: https://www.brecorder.com/robots.txt
  Disallows: /search, */print, /authors/*/1..9*
  Sitemap:   https://www.brecorder.com/feeds/sitemap

Strategy: Parse the sitemap XML which contains recent news articles with
<title>, <loc> (URL), and <lastmod> dates.  This avoids scraping HTML
and respects the site's structure.
"""

import logging
import re
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from app.services.news_pipeline.base import NormalizedArticle

log = logging.getLogger(__name__)

_SITEMAP_URL = "https://www.brecorder.com/feeds/sitemap"
_LATEST_NEWS_URL = "https://www.brecorder.com/latest-news"
_BASE = "https://www.brecorder.com"

# PSX / Pakistan finance keywords for filtering relevant articles
_PAK_KEYWORDS = {
    "psx", "kse", "karachi stock", "pakistan", "sbp", "secp",
    "rupee", "pkr", "imf", "oil", "cement", "bank", "earnings",
    "dividend", "fertilizer", "textile", "telecom", "energy",
    "power", "gas", "oil and gas", "ogdc", "ssc", "UBL", "HBL",
    "MCB", "ABL", "NBP", "FML", "EFERT", "ENGRO", "LUCK",
    "ACPL", "DGKC", "FCCL", "ARI", "Fatima", "Fauji",
    "k electric", "KEL", "HUBCO", "hub power", "LOTTE",
    "PRL", "NRL", "BYCO", "Attock", "mari", "PPL",
    "police", "serena", "systems", "netSol", "tech",
    "circular debt", "interest rate", "block order",
    "foreign buying", "foreign selling", "institutional",
    "earnings surprise", "monetary policy",
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


def _is_pakistan_finance(title: str, url: str) -> bool:
    """Quick keyword filter to keep only PSX/Pakistan-finance articles."""
    text = f"{title} {url}".lower()
    return any(kw in text for kw in _PAK_KEYWORDS)


def fetch_articles(limit: int = 50) -> list[NormalizedArticle]:
    articles: list[NormalizedArticle] = []

    # Strategy 1: parse the news sitemap (structured, reliable)
    try:
        resp = httpx.get(_SITEMAP_URL, timeout=15, follow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "xml")

        for url_el in soup.find_all("url")[:limit * 3]:  # over-fetch then filter
            loc = url_el.find("loc")
            lastmod = url_el.find("lastmod")
            news_title_el = url_el.find("news:title") or url_el.find("title")

            if not loc:
                continue

            url = loc.get_text(strip=True)
            title = news_title_el.get_text(strip=True) if news_title_el else url.split("/")[-1].replace("-", " ").title()
            pub_date = _parse_iso_date(lastmod.get_text(strip=True) if lastmod else None)

            if _is_pakistan_finance(title, url):
                articles.append(
                    NormalizedArticle(
                        title=title,
                        url=url,
                        source="Business Recorder",
                        source_key="business_recorder",
                        source_type="news",
                        published_at=pub_date,
                        summary=None,
                    )
                )
                if len(articles) >= limit:
                    break
    except Exception as exc:
        log.warning("Business Recorder sitemap fetch failed: %s", exc)

    # Strategy 2: if sitemap failed, try the latest-news page
    if not articles:
        try:
            resp = httpx.get(_LATEST_NEWS_URL, timeout=15, follow_redirects=True)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            for card in soup.select("article, .news-card, .card")[:limit * 2]:
                link_el = card.find("a")
                if not link_el:
                    continue
                title = link_el.get_text(strip=True)[:500]
                href = link_el.get("href", "")
                url = href if href.startswith("http") else f"{_BASE}{href}"

                if not title or not _is_pakistan_finance(title, url):
                    continue

                articles.append(
                    NormalizedArticle(
                        title=title,
                        url=url,
                        source="Business Recorder",
                        source_key="business_recorder",
                        source_type="news",
                        published_at=None,
                        summary=None,
                    )
                )
                if len(articles) >= limit:
                    break
        except Exception as exc:
            log.warning("Business Recorder latest-news fetch failed: %s", exc)

    return articles[:limit]
