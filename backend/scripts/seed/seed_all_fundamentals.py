import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.remote_exec import run_remote_python

code = """
import time
from datetime import datetime, timezone
from app.data.scraper.symbol_universe import get_active_symbols
from app.services.stock_service import StockService
from app.db.base import get_sync_session_factory
from app.tasks.refresh_fundamentals import _persist_snapshot
from app.models.fundamentals import StockFundamentals

service = StockService()
symbols_info = get_active_symbols()
all_symbols = [item["symbol"] for item in symbols_info]

with get_sync_session_factory()() as session:
    existing = set(r[0] for r in session.query(StockFundamentals.symbol).all())
    print(f"Total symbols: {len(all_symbols)}, Already in DB: {len(existing)}")
    
    needed = [s for s in all_symbols if s not in existing]
    print(f"Symbols to seed: {len(needed)}")
    
    success_count = 0
    fail_count = 0
    
    for i, sym in enumerate(needed, 1):
        t0 = time.time()
        try:
            payload = service._fetch_fundamentals_upstream(sym, allow_synthetic=True, force_refresh=True)
            _persist_snapshot(session, sym, payload, "full_seeding", datetime.now(timezone.utc))
            session.commit()
            success_count += 1
            print(f"[{i}/{len(needed)}] OK: {sym} in {time.time()-t0:.2f}s (status={payload.get('data_status')})")
        except Exception as exc:
            session.rollback()
            fail_count += 1
            print(f"[{i}/{len(needed)}] ERR: {sym} in {time.time()-t0:.2f}s: {exc}")

print(f"Seeding finished. Added: {success_count}, Failed: {fail_count}, Total in DB: {len(existing) + success_count}")
"""

run_remote_python(code)
