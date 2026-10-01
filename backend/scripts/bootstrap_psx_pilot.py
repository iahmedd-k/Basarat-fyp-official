"""Fetch and verify the first ten PSX symbols using no more than 45 days of OHLCV."""

from __future__ import annotations

import json
import logging
import tempfile
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import func, select

from app.db.base import get_sync_session_factory
from app.models.stock import Stock, StockDailyAnalysis, StockPrice, StockReferenceData
from app.tasks.stock_data_pipeline import (
    _symbols,
    compute_daily_analysis_task,
    persist_ohlcv_from_files,
    refresh_company_reference_task,
    refresh_dividends_task,
)

log = logging.getLogger("psx_pilot")


def run_pilot(limit: int = 10) -> dict:
    factory = get_sync_session_factory()
    session = factory()
    try:
        symbols = _symbols(session)[:limit]
    finally:
        session.close()
    if not symbols:
        raise RuntimeError("No active PSX symbols are available for the pilot")

    end = date.today()
    start = end - timedelta(days=45)
    from app.data.scraper.run_scrape import run_scrape

    with tempfile.TemporaryDirectory(prefix="psx-pilot-") as temp_dir:
        price_result = run_scrape(
            mode="full", start=start, end=end, output_dir=Path(temp_dir),
            delay=2.0, symbols_override=symbols,
        )
        database_prices = persist_ohlcv_from_files(symbols_override=symbols, data_dir=Path(temp_dir))

    try:
        reference_result = refresh_company_reference_task.run(symbols_override=symbols, force=True)
    except Exception as exc:
        reference_result = {"status": "partial", "error": f"{type(exc).__name__}: {exc}"}
        log.exception("Company reference refresh stopped; saved rows are retained")
    try:
        dividend_result = refresh_dividends_task.run(symbols_override=symbols)
    except Exception as exc:
        dividend_result = {"status": "partial", "error": f"{type(exc).__name__}: {exc}"}
        log.exception("Dividend refresh incomplete; saved rows are retained")
    try:
        analysis_result = compute_daily_analysis_task.run(symbols_override=symbols)
    except Exception as exc:
        analysis_result = {"status": "partial", "error": f"{type(exc).__name__}: {exc}"}
        log.exception("Indicator snapshot incomplete; saved rows are retained")

    session = factory()
    try:
        rows = session.execute(
            select(Stock.symbol, StockReferenceData.profile_json,
                   StockReferenceData.fundamentals_json, StockReferenceData.dividends_json,
                   StockReferenceData.profile_fetched_at, StockReferenceData.dividends_fetched_at,
                   StockDailyAnalysis.technical_json)
            .join(StockReferenceData, StockReferenceData.stock_id == Stock.id)
            .outerjoin(StockDailyAnalysis, StockDailyAnalysis.stock_id == Stock.id)
            .where(Stock.symbol.in_(symbols))
        ).all()
        price_counts = dict(session.execute(
            select(Stock.symbol, func.count(StockPrice.id))
            .join(StockPrice, StockPrice.stock_id == Stock.id)
            .where(Stock.symbol.in_(symbols), StockPrice.date >= start, StockPrice.date <= end)
            .group_by(Stock.symbol)
        ).all())
    finally:
        session.close()

    by_symbol = {}
    required_indicators = {"rsi_14", "macd", "macd_signal", "macd_histogram", "sma_14", "adx_14"}
    for symbol, profile, fundamentals, dividends, profile_at, dividends_at, technical in rows:
        fund = fundamentals or {}
        latest = (technical or {}).get("latest") or {}
        by_symbol[symbol] = {
            "profile": bool(profile_at and profile),
            "annual": bool(fund.get("annual")),
            "quarterly": bool(fund.get("quarterly")),
            "ratios": bool(fund.get("ratios")),
            "reports_fetched": fund.get("financial_reports_complete") is True,
            "report_count": len(fund.get("financial_reports") or []),
            "dividends_fetched": dividends_at is not None,
            "dividend_count": len(dividends or []),
            "price_rows_45d": price_counts.get(symbol, 0),
            "indicators": sorted(key for key in latest if key in required_indicators),
        }
    missing = []
    for symbol in symbols:
        info = by_symbol.get(symbol, {})
        needed = [key for key in ("profile", "reports_fetched", "dividends_fetched") if not info.get(key)]
        if info.get("price_rows_45d", 0) < 14:
            needed.append("45-day prices (need >=14 bars for SMA14)")
        if not required_indicators.issubset(set(info.get("indicators", []))):
            needed.append("calculated RSI/MACD/SMA14/ADX14")
        if needed:
            missing.append({"symbol": symbol, "missing": needed})

    result = {
        "status": "complete" if not missing else "partial",
        "symbols": symbols,
        "price_source": price_result,
        "database_prices": database_prices,
        "company_reference": reference_result,
        "dividends": dividend_result,
        "analysis": analysis_result,
        "per_symbol": by_symbol,
        "missing": missing,
    }
    print(json.dumps(result, default=str, indent=2))
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run_pilot(10)
    raise SystemExit(0 if result["status"] == "complete" else 2)
