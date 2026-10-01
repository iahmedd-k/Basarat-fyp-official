"""Durable daily stock-data ingestion and analysis snapshots.

External requests are serialized and paced. A missing/failed source response is
never used to overwrite previously stored values.
"""

from __future__ import annotations

import logging
import json
import math
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.celery_app import celery
from app.core.config import get_settings
from app.db.base import get_sync_session_factory
from app.models.stock import Stock, StockPrice, StockReferenceData, StockDailyAnalysis

log = logging.getLogger(__name__)


def _clean(value):
    """Remove null/blank/non-finite values recursively; preserve real zero/False."""
    if isinstance(value, dict):
        return {str(k): cleaned for k, v in value.items() if (cleaned := _clean(v)) is not None}
    if isinstance(value, (list, tuple)):
        return [cleaned for v in value if (cleaned := _clean(v)) is not None]
    if value is None:
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    if hasattr(value, "item"):
        try:
            return _clean(value.item())
        except Exception:
            return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _merge_dict(old: dict, new: dict) -> dict:
    """Non-null recursive merge; missing fields never erase prior good data."""
    merged = dict(old or {})
    for key, value in (new or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dict(merged[key], value)
        elif value not in (None, "", [], {}):
            merged[key] = value
    return merged


def _merge_period_rows(old: list | None, new: list | None) -> list:
    """Keep historical periods that DPS no longer returns; refresh known rows."""
    previous = [row for row in (old or []) if isinstance(row, dict)]
    incoming = [row for row in (new or []) if isinstance(row, dict)]
    keyed = {str(row.get("period")): row for row in previous if row.get("period") is not None}
    for row in incoming:
        period = row.get("period")
        if period is not None:
            key = str(period)
            keyed[key] = _merge_dict(keyed.get(key, {}), row)
    ordered_periods = []
    for row in incoming + previous:
        period = row.get("period")
        if period is not None and str(period) not in ordered_periods:
            ordered_periods.append(str(period))
    return [keyed[period] for period in ordered_periods]


def _stable_record_key(item: dict) -> str:
    return json.dumps(_clean(item), sort_keys=True, ensure_ascii=False, default=str)


def _merge_report_rows(old: list | None, new: list | None) -> list:
    """Keep report links permanently, refreshing metadata for known URLs."""
    rows: dict[str, dict] = {}
    for item in (old or []) + (new or []):
        if not isinstance(item, dict):
            continue
        key = str(item.get("url") or _stable_record_key(item))
        rows[key] = _merge_dict(rows.get(key, {}), item)
    return list(rows.values())


def _pace_source_request() -> None:
    time.sleep(max(2.0, float(get_settings().PSX_MIN_REQUEST_INTERVAL_SECONDS)))


def _symbols(session) -> list[str]:
    rows = session.execute(select(Stock.symbol).where(Stock.is_active.is_(True)).order_by(Stock.symbol)).scalars().all()
    symbols = [str(s).upper() for s in rows]
    # The central market-watch board contains the broader listed universe, while
    # the checked-in seed universe currently covers only a subset of equities.
    try:
        from app.core.redis import cache_get_sync
        board = cache_get_sync("market:quotes") or cache_get_sync("market:quotes:last_known") or []
        symbols.extend(str(item.get("symbol", "")).upper() for item in board if isinstance(item, dict))
    except Exception:
        pass
    from app.data.scraper.symbol_universe import get_active_symbols
    symbols.extend(item["symbol"].upper() for item in get_active_symbols() if item.get("symbol"))
    return sorted(set(s for s in symbols if s))


def _stock_row(session, symbol: str, source_name: str | None = None) -> Stock:
    row = session.execute(select(Stock).where(Stock.symbol == symbol)).scalar_one_or_none()
    if row is None:
        row = Stock(id=uuid4().hex, symbol=symbol, name=source_name or symbol, is_active=True)
        session.add(row)
        session.flush()
    elif source_name and source_name.strip() and source_name.strip().upper() != symbol:
        row.name = source_name.strip()
    return row


def _profile_fields(info: dict, sector: str | None, symbol: str) -> dict:
    profile = info.get("Profile") if isinstance(info.get("Profile"), dict) else {}
    governance = info.get("Governance") if isinstance(info.get("Governance"), dict) else {}
    equity = info.get("Equity Profile") if isinstance(info.get("Equity Profile"), dict) else {}
    market_data = info.get("Market Data") if isinstance(info.get("Market Data"), dict) else {}
    people = {}
    for key, value in governance.items():
        label, person = str(value).casefold(), str(key)
        if "chief executive" in label or "ceo" in label:
            people["ceo"] = person
        elif "chair" in label:
            people["chairperson"] = person
        elif "secretary" in label:
            people["company_secretary"] = person
    def number(value):
        try:
            return float(str(value).replace(",", "").replace("%", "").strip())
        except (TypeError, ValueError):
            return None
    company_name = info.get("company_name") or info.get("name")
    return _clean({
        "name": company_name if company_name and str(company_name).upper() != symbol else None,
        "sector": sector or info.get("sector"),
        "business_description": profile.get("Business Description") or info.get("business_description"),
        "website": profile.get("Website") or info.get("website"),
        "address": profile.get("Address") or info.get("address"),
        "registrar": profile.get("Registrar"),
        "auditor": profile.get("Auditor"),
        "fiscal_year_end": profile.get("Fiscal Year End"),
        "ceo": people.get("ceo"),
        "chairperson": people.get("chairperson"),
        "company_secretary": people.get("company_secretary"),
        "psx_url": f"https://dps.psx.com.pk/company/{symbol}",
        "market_cap": number(equity.get("Market Cap (000's)")),
        "shares_outstanding": number(equity.get("Shares")),
        "free_float": number(equity.get("Free Float")),
        "free_float_shares": number(info.get("free_float_shares")),
        "market_data": market_data,
    }) or {}


def _make_fundamentals_response(symbol: str, profile: dict, raw: dict, dividends: list | None = None) -> dict:
    fields = profile or {}
    company_profile = _clean({key: fields.get(key) for key in (
        "name", "sector", "business_description", "website", "address", "ceo",
        "chairperson", "company_secretary", "registrar", "auditor", "fiscal_year_end", "psx_url",
    )}) or {}
    market_cap = fields.get("market_cap")
    shares = fields.get("shares_outstanding")
    try:
        shares = int(shares) if shares is not None else None
    except (TypeError, ValueError):
        shares = None
    market_data = raw.get("market_data") or fields.get("market_data") or {}
    ratio_history = raw.get("ratios") or []
    ratio_values = ratio_history[0].get("values", {}) if ratio_history and isinstance(ratio_history[0], dict) else {}
    equity_profile = _clean({
        "market_cap_pkr": float(market_cap) * 1000 if market_cap is not None else None,
        "market_cap_pkr_m": float(market_cap) if market_cap is not None else None,
        "total_shares": shares,
        "free_float_pct": fields.get("free_float"),
        "free_float_shares": fields.get("free_float_shares"),
    }) or {}
    return _clean({
        "symbol": symbol,
        "data_status": "available" if raw.get("annual") or raw.get("quarterly") or raw.get("ratios") else "partial",
        "data_message": "Loaded from the latest durable PSX snapshot.",
        "psx_official_url": fields.get("psx_url") or f"https://dps.psx.com.pk/company/{symbol}",
        "company_profile": company_profile,
        "equity_profile": equity_profile,
        "financials_annual": raw.get("annual") or [],
        "financials_quarterly": raw.get("quarterly") or [],
        "financials_unit": "PKR thousands except EPS",
        "ratio_history": ratio_history,
        "market_data": market_data,
        "ratios": {
            "pe_ratio": market_data.get("pe_ratio_ttm") or ratio_values.get("pe_ratio"),
            "peg_ratio": ratio_values.get("peg_ratio"),
            "eps": ratio_values.get("eps"),
            "eps_growth_pct": ratio_values.get("eps_growth_pct"),
            "net_profit_margin_pct": ratio_values.get("net_profit_margin_pct"),
            "gross_profit_margin_pct": ratio_values.get("gross_profit_margin_pct"),
            "dividend_yield_pct": ratio_values.get("dividend_yield_pct"),
        },
        "trading_limits": {
            "year_high": market_data.get("week52_high"),
            "year_low": market_data.get("week52_low"),
        },
        "financial_reports": raw.get("financial_reports") or [],
        "financial_reports_count": raw.get("financial_reports_count") or len(raw.get("financial_reports") or []),
        "dividend_history": dividends or [],
        "announcements": [],
        "metrics": [],
    }) or {"symbol": symbol, "data_status": "unavailable"}


@celery.task(name="app.tasks.stock_data_pipeline.refresh_company_reference")
def refresh_company_reference_task(symbols_override: list[str] | None = None, force: bool = False):
    """Refresh profile, statements, and ratios from one company-page scrape per symbol."""
    factory = get_sync_session_factory()
    updated = failed = 0
    session = factory()
    try:
        symbols = _symbols(session)
        if symbols_override is not None:
            requested = {str(symbol).strip().upper() for symbol in symbols_override}
            symbols = [symbol for symbol in symbols if symbol in requested]
        session.close()
        # Database timestamps are the durable daily cache: a retried or
        # manually re-fired task does not repeat successful DPS page requests.
        today = datetime.now(timezone.utc).date()
        session = factory()
        fresh_rows = session.execute(
            select(Stock.symbol, StockReferenceData.profile_fetched_at,
                   StockReferenceData.fundamentals_fetched_at, StockReferenceData.fundamentals_json)
            .join(StockReferenceData, StockReferenceData.stock_id == Stock.id)
            .where(Stock.symbol.in_(symbols))
        ).all() if symbols else []
        session.close()
        fresh_today = {
            str(symbol).upper() for symbol, profile_at, fundamentals_at, saved_fundamentals in fresh_rows
            if profile_at and fundamentals_at
            and profile_at.date() == today and fundamentals_at.date() == today
            and (
                (saved_fundamentals or {}).get("financial_reports_complete") is True
                if "financial_reports_complete" in (saved_fundamentals or {})
                else bool((saved_fundamentals or {}).get("financial_reports"))
            )
        }
        pending_symbols = symbols if force else [symbol for symbol in symbols if symbol not in fresh_today]
        from app.services.psx_company_tables import (
            _fetch_company_tables, _fetch_financial_reports, cache_company_tables,
            cache_financial_reports, close_psx_connection_batch,
            clear_psx_source_failure, psx_access_denied,
            psx_source_failure, reset_psx_access_denied,
        )
        reset_psx_access_denied()
        consecutive_empty_pages = 0
        layout_failure = False
        incomplete_symbols: list[str] = []

        for index, symbol in enumerate(pending_symbols):
            if index:
                _pace_source_request()
            try:
                payload = _fetch_company_tables(symbol, allow_fallback=False) or {}
                if psx_access_denied():
                    failed += len(pending_symbols) - index
                    log.error("Stopping company refresh after PSX denied requests; stored rows are unchanged")
                    break
                info = payload.get("source_info") or {}
                if not info:
                    failed += 1
                    incomplete_symbols.append(symbol)
                    consecutive_empty_pages += 1
                    log.warning("No usable DPS company page for %s; stored values retained", symbol)
                    layout_failure = layout_failure or consecutive_empty_pages >= 3
                    continue
                consecutive_empty_pages = 0
                # Report links live on the official PSX Financials host. Keep
                # a full minimum interval between it and the DPS company page.
                _pace_source_request()
                report_data = _fetch_financial_reports(symbol)
                if psx_access_denied():
                    failed += len(pending_symbols) - index
                    log.error("Stopping company refresh after PSX denied financial-report access")
                    break
                reports_complete = psx_source_failure() is None
                if reports_complete:
                    cache_financial_reports(symbol, report_data)
                else:
                    failed += 1
                    incomplete_symbols.append(symbol)
                profile = _profile_fields(info, info.get("sector"), symbol)
                profile_raw = _clean({
                    "symbol": symbol,
                    "profile": info.get("Profile"),
                    "governance": info.get("Governance"),
                    "equity_profile": info.get("Equity Profile"),
                    "market_data": info.get("Market Data"),
                    "free_float_shares": info.get("free_float_shares"),
                    "source_url": payload.get("source_url"),
                }) or {}
                fundamentals = _clean({
                    "annual": payload.get("financials_annual"),
                    "quarterly": payload.get("financials_quarterly"),
                    "ratios": payload.get("ratio_history"),
                    "market_data": info.get("Market Data"),
                    "financial_reports": report_data.get("financial_reports"),
                    "financial_reports_count": report_data.get("total_reports_count"),
                    "financial_reports_complete": reports_complete,
                    "payouts": info.get("Payouts") or [],
                }) or {}
                has_profile_values = any(key not in {"symbol", "source_url"} for key in profile_raw)
                if not has_profile_values and not fundamentals:
                    failed += 1
                    continue

                session = factory()
                stock = _stock_row(session, symbol, profile.get("name"))
                if profile.get("sector"):
                    stock.sector = str(profile["sector"])
                record = session.get(StockReferenceData, stock.id)
                if record is None:
                    record = StockReferenceData(stock_id=stock.id)
                    session.add(record)
                now = datetime.now(timezone.utc)
                if profile_raw:
                    record.profile_json = _merge_dict(record.profile_json or {}, {**profile_raw, **profile})
                    record.profile_fetched_at = now
                if fundamentals:
                    previous_fundamentals = record.fundamentals_json or {}
                    for history_key in ("annual", "quarterly", "ratios"):
                        fundamentals[history_key] = _merge_period_rows(
                            previous_fundamentals.get(history_key), fundamentals.get(history_key),
                        )
                    fundamentals["financial_reports"] = _merge_report_rows(
                        previous_fundamentals.get("financial_reports"), fundamentals.get("financial_reports"),
                    )
                    record.fundamentals_json = _merge_dict(previous_fundamentals, fundamentals)
                if "Payouts" in info:
                    record.dividends_json = _merge_report_rows(record.dividends_json or [], info.get("Payouts") or [])
                    record.dividends_fetched_at = now
                # The timestamp records a successful page check, including a
                # valid company with no financial table yet. That keeps daily
                # retries from re-requesting the same unchanged page.
                record.fundamentals_fetched_at = now
                if profile or fundamentals:
                    record.fundamentals_response_json = _make_fundamentals_response(
                        symbol, _merge_dict(record.profile_json or {}, profile),
                        _merge_dict(record.fundamentals_json or {}, fundamentals),
                        record.dividends_json or [],
                    )
                stock.last_synced_at = now.replace(tzinfo=None)
                session.commit()
                updated += 1
                cache_company_tables(symbol, payload)
                if not reports_complete:
                    log.warning("Saved DPS page data for %s; report index is pending (%s)",
                                symbol, psx_source_failure())
            except Exception:
                if session:
                    session.rollback()
                failed += 1
                log.warning("Reference refresh failed for %s; retained existing values", symbol, exc_info=True)
            finally:
                if session:
                    session.close()
                if (index + 1) % 10 == 0:
                    close_psx_connection_batch()
                clear_psx_source_failure()
        if psx_access_denied():
            raise RuntimeError("PSX denied profile/fundamental scraping; pipeline halted without overwriting stored values")
        if not updated and not fresh_today:
            raise RuntimeError("No valid profile/fundamental source records were returned; pipeline halted")
        close_psx_connection_batch()
        return {
            "status": "completed", "symbols": len(symbols), "updated": updated,
            "failed": failed, "incomplete_symbols": incomplete_symbols,
            "layout_warning": layout_failure, "already_fresh_today": len(fresh_today),
        }
    finally:
        try:
            session.close()
        except Exception:
            pass


@celery.task(name="app.tasks.stock_data_pipeline.refresh_dividends")
def refresh_dividends_task(symbols_override: list[str] | None = None, force: bool = False):
    """Refresh dividend history, appending valid source records without deleting history."""
    factory = get_sync_session_factory()
    session = factory()
    symbols = _symbols(session)
    session.close()
    if symbols_override is not None:
        requested = {str(symbol).strip().upper() for symbol in symbols_override}
        symbols = [symbol for symbol in symbols if symbol in requested]
    today = datetime.now(timezone.utc).date()
    session = factory()
    fresh_rows = session.execute(
        select(Stock.symbol, StockReferenceData.dividends_fetched_at)
        .join(StockReferenceData, StockReferenceData.stock_id == Stock.id)
        .where(Stock.symbol.in_(symbols))
    ).all() if symbols else []
    session.close()
    fresh_today = {
        str(symbol).upper() for symbol, fetched_at in fresh_rows
        if fetched_at and fetched_at.date() == today
    }
    pending_symbols = symbols if force else [symbol for symbol in symbols if symbol not in fresh_today]
    if not pending_symbols:
        return {"status": "completed", "symbols": len(symbols), "updated": 0, "failed": 0,
                "already_fresh_today": len(fresh_today)}
    from app.services.stock_service import StockService

    updated = failed = 0
    blocked = False
    service = StockService()
    for index, symbol in enumerate(pending_symbols):
        if index and index % 10 == 0:
            service = StockService()
        if index:
            _pace_source_request()
        try:
            frame = service._get_dividend_frame(symbol, allow_source=True, force=True)
            if frame is None or getattr(frame, "empty", True):
                failed += 1
                continue
            incoming = _clean(frame.to_dict(orient="records")) or []
            if not incoming:
                failed += 1
                continue
            session = factory()
            stock = _stock_row(session, symbol)
            record = session.get(StockReferenceData, stock.id)
            if record is None:
                record = StockReferenceData(stock_id=stock.id)
                session.add(record)
            old = list(record.dividends_json or [])
            # Merge by stable content identity; source omissions do not erase past records.
            keyed = {_stable_record_key(item): item for item in old if isinstance(item, dict)}
            for item in incoming:
                if isinstance(item, dict):
                    key = _stable_record_key(item)
                    keyed[key] = _merge_dict(keyed.get(key, {}), item)
            record.dividends_json = list(keyed.values())
            record.dividends_fetched_at = datetime.now(timezone.utc)
            normalized = []
            for item in record.dividends_json:
                lowered = {str(k).casefold().replace("_", " "): v for k, v in item.items()}
                mapped = _clean({
                    "ex_date": next((v for k, v in lowered.items() if "ex date" in k or "ex-date" in k), None),
                    "cash_amount": next((v for k, v in lowered.items() if "cash" in k and "dividend" in k), None),
                    "record_date": next((v for k, v in lowered.items() if "record date" in k or "book closure" in k), None),
                    "pay_date": next((v for k, v in lowered.items() if "payment date" in k or "pay date" in k), None),
                }) or {}
                if mapped:
                    normalized.append(mapped)
            if record.fundamentals_json:
                raw = record.fundamentals_json or {}
                record.fundamentals_response_json = _make_fundamentals_response(
                    symbol, record.profile_json or {}, raw, normalized,
                )
            session.commit()
            updated += 1
        except Exception as exc:
            failed += 1
            if "session" in locals():
                session.rollback()
            log.warning("Dividend refresh failed for %s; retained existing values", symbol, exc_info=True)
            response = getattr(exc, "response", None)
            status_code = getattr(response, "status_code", None) or getattr(exc, "status_code", None)
            if status_code in (403, 429):
                blocked = True
                failed += max(0, len(pending_symbols) - index - 1)
                break
        finally:
            if "session" in locals():
                session.close()
    if blocked:
        raise RuntimeError("PSX denied dividend scraping; pipeline halted without deleting existing history")
    if not updated:
        raise RuntimeError("No valid dividend source records were returned; previous dividend records were retained")
    return {"status": "completed", "symbols": len(symbols), "updated": updated, "failed": failed,
            "already_fresh_today": len(fresh_today)}


def persist_ohlcv_from_files(
    symbols_override: list[str] | None = None,
    data_dir: Path | None = None,
) -> dict:
    """Persist a 45-day OHLCV window, optionally from an isolated pilot folder."""
    cutoff = date.today() - timedelta(days=45)
    base = Path(data_dir) if data_dir is not None else Path("data/raw/ohlcv")
    if data_dir is None and not base.exists():
        base = Path(__file__).resolve().parents[2] / "data" / "raw" / "ohlcv"
    paths = sorted(p for p in base.glob("*.parquet") if p.name != "all_symbols.parquet")
    if symbols_override is not None:
        selected = {str(symbol).strip().upper() for symbol in symbols_override}
        paths = [path for path in paths if path.stem.upper() in selected]
    factory = get_sync_session_factory()
    session = factory()
    inserted = invalid = 0
    try:
        symbols = {p.stem.upper() for p in paths}
        stocks = {s.symbol: s for s in session.execute(select(Stock).where(Stock.symbol.in_(symbols))).scalars().all()} if symbols else {}
        for symbol in symbols:
            if symbol not in stocks:
                stocks[symbol] = _stock_row(session, symbol)
        session.flush()
        stock_ids = {symbol: row.id for symbol, row in stocks.items()}
        rows = []
        for path in paths:
            symbol = path.stem.upper()
            try:
                frame = pd.read_parquet(path)
                frame.columns = [str(c).lower() for c in frame.columns]
                if "date" not in frame.columns:
                    continue
                frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.date
                frame = frame[frame["date"] >= cutoff]
                for item in frame.to_dict(orient="records"):
                    try:
                        trade_date = pd.to_datetime(item["date"]).date()
                        values = {key: float(item[key]) for key in ("open", "high", "low", "close")}
                        if not all(math.isfinite(v) and v > 0 for v in values.values()):
                            invalid += 1
                            continue
                        volume = int(float(item.get("volume") or 0))
                        rows.append({"id": uuid4().hex, "stock_id": stock_ids[symbol], "date": trade_date,
                                     **values, "volume": max(0, volume), "adjusted_close": values["close"]})
                    except Exception:
                        invalid += 1
            except Exception:
                log.warning("Could not read OHLCV file %s", path, exc_info=True)
        for start in range(0, len(rows), 1000):
            statement = pg_insert(StockPrice).values(rows[start:start + 1000])
            statement = statement.on_conflict_do_update(
                constraint="uq_stock_prices_stock_date",
                set_={key: getattr(statement.excluded, key) for key in ("open", "high", "low", "close", "volume", "adjusted_close")},
            )
            session.execute(statement)
            inserted += min(1000, len(rows) - start)
        pruned = session.query(StockPrice).filter(StockPrice.date < cutoff).delete(synchronize_session=False)
        session.commit()
        return {"rows_upserted": inserted, "rows_pruned": pruned, "retention_days": 45,
                "cutoff_date": cutoff.isoformat(), "invalid_rows_skipped": invalid, "files": len(paths)}
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def hydrate_ohlcv_files_from_database() -> dict:
    """Seed scraper history files from PostgreSQL before incremental scraping.

    The scraper calculates each symbol's next request date from its Parquet
    file. Without this seed, a missing local file makes it request history from
    2000 even when PostgreSQL already contains years of durable price data.
    """
    base = Path("data/raw/ohlcv")
    if not base.exists():
        base = Path(__file__).resolve().parents[2] / "data" / "raw" / "ohlcv"
    base.mkdir(parents=True, exist_ok=True)
    factory = get_sync_session_factory()
    session = factory()
    try:
        rows = session.execute(
            select(Stock.symbol, StockPrice.date, StockPrice.open, StockPrice.high,
                   StockPrice.low, StockPrice.close, StockPrice.volume)
            .join(Stock, Stock.id == StockPrice.stock_id)
            .order_by(Stock.symbol, StockPrice.date)
        ).all()
    finally:
        session.close()
    grouped: dict[str, list[dict]] = {}
    for symbol, trade_date, open_, high, low, close, volume in rows:
        prices = (open_, high, low, close)
        if any(value is None or not math.isfinite(float(value)) or float(value) <= 0 for value in prices):
            continue
        grouped.setdefault(str(symbol).upper(), []).append({
            "date": pd.Timestamp(trade_date), "open": float(open_), "high": float(high),
            "low": float(low), "close": float(close), "volume": int(volume or 0),
        })
    from app.data.scraper.writers import write_symbol_parquet
    written = 0
    for symbol, database_rows in grouped.items():
        frame = pd.DataFrame(database_rows)
        path = base / f"{symbol}.parquet"
        if path.exists():
            try:
                existing = pd.read_parquet(path)
                existing.columns = [str(column).lower() for column in existing.columns]
                frame = pd.concat([existing, frame], ignore_index=True)
                frame = frame.drop_duplicates(subset=["date"], keep="last").sort_values("date")
            except Exception:
                log.warning("Could not merge local OHLCV file for %s; reseeding from PostgreSQL", symbol)
        write_symbol_parquet(frame, symbol, base)
        written += 1
    return {"files_seeded": written, "database_rows": len(rows)}


@celery.task(name="app.tasks.stock_data_pipeline.persist_daily_prices")
def persist_daily_prices_task():
    return {"status": "completed", **persist_ohlcv_from_files()}


@celery.task(name="app.tasks.stock_data_pipeline.compute_daily_analysis")
def compute_daily_analysis_task(symbols_override: list[str] | None = None):
    """Calculate recent technical indicators from the stored 45-day OHLCV window."""
    factory = get_sync_session_factory()
    session = factory()
    query = select(Stock.id, Stock.symbol, StockReferenceData.fundamentals_fetched_at,
                   StockReferenceData.fundamentals_json).join(
        StockReferenceData, StockReferenceData.stock_id == Stock.id,
    ).where(Stock.is_active.is_(True), StockReferenceData.fundamentals_fetched_at.is_not(None))
    if symbols_override is not None:
        selected = [str(symbol).strip().upper() for symbol in symbols_override]
        query = query.where(Stock.symbol.in_(selected))
    references = session.execute(query.order_by(Stock.symbol)).all()
    cutoff = date.today() - timedelta(days=45)
    prices = session.execute(
        select(Stock.symbol, StockPrice.date, StockPrice.high, StockPrice.low, StockPrice.close)
        .join(Stock, Stock.id == StockPrice.stock_id)
        .where(Stock.symbol.in_([row.symbol for row in references]), StockPrice.date >= cutoff,
               StockPrice.high.is_not(None), StockPrice.low.is_not(None), StockPrice.close.is_not(None))
        .order_by(Stock.symbol, StockPrice.date)
    ).all() if references else []
    session.close()
    grouped: dict[str, list[dict]] = {}
    for symbol, trade_date, high, low, close in prices:
        grouped.setdefault(symbol, []).append({
            "date": trade_date, "high": float(high), "low": float(low), "close": float(close),
        })

    from app.services.technical_calculator import calculate_recent_indicators
    snapshots = []
    skipped = 0
    for stock_id, symbol, fetched_at, fundamentals in references:
        calculated = calculate_recent_indicators(pd.DataFrame(grouped.get(symbol, [])), period=14)
        if not calculated.get("as_of_date") or not calculated.get("latest"):
            skipped += 1
            continue
        source = fundamentals or {}
        snapshots.append((stock_id, symbol, date.fromisoformat(calculated["as_of_date"]), _clean({
            "source": "PSX OHLCV; locally calculated indicators",
            "as_of_date": calculated["as_of_date"],
            "source_data_as_of": fetched_at,
            "lookback_days": 45,
            "latest": calculated["latest"],
            "history": calculated["history"],
            "market_data": source.get("market_data") or {},
            "financial_ratios": source.get("ratios") or [],
        }) or {}))

    session = factory()
    saved = 0
    try:
        for stock_id, symbol, as_of, technical in snapshots:
            row = session.execute(select(StockDailyAnalysis).where(
                StockDailyAnalysis.stock_id == stock_id,
                StockDailyAnalysis.as_of_date == as_of,
            )).scalar_one_or_none()
            if row is None:
                row = StockDailyAnalysis(id=uuid4().hex, stock_id=stock_id, as_of_date=as_of)
                session.add(row)
            row.technical_json = technical
            row.risk_json = {}
            saved += 1
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    return {"status": "completed" if saved else "empty", "symbols": len(references), "saved": saved, "skipped": skipped}
