"""Celery tasks for sentiment aggregation.

Scheduled job: runs daily to refresh per-stock and market sentiment.
Uses 7-day rolling window with decay-weighted averaging.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from celery import shared_task
from sqlalchemy import desc, or_, text
from app.models.stock import Stock

from app.db.base import get_sync_session_factory
from app.models.news import NewsArticle, NewsArticleSymbol
from app.models.sentiment import SentimentAggregate, SentimentResult
from app.services.sentiment_service import SENTIMENT_DIR, score_text

log = logging.getLogger(__name__)


def compute_stock_sentiment_sync(db, symbol: str, days: int = 7) -> dict:
    """Synchronous version of compute_stock_sentiment for Celery workers."""
    symbol = symbol.upper()
    stock_registered = db.query(Stock.id).filter(Stock.symbol == symbol).first() is not None
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    sym_clean = symbol.strip().upper()
    sym_subq = db.query(NewsArticleSymbol.article_id).filter(NewsArticleSymbol.symbol == sym_clean)

    articles = (
        db.query(NewsArticle)
        .filter(
            or_(
                NewsArticle.published_at >= cutoff,
                NewsArticle.published_at.is_(None),
            ),
            or_(
                NewsArticle.id.in_(sym_subq),
                NewsArticle.symbols.ilike(f'%"{sym_clean}"%'),
                NewsArticle.symbols.ilike(f'%{sym_clean}%'),
                NewsArticle.title.ilike(f'%{sym_clean}%'),
            ),
        )
        .order_by(NewsArticle.published_at.desc().nulls_last(), NewsArticle.created_at.desc())
        .limit(100)
        .all()
    )

    matched = []
    symbol_lower = symbol.lower()
    for a in articles:
        text_content = f"{a.title or ''} {a.summary or ''}".lower()
        if symbol_lower in text_content or (a.symbols and symbol_lower in a.symbols.lower()):
            matched.append({
                "text": f"{a.title}. {a.summary or ''}",
                "source": a.source or "unknown",
                "published_at": a.published_at.isoformat() if a.published_at else None,
                "existing_score": float(a.sentiment_score) if a.sentiment_score is not None else None,
                "existing_model": a.sentiment_method or "cached",
                "news_article_id": a.id,
                "article": a,
            })

    if not matched:
        result = {
            "symbol": symbol,
            "score": 0.0,
            "label": "neutral",
            "article_count": 0,
            "source_breakdown": {"news": 0},
            "trend": "stable",
            "daily_scores": [],
            "details": [],
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "model": "no_news",
        }
        cache_path = SENTIMENT_DIR / f"{symbol}.json"
        with open(cache_path, "w") as f:
            json.dump(result, f, default=str, indent=2)
        return result

    details = []
    all_scores = []

    for item in matched:
        if item["existing_score"] is not None:
            score = item["existing_score"]
            model = item.get("existing_model") or "cached"
        else:
            scored = score_text(item["text"])
            score = scored["score"]
            model = scored["model"]
            # Store the article-level score once. The same article can match
            # multiple symbols; later aggregates reuse this persisted FinBERT
            # result instead of calling the model once per ticker.
            article = item["article"]
            article.sentiment_score = score
            article.sentiment_label = scored.get("label")
            article.sentiment_method = "finbert" if str(model).startswith("finbert") else "eps_rule"
            article.sentiment_status = "ok"

            # Persist sentiment result
            if stock_registered:
                sr = SentimentResult(
                    news_article_id=item["news_article_id"],
                    symbol=symbol,
                    model_name=model,
                    label=scored["label"],
                    score=score,
                    positive_score=scored.get("positive_score"),
                    neutral_score=scored.get("neutral_score"),
                    negative_score=scored.get("negative_score"),
                )
                db.add(sr)
                db.flush()

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
    for a in articles:
        pub_dt = a.published_at
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

    # Label
    if overall_score >= 0.15:
        label = "positive"
    elif overall_score <= -0.15:
        label = "negative"
    else:
        label = "neutral"

    # Trend
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

    # Daily scores
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

    result = {
        "symbol": symbol,
        "score": round(overall_score, 4),
        "label": label,
        "article_count": len(details),
        "source_breakdown": {"news": len(matched)},
        "trend": trend,
        "daily_scores": daily_scores,
        "details": details[:20],
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "model": "finbert" if details and all(d.get("model") in {"finbert", "finbert_api"} for d in details) else "heuristic_or_mixed",
        "persistence": "stored" if stock_registered else "cache_only_stock_not_registered",
    }

    # Cache to disk
    cache_path = SENTIMENT_DIR / f"{symbol}.json"
    with open(cache_path, "w") as f:
        json.dump(result, f, default=str, indent=2)

    # Persist aggregate
    period_end = datetime.now(timezone.utc)
    period_start = period_end - timedelta(days=days)
    pos_ratio = sum(1 for s in all_scores if s >= 0.15) / len(all_scores) if all_scores else None
    neu_ratio = sum(1 for s in all_scores if -0.15 < s < 0.15) / len(all_scores) if all_scores else None
    neg_ratio = sum(1 for s in all_scores if s <= -0.15) / len(all_scores) if all_scores else None

    # Upsert aggregate
    agg = (
        db.query(SentimentAggregate)
        .filter(
            SentimentAggregate.symbol == symbol,
            SentimentAggregate.period == f"{days}D",
            SentimentAggregate.period_end == period_end,
        )
        .first()
    )
    if not stock_registered:
        return result
    if agg:
        agg.overall_score = result["score"]
        agg.label = label
        agg.article_count = result["article_count"]
        agg.positive_ratio = pos_ratio
        agg.neutral_ratio = neu_ratio
        agg.negative_ratio = neg_ratio
        agg.trend = trend
        agg.daily_scores = json.dumps(daily_scores)
        agg.source_breakdown = json.dumps(result["source_breakdown"])
        agg.computed_at = datetime.utcnow()
    else:
        agg = SentimentAggregate(
            symbol=symbol,
            period=f"{days}D",
            period_start=period_start,
            period_end=period_end,
            overall_score=result["score"],
            label=label,
            article_count=result["article_count"],
            positive_ratio=pos_ratio,
            neutral_ratio=neu_ratio,
            negative_ratio=neg_ratio,
            trend=trend,
            daily_scores=json.dumps(daily_scores),
            source_breakdown=json.dumps(result["source_breakdown"]),
        )
        db.add(agg)
    db.flush()

    return result


def compute_market_sentiment_sync(db) -> dict:
    """Synchronous version of compute_market_sentiment for Celery workers."""
    cutoff = datetime.utcnow() - timedelta(days=7)
    articles = (
        db.query(NewsArticle)
        .filter(NewsArticle.published_at >= cutoff)
        .order_by(desc(NewsArticle.published_at))
        .limit(500)
        .all()
    )

    news_scores = []
    for a in articles:
        if a.sentiment_score is not None:
            news_scores.append(float(a.sentiment_score))
        else:
            result = score_text(f"{a.title}. {a.summary or ''}")
            news_scores.append(result["score"])

    all_scores = news_scores
    overall_score = float(np.mean(all_scores)) if all_scores else 0.0

    if overall_score > 0.15:
        mood = "bullish"
    elif overall_score < -0.15:
        mood = "bearish"
    else:
        mood = "neutral"

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
    }

    cache_path = SENTIMENT_DIR / "market_overview.json"
    with open(cache_path, "w") as f:
        json.dump(result, f, default=str, indent=2)

    return result


@shared_task(
    name="app.tasks.sentiment_tasks.aggregate_sentiment",
    bind=True,
    max_retries=2,
    acks_late=True,
)
def aggregate_sentiment_task(self, symbols: list[str] | None = None):
    """Aggregate sentiment for all (or specified) symbols.

    Runs the FinBERT pipeline on news data,
    computes 7-day decay-weighted scores, and caches to disk.
    """
    log.info("Sentiment aggregation started: symbols=%s", symbols or "all")
    SessionFactory = get_sync_session_factory()
    try:
        with SessionFactory() as db:
            if not symbols:
                # Recommendation and sentiment coverage must match the same
                # frozen KSE-100 universe, independent of the stocks table seed.
                from app.data.scraper.symbol_universe import get_active_symbols
                symbols_to_process = [item["symbol"] for item in get_active_symbols()]
            else:
                symbols_to_process = [s.upper() for s in symbols]

            processed = 0
            errors = []

            for sym in symbols_to_process:
                try:
                    compute_stock_sentiment_sync(db, sym, days=7)
                    processed += 1
                except Exception as exc:
                    errors.append({"symbol": sym, "error": str(exc)})
                    log.warning("Sentiment failed for %s: %s", sym, exc)

            try:
                compute_market_sentiment_sync(db)
            except Exception as exc:
                errors.append({"symbol": "MARKET", "error": str(exc)})
                log.warning("Market sentiment failed: %s", exc)

            db.commit()
            log.info("Sentiment aggregation completed: processed=%d", processed)
            return {
                "status": "completed",
                "processed": processed,
                "errors": errors,
                "completed_at": datetime.utcnow().isoformat(),
            }
    except Exception as exc:
        log.exception("Sentiment aggregation task failed")
        raise self.retry(exc=exc, countdown=120)


@shared_task(
    name="app.tasks.sentiment_tasks.refresh_single_stock",
    bind=True,
    max_retries=1,
)
def refresh_stock_sentiment_task(self, symbol: str):
    """Refresh sentiment for a single stock (on-demand)."""
    SessionFactory = get_sync_session_factory()
    try:
        with SessionFactory() as db:
            result = compute_stock_sentiment_sync(db, symbol, days=7)
            db.commit()
            return result
    except Exception as exc:
        log.exception("Sentiment refresh failed for %s", symbol)
        raise self.retry(exc=exc, countdown=60)


@shared_task(
    name="app.tasks.sentiment_tasks.rescore_failed_sentiment",
    bind=True,
    max_retries=1,
    acks_late=True,
)
def rescore_failed_sentiment_task(self, limit: int = 50):
    """Retry scoring articles that previously failed FinBERT.

    Runs hourly. Fetches articles with sentiment_status='failed',
    retries FinBERT up to 3 times, updates on success.
    """
    import time
    log.info("Rescore failed sentiment task started")
    SessionFactory = get_sync_session_factory()
    try:
        with SessionFactory() as db:
            articles = (
                db.query(NewsArticle)
                .filter(
                    NewsArticle.sentiment_status == "failed",
                    NewsArticle.source_type == "news",
                )
                .limit(limit)
                .all()
            )

            if not articles:
                log.info("No failed sentiment articles to rescore")
                return {"status": "completed", "retried": 0, "succeeded": 0}

            retried = 0
            succeeded = 0

            for article in articles:
                text_content = f"{article.title}. {article.summary or ''}"
                text_content = text_content[:1500]

                for attempt in range(3):
                    try:
                        sentiment = score_text(text_content)
                        if sentiment and sentiment.get("score") is not None:
                            score = sentiment["score"]
                            label = sentiment["label"]
                            min_conf = 0.6
                            if abs(score) < min_conf:
                                label = "neutral"
                                score = 0.0

                            article.sentiment_label = label
                            article.sentiment_score = round(score, 4)
                            article.sentiment_method = "finbert"
                            article.sentiment_status = "ok"
                            db.flush()
                            succeeded += 1
                            break
                    except Exception:
                        if attempt == 2:
                            raise
                        time.sleep(2 ** attempt)

                retried += 1

            db.commit()
            log.info("Rescore failed sentiment task finished: retried=%d, succeeded=%d", retried, succeeded)
            return {"status": "completed", "retried": retried, "succeeded": succeeded}
    except Exception as exc:
        log.exception("Rescore failed sentiment task failed")
        raise self.retry(exc=exc, countdown=300)
