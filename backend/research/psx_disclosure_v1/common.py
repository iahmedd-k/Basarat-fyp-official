"""Shared data preparation for isolated PSX disclosure experiments.

Run from backend/: python research/psx_disclosure_v1/common.py --help
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
RAW_OHLCV = BACKEND / "data" / "raw" / "ohlcv" / "all_symbols.parquet"
UNIVERSE = BACKEND / "data" / "config" / "symbol_universe.json"
DATA_DIR = HERE / "data"
OHLCV_PATH = DATA_DIR / "ohlcv_8y.parquet"
FEATURES_PATH = DATA_DIR / "features.parquet"
EVENTS_PATH = DATA_DIR / "events.csv"
EVENT_COVERAGE_PATH = DATA_DIR / "events_coverage.json"
META_PATH = DATA_DIR / "dataset_metadata.json"
LOG = logging.getLogger("psx_disclosure_v1")

# PSX close cutoff used for daily observations. An after-close notice can only
# affect the next market session's feature row.
PKT = timezone(timedelta(hours=5))
PSX_CLOSE = time(15, 30)
HORIZON_SESSIONS = 5
SEQUENCE_LENGTH = 45
MAX_SEQUENCE_CALENDAR_DAYS = 90
MIN_EVENT_ARCHIVE_MONTHS = 24

SECTOR_MAP: dict[str, str] = {
    # Commercial & Islamic Banks
    "ABL": "COMMERCIAL_BANKS", "AKBL": "COMMERCIAL_BANKS", "BAFL": "COMMERCIAL_BANKS", "BAHL": "COMMERCIAL_BANKS",
    "BOP": "COMMERCIAL_BANKS", "FABL": "COMMERCIAL_BANKS", "HBL": "COMMERCIAL_BANKS", "HMB": "COMMERCIAL_BANKS",
    "MCB": "COMMERCIAL_BANKS", "MEBL": "COMMERCIAL_BANKS", "NBP": "COMMERCIAL_BANKS", "SCBPL": "COMMERCIAL_BANKS",
    "UBL": "COMMERCIAL_BANKS",
    # Oil & Gas Exploration & Production
    "OGDC": "OIL_GAS_EXPLORATION", "PPL": "OIL_GAS_EXPLORATION", "MARI": "OIL_GAS_EXPLORATION", "POL": "OIL_GAS_EXPLORATION",
    # Oil & Gas Marketing
    "APL": "OIL_GAS_MARKETING", "PSO": "OIL_GAS_MARKETING", "SNGP": "OIL_GAS_MARKETING", "SSGC": "OIL_GAS_MARKETING",
    # Refineries
    "ATRL": "REFINERY", "CNERGY": "REFINERY", "NRL": "REFINERY", "PRL": "REFINERY",
    # Fertilizer
    "EFERT": "FERTILIZER", "ENGROH": "FERTILIZER", "FATIMA": "FERTILIZER", "FFC": "FERTILIZER",
    # Cement
    "BWCL": "CEMENT", "CHCC": "CEMENT", "DGKC": "CEMENT", "FCCL": "CEMENT", "KOHC": "CEMENT",
    "LUCK": "CEMENT", "MLCF": "CEMENT", "PIOC": "CEMENT", "POWER": "CEMENT",
    # Power Generation & Distribution
    "HUBC": "POWER_GENERATION", "KAPCO": "POWER_GENERATION", "KEL": "POWER_GENERATION", "NPL": "POWER_GENERATION",
    # Technology & Telecommunications
    "AIRLINK": "TECHNOLOGY_COMMUNICATION", "HUMNL": "TECHNOLOGY_COMMUNICATION", "PTC": "TECHNOLOGY_COMMUNICATION",
    "SYS": "TECHNOLOGY_COMMUNICATION", "TRG": "TECHNOLOGY_COMMUNICATION",
    # Pharmaceuticals
    "ABOT": "PHARMACEUTICALS", "AGP": "PHARMACEUTICALS", "CPHL": "PHARMACEUTICALS", "GLAXO": "PHARMACEUTICALS",
    "HALEON": "PHARMACEUTICALS", "HINOON": "PHARMACEUTICALS", "SEARL": "PHARMACEUTICALS", "SHFA": "PHARMACEUTICALS",
    # Automobile Assembler & Parts
    "ATLH": "AUTOMOBILE", "HCAR": "AUTOMOBILE", "INDU": "AUTOMOBILE", "MTL": "AUTOMOBILE", "SAZEW": "AUTOMOBILE", "THALL": "AUTOMOBILE",
    # Textile Composite & Spinning
    "BNWM": "TEXTILE", "GADT": "TEXTILE", "IBFL": "TEXTILE", "ILP": "TEXTILE", "KTML": "TEXTILE", "MEHT": "TEXTILE", "NML": "TEXTILE", "YOUW": "TEXTILE",
    # Chemical & Glass
    "GAL": "CHEMICAL_GLASS", "GHGL": "CHEMICAL_GLASS", "GHNI": "CHEMICAL_GLASS", "LCI": "CHEMICAL_GLASS", "LOTCHEM": "CHEMICAL_GLASS", "TGL": "CHEMICAL_GLASS",
    # Engineering, Cable & Steel
    "INIL": "ENGINEERING", "ISL": "ENGINEERING", "PAEL": "ENGINEERING", "PABC": "ENGINEERING",
    # Food & Personal Care
    "COLG": "FOOD_PERSONAL_CARE", "FFL": "FOOD_PERSONAL_CARE", "JDWS": "FOOD_PERSONAL_CARE", "MUREB": "FOOD_PERSONAL_CARE",
    "NATF": "FOOD_PERSONAL_CARE", "NESTLE": "FOOD_PERSONAL_CARE", "PAKT": "FOOD_PERSONAL_CARE", "RMPL": "FOOD_PERSONAL_CARE",
    "TREET": "FOOD_PERSONAL_CARE", "UPFL": "FOOD_PERSONAL_CARE",
    # Financial Services, Inv. Banks & REIT
    "AHCL": "FINANCIAL_SERVICES", "AICL": "FINANCIAL_SERVICES", "DCR": "FINANCIAL_SERVICES", "FHAM": "FINANCIAL_SERVICES",
    "HGFA": "FINANCIAL_SERVICES", "JVDC": "FINANCIAL_SERVICES", "PGLC": "FINANCIAL_SERVICES", "PIBTL": "FINANCIAL_SERVICES",
    "PKGS": "FINANCIAL_SERVICES", "PSEL": "FINANCIAL_SERVICES", "PSX": "FINANCIAL_SERVICES", "SRVI": "FINANCIAL_SERVICES",
    "SSOM": "FINANCIAL_SERVICES", "TPLRF1": "FINANCIAL_SERVICES",
}

STATIONARY_CORE = [
    "dist_sma20", "dist_sma50", "dist_ema12", "dist_ema26",
    "sma_cross_20_50", "ema_cross_12_26",
    "bb_pct_b", "bb_width", "norm_atr14", "hl_range", "co_range",
    "keltner_pos", "rsi_norm", "macd_norm", "macd_hist_norm",
    "stoch_k_14", "stoch_d_3", "mfi_14", "cci_20", "cmf_20",
    "dist_vwap_5d", "dist_vwap_20d", "log_return",
    "ret_1d", "ret_2d", "ret_3d", "ret_5d", "ret_10d", "ret_20d", "ret_60d", "ret_120d",
    "volatility_10d", "volatility_20d", "volatility_30d", "volatility_60d",
    "parkinson_vol_20d", "garman_klass_vol_20d", "vol_ratio_10_60",
    "volume_zscore_20", "volume_change_5d", "volume_change_10d", "volume_change_20d", "rel_vol_50d",
    "market_breadth_20d", "rel_to_index_5d", "rel_to_index_10d", "rel_to_index_20d", "rel_to_index_60d", "rel_to_index_120d",
    "index_return_5d", "index_return_10d", "index_return_20d", "index_return_60d", "index_return_120d",
    "rel_to_sector_1d", "rel_to_sector_5d", "rel_to_sector_20d", "rel_to_sector_60d",
    "sector_return_5d", "sector_return_20d", "sector_vol_share",
    "within_sector_csrank_ret_5d", "within_sector_csrank_rsi", "within_sector_csrank_mom",
    "policy_rate_chg_20d", "pkr_usd_ret_20d",
]

XGB_RANK_CORE = [
    "dist_52w_high", "mom_12m_1m", "ret_1d", "ret_3d", "ret_5d", "ret_10d", "ret_20d", "ret_60d", "ret_120d",
    "amihud_illiquidity", "is_lower_circuit", "volatility_10d", "volatility_20d", "volatility_60d",
    "parkinson_vol_20d", "garman_klass_vol_20d", "vol_ratio_10_60",
    "norm_atr14", "hl_range", "co_range", "dist_sma20", "dist_sma50",
    "dist_ema12", "dist_ema26", "sma_cross_20_50", "ema_cross_12_26",
    "bb_pct_b", "bb_width", "keltner_pos", "rsi_norm", "macd_norm", "macd_hist_norm",
    "stoch_k_14", "stoch_d_3", "mfi_14", "cci_20", "cmf_20",
    "dist_vwap_5d", "dist_vwap_20d", "volume_zscore_20", "vol_growth_5d", "vol_growth_20d", "rel_vol_50d",
    "rel_to_index_5d", "rel_to_index_20d", "rel_to_index_60d", "rel_to_index_120d",
    "rel_to_sector_1d", "rel_to_sector_5d", "rel_to_sector_20d", "rel_to_sector_60d",
    "sector_vol_share", "within_sector_csrank_ret_5d", "within_sector_csrank_rsi", "within_sector_csrank_mom",
]
XGB_MACRO = ["policy_rate_chg_20d", "pkr_usd_ret_20d"]
XGB_CORE = [f"{c}_csrank" for c in XGB_RANK_CORE] + XGB_MACRO

EVENT_XGB = [
    "evt_results_published", "evt_dividend_announced", "evt_bonus_or_rights",
    "evt_board_meeting_notice", "evt_material_info", "evt_count_5s",
    "sessions_since_results", "sessions_to_board_meeting", "dividend_yield",
    "eps_delta_over_price", "fund_dividend_yield", "fund_payout_ratio",
]
EVENT_GRU = [
    "evt_results_published", "evt_dividend_announced", "evt_bonus_or_rights",
    "evt_board_meeting_notice", "evt_material_info", "sessions_since_results",
    "sessions_to_board_meeting", "dividend_yield", "eps_delta_over_price",
    "dividend_parsed", "eps_parsed", "fund_dividend_yield", "fund_payout_ratio",
]
XGB_FEATURES = XGB_CORE + EVENT_XGB
GRU_FEATURES = STATIONARY_CORE + EVENT_GRU


TARGET_COLUMNS = ["target_class", "target_direction", "target_excess_return", "target_date"]
CLASS_NAMES = {0: "avoid", 1: "neutral", 2: "buy"}
DIRECTION_NAMES = {0: "down", 1: "up"}


def _read_symbols() -> list[str]:
    symbols: set[str] = set()
    if RAW_OHLCV.exists():
        raw = pd.read_parquet(RAW_OHLCV, columns=["symbol"])
        symbols.update(raw["symbol"].dropna().astype(str).str.upper().str.strip())
    if UNIVERSE.exists():
        payload = json.loads(UNIVERSE.read_text(encoding="utf-8"))
        symbols.update(str(x.get("symbol", "")).upper().strip() for x in payload if x.get("symbol"))
    return sorted(s for s in symbols if s)


def fetch_eight_years(years: int = 8, out_path: Path = OHLCV_PATH) -> pd.DataFrame:
    """Attempt an isolated historical refresh using the repo's PSX fetcher."""
    from app.data.scraper.ohlcv import fetch_ohlcv

    symbols = _read_symbols()
    if not symbols:
        raise RuntimeError(f"No ticker symbols found in {RAW_OHLCV} or {UNIVERSE}")
    end = date.today()
    start = end - timedelta(days=365 * years)
    existing = pd.read_parquet(RAW_OHLCV) if RAW_OHLCV.exists() else pd.DataFrame()
    chunks: list[pd.DataFrame] = []
    failures: list[str] = []
    for i, symbol in enumerate(symbols, start=1):
        try:
            hist = fetch_ohlcv(symbol, start=start, end=end)
            if hist is None or hist.empty:
                failures.append(symbol)
                continue
            hist = hist.rename(columns={c: c.lower() for c in hist.columns})
            hist["symbol"] = symbol
            chunks.append(hist)
            LOG.info("Fetched %s (%d/%d): %d bars", symbol, i, len(symbols), len(hist))
        except Exception as exc:  # collect per-symbol failures and continue
            LOG.warning("Fetch failed for %s: %s", symbol, exc)
            failures.append(symbol)
    if existing.empty and not chunks:
        raise RuntimeError("No OHLCV returned by PSX.")
    pieces = [x for x in [existing, *chunks] if not x.empty]
    combined = pd.concat(pieces, ignore_index=True, sort=False)
    required = {"symbol", "date", "open", "high", "low", "close", "volume"}
    missing = required - set(combined.columns)
    if missing:
        raise ValueError(f"OHLCV missing columns {sorted(missing)}")
    combined["symbol"] = combined["symbol"].astype(str).str.upper().str.strip()
    combined["date"] = pd.to_datetime(combined["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    for col in ["open", "high", "low", "close", "volume"]:
        combined[col] = pd.to_numeric(combined[col], errors="coerce")
    combined = combined.dropna(subset=["symbol", "date", "close"])
    combined = combined.sort_values(["symbol", "date"]).drop_duplicates(["symbol", "date"], keep="last")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(out_path, index=False)
    (DATA_DIR / "fetch_report.json").write_text(json.dumps({
        "requested_start": start.isoformat(), "requested_end": end.isoformat(),
        "symbols_requested": len(symbols), "symbols_failed_or_empty": failures,
        "row_count": int(len(combined)), "actual_min_date": str(combined.date.min().date()),
        "actual_max_date": str(combined.date.max().date()),
    }, indent=2), encoding="utf-8")
    return combined


def load_prices(path: Path | None = None) -> pd.DataFrame:
    path = path or (OHLCV_PATH if OHLCV_PATH.exists() else RAW_OHLCV)
    if not path.exists():
        raise FileNotFoundError(f"No OHLCV parquet found: {path}. Run common.py --fetch first.")
    df = pd.read_parquet(path)
    df.columns = [str(c).lower() for c in df.columns]
    needed = ["symbol", "date", "open", "high", "low", "close", "volume"]
    missing = set(needed) - set(df.columns)
    if missing:
        raise ValueError(f"OHLCV parquet missing columns {sorted(missing)}")
    df = df[needed].copy()
    df["symbol"] = df["symbol"].astype(str).str.upper().str.strip()
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    for col in needed[2:]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["symbol", "date", "close"])
    df = df.sort_values(["symbol", "date"]).drop_duplicates(["symbol", "date"], keep="last")
    df = df[df["close"] > 0].copy()
    # Conservative point-in-time macro join: the value is available from its
    # effective/source date onward. These source files do not carry reliable
    # announcement timestamps, so do not backdate a rate before effective date.
    macro_dir = BACKEND / "data" / "config" / "macro"
    for filename, date_col, value_col, out_col in [
        ("sbp_rate.csv", "effective_date", "policy_rate", "policy_rate"),
        ("pkr_usd.csv", "date", "rate", "pkr_usd_rate"),
    ]:
        source = macro_dir / filename
        if not source.exists():
            continue
        macro = pd.read_csv(source)
        if not {date_col, value_col}.issubset(macro.columns):
            LOG.warning("Skipping malformed macro file %s", source)
            continue
        macro[date_col] = pd.to_datetime(macro[date_col], errors="coerce").dt.tz_localize(None).dt.normalize()
        macro[value_col] = pd.to_numeric(macro[value_col], errors="coerce")
        macro = macro.dropna(subset=[date_col, value_col]).sort_values(date_col).drop_duplicates(date_col, keep="last")
        left = df.sort_values("date")
        merged = pd.merge_asof(left, macro[[date_col, value_col]].rename(columns={date_col:"_macro_date", value_col:out_col}).sort_values("_macro_date"),
                               left_on="date", right_on="_macro_date", direction="backward")
        df = merged.drop(columns="_macro_date").sort_values(["symbol", "date"]).reset_index(drop=True)
    return df.reset_index(drop=True)


def _safe_pct(current: pd.Series, previous: pd.Series) -> pd.Series:
    return current.div(previous.where(previous.abs() > 1e-12)).sub(1)


def _market_loo_median(group: pd.DataFrame, value_col: str) -> pd.Series:
    """Leave-one-symbol-out median in O(n log n), robust to ties."""
    values = group[value_col].to_numpy(dtype=float)
    n = len(values)
    result = np.full(n, np.nan, dtype=float)
    valid = np.isfinite(values)
    if valid.sum() < 2:
        return pd.Series(result, index=group.index)
    original_positions = np.flatnonzero(valid)
    arr = values[valid]
    order = np.argsort(arr, kind="mergesort")
    sorted_arr = arr[order]
    ranks = np.empty(len(arr), dtype=int)
    ranks[order] = np.arange(len(arr))

    def kth_without(k: int) -> np.ndarray:
        j = ranks
        return sorted_arr[np.where(j <= k, k + 1, k)]

    n_valid = len(arr)
    if n_valid % 2 == 0:
        med = kth_without((n_valid - 2) // 2)
    else:
        k = (n_valid - 1) // 2
        med = (kth_without(k - 1) + kth_without(k)) / 2
    result[original_positions] = med
    return pd.Series(result, index=group.index)


def _engineer_price_features(raw: pd.DataFrame) -> tuple[pd.DataFrame, list[pd.Timestamp]]:
    df = raw.copy().sort_values(["symbol", "date"]).reset_index(drop=True)
    sessions = sorted(pd.Timestamp(x) for x in df.date.unique())
    session_index = {d: i for i, d in enumerate(sessions)}
    df["session_idx"] = df.date.map(session_index).astype(int)

    def one_symbol(g: pd.DataFrame) -> pd.DataFrame:
        g = g.sort_values("date").copy()
        c, o, h, l, v = g.close, g.open, g.high, g.low, g.volume
        prev = c.shift(1)
        lr = np.log(c / prev.replace(0, np.nan))
        g["log_return"] = lr.replace([np.inf, -np.inf], np.nan)
        for n in [1, 2, 3, 5, 10, 20, 60, 120]:
            g[f"ret_{n}d"] = _safe_pct(c, c.shift(n))
        sma20 = c.rolling(20, min_periods=20).mean()
        sma50 = c.rolling(50, min_periods=50).mean()
        g["dist_sma20"] = c / sma20 - 1
        g["dist_sma50"] = c / sma50 - 1
        g["sma_cross_20_50"] = (sma20 / sma50.replace(0, np.nan) - 1).clip(-0.5, 0.5)

        ema12 = c.ewm(span=12, adjust=False, min_periods=12).mean()
        ema26 = c.ewm(span=26, adjust=False, min_periods=26).mean()
        g["dist_ema12"] = c / ema12 - 1
        g["dist_ema26"] = c / ema26 - 1
        g["ema_cross_12_26"] = (ema12 / ema26.replace(0, np.nan) - 1).clip(-0.5, 0.5)

        std20 = c.rolling(20, min_periods=20).std()
        upper, lower = sma20 + 2 * std20, sma20 - 2 * std20
        band = (upper - lower).replace(0, np.nan)
        g["bb_pct_b"] = (c - lower) / band
        g["bb_width"] = band / sma20.replace(0, np.nan)

        tr = pd.concat([(h-l), (h-prev).abs(), (l-prev).abs()], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
        g["norm_atr14"] = atr / c
        g["hl_range"] = (h-l) / c
        g["co_range"] = (c-o) / o.replace(0, np.nan)

        ema20 = c.ewm(span=20, adjust=False, min_periods=20).mean()
        g["keltner_pos"] = ((c - ema20) / (2 * atr.replace(0, np.nan))).clip(-3, 3)

        delta = c.diff()
        gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False, min_periods=14).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False, min_periods=14).mean()
        rsi = 100 * gain / (gain + loss).replace(0, np.nan)
        g["rsi_norm"] = (rsi - 50) / 50

        macd = ema12 - ema26
        hist = macd - macd.ewm(span=9, adjust=False, min_periods=9).mean()
        g["macd_norm"] = macd / c
        g["macd_hist_norm"] = hist / c

        # Stochastic %K and %D (14, 3)
        l14 = l.rolling(14, min_periods=14).min()
        h14 = h.rolling(14, min_periods=14).max()
        stoch_k = ((c - l14) / (h14 - l14).replace(0, np.nan)).clip(0, 1)
        g["stoch_k_14"] = (stoch_k - 0.5) * 2.0
        g["stoch_d_3"] = (stoch_k.rolling(3, min_periods=3).mean() - 0.5) * 2.0

        # Money Flow Index (MFI 14)
        tp = (h + l + c) / 3.0
        raw_money_flow = tp * v
        pos_flow = raw_money_flow.where(tp > tp.shift(1), 0.0)
        neg_flow = raw_money_flow.where(tp < tp.shift(1), 0.0)
        pos_sum = pos_flow.rolling(14, min_periods=14).sum()
        neg_sum = neg_flow.rolling(14, min_periods=14).sum()
        money_ratio = pos_sum / neg_sum.replace(0, np.nan)
        mfi = 100.0 - (100.0 / (1.0 + money_ratio))
        g["mfi_14"] = (mfi.fillna(50.0) - 50.0) / 50.0

        # Commodity Channel Index (CCI 20)
        tp_ma = tp.rolling(20, min_periods=20).mean()
        tp_md = (tp - tp_ma).abs().rolling(20, min_periods=20).mean()
        cci = (tp - tp_ma) / (0.015 * tp_md.replace(0, np.nan))
        g["cci_20"] = (cci / 100.0).clip(-3.0, 3.0)

        # Chaikin Money Flow (CMF 20)
        mf_multiplier = ((c - l) - (h - c)) / (h - l).replace(0, np.nan)
        mf_vol = mf_multiplier * v
        v_sum20 = v.rolling(20, min_periods=20).sum().replace(0, np.nan)
        g["cmf_20"] = (mf_vol.rolling(20, min_periods=20).sum() / v_sum20).clip(-1.0, 1.0)

        # Rolling VWAP Distances (5d, 20d)
        v_sum5 = v.rolling(5, min_periods=5).sum().replace(0, np.nan)
        vwap5 = (tp * v).rolling(5, min_periods=5).sum() / v_sum5
        vwap20 = (tp * v).rolling(20, min_periods=20).sum() / v_sum20
        g["dist_vwap_5d"] = (c / vwap5 - 1.0).clip(-0.5, 0.5)
        g["dist_vwap_20d"] = (c / vwap20 - 1.0).clip(-0.5, 0.5)

        for n, minp in [(10,5), (20,10), (30,15), (60,30)]:
            g[f"volatility_{n}d"] = g.log_return.rolling(n, min_periods=minp).std()

        # Advanced Volatilities: Parkinson & Garman-Klass
        hl_log_sq = (np.log(h / l.replace(0, np.nan)) ** 2)
        g["parkinson_vol_20d"] = np.sqrt((hl_log_sq.rolling(20, min_periods=10).mean() / (4.0 * np.log(2.0))).clip(lower=0))
        co_log_sq = (np.log(c / o.replace(0, np.nan)) ** 2)
        gk = 0.5 * hl_log_sq - (2.0 * np.log(2.0) - 1.0) * co_log_sq
        g["garman_klass_vol_20d"] = np.sqrt(gk.rolling(20, min_periods=10).mean().clip(lower=0))
        g["vol_ratio_10_60"] = (g["volatility_10d"] / g["volatility_60d"].replace(0, np.nan)).clip(0, 5.0)

        vmean, vstd = v.rolling(20, min_periods=10).mean(), v.rolling(20, min_periods=10).std()
        g["volume_zscore_20"] = (v-vmean)/vstd.replace(0, np.nan)
        for n in [5, 10, 20]:
            old = v.shift(n)
            g[f"volume_change_{n}d"] = ((v-old)/(old.abs()+1)).clip(-1, 5)
        v_sma50 = v.rolling(50, min_periods=20).mean()
        g["rel_vol_50d"] = (v / v_sma50.replace(0, np.nan)).clip(0, 10.0)

        g["dist_52w_high"] = c / h.rolling(252, min_periods=50).max() - 1
        g["mom_12m_1m"] = _safe_pct(c, c.shift(252)) - _safe_pct(c, c.shift(21))
        g["amihud_illiquidity"] = np.log1p(g.ret_1d.abs() / (v*c+1e-3) * 1e8)
        daily_change = c.pct_change()
        g["is_lower_circuit"] = (daily_change <= -0.074).astype(float)
        g["market_breadth_20d"] = (c > c.rolling(20, min_periods=20).mean()).astype(float)
        return g

    symbol_frames = []
    for sym, g in df.groupby("symbol", sort=False):
        res = one_symbol(g)
        res["symbol"] = sym
        symbol_frames.append(res)
    df = pd.concat(symbol_frames, ignore_index=True)

    # Market reference series by PSX date, never by dataframe row position.
    daily = df.groupby("date", sort=True).agg(
        index_return_1d=("ret_1d", "median"),
        market_breadth_20d=("market_breadth_20d", "mean"),
        pkr_usd_rate=("pkr_usd_rate", "first") if "pkr_usd_rate" in df else ("close", "size"),
        policy_rate=("policy_rate", "first") if "policy_rate" in df else ("close", "size"),
    )
    if "pkr_usd_rate" not in df:
        daily = daily.drop(columns="pkr_usd_rate")
    if "policy_rate" not in df:
        daily = daily.drop(columns="policy_rate")
    for n in [5, 10, 20, 60, 120]:
        daily[f"index_return_{n}d"] = (1 + daily.index_return_1d.fillna(0)).rolling(n, min_periods=n).apply(np.prod, raw=True) - 1
    daily["policy_rate_chg_20d"] = daily.policy_rate.diff(20) if "policy_rate" in daily else np.nan
    daily["pkr_usd_ret_20d"] = daily.pkr_usd_rate.pct_change(20) if "pkr_usd_rate" in daily else np.nan
    df = df.drop(columns=["market_breadth_20d"], errors="ignore").merge(
        daily[[c for c in daily.columns if c.startswith("index_return_") or c in {"market_breadth_20d", "policy_rate_chg_20d", "pkr_usd_ret_20d"}]],
        left_on="date", right_index=True, how="left")
    for n in [5, 10, 20, 60, 120]:
        df[f"rel_to_index_{n}d"] = df[f"ret_{n}d"] - df[f"index_return_{n}d"]

    # Map sector for each symbol
    df["sector"] = df["symbol"].map(SECTOR_MAP).fillna("OTHER")

    # Sector daily aggregates (calculated dynamically per date and sector)
    sec_daily = df.groupby(["date", "sector"], sort=False).agg(
        sec_ret_1d=("ret_1d", "median"),
        sec_ret_5d=("ret_5d", "median"),
        sec_ret_20d=("ret_20d", "median"),
        sec_ret_60d=("ret_60d", "median"),
        sec_vol_sum=("volume", "sum"),
    ).reset_index()

    df = df.merge(sec_daily, on=["date", "sector"], how="left")

    df["rel_to_sector_1d"] = df["ret_1d"] - df["sec_ret_1d"]
    df["rel_to_sector_5d"] = df["ret_5d"] - df["sec_ret_5d"]
    df["rel_to_sector_20d"] = df["ret_20d"] - df["sec_ret_20d"]
    df["rel_to_sector_60d"] = df["ret_60d"] - df["sec_ret_60d"]
    df["sector_return_5d"] = df["sec_ret_5d"]
    df["sector_return_20d"] = df["sec_ret_20d"]
    df["sector_vol_share"] = (df["volume"] / df["sec_vol_sum"].replace(0, np.nan)).clip(0, 1.0).fillna(0.0)

    # Within-sector cross-sectional rankings per date
    df["within_sector_csrank_ret_5d"] = df.groupby(["date", "sector"])["ret_5d"].rank(pct=True, method="average")
    df["within_sector_csrank_rsi"] = df.groupby(["date", "sector"])["rsi_norm"].rank(pct=True, method="average")
    df["within_sector_csrank_mom"] = df.groupby(["date", "sector"])["mom_12m_1m"].rank(pct=True, method="average")

    df = df.drop(columns=["sec_ret_1d", "sec_ret_5d", "sec_ret_20d", "sec_ret_60d", "sec_vol_sum"], errors="ignore")

    df["vol_growth_5d"] = df.volume_change_5d
    df["vol_growth_20d"] = df.volume_change_20d
    df["eps_delta_over_price"] = np.nan
    df["dividend_yield"] = np.nan
    return df, sessions


def _parse_datetime(value: Any) -> pd.Timestamp | None:
    if value is None or pd.isna(value) or not str(value).strip():
        return None
    try:
        dt = pd.Timestamp(value)
        if dt.tzinfo is None:
            dt = dt.tz_localize(PKT)
        else:
            dt = dt.tz_convert(PKT)
        return dt
    except Exception:
        return None


def _event_kind(event_type: Any, title: Any) -> str:
    text = f"{event_type or ''} {title or ''}".lower()
    if any(x in text for x in ["bonus", "right issue", "rights issue", "right shares"]): return "bonus"
    if any(x in text for x in ["dividend", "payout", "cash dividend", "interim dividend", "final dividend"]): return "dividend"
    if any(x in text for x in ["board meeting", "meeting of the board", "board of directors meeting", "closed period"]): return "board"
    if any(x in text for x in ["financial result", "financial statement", "earnings", "eps", "quarterly result", "annual result", "half yearly result", "profit after tax", "un-audited financial", "audited financial"]): return "results"
    if any(x in text for x in ["material information", "material fact", "discovery", "agreement", "commissioning", "acquisition", "expansion", "joint venture", "contract awarded", "license", "gas discovery", "oil discovery"]): return "material"
    return "other"


def _event_flags(event_type: Any, title: Any) -> dict[str, bool]:
    """Conservative multi-label event flags; agenda items are not outcomes."""
    text = f"{event_type or ''} {title or ''}".lower()
    board = any(x in text for x in ["board meeting", "meeting of the board", "board of directors meeting", "closed period"])
    agenda = any(x in text for x in ["to consider", "consideration of", "agenda of", "notice of board meeting"])
    results_words = any(x in text for x in [
        "financial result", "financial statement", "announcement of results", "results for the",
        "profit after tax", "un-audited financial", "audited financial", "half year financial",
        "condensed interim financial", "quarter ended", "quarterly financial", "annual financial"
    ])
    dividend_words = any(x in text for x in ["dividend", "payout", "cash dividend", "interim cash dividend", "final cash dividend"])
    bonus_words = any(x in text for x in ["bonus share", "bonus shares", "right issue", "rights issue", "issue of bonus"])
    material_words = any(x in text for x in [
        "material information", "material fact", "discovery", "agreement", "commissioning",
        "acquisition", "joint venture", "expansion", "contract awarded", "gas discovery",
        "oil discovery", "plant shutdown", "commercial operations", "ppa signed"
    ])
    return {
        "evt_results_published": bool(results_words and not (board and agenda)),
        "evt_dividend_announced": bool(dividend_words and not (board and agenda)),
        "evt_bonus_or_rights": bool(bonus_words and not (board and agenda)),
        "evt_board_meeting_notice": bool(board),
        "evt_material_info": bool(material_words),
    }


def _coverage_window(require_events: bool, allow_price_only: bool) -> tuple[pd.Timestamp | None, pd.Timestamp | None, bool]:
    if not EVENTS_PATH.exists() or not EVENT_COVERAGE_PATH.exists():
        if require_events and not allow_price_only:
            raise FileNotFoundError(
                f"Event training requires both {EVENTS_PATH} and {EVENT_COVERAGE_PATH}. "
                "See README.md; do not interpret absent history as zero events."
            )
        return None, None, False
    coverage = json.loads(EVENT_COVERAGE_PATH.read_text(encoding="utf-8"))
    if coverage.get("coverage_verified") is not True:
        if allow_price_only:
            LOG.warning("Event archive exists but is unverified; building explicit price-only diagnostic data.")
            return None, None, False
        raise ValueError("events_coverage.json must set coverage_verified=true after completeness has been checked.")
    start, end = pd.Timestamp(coverage["coverage_start"]), pd.Timestamp(coverage["coverage_end"])
    months = (end.year - start.year) * 12 + end.month - start.month
    if months < MIN_EVENT_ARCHIVE_MONTHS:
        raise ValueError(f"Verified event archive spans {months} months; need at least {MIN_EVENT_ARCHIVE_MONTHS}.")
    return start.normalize(), end.normalize(), True


def add_events(df: pd.DataFrame, sessions: list[pd.Timestamp], require_events: bool, allow_price_only: bool) -> tuple[pd.DataFrame, dict]:
    start, end, has_archive = _coverage_window(require_events, allow_price_only)
    out = df.copy()
    for col in set(EVENT_XGB + EVENT_GRU):
        out[col] = 0.0
    out["dividend_yield"] = np.nan
    out["eps_delta_over_price"] = np.nan
    out["dividend_parsed"] = 0.0
    out["eps_parsed"] = 0.0
    if not has_archive:
        out[EVENT_XGB + ["dividend_parsed", "eps_parsed"]] = 0.0
        out["events_covered"] = False
        return out, {"available": False, "mode": "price_only_diagnostic"}

    raw = pd.read_csv(EVENTS_PATH)
    if "document_url" not in raw.columns:
        raw["document_url"] = ""
    if "source_id" not in raw.columns:
        raw["source_id"] = ""
    required = {"symbol", "published_at", "title"}
    missing = required - set(raw.columns)
    if missing: raise ValueError(f"events.csv missing columns: {sorted(missing)}")
    raw["symbol"] = raw.symbol.astype(str).str.upper().str.strip()
    raw["published_local"] = raw.published_at.map(_parse_datetime)
    parse_fail = int(raw.published_local.isna().sum())
    raw = raw.dropna(subset=["published_local"]).copy()
    session_arr = np.array(sessions, dtype="datetime64[ns]")
    idx_by_date = {pd.Timestamp(d): i for i, d in enumerate(sessions)}
    available_indices = []
    for dt in raw.published_local:
        day = dt.normalize().tz_localize(None)
        idx = int(np.searchsorted(session_arr, np.datetime64(day), side="left"))
        if day in idx_by_date and dt.time() > PSX_CLOSE:
            idx = idx_by_date[day] + 1
        available_indices.append(idx if idx < len(sessions) else -1)
    raw["available_idx"] = available_indices
    raw = raw[raw.available_idx >= 0].copy()
    raw["available_date"] = raw.available_idx.map(lambda i: sessions[int(i)])
    raw["kind"] = raw.apply(lambda r: _event_kind(r.get("event_type"), r.get("title")), axis=1)
    flag_rows = raw.apply(lambda r: _event_flags(r.get("event_type"), r.get("title")), axis=1, result_type="expand")
    raw = pd.concat([raw, flag_rows], axis=1)
    raw = raw.drop_duplicates(subset=["symbol", "published_local", "title", "document_url"], keep="last")

    symbol_index = {sym: g for sym, g in out.groupby("symbol", sort=False)}
    for sym, rows in symbol_index.items():
        ev = raw[raw.symbol == sym].sort_values("available_idx")
        if ev.empty: continue
        row_idx = rows.index.to_numpy()
        row_sessions = rows.session_idx.to_numpy(dtype=int)
        eidx = ev.available_idx.to_numpy(dtype=int)
        kinds = ev.kind.to_numpy()
        for kind, col in [("evt_results_published", "evt_results_published"), ("evt_dividend_announced", "evt_dividend_announced"),
                          ("evt_bonus_or_rights", "evt_bonus_or_rights"), ("evt_board_meeting_notice", "evt_board_meeting_notice"),
                          ("evt_material_info", "evt_material_info")]:
            event_s = ev.loc[ev[kind].astype(bool), "available_idx"].to_numpy(dtype=int)
            if len(event_s):
                out.loc[row_idx, col] = np.isin(row_sessions, event_s).astype(float)
        result_idx = ev.loc[ev.evt_results_published.astype(bool), "available_idx"].to_numpy(dtype=int)
        if len(result_idx) > 0:
            past_pos = np.searchsorted(result_idx, row_sessions, side="right") - 1
            since = np.where(past_pos >= 0, row_sessions - result_idx[np.maximum(past_pos, 0)], 252.0)
            out.loc[row_idx, "sessions_since_results"] = np.minimum(since, 252)
        else:
            out.loc[row_idx, "sessions_since_results"] = 252.0

        # Board date is only exposed after a notice is published. A board date
        # written in a future notice is never visible to earlier feature rows.
        if "meeting_date" in ev.columns:
            meetings: list[tuple[int, int]] = []
            for _, erow in ev[ev.evt_board_meeting_notice.astype(bool)].iterrows():
                if pd.isna(erow.get("meeting_date")): continue
                md = pd.to_datetime(erow.meeting_date, errors="coerce")
                if pd.isna(md): continue
                meeting_session = int(np.searchsorted(session_arr, np.datetime64(pd.Timestamp(md).normalize()), side="left"))
                if meeting_session >= len(sessions): continue
                meetings.append((int(erow.available_idx), meeting_session))
            for ri, rs in zip(row_idx, row_sessions):
                known = [m for pub, m in meetings if pub <= rs and m >= rs]
                out.loc[ri, "sessions_to_board_meeting"] = min(known) - rs if known else np.nan

        # At each feature date, aggregate disclosures released in the preceding
        # five market sessions. Deduplication above defines the event identity.
        all_idx = np.sort(eidx)
        left = np.searchsorted(all_idx, row_sessions - 4, side="left")
        right = np.searchsorted(all_idx, row_sessions, side="right")
        out.loc[row_idx, "evt_count_5s"] = right - left

        # Numeric facts are conservative: structured fields only; no guess from
        # free text. Face-value percentages require an explicit face value.
        for col in ["dividend_pkr_per_share", "dividend_face_value_pct", "face_value_pkr", "eps_current", "eps_comparison"]:
            if col not in ev.columns: ev[col] = np.nan
        if "eps_period" not in ev.columns: ev["eps_period"] = ""
        if "eps_basis" not in ev.columns: ev["eps_basis"] = ""
        for ev_pos, (_, erow) in enumerate(ev.iterrows()):
            available = int(erow.available_idx)
            eligible = row_idx[row_sessions >= available]
            if len(eligible) == 0: continue
            dividend = pd.to_numeric(pd.Series([erow.dividend_pkr_per_share]), errors="coerce").iloc[0]
            if pd.isna(dividend):
                pct = pd.to_numeric(pd.Series([erow.dividend_face_value_pct]), errors="coerce").iloc[0]
                face = pd.to_numeric(pd.Series([erow.face_value_pkr]), errors="coerce").iloc[0]
                if pd.notna(pct) and pd.notna(face): dividend = pct / 100.0 * face
            if pd.notna(dividend):
                # Do not let an old payout announcement become a permanent
                # feature. Use a published ex-date when supplied, else cap at
                # 60 market sessions after publication.
                dividend_end = min(available + 60, len(sessions)-1)
                if "ex_date" in ev.columns and pd.notna(erow.get("ex_date")):
                    ex_date = pd.to_datetime(erow.get("ex_date"), errors="coerce")
                    if pd.notna(ex_date):
                        dividend_end = min(dividend_end, int(np.searchsorted(session_arr, np.datetime64(ex_date.normalize()), side="left")))
                active = eligible[row_sessions[row_sessions >= available] <= dividend_end]
                if len(active):
                    out.loc[active, "dividend_yield"] = float(dividend) / out.loc[active, "close"].values
                    out.loc[active, "dividend_parsed"] = 1.0
            cur = pd.to_numeric(pd.Series([erow.eps_current]), errors="coerce").iloc[0]
            prev = pd.to_numeric(pd.Series([erow.eps_comparison]), errors="coerce").iloc[0]
            basis = str(erow.eps_basis or "").strip().lower()
            period = str(erow.eps_period or "").strip().lower()
            if pd.notna(cur) and pd.notna(prev) and period and basis:
                next_results = result_idx[result_idx > available]
                eps_end = min(available + 126, int(next_results[0])-1 if len(next_results) else len(sessions)-1)
                active = eligible[row_sessions[row_sessions >= available] <= eps_end]
                if len(active):
                    out.loc[active, "eps_delta_over_price"] = (float(cur) - float(prev)) / out.loc[active, "close"].values
                    out.loc[active, "eps_parsed"] = 1.0

    # Populate pypsx_toolkit structured fundamental snapshot features
    fund_path = DATA_DIR / "fundamentals_snapshot.json"
    if fund_path.exists():
        try:
            fund_data = json.loads(fund_path.read_text(encoding="utf-8"))
            for sym, fdict in fund_data.items():
                dy_str = fdict.get("dividend_yield")
                pr_str = fdict.get("payout_ratio")
                
                dy_val = float(dy_str.replace("%", "").strip()) / 100.0 if dy_str and "%" in str(dy_str) else np.nan
                pr_val = float(pr_str.replace("%", "").strip()) / 100.0 if pr_str and "%" in str(pr_str) else np.nan
                
                mask = out["symbol"] == sym
                if not np.isnan(dy_val):
                    out.loc[mask, "fund_dividend_yield"] = dy_val
                if not np.isnan(pr_val):
                    out.loc[mask, "fund_payout_ratio"] = pr_val
        except Exception as exc:
            LOG.warning("Failed to parse fundamentals_snapshot.json: %s", exc)

    # Event archive is authoritative only within its declared coverage window.
    out["events_covered"] = out.date.between(start, end).astype(bool)
    counts = raw.groupby("kind").size().to_dict()
    return out, {"available": True, "mode": "event_augmented", "coverage_start": str(start.date()),
                 "coverage_end": str(end.date()), "coverage_months": (end.year-start.year)*12 + end.month-start.month,
                 "event_rows": int(len(raw)), "timestamp_parse_failures": parse_fail, "counts_by_kind": counts}



def add_target(df: pd.DataFrame, sessions: list[pd.Timestamp]) -> pd.DataFrame:
    """Five-market-session excess-return target, aligned to exact session dates."""
    session_arr = np.array(sessions, dtype="datetime64[ns]")
    target_idx = df.session_idx.to_numpy(dtype=int) + HORIZON_SESSIONS
    valid_idx = target_idx < len(sessions)
    target_dates = np.full(len(df), np.datetime64("NaT"), dtype="datetime64[ns]")
    target_dates[valid_idx] = session_arr[target_idx[valid_idx]]
    df = df.copy()
    df["target_date"] = target_dates
    lookup = df[["symbol", "date", "close", "volume"]].rename(columns={"date":"target_date", "close":"target_close", "volume":"target_volume"})
    df = df.merge(lookup, on=["symbol", "target_date"], how="left", validate="many_to_one")
    df["target_return"] = df.target_close / df.close - 1.0
    # Exclude stale/suspended endpoints and nonpositive-volume target sessions.
    df.loc[(df.volume <= 0) | (df.target_volume <= 0), "target_return"] = np.nan
    # Group indices in the dataframe are preserved; compute the leave-one-out
    # market median separately for each market date.
    bench_map = pd.Series(np.nan, index=df.index, dtype=float)
    for dt, grp in df.groupby("date", sort=False):
        bench_map.loc[grp.index] = _market_loo_median(grp, "target_return")
    df["benchmark_future_return"] = bench_map
    df["target_excess_return"] = df.target_return - df.benchmark_future_return
    df["target_class"] = np.nan
    valid = df.target_excess_return.notna()
    df["target_direction"] = np.nan
    df.loc[valid, "target_direction"] = (df.loc[valid, "target_excess_return"] > 0).astype(float)
    ranks = df.loc[valid].groupby("date").target_excess_return.rank(pct=True, method="average")
    df.loc[ranks.index[ranks <= 0.30], "target_class"] = 0  # avoid / bottom 30%
    df.loc[ranks.index[(ranks > 0.30) & (ranks < 0.70)], "target_class"] = 1
    df.loc[ranks.index[ranks >= 0.70], "target_class"] = 2  # buy / top 30%
    df = df.drop(columns=["target_close", "target_volume", "target_return", "benchmark_future_return"], errors="ignore")
    return df


def build_dataset(fetch: bool = False, years: int = 8, allow_price_only: bool = False) -> tuple[pd.DataFrame, dict]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if fetch: fetch_eight_years(years)
    raw = load_prices()
    data, sessions = _engineer_price_features(raw)
    # Relative ranks are computed across the same market date. Sparse/missing
    # technical observations remain NaN; they are not assigned an artificial
    # neutral percentile.
    for col in XGB_RANK_CORE:
        data[f"{col}_csrank"] = data.groupby("date")[col].rank(pct=True, method="average")
    data, event_meta = add_events(data, sessions, require_events=True, allow_price_only=allow_price_only)
    data = add_target(data, sessions)
    needed = set(STATIONARY_CORE + XGB_CORE + EVENT_XGB + EVENT_GRU + TARGET_COLUMNS + ["symbol", "date", "session_idx", "close", "volume", "events_covered"])
    missing = needed - set(data.columns)
    if missing: raise ValueError(f"Generated dataset missing columns: {sorted(missing)}")
    # True historical event coverage only. Price-only mode is marked and may
    # include all rows; event mode restricts training/evaluation to verified coverage.
    if event_meta["available"]:
        data = data[data.events_covered].copy()
    data = data.replace([np.inf, -np.inf], np.nan).sort_values(["date", "symbol"]).reset_index(drop=True)
    dates = sorted(pd.Timestamp(d) for d in data.date.unique())
    if len(dates) < 500:
        raise ValueError(f"Only {len(dates)} market sessions remain; need at least 500 for this experiment.")
    n = len(dates)
    val_start = dates[int(n * 0.70)]
    test_start = dates[int(n * 0.80)]
    # Outcome-end purging: train outcomes must finish before validation begins;
    # validation outcomes must finish before the sealed test begins.
    data["split"] = "test"
    data.loc[data.date < test_start, "split"] = "validation"
    data.loc[data.date < val_start, "split"] = "train"
    data.loc[(data.split == "train") & (data.target_date >= val_start), "split"] = "purged"
    data.loc[(data.split == "validation") & (data.target_date >= test_start), "split"] = "purged"
    data.to_parquet(FEATURES_PATH, index=False)
    coverage = raw.groupby("symbol").date.agg(first="min", last="max", observations="count").reset_index()
    coverage.to_csv(DATA_DIR / "symbol_coverage.csv", index=False)
    meta = {
        "source_path": str(OHLCV_PATH if OHLCV_PATH.exists() else RAW_OHLCV),
        "requested_history_years": years if fetch else None,
        "actual_price_first_date": str(raw.date.min().date()), "actual_price_last_date": str(raw.date.max().date()),
        "market_sessions": len(sessions), "symbols": int(raw.symbol.nunique()), "price_rows": int(len(raw)),
        "training_rows": int((data.split == "train").sum()), "validation_rows": int((data.split == "validation").sum()),
        "test_rows": int((data.split == "test").sum()), "purged_rows": int((data.split == "purged").sum()),
        "validation_start": str(val_start.date()), "test_start": str(test_start.date()),
        "target": "5 union-calendar-session excess return vs leave-one-symbol-out cross-sectional median; per-date 30/40/30 avoid/neutral/buy",
        "event_data": event_meta,
        "event_csv_sha256": hashlib.sha256(EVENTS_PATH.read_bytes()).hexdigest() if EVENTS_PATH.exists() else None,
        "event_coverage_sha256": hashlib.sha256(EVENT_COVERAGE_PATH.read_bytes()).hexdigest() if EVENT_COVERAGE_PATH.exists() else None,
        "gru_feature_count": len(GRU_FEATURES), "xgb_feature_count": len(XGB_FEATURES),
        "corporate_action_adjusted": False,
        "warning": "Historical symbol membership and corporate-action adjustment are not guaranteed by source OHLCV.",
    }
    META_PATH.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    LOG.info("Saved %d rows across %d dates to %s", len(data), len(dates), FEATURES_PATH)
    return data, meta


def get_dataset(rebuild: bool = False, fetch: bool = False, years: int = 8, allow_price_only: bool = False) -> tuple[pd.DataFrame, dict]:
    if rebuild or fetch or not FEATURES_PATH.exists():
        return build_dataset(fetch=fetch, years=years, allow_price_only=allow_price_only)
    df = pd.read_parquet(FEATURES_PATH)
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    _, _, current_events = _coverage_window(False, allow_price_only)
    saved_events = bool(meta.get("event_data", {}).get("available"))
    if not allow_price_only and current_events != saved_events:
        raise RuntimeError("Event input state differs from the saved feature dataset. Rebuild with --rebuild after verifying the archive.")
    if saved_events:
        event_hash = hashlib.sha256(EVENTS_PATH.read_bytes()).hexdigest()
        coverage_hash = hashlib.sha256(EVENT_COVERAGE_PATH.read_bytes()).hexdigest()
        if event_hash != meta.get("event_csv_sha256") or coverage_hash != meta.get("event_coverage_sha256"):
            raise RuntimeError("Event files changed after feature generation. Rebuild with --rebuild so features match the source archive.")
    elif not allow_price_only:
        raise RuntimeError("Saved dataset is price-only. Pass --allow-price-only for diagnostics, or add a verified event archive and rebuild.")
    return df, meta


def add_cli_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--rebuild", action="store_true", help="Rebuild all shared features and targets.")
    parser.add_argument("--fetch", action="store_true", help="Attempt an eight-year PSX refresh; writes only inside this research folder.")
    parser.add_argument("--years", type=int, default=8, help="Requested history for --fetch (default 8). Actual coverage is reported.")
    parser.add_argument("--allow-price-only", action="store_true", help="Explicit diagnostic mode when no verified event archive exists.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    add_cli_args(parser)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    df, meta = get_dataset(True, args.fetch, args.years, args.allow_price_only)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
