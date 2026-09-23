"""PSX Company Announcements Service.

Fetches, parses, caches (Redis 15m TTL), and stores official company announcements
from the PSX DPS portal (https://dps.psx.com.pk/announcements/companies).
"""

import asyncio
import json
import logging
import re
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select, or_, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import cache_get, cache_set
from app.models.news import NewsArticle, NewsArticleSymbol

log = logging.getLogger(__name__)

PSX_BASE_URL = "https://dps.psx.com.pk"
PSX_ANNOUNCEMENTS_POST_URL = f"{PSX_BASE_URL}/announcements"
PSX_COMPANIES_PAGE_URL = f"{PSX_BASE_URL}/announcements/companies"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
CACHE_TTL_SECONDS = 900  # 15 minutes


def _classify_event_type(title: str) -> str:
    """Classify announcement title into structured event category."""
    t = (title or "").lower()
    if any(k in t for k in ["financial result", "financial statement", "profit after tax", "eps", "q1", "q2", "q3", "half year", "annual account"]):
        return "earnings"
    if any(k in t for k in ["dividend", "bonus share", "book closure", "right share", "payout"]):
        return "dividend"
    if any(k in t for k in ["board meeting", "closed period", "meeting of the board"]):
        return "board_meeting"
    if any(k in t for k in ["material information", "discovery", "hydrocarbon", "contract", "agreement", "commissioning", "acquisition"]):
        return "material_information"
    if any(k in t for k in ["agm", "egm", "general meeting", "notice of meeting"]):
        return "general_meeting"
    if any(k in t for k in ["credit of shares", "transmission", "unclaimed"]):
        return "shareholding"
    return "other"


def _estimate_sentiment(title: str, event_type: str) -> dict:
    """Rule-based sentiment classification for official PSX notices."""
    t = (title or "").lower()
    if any(k in t for k in ["profit up", "highest ever", "growth", "dividend", "bonus", "discovery", "secures", "win", "expansion"]):
        return {"label": "bullish", "score": 0.80, "method": "eps_rule"}
    if any(k in t for k in ["loss", "profit down", "shutdown", "decline", "penalty", "default"]):
        return {"label": "bearish", "score": -0.80, "method": "eps_rule"}
    if event_type in ("earnings", "dividend", "material_information"):
        return {"label": "bullish", "score": 0.50, "method": "eps_rule"}
    return {"label": "neutral", "score": 0.0, "method": "eps_rule"}


def _parse_pkt_datetime(date_str: str | None, time_str: str | None) -> str:
    """Parse PKT date string into ISO UTC string."""
    if not date_str:
        return datetime.now(timezone.utc).isoformat()

    date_str = date_str.strip()
    time_str = (time_str or "00:00").strip()
    pkt = timezone(timedelta(hours=5))

    for date_fmt in ("%b %d, %Y", "%d-%b-%Y", "%d %b %Y", "%Y-%m-%d", "%d/%m/%Y"):
        for time_fmt in ("%I:%M %p", "%H:%M", "%H:%M:%S"):
            try:
                dt_str = f"{date_str} {time_str}"
                fmt = f"{date_fmt} {time_fmt}"
                dt = datetime.strptime(dt_str, fmt)
                dt = dt.replace(tzinfo=pkt)
                return dt.astimezone(timezone.utc).isoformat()
            except ValueError:
                continue

    try:
        dt = datetime.strptime(date_str, "%b %d, %Y").replace(tzinfo=pkt)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()


