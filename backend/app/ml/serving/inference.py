"""Inference — dual-model ensemble (GRU v1 + XGB weighted) with confidence gate.

Runs both models on the same symbol/date. Applies ensemble decision logic:
  - Either model near-tie (gap <= 5pp) -> direction = "uncertain"
  - Both non-near-tie AND agree -> return that direction
  - Both non-near-tie AND disagree -> direction = "uncertain"

No HTTP logic here — just data loading, scaling, prediction, and formatting.
"""

import logging
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from app.data.scraper.symbol_universe import get_active_symbols
from app.ml.serving.model_loader import artifacts

log = logging.getLogger(__name__)

FEATURES_PATH = Path("data/features/features_daily.parquet")

NEAR_TIE_THRESHOLD_PP = 5.0


class SymbolNotFoundError(Exception):
    """Raised when the requested symbol is not in the active 98-symbol universe."""
    pass


class InsufficientHistoryError(Exception):
    """Raised when fewer than window_size rows exist for the symbol."""
    pass


def _run_gru(symbol: str, sym_df: pd.DataFrame) -> dict | None:
    """Run GRU inference. Returns dict with direction/probs/gap or None on failure."""
    if not artifacts.model_ready:
        return None

    if len(sym_df) < artifacts.window_size:
        return None

    window_df = sym_df.tail(artifacts.window_size)
    missing_cols = set(artifacts.feature_columns) - set(window_df.columns)
    if missing_cols:
        log.warning("GRU: missing columns for %s: %s", symbol, missing_cols)
        return None

    X = window_df[artifacts.feature_columns].values.astype(np.float32)

    n, T, F = 1, X.shape[0], X.shape[1]
    flat = X.reshape(n * T, F)
    flat = artifacts.scaler.transform(flat)
    X_scaled = flat.reshape(n, T, F)

    proba = artifacts.model.predict(X_scaled, verbose=0)[0]

    bullish_pct = round(float(proba[0]) * 100, 1)
    bearish_pct = round(float(proba[1]) * 100, 1)
    sideways_pct = round(float(proba[2]) * 100, 1)

    total = bullish_pct + bearish_pct + sideways_pct
    if abs(total - 100.0) > 0.5:
        factor = 100.0 / total
        bullish_pct = round(bullish_pct * factor, 1)
        bearish_pct = round(bearish_pct * factor, 1)
        sideways_pct = round(sideways_pct * factor, 1)

    pred_class = int(np.argmax(proba))
    direction = artifacts.label_names.get(pred_class, "unknown")
    top_prob = round(float(np.max(proba)) * 100, 1)

    sorted_probs = sorted(proba, reverse=True)
    gap_pp = round((sorted_probs[0] - sorted_probs[1]) * 100, 1)

    return {
        "direction": direction,
        "bullish_pct": bullish_pct,
        "bearish_pct": bearish_pct,
        "sideways_pct": sideways_pct,
        "top_class_probability": top_prob,
        "gap_pp": gap_pp,
        "model_version": artifacts.model_version,
    }


def _run_xgb(symbol: str, as_of_date: date) -> dict | None:
    """Run XGB inference. Returns dict with direction/probs/gap or None on failure."""
    if not artifacts.xgb_ready or artifacts.xgb_model is None:
        return None

    try:
        xgb_df = pd.read_parquet(artifacts.xgb_data_path)
        xgb_df["date"] = pd.to_datetime(xgb_df["date"])
        xgb_df["date_only"] = xgb_df["date"].dt.date

        sym_xgb = xgb_df[xgb_df["symbol"] == symbol]
        if sym_xgb.empty:
            return None

        rows = sym_xgb[sym_xgb["date_only"] == as_of_date]
        if rows.empty:
            # Try nearest available date
            available = sorted(sym_xgb["date_only"].unique())
            if not available:
                return None
            nearest = min(available, key=lambda d: abs((d - as_of_date).days))
            rows = sym_xgb[sym_xgb["date_only"] == nearest]
            if rows.empty:
                return None

        row = rows.iloc[0]
        feat_values = []
        for fname in artifacts.xgb_feature_names:
            val = row.get(fname, 0.0)
            feat_values.append(float(val) if not pd.isna(val) else 0.0)

        X_pred = np.array([feat_values], dtype=np.float32)
        proba = artifacts.xgb_model.predict_proba(X_pred)[0]

        bullish_pct = round(float(proba[0]) * 100, 1)
        bearish_pct = round(float(proba[1]) * 100, 1)
        sideways_pct = round(float(proba[2]) * 100, 1)

        pred_class = int(np.argmax(proba))
        label_names = {v: k for k, v in artifacts.label_mapping.items()}
        direction = label_names.get(pred_class, "unknown")
        top_prob = round(float(np.max(proba)) * 100, 1)

        sorted_probs = sorted(proba, reverse=True)
        gap_pp = round((sorted_probs[0] - sorted_probs[1]) * 100, 1)

        return {
            "direction": direction,
            "bullish_pct": bullish_pct,
            "bearish_pct": bearish_pct,
            "sideways_pct": sideways_pct,
            "top_class_probability": top_prob,
            "gap_pp": gap_pp,
            "model_version": "xgb_weighted",
        }

    except Exception:
        log.warning("XGB inference failed for %s", symbol, exc_info=True)
        return None


