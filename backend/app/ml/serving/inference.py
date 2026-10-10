"""Inference — dual-model institutional ensemble (Attention-BiGRU v2 + XGBoost v4) with confidence gate.

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


def _finite_float(value) -> float | None:
    """Convert a feature value to a JSON-safe number, or null when unavailable."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if np.isfinite(number) else None


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
    """Run Attention-BiGRU v2 inference. Returns dict with direction/probs/gap or None on failure."""
    if not artifacts.model_ready or artifacts.model is None:
        return None

    if len(sym_df) < artifacts.window_size:
        return None

    try:
        window_df = sym_df.tail(artifacts.window_size).copy()

        # Fill any missing feature columns with 0.0 default if needed
        for col in artifacts.feature_columns:
            if col not in window_df.columns:
                window_df[col] = 0.0

        # Strictly select features in the exact metadata order
        X = window_df[artifacts.feature_columns].values.astype(np.float32)
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

        n, T, F = 1, X.shape[0], X.shape[1]
        flat = X.reshape(n * T, F)
        if artifacts.scaler is not None:
            flat = artifacts.scaler.transform(flat)
        X_scaled = flat.reshape(n, T, F)

        raw_pred = artifacts.model.predict(X_scaled, verbose=0)
        
        # Binary directional output sigmoid [p_up]
        if raw_pred.shape[-1] == 1 or len(raw_pred.shape) == 1:
            p_up = float(np.squeeze(raw_pred))
            p_down = 1.0 - p_up
            bullish_pct = round(p_up * 100, 1)
            bearish_pct = round(p_down * 100, 1)
            sideways_pct = 0.0
            direction = "bullish" if p_up > 0.50 else "bearish" if p_down > 0.50 else "sideways"
            top_prob = round(max(p_up, p_down) * 100, 1)
            gap_pp = round(abs(p_up - p_down) * 100, 1)
        else:
            # 3-class fallback
            proba = raw_pred[0]
            bullish_pct = round(float(proba[0]) * 100, 1)
            bearish_pct = round(float(proba[1]) * 100, 1)
            sideways_pct = round(float(proba[2]) * 100, 1) if len(proba) > 2 else 0.0
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

    except Exception:
        log.warning("GRU inference failed for %s", symbol, exc_info=True)
        return None


def _run_xgb(symbol: str, as_of_date: date, sym_df: pd.DataFrame | None = None, horizon: str = "1W") -> dict | None:
    """Run XGBoost inference with horizon specialization. Returns dict with direction/probs/gap or None on failure."""
    if not artifacts.xgb_ready:
        return None

    xgb_model = artifacts.xgb_models.get(horizon, artifacts.xgb_model)
    if xgb_model is None:
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
            if pd.isna(val):
                val = 0.50
            feat_values.append(float(val))

        X_pred = np.array([feat_values], dtype=np.float32)
        proba = xgb_model.predict_proba(X_pred)[0]

        if len(proba) == 2:
            # Class 0: down (bearish), Class 1: up (bullish)
            p_sell = float(proba[0])
            p_buy = float(proba[1])
            bullish_pct = round(p_buy * 100, 1)
            bearish_pct = round(p_sell * 100, 1)
            sideways_pct = 0.0
            direction = "bullish" if p_buy > 0.50 else "bearish" if p_sell > 0.50 else "sideways"
            top_prob = round(max(p_buy, p_sell) * 100, 1)
            gap_pp = round(abs(p_buy - p_sell) * 100, 1)
        else:
            bullish_pct = round(float(proba[0]) * 100, 1)
            bearish_pct = round(float(proba[1]) * 100, 1)
            sideways_pct = round(float(proba[2]) * 100, 1) if len(proba) > 2 else 0.0
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
            "model_version": getattr(artifacts, "xgb_model_version", "xgb_v4_institutional_multi_horizon"),
        }

    except Exception:
        log.warning("XGB inference failed for %s", symbol, exc_info=True)
        return None


HORIZON_WEIGHTS = {
    "1D": {"gru": 0.65, "xgb": 0.35},
    "1W": {"gru": 0.50, "xgb": 0.50},
    "2W": {"gru": 0.40, "xgb": 0.60},
    "1M": {"gru": 0.30, "xgb": 0.70},
}


