"""Inference — pure function that runs the GRU model on a single symbol.

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

FEATURES_PATH = Path("data/processed/features_daily.parquet")


class SymbolNotFoundError(Exception):
    """Raised when the requested symbol is not in the active 98-symbol universe."""

    pass


class InsufficientHistoryError(Exception):
    """Raised when fewer than window_size rows exist for the symbol."""

    pass


def get_forecast(symbol: str) -> dict:
    """Run GRU inference for a single symbol.

    Parameters
    ----------
    symbol : str
        PSX stock symbol (e.g. "OGDC").

    Returns
    -------
    dict with keys: symbol, horizon, direction, bullish_pct, bearish_pct,
    sideways_pct, confidence, as_of_date, predicted_for_date, model_version.

    Raises
    ------
    SymbolNotFoundError
        If symbol is not in the active 98-symbol universe.
    InsufficientHistoryError
        If fewer than window_size rows exist for the symbol.
    RuntimeError
        If the model is not loaded.
    """
    if not artifacts.model_ready:
        raise RuntimeError("ML model is not loaded")

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

    # ── Check sufficient history ───────────────────────────────────────
    if len(sym_df) < artifacts.window_size:
        raise InsufficientHistoryError(
            f"Symbol '{symbol}' has {len(sym_df)} rows but needs "
            f"{artifacts.window_size} (window_size)"
        )

    # ── Extract window ─────────────────────────────────────────────────
    window_df = sym_df.tail(artifacts.window_size)
    missing_cols = set(artifacts.feature_columns) - set(window_df.columns)
    if missing_cols:
        raise RuntimeError(f"Missing feature columns: {missing_cols}")

    X = window_df[artifacts.feature_columns].values.astype(np.float32)

    # ── Scale ──────────────────────────────────────────────────────────
    n, T, F = 1, X.shape[0], X.shape[1]
    flat = X.reshape(n * T, F)
    flat = artifacts.scaler.transform(flat)
    X_scaled = flat.reshape(n, T, F)

    # ── Predict ────────────────────────────────────────────────────────
    proba = artifacts.model.predict(X_scaled, verbose=0)[0]  # shape: (n_classes,)

    # ── Format output ──────────────────────────────────────────────────
    label_names = artifacts.label_names  # {0: "bullish", 1: "bearish", 2: "sideways"}
    bullish_pct = round(float(proba[0]) * 100, 1)
    bearish_pct = round(float(proba[1]) * 100, 1)
    sideways_pct = round(float(proba[2]) * 100, 1)

    # Normalize to sum to 100
    total = bullish_pct + bearish_pct + sideways_pct
    if abs(total - 100.0) > 0.5:
        factor = 100.0 / total
        bullish_pct = round(bullish_pct * factor, 1)
        bearish_pct = round(bearish_pct * factor, 1)
        sideways_pct = round(sideways_pct * factor, 1)

    pred_class = int(np.argmax(proba))
    direction = label_names.get(pred_class, "unknown")
    confidence = round(float(np.max(proba)) * 100, 1)

    as_of_date = window_df["date"].iloc[-1].date()
    # Next trading day: assume next business day (skip weekends)
    predicted_for_date = as_of_date + timedelta(days=1)
    while predicted_for_date.weekday() >= 5:  # skip weekends
        predicted_for_date += timedelta(days=1)

    log.info("Forecast %s: %s (%.1f%%) as_of=%s for=%s",
             symbol, direction, confidence, as_of_date, predicted_for_date)

    return {
        "symbol": symbol,
        "horizon": "1D",
        "direction": direction,
        "bullish_pct": bullish_pct,
        "bearish_pct": bearish_pct,
        "sideways_pct": sideways_pct,
        "confidence": confidence,
        "as_of_date": as_of_date,
        "predicted_for_date": predicted_for_date,
        "model_version": artifacts.model_version,
    }
