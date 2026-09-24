import logging
import time
from io import StringIO
from datetime import date, timedelta

import pandas as pd
import pypsx_toolkit
from fastapi import Depends

from app.core.redis import cache_get_sync, cache_set_sync
from app.services.stockanalysis_fundamentals import fetch_stockanalysis_fundamentals
from app.services.market_service import MarketService

QUOTE_TTL_SECONDS = 300
FUND_TTL_SECONDS = 1800
OHLCV_TTL_SECONDS = 600
FAILED_SOURCE_TTL_SECONDS = 30
log = logging.getLogger(__name__)

# Unified in-process TTL cache: key -> (value, timestamp).
# NOTE: Per-process only. Not safe across multiple workers.
# For multi-worker deployments, replace with Redis-backed caching.
_cache: dict[str, tuple] = {}
_cache_ttl: dict[str, float] = {}


def _now():
    return time.monotonic()


def _is_empty_frame(value):
    """Treat failed and empty upstream responses as short-lived negative cache entries."""
    if isinstance(value, dict):
        data_fields = [
            item for key, item in value.items()
            if str(key).lower() not in {"symbol", "ticker", "name", "company_name", "sector"}
        ]
        return not any(item not in (None, "", [], {}) for item in data_fields)
    return value is None or bool(getattr(value, "empty", False))


def _cache_source_frame(key, value, ttl_seconds):
    # PSX failures should be briefly damped to avoid hammering the source, but
    # must not mask recovery for the full successful-data TTL.
    _cache[key] = value
    _cache_ttl[key] = _now() - max(0, ttl_seconds - FAILED_SOURCE_TTL_SECONDS) if _is_empty_frame(value) else _now()


def _get_shared_dataframe(key, loader, ttl_seconds=FUND_TTL_SECONDS):
    """Share toolkit DataFrame responses across API replicas through Redis."""
    cached = cache_get_sync(key)
    if isinstance(cached, str):
        try:
            return pd.read_json(StringIO(cached), orient="split")
        except Exception as exc:
            log.warning("Could not decode shared DataFrame cache %s: %s", key, exc)
    try:
        frame = loader()
    except Exception as exc:
        log.warning("External DataFrame fetch failed for %s: %s", key, exc)
        return None
    if frame is not None and hasattr(frame, "to_json"):
        ttl = ttl_seconds if not bool(getattr(frame, "empty", False)) else FAILED_SOURCE_TTL_SECONDS
        try:
            cache_set_sync(key, frame.to_json(orient="split", date_format="iso"), ttl)
        except Exception as exc:
            log.warning("Could not write shared DataFrame cache %s: %s", key, exc)
    return frame