async def fetch_psx_announcements(symbol: Optional[str] = None, count: int = 20) -> List[Dict[str, Any]]:
    """Fetch live company announcements directly from PSX DPS portal."""
    payload = {
        "type": "C",  # Companies announcements
        "count": str(count),
    }
    if symbol:
        payload["symbol"] = symbol.strip().upper()

    headers = {
        "User-Agent": USER_AGENT,
        "Referer": PSX_COMPANIES_PAGE_URL,
        "Origin": PSX_BASE_URL,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(PSX_ANNOUNCEMENTS_POST_URL, data=payload, headers=headers)
            if resp.status_code != 200 or not resp.text:
                log.warning("PSX DPS returned status %s for symbol %s", resp.status_code, symbol)
                return []

        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.find_all("tr")
        if not rows:
            return []

        announcements = []
        for row in rows:
            cols = row.find_all(["td", "th"])
            if len(cols) < 5:
                continue

            # Header check
            if cols[0].get_text(strip=True).upper() == "DATE":
                continue

            date_val = cols[0].get_text(strip=True) if len(cols) > 0 else ""
            time_val = cols[1].get_text(strip=True) if len(cols) > 1 else ""
            sym_val = cols[2].get_text(strip=True).upper() if len(cols) > 2 else (symbol or "")
            comp_name = cols[3].get_text(strip=True) if len(cols) > 3 else ""
            title_val = cols[4].get_text(strip=True) if len(cols) > 4 else ""

            if not title_val or not sym_val:
                continue

            # Extract Document PDF link
            doc_link = None
            for a_tag in row.find_all("a"):
                href = a_tag.get("href", "")
                if "/download/" in href or href.endswith(".pdf"):
                    doc_link = urljoin(PSX_BASE_URL, href)
                    break

            # Fallback document link if none found
            if not doc_link:
                doc_link = f"{PSX_BASE_URL}/company/{sym_val}"

            published_iso = _parse_pkt_datetime(date_val, time_val)
            event_type = _classify_event_type(title_val)
            sentiment = _estimate_sentiment(title_val, event_type)

            # Build readable short summary for frontend
            summary = f"{comp_name or sym_val} ({sym_val}): {title_val}."

            announcements.append({
                "id": f"psx_{sym_val}_{abs(hash(title_val + published_iso)) % 10000000}",
                "title": title_val,
                "url": doc_link,
                "external_url": f"{PSX_BASE_URL}/company/{sym_val}",
                "source": {
                    "key": "psx",
                    "name": "PSX Official Announcements",
                    "type": "official",
                },
                "is_official": True,
                "summary": summary,
                "symbols": [{"symbol": sym_val, "name": comp_name or sym_val}],
                "event_type": event_type,
                "sentiment": sentiment,
                "impact_score": 75 if event_type in ("earnings", "dividend", "material_information") else 50,
                "published_at": published_iso,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

        return announcements

    except Exception as exc:
        log.warning("Live PSX announcements fetch failed for %s: %s", symbol, exc)
        return []


async def save_announcements_to_db(db: AsyncSession, announcements: List[Dict[str, Any]]) -> None:
    """Save newly fetched PSX announcements to PostgreSQL database."""
    if not announcements:
        return

    try:
        for item in announcements:
            doc_url = item["url"]
            existing = await db.execute(select(NewsArticle).where(NewsArticle.url == doc_url))
            if existing.scalars().first():
                continue

            sym_info = item.get("symbols", [{}])[0]
            symbol = sym_info.get("symbol", "")
            comp_name = sym_info.get("name", "")

            published_dt = None
            if item.get("published_at"):
                try:
                    published_dt = datetime.fromisoformat(item["published_at"])
                except Exception:
                    pass

            sentiment = item.get("sentiment", {})
            article = NewsArticle(
                title=item["title"][:500],
                url=doc_url[:1000],
                external_url=item.get("external_url"),
                source=item["source"]["name"],
                source_key=item["source"]["key"],
                source_type=item["source"]["type"],
                summary=item.get("summary"),
                symbols=json.dumps([symbol]) if symbol else None,
                company_names=json.dumps([comp_name]) if comp_name else None,
                event_type=item.get("event_type"),
                sentiment_label=sentiment.get("label"),
                sentiment_score=sentiment.get("score"),
                sentiment_method=sentiment.get("method"),
                sentiment_status="ok",
                impact_score=item.get("impact_score", 50),
                published_at=published_dt,
                published_at_estimated=False,
                created_at=datetime.now(timezone.utc),
            )
            db.add(article)
            await db.flush()

            if symbol:
                db.add(NewsArticleSymbol(article_id=article.id, symbol=symbol))

        await db.commit()
    except Exception as exc:
        await db.rollback()
        log.warning("Could not persist PSX announcements to DB: %s", exc)


class PSXAnnouncementService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_stock_announcements(self, symbol: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get announcements for a stock with Redis caching + on-demand live fetch."""
        sym = symbol.strip().upper()
        cache_key = f"psx:announcements:{sym}"

        # 1. Check Redis cache
        cached = await cache_get(cache_key)
        if cached and isinstance(cached, list) and len(cached) > 0:
            log.info("PSX announcements cache hit for %s (%d items)", sym, len(cached))
            return cached[:limit]

        # 2. Live on-demand fetch from PSX DPS
        announcements = await fetch_psx_announcements(symbol=sym, count=limit)
        if announcements:
            # Cache in Redis for 15 minutes
            await cache_set(cache_key, announcements, ttl_seconds=CACHE_TTL_SECONDS)
            # Persist to database
            await save_announcements_to_db(self.db, announcements)
            return announcements[:limit]

        # 3. Fallback to existing database records
        from app.services.news_service import NewsService
        news_svc = NewsService(self.db)
        articles, _, _ = await news_svc.get_articles(symbol=sym, limit=limit)
        return [news_svc.to_response(a) for a in articles]

    async def get_portfolio_announcements(self, user_id: str, limit: int = 20) -> tuple[List[Dict[str, Any]], Optional[str]]:
        """Get announcements for stocks in user's portfolio."""
        from app.services.news_service import NewsService
        news_svc = NewsService(self.db)
        user_symbols = await news_svc._get_user_symbols(user_id)

        if not user_symbols:
            return [], "no_holdings"

        all_items = []
        # Query cached/live announcements for each portfolio stock
        for sym in user_symbols:
            items = await self.get_stock_announcements(sym, limit=10)
            all_items.extend(items)

        if not all_items:
            # Fallback to database query
            articles, _, _ = await news_svc.get_articles(row="portfolio", user_id=user_id, limit=limit)
            all_items = [news_svc.to_response(a) for a in articles]

        # Deduplicate and sort by published_at DESC
        seen_urls = set()
        deduped = []
        for item in all_items:
            u = item.get("url") or item.get("title")
            if u not in seen_urls:
                seen_urls.add(u)
                deduped.append(item)

        deduped.sort(key=lambda x: x.get("published_at") or "", reverse=True)
        return deduped[:limit], None