def _ensemble_decide(
    gru_result: dict | None,
    xgb_result: dict | None,
    horizon: str = "1W",
    near_tie_threshold_pp: float = NEAR_TIE_THRESHOLD_PP,
) -> dict:
    """Apply horizon-aware dual-model ensemble decision logic.

    Domain specialization:
      - Attention-BiGRU: High-frequency sequential momentum & price velocity (65% weight on 1D).
      - XGBoost v4: Cross-sectional valuation, fundamentals & macro events (65% weight on 1M).

    Logic:
      1. Single model fallback if only one model is available.
      2. Both available: Compute weighted probabilities based on investment horizon.
      3. Agreement: If both models agree on direction, output high-conviction signal.
      4. Balanced / Near-tie: If directional gap <= near_tie_threshold_pp, output clean sideways/neutral.
      5. Disagreement with clear spread: Weighted majority direction with moderate conviction.
    """
    has_gru = gru_result is not None
    has_xgb = xgb_result is not None

    # Single model fallback
    if has_gru and not has_xgb:
        return _single_model_result(gru_result, artifacts.model_version, near_tie_threshold_pp)
    if has_xgb and not has_gru:
        return _single_model_result(xgb_result, getattr(artifacts, "xgb_model_version", "xgb_v4_event_fundamentals"), near_tie_threshold_pp)

    if not has_gru and not has_xgb:
        return {
            "direction": "sideways",
            "top_class_probability": 50.0,
            "bullish_pct": 33.3,
            "bearish_pct": 33.3,
            "sideways_pct": 33.4,
            "model_version": "none",
            "gate_reason": "no_models_available",
            "status": "no_models_available",
        }

    weights = HORIZON_WEIGHTS.get(horizon, {"gru": 0.50, "xgb": 0.50})
    w_gru = weights["gru"]
    w_xgb = weights["xgb"]

    # Blended weighted probabilities
    b_bull = round(gru_result["bullish_pct"] * w_gru + xgb_result["bullish_pct"] * w_xgb, 1)
    b_bear = round(gru_result["bearish_pct"] * w_gru + xgb_result["bearish_pct"] * w_xgb, 1)
    b_side = round(gru_result["sideways_pct"] * w_gru + xgb_result["sideways_pct"] * w_xgb, 1)

    # Normalize to 100%
    tot = b_bull + b_bear + b_side
    if tot > 0 and abs(tot - 100.0) > 0.1:
        b_bull = round(b_bull / tot * 100, 1)
        b_bear = round(b_bear / tot * 100, 1)
        b_side = round(max(0.0, 100.0 - b_bull - b_bear), 1)

    directional_gap = abs(b_bull - b_bear)

    # 1. Both models agree
    if gru_result["direction"] == xgb_result["direction"] and gru_result["direction"] in ("bullish", "bearish"):
        direction = gru_result["direction"]
        top_prob = b_bull if direction == "bullish" else b_bear
        return {
            "direction": direction,
            "bullish_pct": b_bull,
            "bearish_pct": b_bear,
            "sideways_pct": b_side,
            "top_class_probability": top_prob,
            "model_version": "ensemble",
            "gate_reason": f"consensus_agree({direction})",
            "conviction": "High Conviction",
        }

    # 2. Balanced / near-tie regime -> clean sideways/neutral
    if directional_gap <= near_tie_threshold_pp:
        return {
            "direction": "sideways",
            "bullish_pct": b_bull,
            "bearish_pct": b_bear,
            "sideways_pct": b_side,
            "top_class_probability": round(max(b_side, 50.0), 1),
            "model_version": "ensemble",
            "gate_reason": f"neutral_regime(gap={round(directional_gap, 1)}pp, gru={gru_result['direction']}, xgb={xgb_result['direction']})",
            "conviction": "Neutral / Risk-Off",
        }

    # 3. Decisive majority
    direction = "bullish" if b_bull > b_bear else "bearish"
    top_prob = b_bull if direction == "bullish" else b_bear
    return {
        "direction": direction,
        "bullish_pct": b_bull,
        "bearish_pct": b_bear,
        "sideways_pct": b_side,
        "top_class_probability": top_prob,
        "model_version": "ensemble",
        "gate_reason": f"weighted_majority(dir={direction}, horizon={horizon}, gru={gru_result['direction']}, xgb={xgb_result['direction']})",
        "conviction": "Moderate Conviction",
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


_FEATURES_DATAFRAME_CACHE: pd.DataFrame | None = None
_FEATURES_DATAFRAME_MTIME: float = 0.0


def get_features_dataframe() -> pd.DataFrame:
    """Load and cache features dataframe in memory across inference invocations."""
    global _FEATURES_DATAFRAME_CACHE, _FEATURES_DATAFRAME_MTIME
    if not FEATURES_PATH.is_file():
        try:
            from scripts.prepare_feature_assets import prepare_features
            prepare_features()
        except (FileNotFoundError, RuntimeError) as exc:
            raise FileNotFoundError(
                f"Forecast feature data is unavailable at {FEATURES_PATH}; "
                "deploy backend/deploy_assets/ or provide the parquet snapshot."
            ) from exc

    mtime = FEATURES_PATH.stat().st_mtime
    if _FEATURES_DATAFRAME_CACHE is not None and _FEATURES_DATAFRAME_MTIME == mtime:
        return _FEATURES_DATAFRAME_CACHE

    df = pd.read_parquet(FEATURES_PATH)
    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
        df["date"] = pd.to_datetime(df["date"])
    _FEATURES_DATAFRAME_CACHE = df
    _FEATURES_DATAFRAME_MTIME = mtime
    return _FEATURES_DATAFRAME_CACHE


def forecast_cache_key(symbol: str, horizon: str, as_of_date: date) -> str:
    """Build a forecast cache key tied to model versions and feature asset revision."""
    try:
        feature_revision = str(FEATURES_PATH.stat().st_mtime_ns)
    except OSError:
        feature_revision = "missing"
    gru_version = str(getattr(artifacts, "model_version", None) or "unavailable")
    xgb_version = str(getattr(artifacts, "xgb_model_version", None) or "unavailable")
    return (
        f"forecast:v4:{symbol.upper()}:{horizon}:{as_of_date.isoformat()}:"
        f"{gru_version}:{xgb_version}:{feature_revision}"
    )


def get_forecast(symbol: str, horizon: str = "1W", sym_df: pd.DataFrame | None = None) -> dict:
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

    # Recommendation synthesis can pass the already-loaded symbol frame. This
    # keeps the API and recommendation paths on identical model inference while
    # avoiding a full parquet reload for every symbol in a recommendation list.
    if sym_df is None:
        df = get_features_dataframe()
        sym_df = df[df["symbol"] == symbol].copy()
    else:
        sym_df = sym_df.copy()
    if sym_df.empty:
        raise InsufficientHistoryError(f"No forecast feature rows are available for {symbol}")
    if not pd.api.types.is_datetime64_any_dtype(sym_df["date"]):
        sym_df["date"] = pd.to_datetime(sym_df["date"])
    sym_df = sym_df.sort_values("date").reset_index(drop=True)

    as_of_date = sym_df["date"].iloc[-1].date()

    # Inference is deterministic for a (symbol, session, horizon, model)
    # tuple. Share the result in Redis so forecast API calls and recommendation
    # generation do not run the same model repeatedly across workers.
    cache_key = forecast_cache_key(symbol, horizon, as_of_date)
    try:
        from app.core.redis import cache_get_sync
        cached_forecast = cache_get_sync(cache_key)
        if isinstance(cached_forecast, dict):
            for field in ("as_of_date", "predicted_for_date"):
                if isinstance(cached_forecast.get(field), str):
                    cached_forecast[field] = date.fromisoformat(cached_forecast[field][:10])
            from app.core.redis import cache_set_sync

            cache_set_sync(cache_key, cached_forecast, 36 * 3600)
            return cached_forecast
    except Exception:
        pass

    # ── Run both models ────────────────────────────────────────────────
    gru_result = _run_gru(symbol, sym_df)
    xgb_result = _run_xgb(symbol, as_of_date, sym_df, horizon=horizon)
    if gru_result is None and xgb_result is None:
        raise RuntimeError(f"No forecast model produced a result for {symbol} ({horizon})")

    # ── Ensemble decision ──────────────────────────────────────────────
    ensemble = _ensemble_decide(gru_result, xgb_result, horizon=horizon)

    # ── Calculate predicted_for_date based on horizon ──────────────────
    HORIZON_DAYS = {"1D": 1, "1W": 5, "2W": 10, "1M": 22}
    biz_days = HORIZON_DAYS.get(horizon, 5)

    predicted_for_date = as_of_date
    days_added = 0
    while days_added < biz_days:
        predicted_for_date += timedelta(days=1)
        if predicted_for_date.weekday() < 5:
            days_added += 1

    # ── Build model_details (debug/analysis field) ─────────────────────
    model_details = {}
    if gru_result:
        model_details["gru_v2"] = {
            "direction": gru_result["direction"],
            "bullish_pct": gru_result["bullish_pct"],
            "bearish_pct": gru_result["bearish_pct"],
            "sideways_pct": gru_result["sideways_pct"],
            "top_class_probability": gru_result["top_class_probability"],
            "gap_pp": gru_result["gap_pp"],
        }
    if xgb_result:
        model_details["xgb_v4"] = {
            "direction": xgb_result["direction"],
            "bullish_pct": xgb_result["bullish_pct"],
            "bearish_pct": xgb_result["bearish_pct"],
            "sideways_pct": xgb_result["sideways_pct"],
            "top_class_probability": xgb_result["top_class_probability"],
            "gap_pp": xgb_result["gap_pp"],
        }

    # ── Build market_context ──────────────────────────────────────────
    latest_row = sym_df.iloc[-1]
    stock_return_5d = None
    stock_return_20d = None
    if len(sym_df) >= 6:
        close_5d_ago = _finite_float(sym_df.iloc[-6].get("close"))
        close_now = _finite_float(latest_row.get("close"))
        if close_5d_ago and close_5d_ago > 0 and close_now is not None:
            stock_return_5d = (close_now / close_5d_ago) - 1.0
    if len(sym_df) >= 21:
        close_20d_ago = _finite_float(sym_df.iloc[-21].get("close"))
        close_now = _finite_float(latest_row.get("close"))
        if close_20d_ago and close_20d_ago > 0 and close_now is not None:
            stock_return_20d = (close_now / close_20d_ago) - 1.0

    idx_5d = _finite_float(latest_row.get("index_return_5d"))
    idx_20d = _finite_float(latest_row.get("index_return_20d"))
    if stock_return_20d is None:
        stock_return_20d = _finite_float(latest_row.get("stock_return_20d"))
    rel_20d = _finite_float(latest_row.get("stock_relative_return_20d"))
    market_ctx = {
        "market_return_5d": idx_5d,
        "market_return_20d": idx_20d,
        "stock_return_5d": stock_return_5d,
        "stock_return_20d": stock_return_20d,
        "stock_relative_return_20d": rel_20d,
    }

    daily_returns = pd.to_numeric(sym_df["close"], errors="coerce").pct_change().dropna()
    volatility_14d = None
    if len(daily_returns) >= 14:
        volatility_14d = _finite_float(daily_returns.tail(14).std(ddof=1))

    log.info("Forecast %s: %s (%.1f%%) gate=%s as_of=%s for=%s horizon=%s",
             symbol, ensemble["direction"], ensemble["top_class_probability"],
             ensemble.get("gate_reason", "?"), as_of_date, predicted_for_date, horizon)

    response = {
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
        "current_price": _finite_float(latest_row.get("close")),
        "volatility_14d": volatility_14d,
        "rsi": _finite_float(latest_row.get("rsi_14")),
        "macd_hist": _finite_float(latest_row.get("macd_hist")),
    }
    try:
        from app.core.redis import cache_set_sync
        cache_set_sync(cache_key, response, 36 * 3600)
    except Exception:
        log.debug("Could not cache forecast for %s", symbol, exc_info=True)
    return response
