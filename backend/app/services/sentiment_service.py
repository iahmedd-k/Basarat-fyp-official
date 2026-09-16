"""FinBERT sentiment pipeline — per-stock and market-level sentiment.

Pipeline:
  1. Ingest Module 8 (news) + Module 10 (community posts)
  2. Run FinBERT via HuggingFace Inference API → score [-1, 1]
  3. Aggregate per-stock: rolling 7-day decay-weighted average
  4. Aggregate market-level: equal-weight across all scored stocks

Models used:
  - ProsusAI/finbert via HF Inference API (free, no download)
  - Fallback: keyword-based heuristic if API unavailable

Caching:
  - Scores cached to data/reports/sentiment/
  - Per-stock: {symbol}.json
  - Market: market_overview.json
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import pandas as pd
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.news import NewsArticle
from app.models.community import Post

log = logging.getLogger(__name__)

SENTIMENT_DIR = Path("data/reports/sentiment")
SENTIMENT_DIR.mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════════════════════════════════
# FinBERT via HuggingFace Inference API
# ═══════════════════════════════════════════════════════════════════════

HF_API_URL = "https://api-inference.huggingface.co/models/ProsusAI/finbert"
HF_API_TOKEN = getattr(get_settings(), "HF_API_TOKEN", None)


def _call_hf_api(text: str) -> dict[str, Any] | None:
    """Call HuggingFace Inference API for FinBERT sentiment.

    Free tier: 1M tokens/month, ~300ms latency per call.
    No model download, no GPU needed.
    """
    if not HF_API_TOKEN:
        return None

    try:
        headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}
        payload = {"inputs": text[:512], "options": {"wait_for_model": True}}

        resp = httpx.post(HF_API_URL, json=payload, headers=headers, timeout=10.0)
        resp.raise_for_status()

        results = resp.json()
        if isinstance(results, list) and len(results) > 0:
            # FinBERT returns: [{label: "positive", score: 0.95}, ...]
            best = max(results, key=lambda x: x.get("score", 0))
            label = best["label"].lower()
            raw_score = best["score"]

            if label == "positive":
                score = raw_score
            elif label == "negative":
                score = -raw_score
            else:
                score = 0.0

            return {"score": round(score, 4), "label": label, "model": "finbert_api"}

    except Exception as exc:
        log.warning("HF API call failed: %s", exc)

    return None


def _call_hf_api_batch(texts: list[str]) -> list[dict[str, Any] | None]:
    """Call HF API with batch of texts (single request, up to ~16 texts)."""
    if not HF_API_TOKEN or not texts:
        return [None] * len(texts)

    try:
        headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}
        # HF batch endpoint accepts list of strings
        truncated = [t[:512] for t in texts]
        payload = {"inputs": truncated, "options": {"wait_for_model": True}}

        resp = httpx.post(HF_API_URL, json=payload, headers=headers, timeout=30.0)
        resp.raise_for_status()

        results = resp.json()
        if not isinstance(results, list):
            return [None] * len(texts)

        output = []
        for result_set in results:
            if isinstance(result_set, list) and len(result_set) > 0:
                best = max(result_set, key=lambda x: x.get("score", 0))
                label = best["label"].lower()
                raw_score = best["score"]
                if label == "positive":
                    score = raw_score
                elif label == "negative":
                    score = -raw_score
                else:
                    score = 0.0
                output.append({"score": round(score, 4), "label": label, "model": "finbert_api"})
            else:
                output.append(None)
        return output

    except Exception as exc:
        log.warning("HF batch API call failed: %s", exc)
        return [None] * len(texts)


# ═══════════════════════════════════════════════════════════════════════
# Sentiment Scoring
# ═══════════════════════════════════════════════════════════════════════

# Positive/negative keyword lists for heuristic fallback
_POSITIVE_WORDS = {
    "profit", "gain", "rise", "surge", "rally", "bullish", "upgrade",
    "outperform", "buy", "strong", "growth", "revenue", "beat", "exceed",
    "record", "dividend", "upgrade", "positive", "recovery", "boom",
}
_NEGATIVE_WORDS = {
    "loss", "fall", "drop", "crash", "bearish", "downgrade", "underperform",
    "sell", "weak", "decline", "revenue miss", "miss", "deficit", "default",
    "bankruptcy", "fraud", "negative", "recession", "slump", "plunge",
}


def _heuristic_score(text: str) -> float:
    """Keyword-based sentiment score. Returns [-1, 1]."""
    words = set(text.lower().split())
    pos = len(words & _POSITIVE_WORDS)
    neg = len(words & _NEGATIVE_WORDS)
    total = pos + neg
    if total == 0:
        return 0.0
    return round((pos - neg) / total, 3)


def score_text(text: str) -> dict[str, Any]:
    """Score a single text. Returns {score, label, model}.

    Tries HF Inference API first (free, no download).
    Falls back to keyword heuristic if API unavailable.
    """
    if not text or not text.strip():
        return {"score": 0.0, "label": "neutral", "model": "empty"}

    # Try HF API first
    result = _call_hf_api(text)
    if result is not None:
        return result

    # Fallback: keyword heuristic
    score = _heuristic_score(text)
    label = "positive" if score > 0.1 else "negative" if score < -0.1 else "neutral"
    return {"score": round(score, 4), "label": label, "model": "heuristic"}


def score_batch(texts: list[str]) -> list[dict[str, Any]]:
    """Score a batch of texts. Uses HF batch API for efficiency."""
    if not texts:
        return []

    # Try batch API first
    results = _call_hf_api_batch(texts)
    output = []
    for i, (text, result) in enumerate(zip(texts, results)):
        if result is not None:
            output.append(result)
        else:
            # Fallback per text
            score = _heuristic_score(text)
            label = "positive" if score > 0.1 else "negative" if score < -0.1 else "neutral"
            output.append({"score": round(score, 4), "label": label, "model": "heuristic"})
    return output


# ═══════════════════════════════════════════════════════════════════════
# Data Ingestion — News + Community Posts
# ═══════════════════════════════════════════════════════════════════════

async def _fetch_news_for_symbol(db: AsyncSession, symbol: str, days: int = 7) -> list[dict]:
    """Fetch recent news articles mentioning a symbol."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        select(NewsArticle)
        .where(NewsArticle.published_at >= cutoff)
        .order_by(desc(NewsArticle.published_at))
        .limit(100)
    )
    articles = result.scalars().all()

    # Filter by symbol mention in title/summary
    matched = []
    symbol_lower = symbol.lower()
    for a in articles:
        text = f"{a.title or ''} {a.summary or ''}".lower()
        if symbol_lower in text:
            matched.append({
                "text": f"{a.title}. {a.summary or ''}",
                "source": a.source or "unknown",
                "published_at": a.published_at.isoformat() if a.published_at else None,
                "existing_score": float(a.sentiment_score) if a.sentiment_score else None,
            })
    return matched