def _ensemble_decide(gru_result: dict | None, xgb_result: dict | None) -> dict:
    """Apply dual-model ensemble decision logic.

    Rules:
      1. If only one model available, use its prediction (no ensemble possible)
      2. If either model has gap <= 5pp -> "uncertain"
      3. If both non-near-tie AND agree -> return that direction
      4. If both non-near-tie AND disagree -> "uncertain"
    """
    has_gru = gru_result is not None
    has_xgb = xgb_result is not None

    # Single model fallback
    if has_gru and not has_xgb:
        return _single_model_result(gru_result, "gru_v1")
    if has_xgb and not has_gru:
        return _single_model_result(xgb_result, "xgb_weighted")

    if not has_gru and not has_xgb:
        return {"direction": "uncertain", "top_class_probability": 0.0,
                "bullish_pct": 0.0, "bearish_pct": 0.0, "sideways_pct": 0.0,
                "model_version": "none", "gate_reason": "no_models_available"}

    # Both models available — apply ensemble rules
    gru_near_tie = gru_result["gap_pp"] <= NEAR_TIE_THRESHOLD_PP
    xgb_near_tie = xgb_result["gap_pp"] <= NEAR_TIE_THRESHOLD_PP

    if gru_near_tie or xgb_near_tie:
        # Rule 2: either near-tie -> uncertain
        # Use the more confident model's probs for the response
        better = gru_result if gru_result["top_class_probability"] >= xgb_result["top_class_probability"] else xgb_result
        reason = []
        if gru_near_tie:
            reason.append(f"gru_gap={gru_result['gap_pp']}pp")
        if xgb_near_tie:
            reason.append(f"xgb_gap={xgb_result['gap_pp']}pp")
        return {
            "direction": "uncertain",
            "bullish_pct": better["bullish_pct"],
            "bearish_pct": better["bearish_pct"],
            "sideways_pct": better["sideways_pct"],
            "top_class_probability": better["top_class_probability"],
            "model_version": "ensemble",
            "gate_reason": f"near_tie({', '.join(reason)})",
        }

    # Both non-near-tie — check agreement
    if gru_result["direction"] == xgb_result["direction"]:
        # Rule 3: agree -> return that direction
        avg_top = round((gru_result["top_class_probability"] + xgb_result["top_class_probability"]) / 2, 1)
        avg_bull = round((gru_result["bullish_pct"] + xgb_result["bullish_pct"]) / 2, 1)
        avg_bear = round((gru_result["bearish_pct"] + xgb_result["bearish_pct"]) / 2, 1)
        avg_side = round((gru_result["sideways_pct"] + xgb_result["sideways_pct"]) / 2, 1)
        return {
            "direction": gru_result["direction"],
            "bullish_pct": avg_bull,
            "bearish_pct": avg_bear,
            "sideways_pct": avg_side,
            "top_class_probability": avg_top,
            "model_version": "ensemble",
            "gate_reason": f"agree({gru_result['direction']})",
        }

    # Rule 4: disagree -> uncertain
    return {
        "direction": "uncertain",
        "bullish_pct": 0.0,
        "bearish_pct": 0.0,
        "sideways_pct": 0.0,
        "top_class_probability": 0.0,
        "model_version": "ensemble",
        "gate_reason": f"disagree(gru={gru_result['direction']}, xgb={xgb_result['direction']})",
    }


def _single_model_result(result: dict, model_name: str) -> dict:
    """Wrap a single-model result with ensemble metadata."""
    gate_reason = "single_model"
    if result["gap_pp"] <= NEAR_TIE_THRESHOLD_PP:
        gate_reason = f"single_model_near_tie(gap={result['gap_pp']}pp)"
    return {
        "direction": result["direction"],
        "bullish_pct": result["bullish_pct"],
        "bearish_pct": result["bearish_pct"],
        "sideways_pct": result["sideways_pct"],
        "top_class_probability": result["top_class_probability"],
        "model_version": model_name,
        "gate_reason": gate_reason,
    }


