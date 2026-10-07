"""Sync and refresh recommendations cache and database predictions to 2026-10-06."""

import asyncio
import json
import logging
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import numpy as np
import pandas as pd
from sqlalchemy import text

from app.db.base import async_session_factory
from app.services.recommendation_service import (
    BUY_THRESHOLD,
    SELL_THRESHOLD,
    FEATURES_PATH,
    RECOMMENDATIONS_CACHE,
    RecommendationEngine,
    save_recommendations_cache,
)
from app.ml.serving.inference import (
    _run_gru,
    _run_xgb,
    _ensemble_decide,
)
from app.ml.serving.model_loader import load_artifacts, artifacts
from app.api.v1.recommendations import _apply_freshness_guard

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("refresh_latest")

def update_recommendations_cache():
    if not RECOMMENDATIONS_CACHE.exists():
        log.error("Cache file %s does not exist", RECOMMENDATIONS_CACHE)
        return

    cache_data = json.loads(RECOMMENDATIONS_CACHE.read_text(encoding="utf-8"))
    existing_recs = cache_data.get("recommendations", [])
    log.info("Loaded %d existing cached recommendations", len(existing_recs))

    df_feat = pd.read_parquet(FEATURES_PATH)
    df_feat["date"] = pd.to_datetime(df_feat["date"])

    engine = RecommendationEngine()
    load_artifacts()

    updated_recs = []
    today = date(2026, 10, 7)

    for item in existing_recs:
        sym = item.get("symbol")
        sym_feat = df_feat[df_feat["symbol"] == sym].sort_values("date").reset_index(drop=True)
        if sym_feat.empty:
            updated_recs.append(item)
            continue

        last_row = sym_feat.iloc[-1]
        as_of = last_row["date"].date()
        last_close = float(last_row.get("close", 0.0))

        # 1. Technical signal
        tech_score, tech_reasoning = engine._technical_signal(sym_feat, symbol=sym)

        # 2. ML forecast signal
        gru_res = _run_gru(sym, sym_feat)
        xgb_res = _run_xgb(sym, as_of, sym_feat, horizon="1W")
        ensemble = _ensemble_decide(gru_res, xgb_res, horizon="1W")

        p_bull = float(ensemble.get("bullish_pct", 33.3)) / 100.0
        p_bear = float(ensemble.get("bearish_pct", 33.3)) / 100.0
        ml_score = float(np.clip(p_bull - p_bear, -1.0, 1.0))
        ml_reasoning = {
            "status": "available",
            "model": "forecast ensemble",
            "model_version": ensemble.get("model_version", "ensemble"),
            "direction": ensemble.get("direction", "sideways"),
            "gate_reason": ensemble.get("gate_reason", "ok"),
            "as_of_date": as_of.isoformat(),
            "signal_bias": "Bullish" if ml_score > 0.1 else "Bearish" if ml_score < -0.1 else "Neutral",
            "prob_bullish": round(p_bull, 4),
            "prob_bearish": round(p_bear, 4),
            "prob_sideways": round(float(ensemble.get("sideways_pct", 33.4)) / 100.0, 4),
            "probabilities_calibrated": False,
        }

        # 3. Fundamental signal (keep cached score/metrics, or calculate)
        fund_score = float(item.get("signals", {}).get("fundamental", 0.0) or 0.0)
        fund_reasoning = item.get("reasoning", {}).get("fundamental") or {"status": "available"}

        # 4. Sentiment signal (keep cached sentiment)
        sentiment_score = float(item.get("signals", {}).get("sentiment", 0.0) or 0.0)
        sentiment_reasoning = item.get("reasoning", {}).get("sentiment") or {"status": "available"}
        if isinstance(sentiment_reasoning, dict):
            sentiment_reasoning["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Synthesis
        w = engine.weights
        components = [
            ("gru", ml_score, ml_reasoning),
            ("technical", tech_score, tech_reasoning),
            ("fundamental", fund_score, fund_reasoning),
            ("sentiment", sentiment_score, sentiment_reasoning),
        ]
        available = [(key, score, reason) for key, score, reason in components if reason.get("status") != "unavailable"]
        active_weight_total = sum(float(w.get(key, 0.0)) for key, _, _ in available)
        effective_weights = {
            key: (float(w.get(key, 0.0)) / active_weight_total if active_weight_total else 0.0)
            for key, _, _ in available
        }
        composite = sum(effective_weights[key] * score for key, score, _ in available) if active_weight_total else 0.0

        if composite > BUY_THRESHOLD:
            verdict = "buy"
            decision_reason = f"Composite score {composite:.3f} crossed the BUY threshold ({BUY_THRESHOLD:.2f})."
        elif composite < SELL_THRESHOLD:
            verdict = "sell"
            decision_reason = f"Composite score {composite:.3f} crossed the SELL threshold ({SELL_THRESHOLD:.2f})."
        else:
            verdict = "hold"
            decision_reason = f"Composite score {composite:.3f} is between thresholds."

        scores = [score for _, score, _ in available]
        score_std = float(np.std(scores)) if len(scores) > 1 else 0.5
        agreement = max(0.2, 1.0 - (score_std / 1.5))
        coverage_factor = len(available) / float(len(components))
        magnitude = min(abs(composite) / 0.5, 1.0)
        confidence = round(min(1.0, max(0.0, magnitude * agreement * coverage_factor)), 4)

        # Target / stop calculation
        target_stop = engine.compute_target_stop(
            sym, sym_feat, "moderate", ml_direction=verdict, horizon="1W", current_price_override=last_close
        )

        new_rec = {
            "symbol": sym,
            "name": item.get("name") or sym,
            "sector": item.get("sector"),
            "signal": verdict,
            "decision_reason": decision_reason,
            "confidence": confidence,
            "composite_score": round(composite, 4),
            "signals": {
                "ml": round(ml_score, 4),
                "technical": round(tech_score, 4),
                "fundamental": round(fund_score, 4),
                "sentiment": round(sentiment_score, 4),
            },
            "weights": w,
            "effective_weights": effective_weights,
            "status": "available",
            "data_as_of": as_of.isoformat(),
            "quote_as_of": datetime.combine(as_of, time(16, 0, 0), tzinfo=timezone.utc).isoformat(),
            "quote_is_stale": False,
            "target_price": target_stop.get("target_price"),
            "stop_loss": target_stop.get("stop_loss"),
            "expected_range": target_stop.get("expected_range"),
            "upside_pct": target_stop.get("upside_pct"),
            "downside_pct": target_stop.get("downside_pct"),
            "risk_reward_ratio": target_stop.get("risk_reward_ratio"),
            "target_stop_method": target_stop.get("method"),
            "target_stop_reason": "ATR-based target and stop-loss levels.",
            "reasoning": {
                "ml": ml_reasoning,
                "technical": tech_reasoning,
                "fundamental": fund_reasoning,
                "sentiment": sentiment_reasoning,
            },
            "current_price": last_close,
            "atr_14": target_stop.get("atr_14"),
        }

        # Apply freshness guard to verify
        guarded = _apply_freshness_guard(new_rec, today=today)
        new_rec.update({
            "data_freshness": guarded.get("data_freshness"),
            "data_age_calendar_days": guarded.get("data_age_calendar_days"),
            "data_age_trading_days": guarded.get("data_age_trading_days"),
            "signal_suppressed": guarded.get("signal_suppressed", False),
            "suppression_reason": guarded.get("suppression_reason"),
        })

        updated_recs.append(new_rec)

    updated_recs.sort(key=lambda r: float(r.get("composite_score", 0.0) or 0.0), reverse=True)
    save_recommendations_cache(updated_recs)
    log.info("Saved %d updated recommendations to cache. Sample data_as_of: %s, freshness: %s, suppressed: %s",
             len(updated_recs), updated_recs[0]["data_as_of"], updated_recs[0].get("data_freshness"),
             updated_recs[0].get("signal_suppressed"))

async def update_db_predictions():
    log.info("Connecting to database to sync predictions up to 2026-10-06...")
    df_feat = pd.read_parquet(FEATURES_PATH)
    df_feat["date"] = pd.to_datetime(df_feat["date"])

    from app.data.scraper.symbol_universe import get_active_symbols
    active = get_active_symbols()
    symbols = [e["symbol"] for e in active]

    load_artifacts()

    async with async_session_factory() as session:
        # Step 1: Evaluate past predictions
        log.info("Evaluating past predictions...")
        eval_query = text("""
            SELECT id, symbol, horizon, predicted_direction, as_of_date, target_date
            FROM predictions
            WHERE target_date <= :as_of AND (actual_direction IS NULL OR was_correct IS NULL)
        """)
        pending = (await session.execute(eval_query, {"as_of": date(2026, 10, 6)})).fetchall()
        log.info("Found %d pending historical predictions to evaluate", len(pending))

        for row in pending:
            p_id, sym, horiz, pred_dir, as_of_dt, target_dt = row
            sym_df = df_feat[df_feat["symbol"] == sym]
            c_as_of = sym_df.loc[sym_df["date"].dt.date == as_of_dt, "close"]
            c_target = sym_df.loc[sym_df["date"].dt.date == target_dt, "close"]

            if not c_as_of.empty and not c_target.empty and float(c_as_of.iloc[0]) > 0:
                p1 = float(c_as_of.iloc[0])
                p2 = float(c_target.iloc[0])
                ret = (p2 - p1) / p1
                actual_dir = "bullish" if ret > 0.015 else ("bearish" if ret < -0.015 else "sideways")
                correct = (pred_dir == actual_dir) if pred_dir != "uncertain" else None
                await session.execute(text("""
                    UPDATE predictions
                    SET actual_direction = :actual_direction, was_correct = :was_correct
                    WHERE id = :id
                """), {"actual_direction": actual_dir, "was_correct": correct, "id": p_id})

        await session.commit()
        log.info("Evaluated past predictions.")

        # Step 2: Generate/upsert predictions for 2026-10-06 session
        log.info("Upserting latest 2026-10-06 predictions for all active KSE-100 symbols...")
        as_of_session = date(2026, 10, 6)
        pred_at = datetime.combine(as_of_session, time(16, 0, 0))

        upsert_count = 0
        for sym in symbols:
            sym_df = df_feat[df_feat["symbol"] == sym].sort_values("date").reset_index(drop=True)
            if sym_df.empty or len(sym_df) < artifacts.window_size:
                continue

            for horizon, biz_days in [("1D", 1), ("1W", 5), ("2W", 10), ("1M", 22)]:
                gru_res = _run_gru(sym, sym_df)
                xgb_res = _run_xgb(sym, as_of_session, sym_df, horizon=horizon)
                ens = _ensemble_decide(gru_res, xgb_res, horizon=horizon)

                # target date
                t_date = as_of_session
                added = 0
                while added < biz_days:
                    t_date += timedelta(days=1)
                    if t_date.weekday() < 5:
                        added += 1

                # Upsert into predictions
                check_q = text("""
                    SELECT id FROM predictions
                    WHERE symbol = :symbol AND horizon = :horizon AND as_of_date = :as_of
                    LIMIT 1
                """)
                existing_id = (await session.execute(check_q, {"symbol": sym, "horizon": horizon, "as_of": as_of_session})).scalar_one_or_none()

                payload = {
                    "symbol": sym,
                    "horizon": horizon,
                    "predicted_at": pred_at,
                    "predicted_direction": ens["direction"],
                    "bullish_pct": ens["bullish_pct"],
                    "bearish_pct": ens["bearish_pct"],
                    "sideways_pct": ens["sideways_pct"],
                    "top_class_probability": ens["top_class_probability"],
                    "as_of_date": as_of_session,
                    "target_date": t_date,
                    "model_version": ens["model_version"],
                    "gru_direction": gru_res["direction"] if gru_res else None,
                    "gru_bullish_pct": gru_res["bullish_pct"] if gru_res else None,
                    "gru_bearish_pct": gru_res["bearish_pct"] if gru_res else None,
                    "gru_sideways_pct": gru_res["sideways_pct"] if gru_res else None,
                    "gru_gap_pp": gru_res["gap_pp"] if gru_res else None,
                    "xgb_direction": xgb_res["direction"] if xgb_res else None,
                    "xgb_bullish_pct": xgb_res["bullish_pct"] if xgb_res else None,
                    "xgb_bearish_pct": xgb_res["bearish_pct"] if xgb_res else None,
                    "xgb_sideways_pct": xgb_res["sideways_pct"] if xgb_res else None,
                    "xgb_gap_pp": xgb_res["gap_pp"] if xgb_res else None,
                    "gate_reason": ens.get("gate_reason"),
                }

                if existing_id:
                    payload["id"] = existing_id
                    await session.execute(text("""
                        UPDATE predictions
                        SET predicted_at = :predicted_at,
                            predicted_direction = :predicted_direction,
                            bullish_pct = :bullish_pct,
                            bearish_pct = :bearish_pct,
                            sideways_pct = :sideways_pct,
                            top_class_probability = :top_class_probability,
                            target_date = :target_date,
                            model_version = :model_version,
                            gru_direction = :gru_direction,
                            gru_bullish_pct = :gru_bullish_pct,
                            gru_bearish_pct = :gru_bearish_pct,
                            gru_sideways_pct = :gru_sideways_pct,
                            gru_gap_pp = :gru_gap_pp,
                            xgb_direction = :xgb_direction,
                            xgb_bullish_pct = :xgb_bullish_pct,
                            xgb_bearish_pct = :xgb_bearish_pct,
                            xgb_sideways_pct = :xgb_sideways_pct,
                            xgb_gap_pp = :xgb_gap_pp,
                            gate_reason = :gate_reason
                        WHERE id = :id
                    """), payload)
                else:
                    await session.execute(text("""
                        INSERT INTO predictions (
                            symbol, horizon, predicted_at, predicted_direction,
                            bullish_pct, bearish_pct, sideways_pct, top_class_probability,
                            as_of_date, target_date, model_version,
                            gru_direction, gru_bullish_pct, gru_bearish_pct, gru_sideways_pct, gru_gap_pp,
                            xgb_direction, xgb_bullish_pct, xgb_bearish_pct, xgb_sideways_pct, xgb_gap_pp,
                            gate_reason
                        ) VALUES (
                            :symbol, :horizon, :predicted_at, :predicted_direction,
                            :bullish_pct, :bearish_pct, :sideways_pct, :top_class_probability,
                            :as_of_date, :target_date, :model_version,
                            :gru_direction, :gru_bullish_pct, :gru_bearish_pct, :gru_sideways_pct, :gru_gap_pp,
                            :xgb_direction, :xgb_bullish_pct, :xgb_bearish_pct, :xgb_sideways_pct, :xgb_gap_pp,
                            :gate_reason
                        )
                    """), payload)
                upsert_count += 1

        await session.commit()
        log.info("Successfully upserted %d predictions for 2026-10-06 across horizons!", upsert_count)

if __name__ == "__main__":
    update_recommendations_cache()
    asyncio.run(update_db_predictions())
