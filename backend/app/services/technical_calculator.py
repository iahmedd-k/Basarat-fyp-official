"""Pure pandas technical indicators for the recent PSX OHLCV window."""

from __future__ import annotations

import numpy as np
import pandas as pd


def calculate_recent_indicators(frame: pd.DataFrame, period: int = 14) -> dict:
    """Calculate RSI, MACD, SMA, and ADX without requesting extra price history."""
    if frame is None or frame.empty:
        return {"as_of_date": None, "latest": {}, "history": []}

    df = frame.copy()
    df.columns = [str(column).casefold() for column in df.columns]
    if "date" not in df.columns and isinstance(df.index, pd.DatetimeIndex):
        df["date"] = df.index
    required = {"date", "high", "low", "close"}
    if not required.issubset(df.columns):
        return {"as_of_date": None, "latest": {}, "history": []}
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for column in ("high", "low", "close"):
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df = df.dropna(subset=["date", "high", "low", "close"]).sort_values("date").tail(45)
    if df.empty:
        return {"as_of_date": None, "latest": {}, "history": []}

    close, high, low = df["close"], df["high"], df["low"]
    delta = close.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    average_gain = gains.ewm(alpha=1 / period, adjust=False, min_periods=1).mean()
    average_loss = losses.ewm(alpha=1 / period, adjust=False, min_periods=1).mean()
    rs = average_gain.div(average_loss.replace(0, np.nan))
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.where(average_loss.ne(0), 100.0).where(average_gain.ne(0), 0.0)
    rsi = rsi.where(~(average_gain.eq(0) & average_loss.eq(0)), 50.0)

    macd = close.ewm(span=12, adjust=False, min_periods=1).mean() - close.ewm(
        span=26, adjust=False, min_periods=1,
    ).mean()
    macd_signal = macd.ewm(span=9, adjust=False, min_periods=1).mean()
    macd_histogram = macd - macd_signal
    sma = close.rolling(window=period, min_periods=period).mean()

    previous_close = close.shift(1)
    true_range = pd.concat(
        [(high - low), (high - previous_close).abs(), (low - previous_close).abs()], axis=1,
    ).max(axis=1)
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
    smooth = lambda series: series.ewm(alpha=1 / period, adjust=False, min_periods=1).mean()
    atr = smooth(true_range).replace(0, np.nan)
    plus_di = 100 * smooth(plus_dm) / atr
    minus_di = 100 * smooth(minus_dm) / atr
    di_sum = (plus_di + minus_di).replace(0, np.nan)
    dx = (100 * (plus_di - minus_di).abs() / di_sum).fillna(0.0)
    adx = smooth(dx)

    values = pd.DataFrame({
        "rsi_14": rsi,
        "macd": macd,
        "macd_signal": macd_signal,
        "macd_histogram": macd_histogram,
        f"sma_{period}": sma,
        "adx_14": adx,
    }, index=df.index)
    history = []
    for idx, row in values.iterrows():
        item = {"date": df.loc[idx, "date"].date().isoformat()}
        item.update({key: round(float(value), 6) for key, value in row.items() if pd.notna(value)})
        history.append(item)
    latest = {key: value for key, value in history[-1].items() if key != "date"}
    return {"as_of_date": history[-1]["date"], "latest": latest, "history": history}
