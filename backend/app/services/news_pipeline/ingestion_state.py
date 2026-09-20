"""Persistent ingestion state — tracks last successful ingestion time.

Uses a simple JSON file in data/ for state persistence.
No database table needed for this demo/FYP system.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

_STATE_DIR = Path("data/news_state")
_STATE_FILE = _STATE_DIR / "ingestion_state.json"


def _ensure_dir():
    _STATE_DIR.mkdir(parents=True, exist_ok=True)


def get_last_ingestion_time() -> datetime | None:
    """Return the UTC timestamp of the last successful ingestion, or None."""
    if not _STATE_FILE.exists():
        return None
    try:
        with open(_STATE_FILE) as f:
            data = json.load(f)
        ts = data.get("last_successful_ingestion")
        if ts:
            return datetime.fromisoformat(ts)
        return None
    except Exception as exc:
        log.warning("Failed to read ingestion state: %s", exc)
        return None


def set_last_ingestion_time(dt: datetime | None = None):
    """Record the current (or given) UTC timestamp as last successful ingestion."""
    _ensure_dir()
    dt = dt or datetime.now(timezone.utc)
    state = _load_state()
    state["last_successful_ingestion"] = dt.isoformat()
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    try:
        with open(_STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as exc:
        log.warning("Failed to write ingestion state: %s", exc)


def increment_run_count():
    """Increment the total run counter."""
    _ensure_dir()
    state = _load_state()
    state["total_runs"] = state.get("total_runs", 0) + 1
    try:
        with open(_STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception:
        pass


def _load_state() -> dict:
    if _STATE_FILE.exists():
        try:
            with open(_STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}
