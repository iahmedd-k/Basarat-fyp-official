import threading
import time
from datetime import date, timedelta

import pandas as pd
import pypsx_toolkit

from app.services.market_service import MarketService

QUOTE_TTL_SECONDS = 300
FUND_TTL_SECONDS = 1800
OHLCV_TTL_SECONDS = 600

_quote_cache = {}
_quote_cache_time = {}
_quote_lock = threading.Lock()

_fund_cache = {}
_fund_cache_time = {}
_fund_lock = threading.Lock()

_div_cache = {}
_div_cache_time = {}
_div_lock = threading.Lock()

_ohlcv_cache = {}
_ohlcv_cache_time = {}
_ohlcv_lock = threading.Lock()


def _now():
    return time.monotonic()


class StockService:
    def __init__(self, market_service: MarketService = None):
        self._market = market_service or MarketService()

    def _get_market_frame(self):
        return self._market._get_market_frame()

    def search_symbols(self, q: str, limit: int = 10):
        q = (q or "").strip().upper()
        if not q:
            return []
        frame = self._get_market_frame()
        if frame is None:
            return []
        matches = [s for s in frame.index if q in str(s).upper()]
        return [
            {
                "symbol": str(symbol),
                "name": str(symbol),
                "sector": self._sector_of(symbol),
            }
            for symbol in matches[:limit]
        ]

    def _sector_of(self, symbol):
        frame = self._get_market_frame()
        if frame is None:
            return None
        try:
            return frame.loc[symbol, "Sector"]
        except Exception:
            return None

    def get_quote(self, symbol: str):
        rows = self.get_quote_batch([symbol])
        return rows[0] if rows else None

    def get_quote_batch(self, symbols):
        frame = self._get_market_frame()
        if frame is None or len(symbols) == 0:
            return []
        rows = []
        for symbol in symbols:
            symbol = str(symbol).upper()
            if symbol not in frame.index:
                rows.append(self._empty_quote(symbol))
                continue
            row = frame.loc[symbol]
            ldcp = self._num(row["LDCP"])
            current = self._num(row["Current"])
            change = self._num(row["Change"])
            change_pct = (change / ldcp * 100) if ldcp else 0.0
            rows.append(
                {
                    "symbol": symbol,
                    "name": symbol,
                    "sector": row["Sector"],
                    "ldcp": ldcp,
                    "open": self._num(row["Open"]),
                    "high": self._num(row["High"]),
                    "low": self._num(row["Low"]),
                    "current": current,
                    "change": change,
                    "change_pct": round(change_pct, 2),
                    "volume": int(row["Volume"]) if row["Volume"] == row["Volume"] else 0,
                }
            )
        return rows

    @staticmethod
    def _empty_quote(symbol):
        return {
            "symbol": symbol,
            "name": symbol,
            "sector": None,
            "ldcp": 0.0,
            "open": 0.0,
            "high": 0.0,
            "low": 0.0,
            "current": 0.0,
            "change": 0.0,
            "change_pct": 0.0,
            "volume": 0,
        }

    def _get_quote_frame(self, symbol):
        symbol = str(symbol).upper()
        now = _now()
        with _quote_lock:
            cached_at = _quote_cache_time.get(symbol, 0.0)
            if _quote_cache.get(symbol) is not None and now - cached_at <= QUOTE_TTL_SECONDS:
                return _quote_cache[symbol]
            try:
                frame = pypsx_toolkit.get_quote(symbol, format="dataframe")
            except Exception:
                frame = None
            _quote_cache[symbol] = frame
            _quote_cache_time[symbol] = now
            return frame

    def _get_fund_frame(self, symbol):
        symbol = str(symbol).upper()
        now = _now()
        with _fund_lock:
            cached_at = _fund_cache_time.get(symbol, 0.0)
            if _fund_cache.get(symbol) is not None and now - cached_at <= FUND_TTL_SECONDS:
                return _fund_cache[symbol]
            try:
                frame = pypsx_toolkit.get_company_fundamentals(symbol, format="dataframe")
            except Exception:
                frame = None
            _fund_cache[symbol] = frame
            _fund_cache_time[symbol] = now
            return frame

    def _fund_metric(self, symbol, category, metric):
        frame = self._get_fund_frame(symbol)
        if frame is None:
            return None
        try:
            mask = (
                (frame.index.get_level_values(0) == symbol)
                & (frame.index.get_level_values(1) == category)
                & (frame.index.get_level_values(2) == metric)
            )
            matches = frame.loc[mask, "VALUE"]
            if matches.empty:
                return None
            return self._latest_number(matches.iloc[0])
        except Exception:
            return None

    def _get_dividend_frame(self, symbol):
        symbol = str(symbol).upper()
        now = _now()
        with _div_lock:
            cached_at = _div_cache_time.get(symbol, 0.0)
            if _div_cache.get(symbol) is not None and now - cached_at <= FUND_TTL_SECONDS:
                return _div_cache[symbol]
            try:
                frame = pypsx_toolkit.get_dividend_info(symbol, format="dataframe")
            except Exception:
                frame = None
            _div_cache[symbol] = frame
            _div_cache_time[symbol] = now
            return frame

    def _get_ohlcv(self, symbol, start: date, end: date):
        symbol = str(symbol).upper()
        key = f"{symbol}:{start.isoformat()}:{end.isoformat()}"
        now = _now()
        with _ohlcv_lock:
            cached_at = _ohlcv_cache_time.get(key, 0.0)
            if _ohlcv_cache.get(key) is not None and now - cached_at <= OHLCV_TTL_SECONDS:
                return _ohlcv_cache[key]
            try:
                df = pypsx_toolkit.get_historical(
                    symbol, start_date=start.isoformat(), end_date=end.isoformat()
                )
            except Exception:
                df = None
            _ohlcv_cache[key] = df
            _ohlcv_cache_time[key] = now
            return df

    def get_overview(self, symbol: str):
        symbol = str(symbol).upper()
        batch = self.get_quote_batch([symbol])
        if not batch:
            return {"symbol": symbol, "message": "no data"}
        q = batch[0]
        quote = self._get_quote_frame(symbol)
        return {
            "symbol": symbol,
            "name": symbol,
            "sector": q["sector"],
            "ltp": q["current"],
            "ldcp": q["ldcp"],
            "change": q["change"],
            "change_pct": q["change_pct"],
            "day_range": {"low": q["low"], "high": q["high"]},
            "volume": q["volume"],
            "market_cap_m": self._market_cap_m(symbol),
            "market_cap": self._market_cap_m(symbol),
            "pe_ratio": self._quote_field(quote, "P/E RATIO (TTM) **"),
            "year_change_pct": self._quote_field(quote, "1-YEAR CHANGE * ^"),
            "ytd_change_pct": self._quote_field(quote, "YTD CHANGE * ^"),
        }

    def _market_cap_m(self, symbol):
        raw = self._fund_metric(symbol, "Equity Profile", "Market Cap (000's)")
        if raw is None:
            return None
        return round(raw / 1000.0, 2)

    def _quote_field(self, frame, column):
        if frame is None or frame.empty or column not in frame.columns:
            return None
        value = frame.iloc[0][column]
        return self._latest_number(value)

    RANGE_MAP = {
        "1D": ("1D", timedelta(days=3)),
        "1W": ("1W", timedelta(days=8)),
        "1M": ("1M", timedelta(days=32)),
        "1Y": ("1Y", timedelta(days=366)),
    }

    def get_price_history(self, symbol: str, range: str = "1M"):
        symbol = str(symbol).upper()
        label, lookback = self.RANGE_MAP.get(range.upper(), self.RANGE_MAP["1M"])
        end = date.today()
        start = end - lookback
        df = self._get_ohlcv(symbol, start, end)
        if df is None or df.empty:
            return {"symbol": symbol, "range": label, "bars": []}

        bars = []
        for ts, row in df.iterrows():
            bars.append(
                {
                    "date": str(ts.date()),
                    "open": self._num(row["OPEN"]),
                    "high": self._num(row["HIGH"]),
                    "low": self._num(row["LOW"]),
                    "close": self._num(row["CLOSE"]),
                    "volume": int(row["VOLUME"]) if row["VOLUME"] == row["VOLUME"] else 0,
                }
            )
        return {"symbol": symbol, "range": label, "bars": bars}

    def technical_indicators(self, symbol: str, indicators: str = "RSI,MACD,BB,SMA,ADX", period: int = 14):
        symbol = str(symbol).upper()
        requested = [i.strip().upper() for i in indicators.split(",") if i.strip()]
        end = date.today()
        df = self._get_ohlcv(symbol, end - timedelta(days=370), end)
        if df is None or df.empty:
            return {"symbol": symbol, "period": period, "indicators": {}}

        close = df["CLOSE"].astype(float)
        result = {"symbol": symbol, "period": period, "indicators": {}}

        def to_series(s):
            out = []
            for ts, val in s.items():
                v = float(val)
                if v != v:
                    continue
                out.append({"date": str(ts.date()), "value": round(v, 3)})
            return out

        if "RSI" in requested:
            result["indicators"]["RSI"] = to_series(pypsx_toolkit.rsi(df, window=period, column="CLOSE"))
        if "MACD" in requested:
            macd_line, macd_signal, _hist = pypsx_toolkit.macd(df, fast=12, slow=26, signal=9, column="CLOSE")
            result["indicators"]["MACD"] = to_series(macd_line)
            result["indicators"]["MACD_SIGNAL"] = to_series(macd_signal)
        if "BB" in requested or "BOLLINGER" in requested:
            bb_low, bb_mid, bb_up = pypsx_toolkit.bollinger_bands(df, window=20, num_std=2.0, column="CLOSE")
            result["indicators"]["BB_LOWER"] = to_series(bb_low)
            result["indicators"]["BB_MID"] = to_series(bb_mid)
            result["indicators"]["BB_UPPER"] = to_series(bb_up)
        if "SMA" in requested:
            result["indicators"]["SMA"] = to_series(close.rolling(window=period).mean())
        if "ADX" in requested:
            result["indicators"]["ADX"] = to_series(self._adx(df, period))
        return result

    @staticmethod
    def _adx(df, period=14):
        import numpy as np

        high = df["HIGH"].astype(float)
        low = df["LOW"].astype(float)
        close = df["CLOSE"].astype(float)

        plus_dm = high.diff().where(high.diff() > -low.diff(), 0.0).clip(lower=0.0)
        minus_dm = (-low.diff()).where(-low.diff() > high.diff(), 0.0).clip(lower=0.0)

        tr = pd.concat(
            [
                (high - low),
                (high - close.shift(1)).abs(),
                (low - close.shift(1)).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr = tr.ewm(alpha=1 / period, adjust=False).mean()

        plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr
        minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
        adx = dx.ewm(alpha=1 / period, adjust=False).mean()
        return adx

    def get_fundamentals(self, symbol: str):
        symbol = str(symbol).upper()
        quote = self._get_quote_frame(symbol)
        fund = self._get_fund_frame(symbol)
        div = self._get_dividend_frame(symbol)

        pe_ratio = self._quote_field(quote, "P/E RATIO (TTM) **")
        eps = self._fund_metric(symbol, "Financials Annual", "EPS")
        market_cap_m = self._market_cap_m(symbol)
        div_yield = self._div_yield(div)

        metrics = [
            _metric("EPS", eps, "Earnings per share over the last twelve months."),
            _metric("P/E Ratio", pe_ratio, "Price-to-earnings; lower values suggest cheaper valuation."),
            _metric("ROE", None, "Not provided by the PSX fundamentals feed."),
            _metric("Debt-to-Equity", None, "Not provided by the PSX fundamentals feed."),
            _metric("Dividend Yield", div_yield, "Trailing dividend yield relative to the last traded price."),
            _metric("Market Cap (PKR M)", market_cap_m, "Market capitalisation in millions of PKR."),
        ]

        extras = {
            "year_change_pct": self._quote_field(quote, "1-YEAR CHANGE * ^"),
            "ytd_change_pct": self._quote_field(quote, "YTD CHANGE * ^"),
            "gross_profit_margin_pct": self._fund_metric(symbol, "Ratios", "Gross Profit Margin (%)"),
            "net_profit_margin_pct": self._fund_metric(symbol, "Ratios", "Net Profit Margin (%)"),
            "eps_growth_pct": self._fund_metric(symbol, "Ratios", "EPS Growth (%)"),
        }

        return {"symbol": symbol, "metrics": metrics, "extras": extras}

    def _div_yield(self, div):
        if div is None or div.empty or "DIVIDEND YIELD" not in div.columns:
            return None
        value = div.iloc[0]["DIVIDEND YIELD"]
        return self._latest_number(value)

    @staticmethod
    def _num(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _latest_number(value):
        if value is None:
            return None
        text = str(value).strip().replace(",", "").replace("%", "")
        parts = [p.strip() for p in text.split("|")]
        for part in parts:
            try:
                return round(float(part), 4)
            except ValueError:
                continue
        return None


def _metric(key, value, note):
    return {"key": key, "value": value, "note": note}
