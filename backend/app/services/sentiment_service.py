"""FinBERT sentiment pipeline — per-stock and market-level sentiment.

Pipeline:
  1. Ingest Module 8 (news)
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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import pandas as pd
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.news import NewsArticle
from app.models.sentiment import SentimentAggregate, SentimentResult
from app.models.stock import Stock
from app.repository.sentiment_repository import SentimentRepository

log = logging.getLogger(__name__)

SENTIMENT_DIR = Path("data/reports/sentiment")
SENTIMENT_DIR.mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════════════════════════════════
# FinBERT via HuggingFace Inference API & Local Inference
# ═══════════════════════════════════════════════════════════════════════

HF_API_URL = "https://api-inference.huggingface.co/models/ProsusAI/finbert"
HF_API_TOKEN = getattr(get_settings(), "HF_API_TOKEN", None)


def _extract_finbert_probabilities(result_items: list[dict] | dict) -> tuple[float, float, float, float, str]:
    """Extract continuous score, class probabilities, and label from FinBERT outputs.

    Continuous score formula:
        Score = P(positive) - P(negative) in [-1.0, +1.0]

    Returns:
        (continuous_score, positive_score, neutral_score, negative_score, label)
    """
    if isinstance(result_items, dict):
        result_items = [result_items]

    pos_p = 0.0
    neu_p = 0.0
    neg_p = 0.0

    for item in result_items:
        if not isinstance(item, dict):
            continue
        lbl = str(item.get("label", "")).lower()
        val = float(item.get("score", 0.0))
        if lbl in ("positive", "pos", "bullish"):
            pos_p = val
        elif lbl in ("negative", "neg", "bearish"):
            neg_p = val
        elif lbl in ("neutral", "neu"):
            neu_p = val

    # If no neutral probability was explicitly returned, calculate remainder
    total = pos_p + neg_p + neu_p
    if total > 0:
        pos_p /= total
        neg_p /= total
        neu_p /= total

    # Continuous compound score formula: P(pos) - P(neg)
    continuous_score = round(pos_p - neg_p, 4)

    # Standard financial sentiment threshold (+/- 0.15)
    if continuous_score >= 0.15:
        label = "positive"
    elif continuous_score <= -0.15:
        label = "negative"
    else:
        label = "neutral"

    return continuous_score, round(pos_p, 4), round(neu_p, 4), round(neg_p, 4), label


def _call_hf_api(text: str) -> dict[str, Any] | None:
    """Call HuggingFace Inference API for FinBERT sentiment.

    Processes up to 2048 characters with full probability distribution extraction.
    """
    if not HF_API_TOKEN:
        return None

    try:
        headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}
        # Allow up to 2048 chars so title + summary are preserved for subword tokenization
        payload = {"inputs": text[:2048], "options": {"wait_for_model": True}}

        resp = httpx.post(HF_API_URL, json=payload, headers=headers, timeout=10.0)
        resp.raise_for_status()

        results = resp.json()
        if isinstance(results, list) and len(results) > 0:
            raw_items = results[0] if isinstance(results[0], list) else results
            score, pos_p, neu_p, neg_p, label = _extract_finbert_probabilities(raw_items)

            return {
                "score": score,
                "label": label,
                "positive_score": pos_p,
                "neutral_score": neu_p,
                "negative_score": neg_p,
                "model": "finbert_api",
            }

    except Exception as exc:
        log.warning("HF API call failed: %s", exc)

    return None


def _call_hf_api_batch(texts: list[str]) -> list[dict[str, Any] | None]:
    """Call HF API with batch of texts (single request, up to ~16 texts)."""
    if not HF_API_TOKEN or not texts:
        return [None] * len(texts)

    try:
        headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}
        truncated = [t[:2048] for t in texts]
        payload = {"inputs": truncated, "options": {"wait_for_model": True}}

        resp = httpx.post(HF_API_URL, json=payload, headers=headers, timeout=30.0)
        resp.raise_for_status()

        results = resp.json()
        if not isinstance(results, list):
            return [None] * len(texts)

        output = []
        for result_set in results:
            if isinstance(result_set, list) and len(result_set) > 0:
                raw_items = result_set[0] if isinstance(result_set[0], list) else result_set
                score, pos_p, neu_p, neg_p, label = _extract_finbert_probabilities(raw_items)
                output.append({
                    "score": score,
                    "label": label,
                    "positive_score": pos_p,
                    "neutral_score": neu_p,
                    "negative_score": neg_p,
                    "model": "finbert_api",
                })
            else:
                output.append(None)
        return output

    except Exception as exc:
        log.warning("HF batch API call failed: %s", exc)
        return [None] * len(texts)


# ════════════════════════════════════════════════════════════════════════
# Sentiment Scoring — Heuristic Fallback with Negation & Phrase Matching
# ════════════════════════════════════════════════════════════════════════

_POSITIVE_PHRASES = [
    "profit surge", "profit rises", "net profit up", "dividend payout",
    "revenue growth", "beats estimate", "all-time high", "bullish momentum",
    "record high", "outperform", "buy rating", "strong quarterly", "earning beat",
]

_NEGATIVE_PHRASES = [
    "net loss", "profit drops", "profit declines", "profit slump",
    "revenue miss", "circular debt rises", "downgrade", "underperform",
    "selloff", "bearish trend", "defaults on", "legal notice", "fined by",
    "loss widened", "earnings miss",
]

_POSITIVE_WORDS = {
    "profit", "gain", "rise", "surge", "rally", "bullish", "upgrade",
    "outperform", "buy", "strong", "growth", "revenue", "beat", "exceed",
    "record", "dividend", "positive", "recovery", "boom", "jump",
}

_NEGATIVE_WORDS = {
    "loss", "fall", "drop", "crash", "bearish", "downgrade", "underperform",
    "sell", "weak", "decline", "miss", "deficit", "default",
    "bankruptcy", "fraud", "negative", "recession", "slump", "plunge", "down",
}

_NEGATION_WORDS = {
    "not", "no", "never", "failed", "cannot", "neither", "hardly", "barely",
    "without", "lack", "lacks", "lacking", "didn't", "didnt", "don't", "dont",
    "doesn't", "doesnt", "wasn't", "wasnt", "weren't", "werent", "won't", "wont",
}

_CLAUSE_BREAKERS = {".", ",", ";", "!", "?", "but", "however", "although", "yet", "except"}


def _heuristic_score(text: str) -> tuple[float, float, float, float, str]:
    """Context-aware keyword & phrase sentiment score.

    Returns:
        (score, positive_score, neutral_score, negative_score, label)
    """
    text_lower = text.lower()

    # Step 1: Check multi-word financial phrases with negation awareness
    pos_phrase_count = 0
    neg_phrase_count = 0

    for phrase in _POSITIVE_PHRASES:
        idx = 0
        while True:
            idx = text_lower.find(phrase, idx)
            if idx == -1:
                break
            preceding = text_lower[max(0, idx - 30):idx].split()
            if any(nw in preceding for nw in _NEGATION_WORDS):
                neg_phrase_count += 1
            else:
                pos_phrase_count += 1
            idx += len(phrase)

    for phrase in _NEGATIVE_PHRASES:
        idx = 0
        while True:
            idx = text_lower.find(phrase, idx)
            if idx == -1:
                break
            preceding = text_lower[max(0, idx - 30):idx].split()
            if any(nw in preceding for nw in _NEGATION_WORDS):
                pos_phrase_count += 1
            else:
                neg_phrase_count += 1
            idx += len(phrase)

    # Step 2: Tokenize and apply clause-aware negation window
    raw_tokens = text_lower.split()
    pos_word_count = 0
    neg_word_count = 0

    negate = False
    negation_window = 0

    for raw_token in raw_tokens:
        clean_token = raw_token.strip(".,;:!?\"'()[]{}")
        has_punctuation = any(p in raw_token for p in ".,;:!?")

        if clean_token in _CLAUSE_BREAKERS or has_punctuation:
            if clean_token not in _NEGATION_WORDS:
                negate = False
                negation_window = 0

        if clean_token in _NEGATION_WORDS:
            negate = True
            negation_window = 5
            continue

        if clean_token in _POSITIVE_WORDS:
            if negate:
                neg_word_count += 1
            else:
                pos_word_count += 1
        elif clean_token in _NEGATIVE_WORDS:
            if negate:
                pos_word_count += 1
            else:
                neg_word_count += 1

        if negation_window > 0:
            negation_window -= 1
            if negation_window == 0:
                negate = False

    total_pos = pos_word_count + (pos_phrase_count * 2)
    total_neg = neg_word_count + (neg_phrase_count * 2)
    total_active = total_pos + total_neg

    if total_active == 0:
        return 0.0, 0.0, 1.0, 0.0, "neutral"

    # Normalize continuous score between -1.0 and +1.0
    continuous_score = round((total_pos - total_neg) / max(total_active, 1), 4)
    pos_p = round(total_pos / (total_active + 2.0), 4)
    neg_p = round(total_neg / (total_active + 2.0), 4)
    neu_p = round(max(0.0, 1.0 - pos_p - neg_p), 4)

    if continuous_score >= 0.15:
        label = "positive"
    elif continuous_score <= -0.15:
        label = "negative"
    else:
        label = "neutral"

    return continuous_score, pos_p, neu_p, neg_p, label


def score_text(text: str) -> dict[str, Any]:
    """Score a single text. Returns {score, label, positive_score, neutral_score, negative_score, model}.

    Tries HF Inference API first (FinBERT), falls back to context-aware heuristic.
    """
    if not text or not text.strip():
        return {
            "score": 0.0,
            "label": "neutral",
            "positive_score": 0.0,
            "neutral_score": 1.0,
            "negative_score": 0.0,
            "model": "empty",
        }

    # Try HF API first
    result = _call_hf_api(text)
    if result is not None:
        return result

    # Fallback: context-aware heuristic
    score, pos_p, neu_p, neg_p, label = _heuristic_score(text)
    return {
        "score": score,
        "label": label,
        "positive_score": pos_p,
        "neutral_score": neu_p,
        "negative_score": neg_p,
        "model": "heuristic",
    }


def score_batch(texts: list[str]) -> list[dict[str, Any]]:
    """Score a batch of texts. Uses HF batch API with heuristic fallback."""
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
            score, pos_p, neu_p, neg_p, label = _heuristic_score(text)
            output.append({
                "score": score,
                "label": label,
                "positive_score": pos_p,
                "neutral_score": neu_p,
                "negative_score": neg_p,
                "model": "heuristic",
            })
    return output


# ════════════════════════════════════════════════════════════════════════
# Data Ingestion — News
# ════════════════════════════════════════════════════════════════════════

async def _fetch_news_for_symbol(
    repo: SentimentRepository,
    symbol: str,
    days: int = 7,
) -> list[dict]:
    """Fetch recent news articles mentioning a symbol with sentiment results."""
    articles, _ = await repo.get_recent_news(symbol=symbol, days=days, limit=100)

    matched = []
    symbol_lower = symbol.lower()
    for a in articles:
        text = f"{a.title or ''} {a.summary or ''}".lower()
        if symbol_lower in text or (a.symbols and symbol_lower in a.symbols.lower()):
            matched.append({
                "text": f"{a.title}. {a.summary or ''}",
                "source": a.source or "unknown",
                "published_at": a.published_at.isoformat() if a.published_at else None,
                "published_at_dt": a.published_at,
                "existing_score": float(a.sentiment_score) if a.sentiment_score is not None else None,
                "news_article_id": a.id,
                "article": a,
            })
    return matched


# ════════════════════════════════════════════════════════════════════════
# Per-Stock Sentiment
# ════════════════════════════════════════════════════════════════════════

async def compute_stock_sentiment(
    db: AsyncSession,
    symbol: str,
    days: int = 7,
) -> dict[str, Any]:
    """Compute sentiment score for a single stock using exponential time-decay weighting.

    Returns:
        {symbol, score, label, article_count, source_breakdown,
         trend, daily_scores, details}
    """
    symbol = symbol.upper()
    repo = SentimentRepository(db)
    # The filesystem-backed PSX universe can contain symbols that have not yet
    # been registered in the relational stock catalog. Scores can still be
    # computed for those symbols, but sentiment rows reference stocks.symbol.
    stock_exists = await db.scalar(
        select(Stock.symbol).where(Stock.symbol == symbol).limit(1)
    ) is not None

    news = await _fetch_news_for_symbol(repo, symbol, days)

    if not news:
        return {
            "symbol": symbol,
            "score": 0.0,
            "label": "neutral",
            "confidence": 0.0,
            "positive_ratio": 0.0,
            "neutral_ratio": 1.0,
            "negative_ratio": 0.0,
            "article_count": 0,
            "trend": "stable",
            "daily_scores": [],
            "updated_at": datetime.utcnow().isoformat(),
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
            # Persist the text score once per article so recommendations for
            # other symbols mentioned by that story can reuse it.
            article = item["article"]
            article.sentiment_score = score
            article.sentiment_label = result.get("label")
            article.sentiment_method = "finbert" if str(model).startswith("finbert") else "eps_rule"
            article.sentiment_status = "ok"

            # Persist sentiment result with full probability distribution
            if stock_exists:
                await repo.create_sentiment_result(
                    news_article_id=item["news_article_id"],
                    symbol=symbol,
                    model_name=model,
                    label=result["label"],
                    score=score,
                    positive_score=result.get("positive_score"),
                    neutral_score=result.get("neutral_score"),
                    negative_score=result.get("negative_score"),
                )

        all_scores.append(score)
        details.append({
            "source": "news",
            "text_preview": item["text"][:120],
            "score": score,
            "model": model,
            "published_at": item["published_at"],
        })

    # Calendar time-decay weighted average (half-life = 3.0 days)
    # Weight formula: w_i = exp(-lambda * delta_t_days)
    now_utc = datetime.now(timezone.utc)
    half_life_days = 3.0
    decay_lambda = np.log(2) / half_life_days

    weights = []
    for item in news:
        pub_dt = item.get("published_at_dt")
        if pub_dt:
            if pub_dt.tzinfo is None:
                pub_dt = pub_dt.replace(tzinfo=timezone.utc)
            age_days = max(0.0, (now_utc - pub_dt).total_seconds() / 86400.0)
        else:
            age_days = 1.0
        weights.append(np.exp(-decay_lambda * age_days))

    weights_arr = np.array(weights)
    if weights_arr.sum() > 0:
        decay_weights = weights_arr / weights_arr.sum()
        overall_score = float(np.average(all_scores, weights=decay_weights))
    else:
        overall_score = float(np.mean(all_scores)) if all_scores else 0.0

    # Label assignment based on continuous score
    if overall_score >= 0.15:
        label = "positive"
    elif overall_score <= -0.15:
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
        dt = d.get("published_at")
        if dt:
            day = dt[:10]
            daily.setdefault(day, []).append(d["score"])
    daily_scores = [
        {"date": day, "score": round(float(np.mean(scores)), 4), "count": len(scores)}
        for day, scores in sorted(daily.items())
    ]

    period_end = datetime.now(timezone.utc)
    pos_ratio = round(sum(1 for s in all_scores if s >= 0.15) / len(all_scores), 4) if all_scores else 0.0
    neu_ratio = round(sum(1 for s in all_scores if -0.15 < s < 0.15) / len(all_scores), 4) if all_scores else 0.0
    neg_ratio = round(sum(1 for s in all_scores if s <= -0.15) / len(all_scores), 4) if all_scores else 0.0
    confidence = round(min(1.0, (abs(overall_score) * 0.7) + (min(len(details), 10) / 10.0 * 0.3)), 2)
    updated_at = period_end.isoformat()

    result = {
        "symbol": symbol,
        "score": round(overall_score, 4),
        "label": label,
        "confidence": confidence,
        "positive_ratio": pos_ratio,
        "neutral_ratio": neu_ratio,
        "negative_ratio": neg_ratio,
        "article_count": len(details),
        "trend": trend,
        "daily_scores": daily_scores,
        "updated_at": updated_at,
        "details": details[:20],  # cap for response size
        "persistence": "stored" if stock_exists else "computed_only_stock_not_registered",
    }

    # Cache to disk
    cache_path = SENTIMENT_DIR / f"{symbol}.json"
    with open(cache_path, "w") as f:
        json.dump(result, f, default=str, indent=2)

    # Persist aggregate
    period_end = datetime.utcnow()
    period_start = period_end - timedelta(days=days)
    pos_ratio = sum(1 for s in all_scores if s >= 0.15) / len(all_scores) if all_scores else None
    neu_ratio = sum(1 for s in all_scores if -0.15 < s < 0.15) / len(all_scores) if all_scores else None
    neg_ratio = sum(1 for s in all_scores if s <= -0.15) / len(all_scores) if all_scores else None

    if stock_exists:
        await repo.upsert_sentiment_aggregate(
            symbol=symbol,
            period=f"{days}D",
            period_start=period_start,
            period_end=period_end,
            overall_score=result["score"],
            label=label,
            article_count=result["article_count"],
            positive_ratio=pos_ratio,
            neutral_ratio=neu_ratio,
            trend=trend,
            daily_scores=json.dumps(daily_scores),
            source_breakdown=None,
        )

    return result


# ════════════════════════════════════════════════════════════════════════
# Market-Level Sentiment
# ════════════════════════════════════════════════════════════════════════

async def compute_market_sentiment(db: AsyncSession) -> dict[str, Any]:
    """Compute overall market sentiment across all PSX stocks.

    Aggregates:
      - News sentiment (weighted by recency)
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

    # Score all news
    news_scores = []
    for a in articles:
        if a.sentiment_score is not None:
            news_scores.append(float(a.sentiment_score))
        else:
            result = score_text(f"{a.title}. {a.summary or ''}")
            news_scores.append(result["score"])

    # Aggregate
    all_scores = news_scores
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

    ad_ratio = (advancing / declining) if declining > 0 else float(advancing)

    result = {
        "market_mood": mood,
        "overall_score": round(overall_score, 4),
        "article_count": len(articles),
        "advancing": advancing,
        "declining": declining,
        "unchanged": unchanged,
        "advance_decline_ratio": round(ad_ratio, 2),
        "news_sentiment_avg": round(float(np.mean(news_scores)), 4) if news_scores else 0.0,
        "score_distribution": {
            "positive": sum(1 for s in all_scores if s > 0.15),
            "neutral": sum(1 for s in all_scores if -0.15 <= s <= 0.15),
            "negative": sum(1 for s in all_scores if s < -0.15),
        },
        "updated_at": datetime.utcnow().isoformat(),
    }

    # Cache
    cache_path = SENTIMENT_DIR / "market_overview.json"
    with open(cache_path, "w") as f:
        json.dump(result, f, default=str, indent=2)

    return result