def get_forecast(symbol: str, horizon: str = "1D") -> dict:
    """Run dual-model ensemble inference for a single symbol.

    Parameters
    ----------
    symbol : str
        PSX stock symbol (e.g. "OGDC").
    horizon : str
        Forecast horizon: "1D", "1W", or "1M".

    Returns
    -------
    dict with keys: symbol, horizon, direction, bullish_pct, bearish_pct,
    sideways_pct, top_class_probability, as_of_date, predicted_for_date,
    model_version, model_details.
    """
    symbol = symbol.upper()

    # ── Validate symbol ────────────────────────────────────────────────
    active = get_active_symbols()
    active_symbols = {e["symbol"] for e in active}
    if symbol not in active_symbols:
        raise SymbolNotFoundError(
            f"Symbol '{symbol}' is not in the active {len(active_symbols)}-symbol universe"
        )

    # ── Load feature data ──────────────────────────────────────────────
    df = pd.read_parquet(FEATURES_PATH)
    sym_df = df[df["symbol"] == symbol].copy()
    sym_df["date"] = pd.to_datetime(sym_df["date"])
    sym_df = sym_df.sort_values("date").reset_index(drop=True)

    as_of_date = sym_df["date"].iloc[-1].date()

    # ── Run both models ────────────────────────────────────────────────
    gru_result = _run_gru(symbol, sym_df)
    xgb_result = _run_xgb(symbol, as_of_date)

    # ── Ensemble decision ──────────────────────────────────────────────
    ensemble = _ensemble_decide(gru_result, xgb_result)

    # ── Calculate predicted_for_date based on horizon ──────────────────
    HORIZON_DAYS = {"1D": 1, "1W": 5, "1M": 22}
    biz_days = HORIZON_DAYS.get(horizon, 1)

    predicted_for_date = as_of_date
    days_added = 0
    while days_added < biz_days:
        predicted_for_date += timedelta(days=1)
        if predicted_for_date.weekday() < 5:
            days_added += 1

    # ── Build model_details (debug/analysis field) ─────────────────────
    model_details = {}
    if gru_result:
        model_details["gru_v1"] = {
            "direction": gru_result["direction"],
            "bullish_pct": gru_result["bullish_pct"],
            "bearish_pct": gru_result["bearish_pct"],
            "sideways_pct": gru_result["sideways_pct"],
            "top_class_probability": gru_result["top_class_probability"],
            "gap_pp": gru_result["gap_pp"],
        }
    if xgb_result:
        model_details["xgb_weighted"] = {
            "direction": xgb_result["direction"],
            "bullish_pct": xgb_result["bullish_pct"],
            "bearish_pct": xgb_result["bearish_pct"],
            "sideways_pct": xgb_result["sideways_pct"],
            "top_class_probability": xgb_result["top_class_probability"],
            "gap_pp": xgb_result["gap_pp"],
        }

    # ── Build market_context (informational, doesn't affect gate) ────────
    market_ctx = None
    latest_row = sym_df.iloc[-1]
    idx_5d = latest_row.get("index_return_5d")
    idx_20d = latest_row.get("index_return_20d")
    rel_20d = latest_row.get("stock_relative_return_20d")

    # Compute raw stock 20d return if available
    stock_ret_20d = None
    if len(sym_df) >= 20:
        close_now = float(latest_row["close"])
        close_20d_ago = float(sym_df.iloc[-20]["close"])
        if close_20d_ago > 0:
            stock_ret_20d = round((close_now - close_20d_ago) / close_20d_ago, 6)

    if pd.notna(idx_5d) or pd.notna(idx_20d):
        market_ctx = {
            "market_return_5d": round(float(idx_5d), 6) if pd.notna(idx_5d) else None,
            "market_return_20d": round(float(idx_20d), 6) if pd.notna(idx_20d) else None,
            "stock_return_20d": stock_ret_20d,
            "stock_relative_return_20d": round(float(rel_20d), 6) if pd.notna(rel_20d) else None,
        }

    log.info("Forecast %s: %s (%.1f%%) gate=%s as_of=%s for=%s horizon=%s",
             symbol, ensemble["direction"], ensemble["top_class_probability"],
             ensemble.get("gate_reason", "?"), as_of_date, predicted_for_date, horizon)

    return {
        "symbol": symbol,
        "horizon": horizon,
        "direction": ensemble["direction"],
        "bullish_pct": ensemble["bullish_pct"],
        "bearish_pct": ensemble["bearish_pct"],
        "sideways_pct": ensemble["sideways_pct"],
        "top_class_probability": ensemble["top_class_probability"],
        "as_of_date": as_of_date,
        "predicted_for_date": predicted_for_date,
        "model_version": ensemble["model_version"],
        "model_details": model_details,
        "gate_reason": ensemble.get("gate_reason", ""),
        "market_context": market_ctx,
    }
