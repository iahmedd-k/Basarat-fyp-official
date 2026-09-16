import logging
import threading
import time

from collections import defaultdict

import pypsx_toolkit

log = logging.getLogger(__name__)

MARKET_DATA_TTL_SECONDS = 60

_market_data_cache = None
_market_data_cache_time = 0.0
_market_data_lock = threading.Lock()


class MarketService:
    MAIN_INDICES = {
        "KSE100": "KSE-100",
        "KSE30": "KSE-30",
        "KMI30": "KMI-30",
    }

    def get_indices(self):
        indices = pypsx_toolkit.get_indices()
        return [
            {
                "index": self.MAIN_INDICES.get(code, code),
                "code": code,
                "current": row["CURRENT"],
                "change": row["CHANGE"],
                "change_pct": row["PERCENTAGE_CHANGE"],
                "high": row["HIGH"],
                "low": row["LOW"],
            }
            for code, row in indices.iterrows()
            if code in self.MAIN_INDICES
        ]

    @staticmethod
    def _safe_float(value, default=0.0):
        import math
        if value is None:
            return default
        try:
            v = float(value)
            return default if math.isnan(v) or math.isinf(v) else v
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_int(value, default=0):
        import math
        if value is None:
            return default
        try:
            v = float(value)
            return default if math.isnan(v) or math.isinf(v) else int(v)
        except (TypeError, ValueError):
            return default

    def get_index_constituents(self, index_code):
        import pandas as pd

        constituents = pypsx_toolkit.index_constituents(index_code)
        if constituents is None or (isinstance(constituents, pd.DataFrame) and constituents.empty):
            return []

        results = []
        for symbol, row in constituents.iterrows():
            try:
                results.append({
                    "symbol": str(symbol),
                    "name": str(row.get("NAME", symbol)),
                    "ldcp": self._safe_float(row.get("LDCP")),
                    "current": self._safe_float(row.get("CURRENT")),
                    "change": self._safe_float(row.get("CHANGE")),
                    "change_pct": self._safe_float(row.get("CHANGE %")),
                    "weight_pct": self._safe_float(row.get("IDX WTG %")),
                    "index_points": self._safe_float(row.get("IDX POINT")),
                    "volume": self._safe_int(row.get("VOLUME")),
                    "freefloat_m": self._safe_float(row.get("FREEFLOAT (M)")),
                    "market_cap_m": self._safe_float(row.get("MARKET CAP (M)")),
                })
            except Exception:
                log.warning("Skipping malformed constituent row: %s", symbol, exc_info=True)
                continue
        return results

    def get_market_data(self, force_refresh=False):
        global _market_data_cache, _market_data_cache_time
        now = time.monotonic()
        if (
            force_refresh
            or _market_data_cache is None
            or now - _market_data_cache_time > MARKET_DATA_TTL_SECONDS
        ):
            with _market_data_lock:
                if (
                    force_refresh
                    or _market_data_cache is None
                    or now - _market_data_cache_time > MARKET_DATA_TTL_SECONDS
                ):
                    _market_data_cache = self._fetch_market_data()
                    _market_data_cache_time = now
        return _market_data_cache

    def _fetch_market_data(self):
        market = pypsx_toolkit.market_watch()
        rows = []
        for symbol, row in market.iterrows():
            ldcp = row["LDCP"]
            change_pct = (row["Change"] / ldcp * 100) if ldcp else 0.0
            rows.append(
                {
                    "symbol": symbol,
                    "sector": row["Sector"],
                    "ldcp": float(ldcp),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "current": float(row["Current"]),
                    "change": float(row["Change"]),
                    "change_pct": round(float(change_pct), 2),
                    "volume": int(row["Volume"]),
                }
            )
        return rows

    @staticmethod
    def sort_gainers(data):
        return sorted(data, key=lambda d: d["change_pct"], reverse=True)

    @staticmethod
    def sort_losers(data):
        return sorted(data, key=lambda d: d["change_pct"])

    @staticmethod
    def sort_volume(data):
        return sorted(data, key=lambda d: d["volume"], reverse=True)

    def get_top_gainers(self, limit=10):
        data = self.get_market_data()
        return self.sort_gainers(data)[:limit]

    def get_top_losers(self, limit=10):
        data = self.get_market_data()
        return self.sort_losers(data)[:limit]

    def get_volume_spikes(self, limit=10):
        data = self.get_market_data()
        return self.sort_volume(data)[:limit]

    def get_sentiment_overview(self):
        data = self.get_market_data()
        advancing = sum(1 for d in data if d["change_pct"] > 0)
        declining = sum(1 for d in data if d["change_pct"] < 0)
        unchanged = len(data) - advancing - declining
        total = len(data)

        ratio = advancing / declining if declining else float("inf")
        if ratio >= 2:
            market_mood = "strongly_bullish"
        elif ratio >= 1.5:
            market_mood = "bullish"
        elif ratio >= 1.1:
            market_mood = "slightly_bullish"
        elif ratio <= 0.5:
            market_mood = "strongly_bearish"
        elif ratio <= 0.67:
            market_mood = "bearish"
        elif ratio <= 0.9:
            market_mood = "slightly_bearish"
        else:
            market_mood = "neutral"

        sectors = defaultdict(lambda: {"total_change_pct": 0.0, "count": 0})
        for d in data:
            s = sectors[d["sector"]]
            s["total_change_pct"] += d["change_pct"]
            s["count"] += 1

        sector_performance = sorted(
            [
                {
                    "sector": sector,
                    "avg_change_pct": round(stats["total_change_pct"] / stats["count"], 2),
                    "companies": stats["count"],
                }
                for sector, stats in sectors.items()
            ],
            key=lambda x: x["avg_change_pct"],
            reverse=True,
        )

        top_movers = sorted(
            data,
            key=lambda d: abs(d["change_pct"]),
            reverse=True,
        )[:5]

        return {
            "market_mood": market_mood,
            "advancing": advancing,
            "declining": declining,
            "unchanged": unchanged,
            "advance_decline_ratio": round(ratio, 2),
            "gainers_pct": round(advancing / total * 100, 1) if total else 0,
            "losers_pct": round(declining / total * 100, 1) if total else 0,
            "sector_performance": sector_performance,
            "top_movers": top_movers,
        }