async def _fetch_community_for_symbol(db: AsyncSession, symbol: str, days: int = 7) -> list[dict]:
    """Fetch recent community posts about a symbol."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        select(Post)
        .where(Post.symbol == symbol)
        .where(Post.created_at >= cutoff)
        .order_by(desc(Post.created_at))
        .limit(100)
    )
    posts = result.scalars().all()

    return [
        {
            "text": f"{p.stance}: {p.rationale_text}",
            "stance": p.stance,
            "upvotes": p.upvotes,
            "downvotes": p.downvotes,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in posts
    ]


# ═══════════════════════════════════════════════════════════════════════
# Per-Stock Sentiment
# ═══════════════════════════════════════════════════════════════════════

async def compute_stock_sentiment(
    db: AsyncSession,
    symbol: str,
    days: int = 7,
) -> dict[str, Any]:
    """Compute sentiment score for a single stock.

    Returns:
        {symbol, score, label, article_count, source_breakdown,
         trend, daily_scores, details}
    """
    symbol = symbol.upper()

    news = await _fetch_news_for_symbol(db, symbol, days)
    community = await _fetch_community_for_symbol(db, symbol, days)

    if not news and not community:
        return {
            "symbol": symbol,
            "score": 0.0,
            "label": "neutral",
            "article_count": 0,
            "source_breakdown": {"news": 0, "community": 0},
            "trend": "stable",
            "daily_scores": [],
            "details": [],
        }

    # Score all texts
    details = []
    all_scores = []

    for item in news:
        if item["existing_score"] is not None:
            score = item["existing_score"]
            model = "cached"
        else:
            result = score_text(item["text"])
            score = result["score"]
            model = result["model"]
        all_scores.append(score)
        details.append({
            "source": "news",
            "text_preview": item["text"][:120],
            "score": score,
            "model": model,
            "published_at": item["published_at"],
        })

    for item in community:
        result = score_text(item["text"])
        weight = 1.0 + (item["upvotes"] - item["downvotes"]) * 0.1
        weighted_score = result["score"] * max(weight, 0.1)
        all_scores.append(weighted_score)
        details.append({
            "source": "community",
            "text_preview": item["text"][:120],
            "score": result["score"],
            "weighted_score": weighted_score,
            "stance": item["stance"],
            "upvotes": item["upvotes"],
            "downvotes": item["downvotes"],
        })

    # Decay-weighted average (recent items weighted more)
    decay_weights = np.exp(-np.linspace(0, 2, len(all_scores)))
    decay_weights = decay_weights / decay_weights.sum()
    overall_score = float(np.average(all_scores, weights=decay_weights))

    # Label
    if overall_score > 0.15:
        label = "positive"
    elif overall_score < -0.15:
        label = "negative"
    else:
        label = "neutral"

    # Trend (compare first half vs second half)
    mid = len(all_scores) // 2
    if mid > 0:
        first_half = np.mean(all_scores[:mid])
        second_half = np.mean(all_scores[mid:])
        diff = second_half - first_half
        if diff > 0.1:
            trend = "improving"
        elif diff < -0.1:
            trend = "declining"
        else:
            trend = "stable"
    else:
        trend = "stable"

    # Daily scores for chart
    daily = {}
    for d in details:
        dt = d.get("published_at") or d.get("created_at")
        if dt:
            day = dt[:10]
            daily.setdefault(day, []).append(d["score"])
    daily_scores = [
        {"date": day, "score": round(float(np.mean(scores)), 4), "count": len(scores)}
        for day, scores in sorted(daily.items())
    ]

    result = {
        "symbol": symbol,
        "score": round(overall_score, 4),
        "label": label,
        "article_count": len(details),
        "source_breakdown": {
            "news": len(news),
            "community": len(community),
        },
        "trend": trend,
        "daily_scores": daily_scores,
        "details": details[:20],  # cap for response size
    }

    # Cache to disk
    cache_path = SENTIMENT_DIR / f"{symbol}.json"
    with open(cache_path, "w") as f:
        json.dump(result, f, default=str, indent=2)

    return result


# ═══════════════════════════════════════════════════════════════════════
# Market-Level Sentiment
# ═══════════════════════════════════════════════════════════════════════

async def compute_market_sentiment(db: AsyncSession) -> dict[str, Any]:
    """Compute overall market sentiment across all PSX stocks.

    Aggregates:
      - News sentiment (weighted by recency)
      - Community sentiment (weighted by engagement)
      - Market breadth (advance/decline ratio from price data)
    """
    # Get distinct symbols with recent news
    cutoff = datetime.utcnow() - timedelta(days=7)
    news_result = await db.execute(
        select(NewsArticle)
        .where(NewsArticle.published_at >= cutoff)
        .order_by(desc(NewsArticle.published_at))
        .limit(500)
    )
    articles = news_result.scalars().all()

    # Get all community posts
    community_result = await db.execute(
        select(Post)
        .where(Post.created_at >= cutoff)
        .order_by(desc(Post.created_at))
        .limit(500)
    )
    posts = community_result.scalars().all()

    # Score all news
    news_scores = []
    for a in articles:
        if a.sentiment_score is not None:
            news_scores.append(float(a.sentiment_score))
        else:
            result = score_text(f"{a.title}. {a.summary or ''}")
            news_scores.append(result["score"])

    # Score all community posts (weighted by engagement)
    community_scores = []
    for p in posts:
        result = score_text(f"{p.stance}: {p.rationale_text}")
        weight = 1.0 + (p.upvotes - p.downvotes) * 0.1
        community_scores.append(result["score"] * max(weight, 0.1))

    # Aggregate
    all_scores = news_scores + community_scores
    if all_scores:
        overall_score = float(np.mean(all_scores))
    else:
        overall_score = 0.0

    if overall_score > 0.15:
        mood = "bullish"
    elif overall_score < -0.15:
        mood = "bearish"
    else:
        mood = "neutral"

    # Market breadth from price data
    features_path = Path("data/features/features_daily.parquet")
    advancing = declining = unchanged = 0
    if features_path.exists():
        try:
            df = pd.read_parquet(features_path)
            df["date"] = pd.to_datetime(df["date"])
            latest_date = df["date"].max()
            prev_date = latest_date - timedelta(days=5)
            latest = df[df["date"] == latest_date].set_index("symbol")["close"]
            prev = df[df["date"] >= prev_date].groupby("symbol")["close"].first()
            common = latest.index.intersection(prev.index)
            for sym in common:
                chg = (latest[sym] - prev[sym]) / prev[sym]
                if chg > 0.001:
                    advancing += 1
                elif chg < -0.001:
                    declining += 1
                else:
                    unchanged += 1
        except Exception as exc:
            log.warning("Failed to compute market breadth: %s", exc)

    total = advancing + declining + unchanged
    ad_ratio = (advancing / declining) if declining > 0 else float(advancing)

    result = {
        "market_mood": mood,
        "overall_score": round(overall_score, 4),
        "article_count": len(articles),
        "community_post_count": len(posts),
        "advancing": advancing,
        "declining": declining,
        "unchanged": unchanged,
        "advance_decline_ratio": round(ad_ratio, 2),
        "news_sentiment_avg": round(float(np.mean(news_scores)), 4) if news_scores else 0.0,
        "community_sentiment_avg": round(float(np.mean(community_scores)), 4) if community_scores else 0.0,
        "score_distribution": {
            "positive": sum(1 for s in all_scores if s > 0.15),
            "neutral": sum(1 for s in all_scores if -0.15 <= s <= 0.15),
            "negative": sum(1 for s in all_scores if s < -0.15),
        },
    }

    # Cache
    cache_path = SENTIMENT_DIR / "market_overview.json"
    with open(cache_path, "w") as f:
        json.dump(result, f, default=str, indent=2)

    return result


def get_cached_sentiment(symbol: str) -> dict | None:
    """Load cached sentiment for a symbol."""
    path = SENTIMENT_DIR / f"{symbol.upper()}.json"
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def get_cached_market_sentiment() -> dict | None:
    """Load cached market sentiment."""
    path = SENTIMENT_DIR / "market_overview.json"
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None