# ════════════════════════════════════════════════════════════════════════
# Sentiment History & News API
# ════════════════════════════════════════════════════════════════════════

async def get_sentiment_history(
    db: AsyncSession,
    symbol: str,
    period: str = "1M",
    limit: int = 100,
) -> dict[str, Any]:
    """Get historical sentiment aggregates for a symbol."""
    repo = SentimentRepository(db)
    aggregates = await repo.get_sentiment_history(symbol, period, limit)

    if not aggregates:
        return {
            "symbol": symbol.upper(),
            "period": period,
            "data": [],
        }

    data = []
    for agg in aggregates:
        daily_scores = []
        if agg.daily_scores:
            try:
                daily_scores = json.loads(agg.daily_scores)
            except Exception:
                daily_scores = []

        source_breakdown = {}
        if agg.source_breakdown:
            try:
                source_breakdown = json.loads(agg.source_breakdown)
            except Exception:
                source_breakdown = {}

        data.append({
            "date": agg.period_end.isoformat()[:10],
            "score": float(agg.overall_score) if agg.overall_score else 0.0,
            "label": agg.label,
            "article_count": agg.article_count,
            "positive_ratio": float(agg.positive_ratio) if agg.positive_ratio else None,
            "neutral_ratio": float(agg.neutral_ratio) if agg.neutral_ratio else None,
            "negative_ratio": float(agg.negative_ratio) if agg.negative_ratio else None,
            "trend": agg.trend,
            "daily_scores": daily_scores,
        })

    return {
        "symbol": symbol.upper(),
        "period": period,
        "data": data,
    }