class StockService:
    def __init__(self, market_service: MarketService = Depends(MarketService)):
        if market_service is None or not isinstance(market_service, MarketService):
            self._market = MarketService()
        else:
            self._market = market_service

    def _get_market_frame(self):
        import pandas as pd

        data = self._market.get_market_data_sync()
        if data is None:
            return None
        if isinstance(data, pd.DataFrame):
            return data
        if isinstance(data, list):
            if not data:
                return pd.DataFrame()
            return pd.DataFrame(data).set_index("symbol")
        return None

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
                "name": str(symbol),  # market_watch data lacks company names
                "sector": self._sector_of(symbol),
            }
            for symbol in matches[:limit]
        ]

    def _sector_of(self, symbol):
        frame = self._get_market_frame()
        if frame is None:
            return None
        try:
            if "Sector" in frame.columns:
                return frame.loc[symbol, "Sector"]
            if "sector" in frame.columns:
                return frame.loc[symbol, "sector"]
            return None
        except Exception:
            return None

    def get_sector_overview(self, symbol: str, limit: int = 5):
        symbol = str(symbol).upper()
        sector = self._sector_of(symbol)
        if sector is None:
            return None

        data = self._market.get_market_data_sync()
        if not data:
            return None

        peers = [d for d in data if str(d.get("sector", "")) == str(sector)]
        if not peers:
            return None

        peers = sorted(peers, key=lambda d: d.get("change_pct", 0.0), reverse=True)
        valid = [d for d in peers if d.get("change_pct") is not None]
        avg_change = round(sum(d["change_pct"] for d in valid) / len(valid), 2) if valid else 0.0
        advancing = sum(1 for d in peers if d.get("change_pct", 0.0) > 0)
        declining = sum(1 for d in peers if d.get("change_pct", 0.0) < 0)
        unchanged = len(peers) - advancing - declining

        rank = next((i + 1 for i, d in enumerate(peers) if d.get("symbol") == symbol), None)
        stock = next((d for d in peers if d.get("symbol") == symbol), None)

        def _peer(d):
            return {
                "symbol": d.get("symbol"),
                "name": d.get("name", d.get("symbol")),
                "current": d.get("current"),
                "ldcp": d.get("ldcp"),
                "change_pct": d.get("change_pct"),
                "volume": d.get("volume"),
            }

        return {
            "sector": sector,
            "companies_count": len(peers),
            "avg_change_pct": avg_change,
            "advancing": advancing,
            "declining": declining,
            "unchanged": unchanged,
            "stock": _peer(stock) if stock else None,
            "stock_rank": rank,
            "top_gainers": [_peer(d) for d in peers[:limit]],
            "top_losers": [_peer(d) for d in peers[-limit:][::-1]],
        }

    def get_quote(self, symbol: str):
        rows = self.get_quote_batch([symbol])
        return rows[0] if rows else None

    @staticmethod
    def _get_field(row, *names, default=None):
        if isinstance(row, dict):
            for name in names:
                if name in row:
                    return row[name]
        if hasattr(row, "__getitem__"):
            for name in names:
                try:
                    if name in row:
                        return row[name]
                except Exception:
                    pass
        if hasattr(row, "get"):
            for name in names:
                val = row.get(name)
                if val is not None:
                    return val
        return default

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
            ldcp = self._num(self._get_field(row, "LDCP", "ldcp", "close", "Close", default=0.0))
            current = self._num(self._get_field(row, "Current", "current", "price", "Price", default=0.0))
            reported_change = self._num(self._get_field(row, "Change", "change", default=0.0))
            change = round(current - ldcp, 4) if current is not None and current > 0 and ldcp is not None and ldcp > 0 else reported_change
            change_pct = round((change / ldcp * 100) if ldcp else 0.0, 2)
            volume = self._safe_int(self._get_field(row, "Volume", "volume", "Vol", "vol", default=0))
            sector = self._get_field(row, "Sector", "sector", "SECTOR", default=None)
            open_val = self._num(self._get_field(row, "Open", "open", default=0.0))
            high_val = self._num(self._get_field(row, "High", "high", default=0.0))
            low_val = self._num(self._get_field(row, "Low", "low", default=0.0))
            rows.append(
                {
                    "symbol": symbol,
                    "name": symbol,
                    "sector": sector,
                    "ldcp": ldcp,
                    "open": open_val,
                    "high": high_val,
                    "low": low_val,
                    "current": current,
                    "change": change,
                    "change_pct": change_pct,
                    "volume": volume,
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
        cache_key = f"quote:{symbol}"
        shared_key = f"stock:raw_quote:{symbol}"
        cached_at = _cache_ttl.get(cache_key, 0.0)
        if cache_key in _cache and now - cached_at <= QUOTE_TTL_SECONDS:
            return _cache[cache_key]
        shared = cache_get_sync(shared_key)
        if isinstance(shared, dict):
            _cache[cache_key] = shared
            _cache_ttl[cache_key] = now
            return shared
        try:
            frame = pypsx_toolkit.get_quote(symbol, as_dict=True)
        except TypeError:
            try:
                # Newer toolkit releases default to a DataFrame and no longer
                # accept the legacy `format` keyword.
                frame = pypsx_toolkit.get_quote(symbol)
            except TypeError:
                try:
                    frame = pypsx_toolkit.get_quote(symbol, format="dataframe")
                except Exception as exc:
                    log.warning("PSX quote fetch failed for %s: %s", symbol, exc)
                    frame = None
            except Exception as exc:
                log.warning("PSX quote fetch failed for %s: %s", symbol, exc)
                frame = None
        except Exception as exc:
            log.warning("PSX quote fetch failed for %s: %s", symbol, exc)
            frame = None
        if _is_empty_frame(frame):
            try:
                frame = pypsx_toolkit.get_quote(symbol)
            except Exception as exc:
                log.debug("PSX quote fallback failed for %s: %s", symbol, exc)
        _cache_source_frame(cache_key, frame, QUOTE_TTL_SECONDS)
        if isinstance(frame, dict):
            cache_set_sync(shared_key, frame, QUOTE_TTL_SECONDS)
        return frame

    def _get_fund_frame(self, symbol):
        symbol = str(symbol).upper()
        now = _now()
        cache_key = f"fund:{symbol}"
        shared_key = f"stock:raw_fundamentals:{symbol}"
        cached_at = _cache_ttl.get(cache_key, 0.0)
        if cache_key in _cache and now - cached_at <= FUND_TTL_SECONDS:
            return _cache[cache_key]
        shared = cache_get_sync(shared_key)
        if isinstance(shared, dict):
            _cache[cache_key] = shared
            _cache_ttl[cache_key] = now
            return shared
        try:
            frame = pypsx_toolkit.get_company_fundamentals(symbol, as_dict=True)
        except TypeError:
            try:
                # Fall back to the toolkit's default DataFrame response first.
                # `format` was removed from the public API in newer releases.
                frame = pypsx_toolkit.get_company_fundamentals(symbol)
            except TypeError:
                try:
                    frame = pypsx_toolkit.get_company_fundamentals(symbol, format="dataframe")
                except Exception as exc:
                    log.warning("PSX fundamentals fetch failed for %s: %s", symbol, exc)
                    frame = None
            except Exception as exc:
                log.warning("PSX fundamentals fetch failed for %s: %s", symbol, exc)
                frame = None
        except Exception as exc:
            log.warning("PSX fundamentals fetch failed for %s: %s", symbol, exc)
            frame = None
        if _is_empty_frame(frame):
            try:
                frame = pypsx_toolkit.get_company_fundamentals(symbol, format="json")
            except Exception:
                try:
                    frame = pypsx_toolkit.get_company_fundamentals(symbol)
                except Exception as exc:
                    log.debug("PSX fundamentals fallback failed for %s: %s", symbol, exc)
        _cache_source_frame(cache_key, frame, FUND_TTL_SECONDS)
        if isinstance(frame, dict):
            ttl = FUND_TTL_SECONDS if not _is_empty_frame(frame) else FAILED_SOURCE_TTL_SECONDS
            cache_set_sync(shared_key, frame, ttl)
        return frame

    def _fund_metric(self, symbol, category, metric):
        frame = self._get_fund_frame(symbol)
        if frame is None:
            return None
        if isinstance(frame, dict):
            metric_keys = {
                "Market Cap (000's)": ("market_cap",),
                "Shares": ("shares_outstanding", "shares"),
                "Free Float": ("free_float", "free_float_shares", "free_float_pct"),
                "EPS": ("eps",),
                "PEG": ("peg_ratio", "peg"),
                "EPS Growth (%)": ("eps_growth_pct", "eps_growth"),
                "Net Profit Margin (%)": ("net_profit_margin_pct", "net_profit_margin"),
                "Gross Profit Margin (%)": ("gross_profit_margin_pct", "gross_profit_margin"),
                "Business Description": ("business_description",),
                "Website": ("website",),
                "Address": ("address",),
            }
            for key in metric_keys.get(metric, ()):
                value = frame.get(key)
                if value not in (None, ""):
                    return self._latest_number(value)
            category_values = frame.get(category) or frame.get(category.lower())
            if isinstance(category_values, dict):
                for key, value in category_values.items():
                    if str(key).strip().lower() == metric.strip().lower() and value not in (None, ""):
                        return self._latest_number(value)
            return None
        flat_metric_keys = {
            "Market Cap (000's)": "market_cap",
            "Shares": "shares_outstanding",
            "Free Float": "free_float",
            "EPS": "eps",
            "PEG": "peg_ratio",
            "EPS Growth (%)": "eps_growth_pct",
            "Net Profit Margin (%)": "net_profit_margin_pct",
            "Gross Profit Margin (%)": "gross_profit_margin_pct",
        }
        flat_key = flat_metric_keys.get(metric)
        if flat_key and flat_key in getattr(frame, "columns", ()) and len(frame):
            return self._latest_number(frame.iloc[0][flat_key])
        if {"CATEGORY", "METRIC", "VALUE"}.issubset(set(getattr(frame, "columns", ()))):
            mask = frame["CATEGORY"].astype(str).str.casefold().eq(category.casefold()) & frame["METRIC"].astype(str).str.casefold().eq(metric.casefold())
            matches = frame.loc[mask, "VALUE"]
            if not matches.empty:
                return self._latest_number(matches.iloc[-1])
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
        cache_key = f"div:{symbol}"
        shared_key = f"stock:dividends:{symbol}"
        cached_at = _cache_ttl.get(cache_key, 0.0)
        if cache_key in _cache and now - cached_at <= FUND_TTL_SECONDS:
            return _cache[cache_key]
        shared = cache_get_sync(shared_key)
        if isinstance(shared, dict) and shared.get("__dataframe__"):
            frame = pd.DataFrame(shared.get("rows", []), columns=shared.get("columns"))
            _cache[cache_key] = frame
            _cache_ttl[cache_key] = now
            return frame
        try:
            frame = pypsx_toolkit.get_dividend_info(symbol, format="dataframe")
        except Exception:
            frame = None
        _cache_source_frame(cache_key, frame, FUND_TTL_SECONDS)
        if frame is not None and hasattr(frame, "to_dict"):
            rows = frame.to_dict(orient="records")
            columns = [str(column) for column in frame.columns]
            ttl = FUND_TTL_SECONDS if rows else FAILED_SOURCE_TTL_SECONDS
            cache_set_sync(shared_key, {"__dataframe__": True, "columns": columns, "rows": rows}, ttl)
        return frame

    def _get_ohlcv_from_file(self, symbol: str, start: date, end: date):
        import pandas as pd
        from pathlib import Path
        for p in [Path(f"data/raw/ohlcv/{symbol}.parquet"), Path(f"/app/data/raw/ohlcv/{symbol}.parquet")]:
            if p.exists():
                try:
                    df = pd.read_parquet(p)
                    if "date" in df.columns:
                        df["date"] = pd.to_datetime(df["date"])
                        df = df.set_index("date")
                    df.columns = [c.upper() for c in df.columns]
                    start_ts = pd.to_datetime(start)
                    end_ts = pd.to_datetime(end)
                    filtered = df.loc[(df.index >= start_ts) & (df.index <= end_ts)]
                    if not filtered.empty:
                        return filtered
                except Exception:
                    pass
        return None

    def _get_ohlcv(self, symbol, start: date, end: date):
        symbol = str(symbol).upper()
        key = f"ohlcv:{symbol}:{start.isoformat()}:{end.isoformat()}"
        shared_key = f"stock:ohlcv:{symbol}:{start.isoformat()}:{end.isoformat()}"
        now = _now()
        cached_at = _cache_ttl.get(key, 0.0)
        if key in _cache and now - cached_at <= OHLCV_TTL_SECONDS:
            return _cache[key]
        shared = cache_get_sync(shared_key)
        if isinstance(shared, str):
            try:
                df = pd.read_json(StringIO(shared), orient="split")
                df.index = pd.to_datetime(df.index)
                _cache[key] = df
                _cache_ttl[key] = now
                return df
            except Exception as exc:
                log.warning("Could not decode shared OHLCV cache for %s: %s", symbol, exc)
        # The daily Celery data job maintains shared parquet history. Prefer it
        # so every API request does not issue its own upstream history fetch.
        df = self._get_ohlcv_from_file(symbol, start, end)
        if df is None or (hasattr(df, "empty") and df.empty):
            try:
                df = pypsx_toolkit.get_historical(
                    symbol, start_date=start.isoformat(), end_date=end.isoformat()
                )
            except Exception as exc:
                log.warning("PSX history fetch failed for %s: %s", symbol, exc)
                df = None

        _cache_source_frame(key, df, OHLCV_TTL_SECONDS)
        if df is not None:
            ttl = OHLCV_TTL_SECONDS if not df.empty else FAILED_SOURCE_TTL_SECONDS
            try:
                cache_set_sync(shared_key, df.to_json(orient="split", date_format="iso"), ttl)
            except Exception as exc:
                log.warning("Could not write shared OHLCV cache for %s: %s", symbol, exc)
        return df

    def get_overview(self, symbol: str):
        symbol = str(symbol).upper()
        batch = self.get_quote_batch([symbol])
        if not batch:
            return {"symbol": symbol, "message": "no data"}
        q = batch[0]
        # Validate that we got real data (not an empty/default quote)
        if q.get("current") == 0.0 and q.get("volume") == 0:
            return {"symbol": symbol, "message": "no data"}
        quote = self._get_quote_frame(symbol)
        quote_freshness = self._market.quote_freshness()
        market_cap_m = self._market_cap_m(symbol)
        pe_ratio = self._quote_field(quote, "P/E RATIO (TTM) **")
        year_change_pct = self._quote_field(quote, "1-YEAR CHANGE * ^")
        ytd_change_pct = self._quote_field(quote, "YTD CHANGE * ^")

        # When the dps.psx.com.pk quote/fundamentals pages are unreachable
        # (cloud/datacenter IPs), fill the gaps from StockAnalysis.com, which
        # is reachable from those environments.
        if market_cap_m is None or pe_ratio is None or year_change_pct is None:
            try:
                sa = fetch_stockanalysis_fundamentals(symbol)
                sa_eq = sa.get("equity_profile") or {}
                sa_ratio = sa.get("ratios") or {}
                sa_limits = sa.get("trading_limits") or {}
                if market_cap_m is None:
                    market_cap_m = sa_eq.get("market_cap_pkr_m")
                if pe_ratio is None:
                    pe_ratio = sa_ratio.get("pe_ratio")
                if year_change_pct is None:
                    year_change_pct = sa_limits.get("year_change_pct")
            except Exception as exc:
                log.warning("StockAnalysis fallback failed for %s overview: %s", symbol, exc)

        if ytd_change_pct is None:
            ytd_change_pct = self._ytd_change_from_history(symbol)

        return {
            "symbol": symbol,
            "name": symbol,
            "sector": q["sector"],
            # market-watch snapshot may be from the last session (market closed /
            # cache refreshed by Celery), but it is still the most current price.
            "current_price": q["current"],
            "ltp": q["current"],
            "ldcp": q["ldcp"],
            "change": q["change"],
            "change_pct": q["change_pct"],
            "day_range": {"low": q["low"], "high": q["high"]},
            "volume": q["volume"],
            "market_cap_m": market_cap_m,
            "market_cap": market_cap_m,
            "pe_ratio": pe_ratio,
            "year_change_pct": year_change_pct,
            "ytd_change_pct": ytd_change_pct,
            "quote_as_of": quote_freshness["as_of"],
            "quote_is_stale": quote_freshness["is_stale"],
        }

    def _ytd_change_from_history(self, symbol: str):
        """Calculate year-to-date price change from the available daily bars."""
        start = date(date.today().year, 1, 1)
        frame = self._get_ohlcv(str(symbol).upper(), start, date.today())
        if frame is None or frame.empty or "CLOSE" not in frame.columns:
            return None
        first_close = self._num(frame.iloc[0].get("CLOSE"))
        last_close = self._num(frame.iloc[-1].get("CLOSE"))
        if first_close is None or first_close <= 0 or last_close is None:
            return None
        return round((last_close / first_close - 1) * 100, 2)

    def _market_cap_m(self, symbol):
        raw = self._fund_metric(symbol, "Equity Profile", "Market Cap (000's)")
        if raw is None:
            return None
        return round(raw / 1000.0, 2)

    def _quote_field(self, frame, column):
        if frame is None:
            return None
        if isinstance(frame, dict):
            aliases = {
                "P/E RATIO (TTM) **": ("pe_ratio", "pe"),
                "1-YEAR CHANGE * ^": ("year_change_pct", "year_change"),
                "YTD CHANGE * ^": ("ytd_change_pct", "ytd_change"),
            }
            for key in aliases.get(column, (column,)):
                if frame.get(key) not in (None, ""):
                    return self._latest_number(frame[key])
            return None
        if frame.empty or column not in frame.columns:
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
            return {"symbol": symbol, "range": label, "bars": [], "as_of_date": None, "data_age_days": None, "is_stale": True}

        bars = []
        for ts, row in df.iterrows():
            bars.append(
                {
                    "date": str(ts.date()),
                    "open": self._num(row["OPEN"]),
                    "high": self._num(row["HIGH"]),
                    "low": self._num(row["LOW"]),
                    "close": self._num(row["CLOSE"]),
                    "volume": self._safe_int(row["VOLUME"]),
                }
            )
        as_of = df.index[-1].date()
        age_days = max(0, (date.today() - as_of).days)
        return {"symbol": symbol, "range": label, "bars": bars, "as_of_date": as_of.isoformat(), "data_age_days": age_days, "is_stale": age_days > 3}

    def technical_indicators(
        self,
        symbol: str,
        indicators: str = "RSI,MACD,BB,SMA,ADX",
        period: int = 14,
        limit: int = 30,
    ):
        symbol = str(symbol).upper()
        norm_indicators = ",".join(sorted([i.strip().upper() for i in indicators.split(",") if i.strip()]))
        cache_key = f"tech:v2:{symbol}:{norm_indicators}:{period}:{limit}"

        # 1. Check Redis cache first
        cached = cache_get_sync(cache_key)
        if cached is not None:
            return cached

        requested = [i.strip().upper() for i in indicators.split(",") if i.strip()]
        end = date.today()
        df = self._get_ohlcv(symbol, end - timedelta(days=370), end)
        if df is None or df.empty:
            return {
                "symbol": symbol,
                "period": period,
                "overall_signal": "NEUTRAL",
                "summary_message": "No historical price data available to compute technical indicators.",
                "as_of_date": None,
                "data_age_days": None,
                "is_stale": True,
                "signals_breakdown": {"buy": 0, "neutral": 0, "sell": 0},
                "summary": {},
                "indicators": {},
            }

        close = df["CLOSE"].astype(float)
        latest_close = float(close.iloc[-1]) if not close.empty else 0.0

        def to_series(s):
            out = []
            for ts, val in s.items():
                v = float(val)
                if v != v:
                    continue
                out.append({"date": str(ts.date()), "value": round(v, 3)})
            # Apply limit to slice only recent points
            if limit and limit > 0:
                return out[-limit:]
            return out

        ind_series = {}
        summary = {}
        signals = {"buy": 0, "neutral": 0, "sell": 0}

        # --- RSI ---
        if "RSI" in requested:
            full_rsi = to_series(pypsx_toolkit.rsi(df, window=period, column="CLOSE"))
            ind_series["RSI"] = full_rsi
            if full_rsi:
                latest_rsi = full_rsi[-1]["value"]
                if latest_rsi >= 70:
                    sig, desc = "SELL", "RSI is in overbought territory (>=70); potential pullback risk."
                    signals["sell"] += 1
                elif latest_rsi <= 30:
                    sig, desc = "BUY", "RSI is in oversold territory (<=30); potential bullish rebound."
                elif latest_rsi >= 50:
                    sig, desc = "BUY", "RSI indicates positive upward momentum (50-70)."
                    signals["buy"] += 1
                else:
                    sig, desc = "NEUTRAL", "RSI is below 50, showing subdued momentum."
                    signals["neutral"] += 1
                summary["rsi"] = {"value": latest_rsi, "signal": sig, "description": desc}

        # --- MACD ---
        if "MACD" in requested:
            macd_line, macd_signal, _hist = pypsx_toolkit.macd(df, fast=12, slow=26, signal=9, column="CLOSE")
            macd_s = to_series(macd_line)
            sig_s = to_series(macd_signal)
            ind_series["MACD"] = macd_s
            ind_series["MACD_SIGNAL"] = sig_s
            if macd_s and sig_s:
                latest_macd = macd_s[-1]["value"]
                latest_sig = sig_s[-1]["value"]
                if latest_macd > latest_sig:
                    sig, desc = "BUY", "Bullish MACD crossover; upward momentum is accelerating."
                    signals["buy"] += 1
                elif latest_macd < latest_sig:
                    sig, desc = "SELL", "Bearish MACD crossover; downward momentum detected."
                    signals["sell"] += 1
                else:
                    sig, desc = "NEUTRAL", "MACD line is converging with signal line."
                    signals["neutral"] += 1
                summary["macd"] = {
                    "value": latest_macd,
                    "signal_line": latest_sig,
                    "signal": sig,
                    "description": desc,
                }

        # --- Bollinger Bands ---
        if "BB" in requested or "BOLLINGER" in requested:
            bands = pypsx_toolkit.bollinger_bands(df, window=20, num_std=2.0, column="CLOSE")
            # Toolkit documentation has used different tuple orders across
            # releases. Normalize each row mathematically so labels can never
            # invert even if an upstream version changes its return order.
            bands_frame = pd.concat([pd.Series(band) for band in bands], axis=1)
            low_s = to_series(bands_frame.min(axis=1))
            mid_s = to_series(bands_frame.median(axis=1))
            up_s = to_series(bands_frame.max(axis=1))
            ind_series["BB_LOWER"] = low_s
            ind_series["BB_MID"] = mid_s
            ind_series["BB_UPPER"] = up_s
            if low_s and mid_s and up_s:
                cur_up = up_s[-1]["value"]
                cur_low = low_s[-1]["value"]
                cur_mid = mid_s[-1]["value"]
                if latest_close >= cur_up:
                    sig, desc = "SELL", "Price is touching the upper Bollinger Band (overbought zone)."
                    signals["sell"] += 1
                elif latest_close <= cur_low:
                    sig, desc = "BUY", "Price is touching the lower Bollinger Band (oversold zone)."
                    signals["buy"] += 1
                else:
                    sig, desc = "NEUTRAL", "Price is oscillating within normal volatility bands."
                    signals["neutral"] += 1
                summary["bollinger"] = {
                    "lower": cur_low,
                    "mid": cur_mid,
                    "upper": cur_up,
                    "signal": sig,
                    "description": desc,
                }

        # --- SMA ---
        if "SMA" in requested:
            sma_s = to_series(close.rolling(window=period).mean())
            ind_series["SMA"] = sma_s
            if sma_s:
                latest_sma = sma_s[-1]["value"]
                if latest_close > latest_sma:
                    sig, desc = "BUY", f"Price (PKR {latest_close:.2f}) is above the {period}-day moving average ({latest_sma:.2f})."
                    signals["buy"] += 1
                elif latest_close < latest_sma:
                    sig, desc = "SELL", f"Price (PKR {latest_close:.2f}) is below the {period}-day moving average ({latest_sma:.2f})."
                    signals["sell"] += 1
                else:
                    sig, desc = "NEUTRAL", f"Price is matching the {period}-day moving average."
                    signals["neutral"] += 1
                summary["sma"] = {"value": latest_sma, "signal": sig, "description": desc}

        # --- ADX ---
        if "ADX" in requested:
            adx_s = to_series(self._adx(df, period))
            ind_series["ADX"] = adx_s
            if adx_s:
                latest_adx = adx_s[-1]["value"]
                if latest_adx >= 25:
                    trend_str, desc = "STRONG", f"ADX ({latest_adx:.1f}) confirms a strong directional trend."
                elif latest_adx < 20:
                    trend_str, desc = "WEAK", f"ADX ({latest_adx:.1f}) indicates a weak, choppy or range-bound market."
                else:
                    trend_str, desc = "MODERATE", f"ADX ({latest_adx:.1f}) indicates moderate trend development."
                summary["adx"] = {
                    "value": latest_adx,
                    "trend_strength": trend_str,
                    "description": desc,
                }

        # --- Overall Signal & Message ---
        buy_c, neut_c, sell_c = signals["buy"], signals["neutral"], signals["sell"]
        if buy_c >= 3 and sell_c == 0:
            overall = "STRONGLY_BULLISH"
            msg = f"Technical outlook is Strongly Bullish based on {buy_c} buy signals with 0 sell signals."
        elif buy_c > sell_c:
            overall = "BULLISH"
            msg = f"Technical outlook is Moderately Bullish with {buy_c} buy, {neut_c} neutral, and {sell_c} sell signals."
        elif sell_c >= 3 and buy_c == 0:
            overall = "STRONGLY_BEARISH"
            msg = f"Technical outlook is Strongly Bearish based on {sell_c} sell signals with 0 buy signals."
        elif sell_c > buy_c:
            overall = "BEARISH"
            msg = f"Technical outlook is Bearish with {sell_c} sell, {neut_c} neutral, and {buy_c} buy signals."
        else:
            overall = "NEUTRAL"
            msg = f"Technical outlook is Neutral / Consolidating with {buy_c} buy, {neut_c} neutral, and {sell_c} sell signals."

        result = {
            "symbol": symbol,
            "period": period,
            "as_of_date": df.index[-1].date().isoformat(),
            "data_age_days": max(0, (date.today() - df.index[-1].date()).days),
            "is_stale": (date.today() - df.index[-1].date()).days > 3,
            "overall_signal": overall,
            "summary_message": msg,
            "signals_breakdown": signals,
            "summary": summary,
            "indicators": ind_series,
        }

        # Cache in Redis (300s TTL)
        cache_set_sync(cache_key, result, 300)
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

    def _fund_raw_string(self, symbol, category, metric_name=None):
        frame = self._get_fund_frame(symbol)
        if frame is None:
            return None
        if isinstance(frame, dict):
            values = frame.get(category) or frame.get(category.lower())
            if isinstance(values, dict):
                for key, value in values.items():
                    if metric_name is None or metric_name.casefold() in str(key).casefold():
                        if value not in (None, ""):
                            return str(value)
            return None
        if frame.empty:
            return None
        try:
            if {"CATEGORY", "METRIC", "VALUE"}.issubset(set(frame.columns)):
                rows = frame.loc[frame["CATEGORY"].astype(str).str.casefold().eq(category.casefold())]
                if metric_name:
                    rows = rows.loc[rows["METRIC"].astype(str).str.casefold().str.contains(metric_name.casefold(), regex=False)]
                if not rows.empty:
                    return str(rows.iloc[-1]["VALUE"]).strip()
            for idx, row in frame.iterrows():
                cat = idx[1] if isinstance(idx, tuple) and len(idx) > 1 else ""
                met = idx[2] if isinstance(idx, tuple) and len(idx) > 2 else ""
                val = str(row.get("VALUE", "")).strip()
                if category.lower() in str(cat).lower():
                    if metric_name is None:
                        return val
                    if metric_name.lower() in str(met).lower():
                        return val
                    if metric_name.lower() in str(val).lower():
                        return str(met)
            return None
        except Exception:
            return None

    def get_fundamentals(self, symbol: str):
        symbol = str(symbol).upper()
        # v4 avoids reusing null results produced by the old toolkit adapter.
        cache_key = f"fund:v5:{symbol}"

        cached = cache_get_sync(cache_key)
        if cached is not None:
            return cached

        quote = self._get_quote_frame(symbol)
        self._get_fund_frame(symbol)  # populate cache for _fund_metric
        div = self._get_dividend_frame(symbol)

        info_dict = {}
        info_key = f"stock:ticker_info:{symbol}"
        cached_info = cache_get_sync(info_key)
        if isinstance(cached_info, dict):
            info_dict = cached_info
        else:
            try:
                t = pypsx_toolkit.Ticker(symbol)
                if hasattr(t, "info") and isinstance(t.info, dict):
                    info_dict = t.info
                    info_ttl = FUND_TTL_SECONDS if any(
                        value not in (None, "", [], {})
                        for key, value in info_dict.items()
                        if key.lower() not in {"symbol", "name", "company_name", "sector"}
                    ) else FAILED_SOURCE_TTL_SECONDS
                    cache_set_sync(info_key, info_dict, info_ttl)
            except Exception as exc:
                log.warning("PSX ticker info fetch failed for %s: %s", symbol, exc)

        # 1. Company Profile & Governance
        prof = info_dict.get("Profile", {}) if isinstance(info_dict.get("Profile"), dict) else {}
        gov = info_dict.get("Governance", {}) if isinstance(info_dict.get("Governance"), dict) else {}

        fund_data = self._get_fund_frame(symbol)
        flat_info = fund_data if isinstance(fund_data, dict) else info_dict
        desc = (
            prof.get("Business Description")
            or flat_info.get("business_description")
            or flat_info.get("description")
            or info_dict.get("business_description")
            or info_dict.get("description")
        )
        if not desc and not isinstance(fund_data, dict):
            try:
                desc = pypsx_toolkit.get_business_description(symbol)
            except Exception:
                pass
        if not desc:
            desc = self._fund_raw_string(symbol, "Profile", "Business Description")

        # Parse Governance dict where key is person name and value is title, or vice versa
        ceo, chairperson, secretary = None, None, None
        for k, v in gov.items():
            k_str, v_str = str(k).upper(), str(v).upper()
            if "CEO" in v_str or "CHIEF EXECUTIVE" in v_str: ceo = k
            elif "CEO" in k_str or "CHIEF EXECUTIVE" in k_str: ceo = v
            if "CHAIR" in v_str: chairperson = k
            elif "CHAIR" in k_str: chairperson = v
            if "SECRETARY" in v_str: secretary = k
            elif "SECRETARY" in k_str: secretary = v

        if not ceo: ceo = self._fund_raw_string(symbol, "Governance", "CEO")
        if not chairperson: chairperson = self._fund_raw_string(symbol, "Governance", "Chairperson")
        if not secretary: secretary = self._fund_raw_string(symbol, "Governance", "Company Secretary")
        website = prof.get("Website") or flat_info.get("website") or info_dict.get("website") or self._fund_raw_string(symbol, "Profile", "Website")
        address = prof.get("Address") or flat_info.get("address") or info_dict.get("address") or self._fund_raw_string(symbol, "Profile", "Address")
        sector = self._sector_of(symbol) or info_dict.get("sector")

        company_profile = {
            "name": info_dict.get("company_name") or info_dict.get("name") or symbol,
            "sector": sector,
            "business_description": desc,
            "ceo": ceo,
            "chairperson": chairperson,
            "company_secretary": secretary,
            "website": website,
            "address": address,
        }

        # 2. Equity Profile
        eq = info_dict.get("Equity Profile", {}) if isinstance(info_dict.get("Equity Profile"), dict) else {}
        market_cap_k = self._fund_metric(symbol, "Equity Profile", "Market Cap (000's)")
        if not market_cap_k and eq.get("Market Cap (000's)"):
            try: market_cap_k = float(str(eq["Market Cap (000's)"]).replace(",", "").strip())
            except Exception: pass

        # v3 of pypsx-toolkit returns market_cap in PKR; the legacy dataframe
        # field is explicitly denominated in thousands of PKR.
        if isinstance(fund_data, dict) or "market_cap" in info_dict:
            fund_values = fund_data if isinstance(fund_data, dict) else {}
            market_cap_pkr = self._num(fund_values.get("market_cap") or info_dict.get("market_cap"))
            market_cap_m = round(market_cap_pkr / 1_000_000, 2) if market_cap_pkr else None
        else:
            market_cap_pkr = (market_cap_k * 1000.0) if market_cap_k else None
            market_cap_m = round(market_cap_k / 1000.0, 2) if market_cap_k else None

        total_shares = self._safe_int(self._fund_metric(symbol, "Equity Profile", "Shares"))
        if not total_shares:
            total_shares = self._safe_int(flat_info.get("shares_outstanding") or info_dict.get("shares_outstanding"))
        if not total_shares and eq.get("Shares"):
            try: total_shares = int(float(str(eq["Shares"]).replace(",", "").strip()))
            except Exception: pass

        free_float_shares = self._safe_int(self._fund_metric(symbol, "Equity Profile", "Free Float"))
        free_float_pct = self._fund_metric(symbol, "Equity Profile", "Free Float")
        if not free_float_pct and eq.get("Free Float"):
            ff_str = str(eq["Free Float"])
            if "%" in ff_str:
                try: free_float_pct = float(ff_str.replace("%", "").strip())
                except Exception: pass

        if free_float_pct and free_float_pct > 100:
            free_float_pct = round((free_float_shares / total_shares * 100), 2) if total_shares else None
        elif free_float_pct and not free_float_shares and total_shares:
            free_float_shares = int(total_shares * (free_float_pct / 100.0))

        equity_profile = {
            "market_cap_pkr": market_cap_pkr,
            "market_cap_pkr_m": market_cap_m,
            "total_shares": total_shares if total_shares and total_shares > 0 else None,
            "free_float_shares": free_float_shares if free_float_shares and free_float_shares > 0 else None,
            "free_float_pct": free_float_pct,
        }

        # 3. Ratios & Valuation
        pe_ratio = self._quote_field(quote, "P/E RATIO (TTM) **")
        if pe_ratio is None:
            pe_ratio = self._num(flat_info.get("pe_ratio") or info_dict.get("pe_ratio"))
        eps = self._fund_metric(symbol, "Financials Annual", "EPS")
        if eps is None:
            eps = self._num(flat_info.get("eps") or info_dict.get("eps"))

        fin_ann = info_dict.get("Financials Annual", {}) if isinstance(info_dict.get("Financials Annual"), dict) else {}
        if not eps and fin_ann.get("EPS"):
            try:
                eps_parts = str(fin_ann["EPS"]).split("|")
                eps = float(eps_parts[0].strip())
            except Exception: pass

        div_yield = self._div_yield(div)
        peg = self._fund_metric(symbol, "Ratios", "PEG")
        eps_growth = self._fund_metric(symbol, "Ratios", "EPS Growth (%)")
        net_margin = self._fund_metric(symbol, "Ratios", "Net Profit Margin (%)")
        gross_margin = self._fund_metric(symbol, "Ratios", "Gross Profit Margin (%)")

        ratios = {
            "pe_ratio": pe_ratio,
            "peg_ratio": peg,
            "eps": eps,
            "eps_growth_pct": eps_growth,
            "net_profit_margin_pct": net_margin,
            "gross_profit_margin_pct": gross_margin,
            "dividend_yield_pct": div_yield,
        }

        financials_annual = (
            info_dict.get("financials_annual")
            or info_dict.get("Financials Annual")
            or (fund_data.get("financials_annual") if isinstance(fund_data, dict) else None)
        )
        financials_quarterly = (
            info_dict.get("financials_quarterly")
            or info_dict.get("Financials Quarterly")
            or (fund_data.get("financials_quarterly") if isinstance(fund_data, dict) else None)
        )

        def _financial_rows(value):
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                return [value]
            if hasattr(value, "to_dict"):
                try:
                    rows = value.to_dict(orient="records")
                    return rows if isinstance(rows, list) else None
                except (TypeError, ValueError):
                    return None
            return None

        financials_annual = _financial_rows(financials_annual)
        financials_quarterly = _financial_rows(financials_quarterly)


        # 4. Trading Limits & 52-Week Range (via snapshot)
        year_high, year_low = None, None
        cb_low, cb_up = None, None
        year_change, ytd_change = None, None
        try:
            snap = cache_get_sync(f"stock:snapshot:{symbol}")
            if not isinstance(snap, dict):
                snap = pypsx_toolkit.get_snapshot(symbol)
                if isinstance(snap, dict):
                    ttl = FUND_TTL_SECONDS if snap else FAILED_SOURCE_TTL_SECONDS
                    cache_set_sync(f"stock:snapshot:{symbol}", snap, ttl)
            if isinstance(snap, dict):
                reg = snap.get("REG", {})
                cb = reg.get("CIRCUIT BREAKER")
                if cb and isinstance(cb, (tuple, list)) and len(cb) >= 2:
                    cb_low, cb_up = self._num(cb[0]), self._num(cb[1])
                range_52 = reg.get("52-WEEK RANGE ^")
                if range_52 and isinstance(range_52, (tuple, list)) and len(range_52) >= 2:
                    year_low, year_high = self._num(range_52[0]), self._num(range_52[1])
                year_change = self._num(reg.get("1-Year Change * ^"))
                ytd_change = self._num(reg.get("YTD Change * ^"))
        except Exception:
            pass

        if year_change is None:
            year_change = self._quote_field(quote, "1-YEAR CHANGE * ^")
        if ytd_change is None:
            ytd_change = self._quote_field(quote, "YTD CHANGE * ^")

        trading_limits = {
            "year_high": year_high,
            "year_low": year_low,
            "circuit_breaker_lower": cb_low,
            "circuit_breaker_upper": cb_up,
            "year_change_pct": year_change,
            "ytd_change_pct": ytd_change,
        }

        # 5. Dividend History
        dividend_history = []
        try:
            div_df = _get_shared_dataframe(
                f"stock:dividend_history:{symbol}",
                lambda: pypsx_toolkit.get_dividend_history(symbol),
            )
            if div_df is not None and not div_df.empty:
                for _, drow in div_df.head(5).iterrows():
                    dividend_history.append({
                        "ex_date": str(drow.get("EX-DIVIDEND DATE", "")),
                        "cash_amount": str(drow.get("CASH AMOUNT", "")),
                        "record_date": str(drow.get("RECORD DATE", "")),
                        "pay_date": str(drow.get("PAY DATE", "")),
                    })
        except Exception:
            pass

        # 6. Official Announcements
        announcements = []
        try:
            ann_df = _get_shared_dataframe(
                f"stock:announcements:{symbol}",
                lambda: pypsx_toolkit.get_announcements(symbol),
            )
            if ann_df is not None and not ann_df.empty:
                for idx, arow in ann_df.head(5).iterrows():
                    ann_date = idx[1] if isinstance(idx, tuple) and len(idx) > 1 else str(idx)
                    announcements.append({
                        "date": str(ann_date),
                        "title": str(arow.get("TITLE", "")),
                        "pdf_link": str(arow.get("PDF_LINK", "")),
                    })
        except Exception:
            pass

        # Legacy backward compatible metrics & extras
        metrics = [
            _metric("EPS", eps, "Earnings per share over the last twelve months."),
            _metric("P/E Ratio", pe_ratio, "Price-to-earnings; lower values suggest cheaper valuation."),
            _metric("ROE", None, "Not provided by the PSX fundamentals feed."),
            _metric("Debt-to-Equity", None, "Not provided by the PSX fundamentals feed."),
            _metric("Dividend Yield", div_yield, "Trailing dividend yield relative to the last traded price."),
            _metric("Market Cap (PKR M)", market_cap_m, "Market capitalisation in millions of PKR."),
        ]

        extras = {
            "year_change_pct": year_change,
            "ytd_change_pct": ytd_change,
            "gross_profit_margin_pct": gross_margin,
            "net_profit_margin_pct": net_margin,
            "eps_growth_pct": eps_growth,
        }

        # Fallback: when the dps.psx.com.pk company/snapshot/quote pages are
        # unreachable from this environment (common for cloud/datacenter IPs),
        # fill the blank fundamentals from StockAnalysis.com (S&P Global data),
        # which is reachable and covers every PSX symbol.
        missing_core = {
            company_profile.get("business_description"),
            company_profile.get("ceo"),
            equity_profile.get("market_cap_pkr"),
            equity_profile.get("total_shares"),
            eps, pe_ratio, year_high, year_low,
        } == {None}
        if missing_core:
            try:
                sa = fetch_stockanalysis_fundamentals(symbol)
                sa_company = sa.get("company_profile") or {}
                sa_eq = sa.get("equity_profile") or {}
                sa_ratio = sa.get("ratios") or {}
                sa_limits = sa.get("trading_limits") or {}

                if not company_profile.get("business_description"):
                    company_profile["business_description"] = sa.get("business_description")
                if not company_profile.get("ceo"):
                    company_profile["ceo"] = sa_company.get("ceo")
                if not company_profile.get("website"):
                    company_profile["website"] = sa_company.get("website")
                if not company_profile.get("sector") and sa_company.get("sector"):
                    company_profile["sector"] = sa_company["sector"]

                if not equity_profile.get("market_cap_pkr"):
                    equity_profile["market_cap_pkr"] = sa_eq.get("market_cap_pkr")
                if not equity_profile.get("market_cap_pkr_m"):
                    equity_profile["market_cap_pkr_m"] = sa_eq.get("market_cap_pkr_m")
                if not equity_profile.get("total_shares"):
                    equity_profile["total_shares"] = sa_eq.get("total_shares")
                if not equity_profile.get("free_float_shares"):
                    equity_profile["free_float_shares"] = sa_eq.get("free_float_shares")
                if not equity_profile.get("free_float_pct"):
                    equity_profile["free_float_pct"] = sa_eq.get("free_float_pct")

                if not ratios.get("pe_ratio"):
                    ratios["pe_ratio"] = sa_ratio.get("pe_ratio")
                if not ratios.get("eps"):
                    ratios["eps"] = sa_ratio.get("eps")
                if not ratios.get("peg_ratio"):
                    ratios["peg_ratio"] = sa_ratio.get("peg_ratio")
                if not ratios.get("net_profit_margin_pct"):
                    ratios["net_profit_margin_pct"] = sa_ratio.get("net_profit_margin_pct")
                if not ratios.get("gross_profit_margin_pct"):
                    ratios["gross_profit_margin_pct"] = sa_ratio.get("gross_profit_margin_pct")
                if not ratios.get("dividend_yield_pct"):
                    ratios["dividend_yield_pct"] = sa_ratio.get("dividend_yield_pct")
                if not ratios.get("eps_growth_pct"):
                    ratios["eps_growth_pct"] = sa_ratio.get("eps_growth_pct")

                if not trading_limits.get("year_high"):
                    trading_limits["year_high"] = sa_limits.get("year_high")
                if not trading_limits.get("year_low"):
                    trading_limits["year_low"] = sa_limits.get("year_low")
                if not trading_limits.get("year_change_pct"):
                    trading_limits["year_change_pct"] = sa_limits.get("year_change_pct")

                # Refresh metrics[] rows with newly available values.
                for m in metrics:
                    key = m["key"]
                    if key == "EPS" and not m["value"]:
                        m["value"] = ratios.get("eps")
                    elif key == "P/E Ratio" and not m["value"]:
                        m["value"] = ratios.get("pe_ratio")
                    elif key == "ROE" and sa_ratio.get("roe_pct") is not None:
                        m["value"] = sa_ratio["roe_pct"]
                        m["note"] = "Return on equity; trailing twelve months."
                    elif key == "Dividend Yield" and not m["value"]:
                        m["value"] = ratios.get("dividend_yield_pct")
                    elif "Market Cap (PKR M)" in key and not m["value"]:
                        m["value"] = equity_profile.get("market_cap_pkr_m")
            except Exception as exc:
                log.warning("StockAnalysis fallback failed for %s: %s", symbol, exc)

        # Rebuild extras from the live dicts so fallback values propagate here too.
        extras = {
            "year_change_pct": trading_limits.get("year_change_pct"),
            "ytd_change_pct": ytd_change,
            "gross_profit_margin_pct": ratios.get("gross_profit_margin_pct"),
            "net_profit_margin_pct": ratios.get("net_profit_margin_pct"),
            "eps_growth_pct": ratios.get("eps_growth_pct"),
        }

        result = {
            "symbol": symbol,
            "data_status": "partial" if any(value not in (None, [], "") for value in (
                equity_profile.get("market_cap_pkr"), equity_profile.get("total_shares"), eps, pe_ratio,
                peg, eps_growth, net_margin, gross_margin, year_high, year_low, dividend_history,
            )) else "unavailable",
            "data_message": "Some company fundamentals are missing from the upstream PSX feed; blank fields are not estimated." if any(value not in (None, [], "") for value in (
                equity_profile.get("market_cap_pkr"), equity_profile.get("total_shares"), eps, pe_ratio,
                peg, eps_growth, net_margin, gross_margin, year_high, year_low, dividend_history,
            )) else "Fundamentals provider returned no usable company data; unavailable values are left blank.",
            "company_profile": company_profile,
            "equity_profile": equity_profile,
            "financials_annual": financials_annual,
            "financials_quarterly": financials_quarterly,
            "ratios": ratios,
            "trading_limits": trading_limits,
            "dividend_history": dividend_history,
            "announcements": announcements,
            "metrics": metrics,
            "extras": extras,
            "sector_overview": self.get_sector_overview(symbol),
        }

        # Keep useful fundamentals for 30m. When the upstream source is
        # blocked/unavailable, don't pin an all-null response for that long.
        useful_fields = (
            company_profile.get("business_description"), company_profile.get("ceo"),
            company_profile.get("website"), company_profile.get("address"),
            equity_profile.get("market_cap_pkr"), equity_profile.get("total_shares"),
            eps, pe_ratio, peg, eps_growth, net_margin, gross_margin, year_high, year_low,
        )
        cache_ttl = FUND_TTL_SECONDS if any(value not in (None, [], "") for value in useful_fields) else FAILED_SOURCE_TTL_SECONDS
        cache_set_sync(cache_key, result, cache_ttl)
        return result

    def _div_yield(self, div):
        if div is None or div.empty or "DIVIDEND YIELD" not in div.columns:
            return None
        value = div.iloc[0]["DIVIDEND YIELD"]
        return self._latest_number(value)

    @staticmethod
    def _num(value):
        import math

        if value is None:
            return None
        try:
            v = float(value)
            if math.isnan(v) or math.isinf(v):
                return None
            return v
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_int(value, default=0):
        import math

        if value is None:
            return default
        try:
            v = float(value)
            if math.isnan(v) or math.isinf(v):
                return default
            return int(v)
        except (TypeError, ValueError):
            return default

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
