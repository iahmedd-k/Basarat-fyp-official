"""
Technical Indicators — compute TA features per symbol using pure pandas.

All computations are grouped by symbol so rolling windows never leak
across symbol boundaries.  The first 50 rows per symbol are dropped
to account for SMA-50 warm-up.

Indicators computed:
    RSI(14), MACD(12,26,9), Bollinger Bands(20,2), ATR(14),
    SMA(20), SMA(50), EMA(12), EMA(26), rolling 20-day volume z-score
"""

import logging
import warnings
from typing import List

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

# SMA-50 needs 49 prior rows; we drop the first WARMUP_ROWS per symbol.
WARMUP_ROWS = 50


def _rsi(series: pd.Series, length: int = 14) -> pd.Series:
    delta = series.diff()
    positive = delta.copy()
    positive[positive < 0] = 0.0
    negative = delta.copy()
    negative[negative > 0] = 0.0
    # Wilder's smoothing (RMA): plain EWM, no SMA-seeding.
    avg_gain = positive.ewm(alpha=1 / length, adjust=False).mean()
    avg_loss = negative.ewm(alpha=1 / length, adjust=False).mean()
    return 100 * avg_gain / (avg_gain + avg_loss.abs())


def _ema(series: pd.Series, length: int) -> pd.Series:
    """EMA with SMA-seeded initialization (matches pandas-ta presma=True)."""
    s = series.copy().astype(float)
    sma_seed = s.iloc[:length].mean()
    s.iloc[:length - 1] = np.nan
    s.iloc[length - 1] = sma_seed
    return s.ewm(span=length, adjust=False).mean()


