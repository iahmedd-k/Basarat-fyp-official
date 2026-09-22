"""FBR / Finance Ministry (MoF) source — official.

robots.txt: Check https://www.fbr.gov.pk/robots.txt and https://www.finance.gov.pk/robots.txt
RSS: Check for feeds
Public pages:
  - FBR: https://www.fbr.gov.pk/notifications
  - MoF: https://www.finance.gov.pk/press_releases.html

Keyword filter: budget, SRO, sales tax, super tax, capital gains, duty, IMF, fiscal, monetary
Drop: routine notices, filing deadlines, enforcement drives
"""

import logging
import re
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from app.services.news_pipeline.base import NormalizedArticle

log = logging.getLogger(__name__)

_FBR_BASE = "https://www.fbr.gov.pk"
_FBR_NOTIFICATIONS = f"{_FBR_BASE}/notifications"

_MOF_BASE = "https://www.finance.gov.pk"
_MOF_PRESS = f"{_MOF_BASE}/press_releases.html"

# Keywords to keep (Pakistan fiscal/monetary policy relevance)
_KEEP_KEYWORDS = {
    "budget", "sro", "sales tax", "super tax", "capital gains",
    "duty", "imf", "fiscal", "monetary", "tax", "revenue",
    "customs", "excise", "income tax", "withholding", "gst",
    "federal excise", "policy rate", "interest rate",
    "finance bill", "money bill", "ordinance", "act",
}

# Keywords to drop (routine/operational)
_DROP_KEYWORDS = {
    "deadline", "extension", "filing", "return", "audit",
    "enforcement", "recovery", "notice", "show cause",
    "penalty", "prosecution", "raid", "seizure", "arrest",
    "last date", "due date", "extended", "reminder",
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


def _should_keep(title: str, summary: str | None) -> bool:
    text = f"{title} {summary or ''}".lower()

    # Must have at least one keep keyword
    if not any(kw in text for kw in _KEEP_KEYWORDS):
        return False

    # Must NOT have drop keywords (unless it also has a strong keep keyword)
    strong_keep = {"budget", "imf", "capital gains", "super tax", "sro", "finance bill"}
    if any(kw in text for kw in _DROP_KEYWORDS) and not any(kw in text for kw in strong_keep):
        return False

    return True


def _fetch_from_source(base_url: str, list_url: str, source_name: str, limit: int) -> list[NormalizedArticle]:
    articles: list[NormalizedArticle] = []

    try:
        # Try RSS first
        rss_url = f"{base_url}/feed/"
        resp = httpx.get(rss_url, timeout=10, follow_redirects=True)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "xml")
            items = soup.find_all("item")
            for item in items[:limit * 2]:
                title_el = item.find("title")
                link_el = item.find("link")
                pub_date_el = item.find("pubDate")
                desc_el = item.find("description")

                title = title_el.get_text(strip=True) if title_el else ""
                url = link_el.get_text(strip=True) if link_el else ""
                pub_date = _parse_date(pub_date_el.get_text(strip=True) if pub_date_el else None)
                summary = desc_el.get_text(strip=True)[:500] if desc_el else None

                if _should_keep(title, summary):
                    articles.append(NormalizedArticle(
                        title=title[:500],
                        url=url,
                        source=source_name,
                        source_key=source_name.lower().replace(" ", "_").replace("/", "_"),
                        source_type="official",
                        published_at=pub_date,
                        summary=summary,
                        event_type="budget_tax" if "budget" in f"{title} {summary or ''}".lower() else "regulatory",
                        metadata={},
                    ))
                    if len(articles) >= limit:
                        return articles

        # Fallback to HTML scraping
        resp = httpx.get(list_url, timeout=15, follow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Find notification items
        items = soup.find_all("article") or soup.find_all("div", class_=re.compile(r"notification|notice|item|post|news"))
        if not items:
            # Try table rows
            items = soup.find_all("tr")

        for item in items[:limit * 2]:
            title_el = item.find("a") or item.find("h3") or item.find("h4") or item.find(class_=re.compile(r"title"))
            title = title_el.get_text(strip=True) if title_el else item.get_text(strip=True)[:500]
            href = title_el.get("href", "") if title_el and title_el.name == "a" else ""
            url = urljoin(base_url, href) if href else list_url

            date_el = item.find(class_=re.compile(r"date|time"))
            pub_date = _parse_date(date_el.get_text(strip=True) if date_el else None)

            summary_el = item.find("p") or item.find(class_=re.compile(r"desc|summary|excerpt|content"))
            summary = summary_el.get_text(strip=True)[:500] if summary_el else None

            if not title or len(title) < 5:
                continue

            if not _should_keep(title, summary):
                continue

            articles.append(NormalizedArticle(
                title=title[:500],
                url=url,
                source=source_name,
                source_key=source_name.lower().replace(" ", "_").replace("/", "_"),
                source_type="official",
                published_at=pub_date,
                summary=summary,
                event_type="budget_tax" if "budget" in f"{title} {summary or ''}".lower() else "regulatory",
                metadata={},
            ))
            if len(articles) >= limit:
                break

    except Exception as exc:
        log.warning("%s fetch failed: %s", source_name, exc)

    return articles[:limit]


def fetch_articles(limit: int = 50) -> list[NormalizedArticle]:
    settings = get_settings()
    if not getattr(settings, "FBR_MOF_FETCH_ENABLED", True):
        return []

    all_articles: list[NormalizedArticle] = []

    # Fetch from FBR
    fbr_articles = _fetch_from_source(_FBR_BASE, _FBR_NOTIFICATIONS, "FBR", limit // 2)
    all_articles.extend(fbr_articles)

    # Fetch from MoF
    remaining = limit - len(all_articles)
    if remaining > 0:
        mof_articles = _fetch_from_source(_MOF_BASE, _MOF_PRESS, "Finance Ministry", remaining)
        all_articles.extend(mof_articles)

    return all_articles[:limit]


from app.core.config import get_settings
from urllib.parse import urljoin
