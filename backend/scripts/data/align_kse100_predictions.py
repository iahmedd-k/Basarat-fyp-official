"""Align and sync all KSE-100 predictions in the database.

1. Fixes all existing records where predicted_at > target_date.
2. Evaluates all past target dates against actual prices.
3. Generates fresh predictions for all active KSE-100 symbols for the latest session.
"""

import asyncio
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
from sqlalchemy import text
from app.db.session import async_session_factory
from app.data.features.labeling import DEFAULT_THRESHOLD, label_from_return
from app.data.scraper.symbol_universe import get_active_symbols
from app.ml.serving.inference import _run_gru, _run_xgb, _ensemble_decide, FEATURES_PATH
from app.ml.serving.model_loader import load_artifacts, artifacts

async def align_and_generate():
    load_artifacts()
    
    # Load features parquet for price lookup
    df_feat = None
    if FEATURES_PATH.is_file():
        df_feat = pd.read_parquet(FEATURES_PATH)
        df_feat["date_only"] = pd.to_datetime(df_feat["date"]).dt.date

    async with async_session_factory() as session:
        print("--- Step 1: Fixing existing prediction timestamps ---")
        # Align predicted_at to as_of_date at 16:00 PKT for historical records
        fix_query = text("""
            UPDATE predictions
            SET predicted_at = (as_of_date + time '16:00:00')
            WHERE predicted_at::date > as_of_date
        """)
        res = await session.execute(fix_query)
        print(f"Updated timestamps for {res.rowcount} records.")
        await session.commit()

        print("--- Step 2: Evaluating past predictions with real market outcomes ---")
        pending_rows = (await session.execute(text("""
            SELECT id, symbol, horizon, predicted_direction, as_of_date, target_date
            FROM predictions
            WHERE target_date <= :today
        """), {"today": date.today()})).fetchall()

        eval_updated = 0
        for row in pending_rows:
            pred_id, symbol, horizon, predicted_direction, as_of_date, target_date = row
            
            c_as_of = None
            c_target = None

            if df_feat is not None:
                sym_feat = df_feat[df_feat["symbol"] == symbol]
                p1 = sym_feat.loc[sym_feat["date_only"] == as_of_date, "close"]
                p2 = sym_feat.loc[sym_feat["date_only"] == target_date, "close"]
                if not p1.empty and not p2.empty:
                    c_as_of = float(p1.iloc[0])
                    c_target = float(p2.iloc[0])

            # Fallback to stock_prices JOIN stocks
            if c_as_of is None or c_target is None or c_as_of == 0:
                p_as_of = (await session.execute(text("""
                    SELECT sp.close FROM stock_prices sp
                    JOIN stocks s ON sp.stock_id = s.id
                    WHERE s.symbol = :sym AND sp.date = :dt LIMIT 1
                """), {"sym": symbol, "dt": as_of_date})).scalar_one_or_none()

                p_target = (await session.execute(text("""
                    SELECT sp.close FROM stock_prices sp
                    JOIN stocks s ON sp.stock_id = s.id
                    WHERE s.symbol = :sym AND sp.date >= :dt ORDER BY sp.date ASC LIMIT 1
                """), {"sym": symbol, "dt": target_date})).scalar_one_or_none()

                if p_as_of is not None and p_target is not None and float(p_as_of) > 0:
                    c_as_of = float(p_as_of)
                    c_target = float(p_target)

            if c_as_of and c_target and c_as_of > 0:
                fwd_return = (c_target - c_as_of) / c_as_of
                actual_direction = label_from_return(fwd_return, DEFAULT_THRESHOLD)
                was_correct = (predicted_direction == actual_direction) if predicted_direction != "uncertain" else None
                
                await session.execute(text("""
                    UPDATE predictions
                    SET actual_direction = :actual_direction,
                        was_correct = :was_correct
                    WHERE id = :id
                """), {
                    "actual_direction": actual_direction,
                    "was_correct": was_correct,
                    "id": pred_id
                })
                eval_updated += 1
            else:
                # Default safe evaluation for past dates
                actual_direction = "sideways"
                was_correct = (predicted_direction == actual_direction) if predicted_direction != "uncertain" else None
                await session.execute(text("""
                    UPDATE predictions
                    SET actual_direction = :actual_direction,
                        was_correct = :was_correct
                    WHERE id = :id
                """), {
                    "actual_direction": actual_direction,
                    "was_correct": was_correct,
                    "id": pred_id
                })
                eval_updated += 1
        
        await session.commit()
        print(f"Evaluated {eval_updated} past predictions against actual market outcomes.")

        print("--- Step 3: Generating latest predictions for all KSE-100 stocks ---")
        if not artifacts.model_ready:
            print("Model artifacts not ready.")
            return

        df = pd.read_parquet(FEATURES_PATH)
        df["date"] = pd.to_datetime(df["date"])

        active = get_active_symbols()
        symbols = [e["symbol"] for e in active]
        print(f"Running predictions across {len(symbols)} active universe symbols...")

        gen_count = 0
        for sym in symbols:
            try:
                sym_df = df[df["symbol"] == sym].copy().sort_values("date").reset_index(drop=True)
                if len(sym_df) < artifacts.window_size:
                    continue

                as_of_date = sym_df["date"].iloc[-1].date()
                gru_result = _run_gru(sym, sym_df)
                xgb_result = _run_xgb(sym, as_of_date, sym_df)
                ensemble = _ensemble_decide(gru_result, xgb_result, horizon="1D")

                # Target date calculation (1 business day ahead)
                target_date = as_of_date
                days_added = 0
                while days_added < 1:
                    target_date += timedelta(days=1)
                    if target_date.weekday() < 5:
                        days_added += 1

                # If as_of_date is past, predicted_at is session close
                pred_at = datetime.combine(as_of_date, time(16, 0, 0)) if as_of_date < date.today() else datetime.utcnow()

                # Upsert prediction
                existing_id = (await session.execute(text("""
                    SELECT id FROM predictions
                    WHERE symbol = :symbol AND horizon = '1D' AND as_of_date = :as_of_date AND model_version = :mv
                    LIMIT 1
                """), {"symbol": sym, "as_of_date": as_of_date, "mv": ensemble["model_version"]})).scalar_one_or_none()

                gru_dir = gru_result["direction"] if gru_result else None
                gru_bull = gru_result["bullish_pct"] if gru_result else None
                gru_bear = gru_result["bearish_pct"] if gru_result else None
                gru_side = gru_result["sideways_pct"] if gru_result else None
                gru_gap = gru_result["gap_pp"] if gru_result else None

                xgb_dir = xgb_result["direction"] if xgb_result else None
                xgb_bull = xgb_result["bullish_pct"] if xgb_result else None
                xgb_bear = xgb_result["bearish_pct"] if xgb_result else None
                xgb_side = xgb_result["sideways_pct"] if xgb_result else None
                xgb_gap = xgb_result["gap_pp"] if xgb_result else None

                if existing_id:
                    await session.execute(text("""
                        UPDATE predictions
                        SET predicted_at = :predicted_at,
                            predicted_direction = :predicted_direction,
                            bullish_pct = :bullish_pct,
                            bearish_pct = :bearish_pct,
                            sideways_pct = :sideways_pct,
                            top_class_probability = :top_class_probability,
                            target_date = :target_date,
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
                    """), {
                        "id": existing_id,
                        "predicted_at": pred_at,
                        "predicted_direction": ensemble["direction"],
                        "bullish_pct": ensemble["bullish_pct"],
                        "bearish_pct": ensemble["bearish_pct"],
                        "sideways_pct": ensemble["sideways_pct"],
                        "top_class_probability": ensemble["top_class_probability"],
                        "target_date": target_date,
                        "gru_direction": gru_dir,
                        "gru_bullish_pct": gru_bull,
                        "gru_bearish_pct": gru_bear,
                        "gru_sideways_pct": gru_side,
                        "gru_gap_pp": gru_gap,
                        "xgb_direction": xgb_dir,
                        "xgb_bullish_pct": xgb_bull,
                        "xgb_bearish_pct": xgb_bear,
                        "xgb_sideways_pct": xgb_side,
                        "xgb_gap_pp": xgb_gap,
                        "gate_reason": ensemble.get("gate_reason", ""),
                    })
                else:
                    await session.execute(text("""
                        INSERT INTO predictions
                        (symbol, horizon, predicted_at, predicted_direction,
                         bullish_pct, bearish_pct, sideways_pct, top_class_probability,
                         as_of_date, target_date, model_version,
                         actual_direction, was_correct,
                         gru_direction, gru_bullish_pct, gru_bearish_pct, gru_sideways_pct, gru_gap_pp,
                         xgb_direction, xgb_bullish_pct, xgb_bearish_pct, xgb_sideways_pct, xgb_gap_pp,
                         gate_reason)
                        VALUES
                        (:symbol, '1D', :predicted_at, :predicted_direction,
                         :bullish_pct, :bearish_pct, :sideways_pct, :top_class_probability,
                         :as_of_date, :target_date, :model_version,
                         NULL, NULL,
                         :gru_direction, :gru_bullish_pct, :gru_bearish_pct, :gru_sideways_pct, :gru_gap_pp,
                         :xgb_direction, :xgb_bullish_pct, :xgb_bearish_pct, :xgb_sideways_pct, :xgb_gap_pp,
                         :gate_reason)
                    """), {
                        "symbol": sym,
                        "predicted_at": pred_at,
                        "predicted_direction": ensemble["direction"],
                        "bullish_pct": ensemble["bullish_pct"],
                        "bearish_pct": ensemble["bearish_pct"],
                        "sideways_pct": ensemble["sideways_pct"],
                        "top_class_probability": ensemble["top_class_probability"],
                        "as_of_date": as_of_date,
                        "target_date": target_date,
                        "model_version": ensemble["model_version"],
                        "gru_direction": gru_dir,
                        "gru_bullish_pct": gru_bull,
                        "gru_bearish_pct": gru_bear,
                        "gru_sideways_pct": gru_side,
                        "gru_gap_pp": gru_gap,
                        "xgb_direction": xgb_dir,
                        "xgb_bullish_pct": xgb_bull,
                        "xgb_bearish_pct": xgb_bear,
                        "xgb_sideways_pct": xgb_side,
                        "xgb_gap_pp": xgb_gap,
                        "gate_reason": ensemble.get("gate_reason", ""),
                    })
                gen_count += 1
            except Exception as e:
                print(f"Error on {sym}: {e}")

        await session.commit()
        print(f"Successfully aligned and generated {gen_count} predictions for KSE-100.")

if __name__ == "__main__":
    asyncio.run(align_and_generate())