def _sma(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(length, min_periods=length).mean()


def _macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = _ema(series, fast)
    ema_slow = _ema(series, slow)
    macd_line = ema_fast - ema_slow
    fvi = macd_line.first_valid_index()
    macd_fvi = macd_line.loc[fvi:]
    signal_line_full = _ema(macd_fvi, signal)
    signal_line = pd.Series(np.nan, index=series.index)
    signal_line.loc[signal_line_full.index] = signal_line_full.values
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def _bbands(series: pd.Series, length: int = 20, std_dev: float = 2.0):
    mid = _sma(series, length)
    rolling_std = series.rolling(length, min_periods=length).std()
    upper = mid + std_dev * rolling_std
    lower = mid - std_dev * rolling_std
    return upper, mid, lower


def _true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """Compute True Range (shared by ATR and ADX)."""
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    return pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    tr = _true_range(high, low, close)
    # Wilder's smoothing: EMA with alpha=1/length, seeded with SMA of first `length` values
    # Matches pandas-ta's ATR with mamode="rma" and presma=True
    atr_values = tr.copy().astype(float)
    sma_seed = tr.iloc[:length].mean()
    atr_values.iloc[:length - 1] = np.nan
    atr_values.iloc[length - 1] = sma_seed
    atr_result = atr_values.ewm(alpha=1 / length, adjust=False).mean()
    return atr_result


def _adx(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    """Average Directional Index (Wilder's smoothing, same convention as ATR/RSI).

    Steps:
      1. +DM / -DM from directional movement
      2. Smooth with Wilder's (alpha=1/length)
      3. +DI, -DI
      4. DX, then ADX = smoothed DX
    """
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low

    plus_dm = pd.Series(0.0, index=high.index)
    minus_dm = pd.Series(0.0, index=high.index)

    plus_mask = (up_move > down_move) & (up_move > 0)
    minus_mask = (down_move > up_move) & (down_move > 0)
    plus_dm[plus_mask] = up_move[plus_mask]
    minus_dm[minus_mask] = down_move[minus_mask]

    tr = _true_range(high, low, close)

    # Wilder's smoothing (seed with SMA of first `length` values)
    def _wilder_smooth(series: pd.Series, period: int) -> pd.Series:
        out = series.copy().astype(float)
        sma_seed = series.iloc[:period].mean()
        out.iloc[:period - 1] = np.nan
        out.iloc[period - 1] = sma_seed
        return out.ewm(alpha=1 / period, adjust=False).mean()

    atr_smooth = _wilder_smooth(tr, length)
    plus_dm_smooth = _wilder_smooth(plus_dm, length)
    minus_dm_smooth = _wilder_smooth(minus_dm, length)

    plus_di = 100 * plus_dm_smooth / atr_smooth
    minus_di = 100 * minus_dm_smooth / atr_smooth

    di_sum = plus_di + minus_di
    dx = 100 * (plus_di - minus_di).abs() / di_sum.replace(0, np.nan)

    adx = _wilder_smooth(dx, length)
    return adx


def compute_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add technical indicator columns to *df* (per symbol group).

    Columns added:
        rsi_14, macd, macd_signal, macd_hist,
        bb_upper, bb_lower, bb_mid,
        atr_14, sma_20, sma_50, ema_12, ema_26,
        volume_zscore_20

    After computation, the first ``WARMUP_ROWS`` rows per symbol are dropped
    (SMA-50 cannot produce a value until row 50).
    """
    if df.empty:
        return df

    df = df.copy()
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

    log.info("Computing technical indicators for %d symbols ...", df["symbol"].nunique())

    def _apply_group(group: pd.DataFrame) -> pd.DataFrame:
        g = group.copy()

        g["rsi_14"] = _rsi(g["close"], length=14)

        macd_line, signal_line, hist = _macd(g["close"])
        g["macd"] = macd_line
        g["macd_signal"] = signal_line
        g["macd_hist"] = hist

        bb_upper, bb_mid, bb_lower = _bbands(g["close"], length=20, std_dev=2)
        g["bb_upper"] = bb_upper
        g["bb_mid"] = bb_mid
        g["bb_lower"] = bb_lower

        g["atr_14"] = _atr(g["high"], g["low"], g["close"], length=14)
        g["sma_20"] = _sma(g["close"], 20)
        g["sma_50"] = _sma(g["close"], 50)
        g["ema_12"] = _ema(g["close"], 12)
        g["ema_26"] = _ema(g["close"], 26)

        if "volume" in g.columns:
            vol_mean = g["volume"].rolling(20, min_periods=1).mean()
            vol_std = g["volume"].rolling(20, min_periods=1).std().replace(0, 1)
            g["volume_zscore_20"] = (g["volume"] - vol_mean) / vol_std

        # ── New: trend-persistence / regime-strength features ────────────
        g["adx_14"] = _adx(g["high"], g["low"], g["close"], length=14)

        daily_ret = g["close"].pct_change()
        # consecutive_up_days: count of consecutive positive daily returns
        up_groups = (daily_ret <= 0).cumsum()
        g["consecutive_up_days"] = daily_ret.groupby(up_groups).cumcount() + 1
        g.loc[daily_ret <= 0, "consecutive_up_days"] = 0
        # consecutive_down_days: count of consecutive negative daily returns
        down_groups = (daily_ret >= 0).cumsum()
        g["consecutive_down_days"] = daily_ret.groupby(down_groups).cumcount() + 1
        g.loc[daily_ret >= 0, "consecutive_down_days"] = 0

        g["return_5d"] = g["close"].pct_change(5)
        g["return_10d"] = g["close"].pct_change(10)

        rsi = _rsi(g["close"], length=14)
        g["rsi_roc"] = rsi - rsi.shift(5)

        # ── Normalized / Relative Price Features (Task 11) ───────────────
        g["close_to_sma20_ratio"] = (g["close"] / g["sma_20"].replace(0, np.nan)) - 1.0
        g["close_to_sma50_ratio"] = (g["close"] / g["sma_50"].replace(0, np.nan)) - 1.0
        g["ema_cross_ratio"] = (g["ema_12"] / g["ema_26"].replace(0, np.nan)) - 1.0
        bb_width = (g["bb_upper"] - g["bb_lower"]).replace(0, np.nan)
        g["bollinger_pos"] = ((g["close"] - g["bb_lower"]) / bb_width).clip(0, 1)
        g["daily_range_pct"] = (g["high"] - g["low"]) / g["close"].replace(0, np.nan)
        if "volume" in g.columns:
            g["volume_change_1d"] = g["volume"].pct_change(1)
        else:
            g["volume_change_1d"] = 0.0

        # ── Stock returns for market context (Task 12) ───────────────────
        g["stock_return_20d"] = g["close"].pct_change(20)

        return g

    # Suppress FutureWarning about groupby.apply on grouping columns
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=FutureWarning)
        df = df.groupby("symbol", group_keys=False).apply(_apply_group)

    # ── Market Context / Market-Relative Features (Task 12) ──────────────
    # Compute point-in-time equal-weighted market returns across universe
    df["daily_ret"] = df.groupby("symbol")["close"].pct_change(1)
    market_daily = df.groupby("date")["daily_ret"].mean().reset_index()
    market_daily = market_daily.sort_values("date").reset_index(drop=True)

    # Compounded market returns: (1+r1)*(1+r2)... - 1
    m_growth = 1.0 + market_daily["daily_ret"].fillna(0.0)
    market_daily["index_return_5d"] = m_growth.rolling(5, min_periods=5).apply(np.prod, raw=True) - 1.0
    market_daily["index_return_20d"] = m_growth.rolling(20, min_periods=20).apply(np.prod, raw=True) - 1.0
    market_daily["market_return_5d"] = market_daily["index_return_5d"]
    market_daily["market_return_20d"] = market_daily["index_return_20d"]

    market_lookup = market_daily[["date", "index_return_5d", "index_return_20d", "market_return_5d", "market_return_20d"]]
    df = pd.merge(df, market_lookup, on="date", how="left")
    df["stock_relative_return_20d"] = df["stock_return_20d"] - df["index_return_20d"]
    df = df.drop(columns=["daily_ret"])

    # Drop warm-up rows
    before = len(df)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=FutureWarning)
        df = df.groupby("symbol", group_keys=False).apply(
            lambda g: g.iloc[WARMUP_ROWS:].reset_index(drop=True)
        )
    after = len(df)

    log.info(
        "Indicators computed. Dropped %d warm-up rows (%d -> %d, %d symbols)",
        before - after, before, after, df["symbol"].nunique(),
    )

    return df.reset_index(drop=True)