async def get_sentiment_news(
    db: AsyncSession,
    symbol: str,
    page: int = 1,
    limit: int = 20,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    sentiment: str | None = None,
) -> tuple[list[dict], int]:
    """Get paginated news articles with sentiment for a symbol."""
    repo = SentimentRepository(db)

    # Get news articles (fetch more than needed to account for filtering)
    articles, _ = await repo.get_recent_news(
        symbol=symbol,
        days=365,  # Look back up to a year
        limit=limit * 5,  # Get more to filter
        page=1,
    )

    # Apply date filters
    if from_date:
        articles = [a for a in articles if a.published_at and a.published_at >= from_date]
    if to_date:
        articles = [a for a in articles if a.published_at and a.published_at <= to_date]

    # Get sentiment results for these articles
    article_ids = [a.id for a in articles]
    sentiment_results = {}
    if article_ids:
        result = await db.execute(
            select(SentimentResult).where(
                SentimentResult.news_article_id.in_(article_ids),
                SentimentResult.symbol == symbol.upper(),
            )
        )
        for sr in result.scalars().all():
            sentiment_results[sr.news_article_id] = sr

    news_items = []
    for a in articles:
        sr = sentiment_results.get(a.id)
        label = (sr.label if sr else a.sentiment_label) or "NEUTRAL"
        score = float(sr.score) if (sr and sr.score is not None) else (float(a.sentiment_score) if a.sentiment_score is not None else 0.0)
        model = (sr.model_name if sr else a.sentiment_method) or "keyword_heuristic"
        news_items.append({
            "id": a.id,
            "title": a.title,
            "source": a.source or "Market News",
            "published_at": a.published_at.isoformat() if a.published_at else (a.created_at.isoformat() if a.created_at else None),
            "url": a.external_url or a.url,
            "sentiment": label.lower(),
            "sentiment_score": score,
            "sentiment_model": model,
            "positive_score": float(sr.positive_score) if (sr and sr.positive_score is not None) else None,
            "neutral_score": float(sr.neutral_score) if (sr and sr.neutral_score is not None) else None,
            "negative_score": float(sr.negative_score) if (sr and sr.negative_score is not None) else None,
        })

    if sentiment:
        news_items = [n for n in news_items if n.get("sentiment") == sentiment.upper()]

    total = len(news_items)

    # Apply pagination
    start = (page - 1) * limit
    end = start + limit
    paginated = news_items[start:end]

    return paginated, total


# ════════════════════════════════════════════════════════════════════════
# Cache Helpers
# ════════════════════════════════════════════════════════════════════════

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
