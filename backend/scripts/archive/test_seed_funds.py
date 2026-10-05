import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.remote_exec import run_remote_python

code = """
import time
from app.services.stock_service import StockService
from app.db.base import get_sync_session_factory
from app.tasks.refresh_fundamentals import _persist_snapshot
from datetime import datetime, timezone

service = StockService()
symbols = ["LUCK", "ENGROH", "MCB", "PPL"]

with get_sync_session_factory()() as session:
    for sym in symbols:
        t0 = time.time()
        try:
            payload = service._fetch_fundamentals_upstream(sym, allow_synthetic=False, force_refresh=True)
            _persist_snapshot(session, sym, payload, "manual_seed", datetime.now(timezone.utc))
            session.commit()
            print(f"Success {sym} in {time.time()-t0:.2f}s, status={payload.get('data_status')}")
        except Exception as e:
            session.rollback()
            print(f"Failed {sym} in {time.time()-t0:.2f}s: {e}")
"""

run_remote_python(code)
