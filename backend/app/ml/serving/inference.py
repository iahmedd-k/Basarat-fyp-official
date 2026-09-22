"""Inference — dual-model ensemble (GRU v1 + XGB weighted) with confidence gate.

Runs both models on the same symbol/date. Applies ensemble decision logic:
  - Either model near-tie (gap <= threshold) -> direction = "uncertain"
  - Both non-near-tie AND agree -> return that direction
  - Both non-near-tie AND disagree -> blend probabilities

The near-tie threshold is configurable via ``near_tie_threshold_pp``
(default NEAR_TIE_THRESHOLD_PP = 5.0pp).

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

ROOT_DIR = Path(__file__).resolve().parents[3]
FEATURES_PATH = ROOT_DIR / "data" / "features" / "features_daily.parquet"

NEAR_TIE_THRESHOLD_PP = 5.0


def compute_confidence(class_probabilities: dict[str, float]) -> float:
    """Uncalibrated top-class probability mass (Task 4).

    Returns the maximum probability value from the class distribution.
    Note: If probability calibration is not active, this represents raw model probability mass,
    not a calibrated confidence score.
    """
    return max(class_probabilities.values())


class SymbolNotFoundError(Exception):
    """Raised when the requested symbol is not in the active 98-symbol universe."""
    pass


class InsufficientHistoryError(Exception):
    """Raised when fewer than window_size rows exist for the symbol."""
    pass


class FeatureMismatchError(Exception):
    """Raised when required model features are missing or misaligned (Task 19)."""
    pass


def _run_gru(symbol: str, sym_df: pd.DataFrame) -> dict | None:
    """Run GRU inference. Returns dict with direction/probs/gap or raises FeatureMismatchError on feature missing."""
    if not artifacts.model_ready:
        return None

    if len(sym_df) < artifacts.window_size:
        return None

    window_df = sym_df.tail(artifacts.window_size)
    missing_cols = set(artifacts.feature_columns) - set(window_df.columns)
    if missing_cols:
        raise FeatureMismatchError(
            f"GRU feature validation failed for {symbol}: missing required features {sorted(missing_cols)}"
        )

    # Strictly select features in the exact metadata order (Task 19)
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

    # gap_pp: difference between top two probabilities in percentage points (Task 16)
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


def _run_xgb(symbol: str, as_of_date: date, sym_df: pd.DataFrame | None = None) -> dict | None:
    """Run XGB inference. Returns dict with direction/probs/gap or None on failure."""
    if not artifacts.xgb_ready or artifacts.xgb_model is None:
        return None

    try:
        row = None
        if sym_df is not None and not sym_df.empty:
            row = sym_df.iloc[-1]
        elif artifacts.xgb_data_path.exists():
            xgb_df = pd.read_parquet(artifacts.xgb_data_path)
            xgb_df["date"] = pd.to_datetime(xgb_df["date"])
            xgb_df["date_only"] = xgb_df["date"].dt.date

            sym_xgb = xgb_df[xgb_df["symbol"] == symbol]
            if not sym_xgb.empty:
                rows = sym_xgb[sym_xgb["date_only"] == as_of_date]
                if rows.empty:
                    available = sorted(sym_xgb["date_only"].unique())
                    if available:
                        nearest = min(available, key=lambda d: abs((d - as_of_date).days))
                        rows = sym_xgb[sym_xgb["date_only"] == nearest]
                if not rows.empty:
                    row = rows.iloc[0]

        if row is None:
            return None

        feat_values = []
        for fname in artifacts.xgb_feature_names:
            raw_fn = fname.replace("_csrank", "")
            val = row.get(fname, row.get(raw_fn, 0.50))
            feat_values.append(float(val) if pd.notna(val) else 0.50)

        X_pred = np.array([feat_values], dtype=np.float32)
        proba = artifacts.xgb_model.predict_proba(X_pred)[0]

        if len(proba) == 2:
            p_buy = float(proba[0])
            p_sell = float(proba[1])
            bullish_pct = round(p_buy * 100, 1)
            bearish_pct = round(p_sell * 100, 1)
            sideways_pct = 0.0
            direction = "bullish" if p_buy > 0.50 else "bearish" if p_sell > 0.50 else "sideways"
            top_prob = round(max(p_buy, p_sell) * 100, 1)
            gap_pp = round(abs(p_buy - p_sell) * 100, 1)
        else:
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
            "model_version": getattr(artifacts, "xgb_model_version", "xgb_v3_production"),
        }

    except Exception:
        log.warning("XGB inference failed for %s", symbol, exc_info=True)
        return None


def _ensemble_decide(
    gru_result: dict | None,
    xgb_result: dict | None,
    near_tie_threshold_pp: float = NEAR_TIE_THRESHOLD_PP,
) -> dict:
    """Apply dual-model ensemble decision logic.

    Rules:
      1. If only one model available, use its prediction (no ensemble possible)
      2. If either model has gap <= near_tie_threshold_pp -> "uncertain"
      3. If both non-near-tie AND agree (same predicted class) -> return that direction
      4. If both non-near-tie AND disagree -> blend probabilities

    Note on terminology (Task 17 & Task 16):
      - 'agree(direction)': Both models selected the exact same predicted class label.
        Does NOT imply matching probability distributions or calibrated confidence.
      - 'gap_pp': Absolute difference between top-1 and top-2 class probabilities in percentage points.

    Parameters
    ----------
    gru_result : dict from _run_gru() or None
    xgb_result : dict from _run_xgb() or None
    near_tie_threshold_pp : float
        Gap threshold in percentage points (default: 5.0pp).
    """
    has_gru = gru_result is not None
    has_xgb = xgb_result is not None

    # Single model fallback
    if has_gru and not has_xgb:
        return _single_model_result(gru_result, "gru_v1", near_tie_threshold_pp)
    if has_xgb and not has_gru:
        return _single_model_result(xgb_result, "xgb_weighted", near_tie_threshold_pp)

    if not has_gru and not has_xgb:
        return {"direction": "uncertain", "top_class_probability": 0.0,
                "bullish_pct": 0.0, "bearish_pct": 0.0, "sideways_pct": 0.0,
                "model_version": "none", "gate_reason": "no_models_available",
                "status": "no_models_available"}

    # Both models available — apply ensemble rules
    gru_near_tie = gru_result["gap_pp"] <= near_tie_threshold_pp
    xgb_near_tie = xgb_result["gap_pp"] <= near_tie_threshold_pp

    if gru_near_tie or xgb_near_tie:
        # Rule 2: either near-tie -> uncertain
        better = gru_result if gru_result["top_class_probability"] >= xgb_result["top_class_probability"] else xgb_result
        probabilities_source = "gru" if better is gru_result else "xgb"
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
            "probabilities_source": probabilities_source,
            "gate_reason": f"near_tie({', '.join(reason)})",
        }

    # Both non-near-tie — check agreement (Task 17: same predicted class)
    if gru_result["direction"] == xgb_result["direction"]:
        avg_bull = round((gru_result["bullish_pct"] + xgb_result["bullish_pct"]) / 2, 1)
        avg_bear = round((gru_result["bearish_pct"] + xgb_result["bearish_pct"]) / 2, 1)
        avg_side = round((gru_result["sideways_pct"] + xgb_result["sideways_pct"]) / 2, 1)
        avg_pcts = {"bullish": avg_bull, "bearish": avg_bear, "sideways": avg_side}
        return {
            "direction": gru_result["direction"],
            "bullish_pct": avg_bull,
            "bearish_pct": avg_bear,
            "sideways_pct": avg_side,
            "top_class_probability": compute_confidence(avg_pcts),
            "model_version": "ensemble",
            "gate_reason": f"agree({gru_result['direction']})",
        }

    # Disagree branch — blend instead of zeroing out
    bullish_pct = round((gru_result["bullish_pct"] + xgb_result["bullish_pct"]) / 2, 1)
    bearish_pct = round((gru_result["bearish_pct"] + xgb_result["bearish_pct"]) / 2, 1)
    sideways_pct = round((gru_result["sideways_pct"] + xgb_result["sideways_pct"]) / 2, 1)

    pct_map = {"bullish": bullish_pct, "bearish": bearish_pct, "sideways": sideways_pct}
    blended_direction = max(pct_map, key=pct_map.get)
    top_prob = compute_confidence(pct_map)

    return {
        "direction": blended_direction,
        "bullish_pct": bullish_pct,
        "bearish_pct": bearish_pct,
        "sideways_pct": sideways_pct,
        "top_class_probability": top_prob,
        "model_version": "ensemble",
        "status": "disagree_blended",
        "gate_reason": f"disagree(gru={gru_result['direction']}, xgb={xgb_result['direction']}, blended={blended_direction})",
    }


def _single_model_result(
    result: dict,
    model_name: str,
    near_tie_threshold_pp: float = NEAR_TIE_THRESHOLD_PP,
) -> dict:
    """Wrap a single-model result with ensemble metadata."""
    gate_reason = "single_model"
    if result["gap_pp"] <= near_tie_threshold_pp:
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
    # Render's filesystem is ephemeral, and the startup asset step may not have
    # run (for example, when the API is started outside render_start.py). Keep
    # forecast inference self-healing from the tracked, checksummed chunks.
    if not FEATURES_PATH.is_file():
        try:
            from scripts.prepare_render_assets import prepare_features

            prepare_features()
        except (FileNotFoundError, RuntimeError) as exc:
            raise FileNotFoundError(
                f"Forecast feature data is unavailable at {FEATURES_PATH}; "
                "deploy backend/deploy_assets/ or provide the parquet snapshot."
            ) from exc
    df = pd.read_parquet(FEATURES_PATH)
    sym_df = df[df["symbol"] == symbol].copy()
    sym_df["date"] = pd.to_datetime(sym_df["date"])
    sym_df = sym_df.sort_values("date").reset_index(drop=True)

    as_of_date = sym_df["date"].iloc[-1].date()

    # ── Run both models ────────────────────────────────────────────────
    gru_result = _run_gru(symbol, sym_df)
    xgb_result = _run_xgb(symbol, as_of_date, sym_df)

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
