"""
Comprehensive Redis Cache Warmup Service for Basarat Backend.

Pre-warms all shared read-paths across every domain on application startup
and background scheduled refreshes, ensuring instant sub-10ms response times.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List

from app.db.session import db_session
from app.services.market_service import MarketService
from app.services.ipo_service import IPOService
from app.services.etf_service import ETFService
from app.services.assistant_context_cache import AssistantContextCache
from app.tasks.refresh_shariah_cache import _refresh_shariah_cache

log = logging.getLogger(__name__)

TOP_BENCHMARK_SYMBOLS = [
    "OGDC", "PPL", "HBL", "MCB", "ENGRO", 
    "LUCK", "HUBC", "SYS", "PSO", "FFC"
]

TOP_ETFS = ["MIIETF", "MZNPETF", "NITGETF", "UBLPETF", "JSGBETF"]


class CacheWarmupService:
    """Orchestrates comprehensive, non-blocking Redis pre-warming across all backend domains."""

    @classmethod
    async def warm_all(cls) -> Dict[str, Any]:
        """Execute full-spectrum cache warming in parallel."""
        t0 = time.perf_counter()
        log.info("Starting comprehensive Redis cache pre-warming across all domains...")

        results: Dict[str, Any] = {}

        # 1. Market Data & Quotes
        async def _warm_market():
            svc = MarketService()
            try:
                quotes = await svc.get_market_data(read_only=True)
                indices = await svc.get_indices(read_only=True)
                sectors = await svc.get_sector_performance()
                gainers = await svc.get_top_gainers()
                losers = await svc.get_top_losers()
                volume = await svc.get_volume_spikes()
                return {
                    "status": "ok",
                    "quotes_count": len(quotes) if quotes else 0,
                    "indices_count": len(indices) if indices else 0,
                    "sectors_count": len(sectors) if sectors else 0,
                    "gainers_count": len(gainers) if gainers else 0,
                    "losers_count": len(losers) if losers else 0,
                    "volume_count": len(volume) if volume else 0,
                }
            except Exception as e:
                log.warning("Market warmup exception: %s", e)
                return {"status": "error", "error": str(e)}

        # 2. Shariah Compliance
        async def _warm_shariah():
            try:
                shariah_res = await _refresh_shariah_cache()
                return {"status": "ok", "shariah_result": shariah_res}
            except Exception as e:
                log.warning("Shariah warmup exception: %s", e)
                return {"status": "error", "error": str(e)}

        # 3. IPOs Catalog, Calendar & Performance
        async def _warm_ipos():
            try:
                async with db_session() as db:
                    svc = IPOService(db)
                    ipos = await svc.get_ipos(limit=50)
                    cal = await svc.get_calendar()
                    perf = await svc.get_performance()
                    return {
                        "status": "ok",
                        "ipos_count": ipos.total if ipos else 0,
                        "calendar_events": len(cal.upcoming_milestones) if cal else 0,
                        "listed_count": perf.total_listed if perf else 0,
                    }
            except Exception as e:
                log.warning("IPO warmup exception: %s", e)
                return {"status": "error", "error": str(e)}

        # 4. ETFs Catalog, Details & Performance
        async def _warm_etfs():
            try:
                async with db_session() as db:
                    svc = ETFService(db)
                    etfs = await svc.get_etfs()
                    for sym in TOP_ETFS:
                        try:
                            await svc.get_etf_by_symbol(sym)
                            await svc.get_performance(sym)
                            await svc.get_history(sym, timeframe="1M")
                        except Exception:
                            pass
                    return {
                        "status": "ok",
                        "etf_count": etfs.total if etfs else 0,
                    }
            except Exception as e:
                log.warning("ETF warmup exception: %s", e)
                return {"status": "error", "error": str(e)}

        # 5. Assistant Universe, AI Profiles & Feature Knowledge Base
        async def _warm_assistant():
            try:
                from app.services.assistant_knowledge import AssistantKnowledgeService
                universe = await AssistantContextCache().warm_universe()
                features = await AssistantKnowledgeService.get_feature_knowledge()
                return {
                    "status": "ok",
                    "universe_symbols": len(universe.get("symbols", {})),
                    "feature_modules_cached": len(features),
                }
            except Exception as e:
                log.warning("Assistant universe warmup exception: %s", e)
                return {"status": "error", "error": str(e)}

        # 6. Benchmark Stock Technical Indicators & Overviews
        async def _warm_stock_profiles():
            try:
                from app.services.stock_service import StockService
                stock_svc = StockService()
                warmed = 0
                for sym in TOP_BENCHMARK_SYMBOLS:
                    try:
                        await asyncio.to_thread(stock_svc.get_overview, sym)
                        await asyncio.to_thread(stock_svc.get_technicals, sym)
                        warmed += 1
                    except Exception:
                        pass
                return {"status": "ok", "stocks_warmed": warmed}
            except Exception as e:
                log.warning("Stock profiles warmup exception: %s", e)
                return {"status": "error", "error": str(e)}

        # Execute domain warmers concurrently
        task_names = [
            "market", "shariah", "ipos", "etfs", 
            "assistant_universe", "stock_profiles"
        ]
        res_list = await asyncio.gather(
            _warm_market(),
            _warm_shariah(),
            _warm_ipos(),
            _warm_etfs(),
            _warm_assistant(),
            _warm_stock_profiles(),
            return_exceptions=True
        )

        for name, r in zip(task_names, res_list):
            results[name] = r if not isinstance(r, Exception) else {"status": "error", "error": str(r)}

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        log.info("Comprehensive cache warmup completed in %.2fms", elapsed_ms)
        results["elapsed_ms"] = round(elapsed_ms, 2)
        return results


def schedule_startup_cache_warmup():
    """Fire background cache warmup task immediately on startup."""
    try:
        asyncio.create_task(CacheWarmupService.warm_all())
        log.info("Enqueued background startup cache warmup task.")
    except Exception as exc:
        log.warning("Could not schedule startup cache warmup: %s", exc)
