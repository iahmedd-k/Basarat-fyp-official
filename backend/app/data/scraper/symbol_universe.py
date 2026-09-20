"""
Symbol Universe — fetch, freeze, and load the PSX stock universe.

The frozen list is stored at ``data/config/symbol_universe.json`` and read
by all downstream scraping.  Re-freezing (re-fetching index constituents)
is a manual/periodic step, NOT part of the normal scrape job.
"""

import json
import logging
from datetime import date
from pathlib import Path
from typing import Dict, List

log = logging.getLogger(__name__)

# Indices to union together
# Note: KMI100 is excluded — PSX returns 404 for that index code.
_INDEX_NAMES: List[str] = ["KSE100", "KSE30", "KMI30"]

# Default path relative to project root or backend
_BACKEND_DIR = Path(__file__).resolve().parents[3]
_DEFAULT_CONFIG_DIR = Path("data/config") if Path("data/config").exists() else _BACKEND_DIR / "data" / "config"
_DEFAULT_UNIVERSE_FILE = _DEFAULT_CONFIG_DIR / "symbol_universe.json"


def _fetch_index_constituents(index_name: str) -> List[str]:
    """Return list of symbol strings for a single index via psxdata."""
    import psxdata

    log.info("Fetching constituents for %s ...", index_name)
    result = psxdata.indices(index_name)
    if result is None or (hasattr(result, "empty") and result.empty):
        log.warning("psxdata.indices(%s) returned empty result", index_name)
        return []

    # psxdata.indices returns a DataFrame; the symbol column is typically
    # the index or the first column.  Handle both cases.
    if hasattr(result, "index") and result.index.name:
        symbols = result.index.astype(str).tolist()
    elif hasattr(result, "columns") and len(result.columns) > 0:
        symbols = result.iloc[:, 0].astype(str).tolist()
    else:
        symbols = [str(s) for s in result.tolist()]

    log.info("  %s: %d symbols", index_name, len(symbols))
    return symbols


def fetch_symbol_universe(config_dir: Path | None = None) -> List[Dict]:
    """Fetch constituents from all indices, union, deduplicate, and return
    the unified list (not yet written to disk).

    Each entry: ``{symbol, indices: [...], frozen_date: "YYYY-MM-DD"}``
    """
    today = date.today().isoformat()
    symbol_map: Dict[str, Dict] = {}

    for idx_name in _INDEX_NAMES:
        try:
            symbols = _fetch_index_constituents(idx_name)
        except Exception as exc:
            log.error("Failed to fetch %s constituents: %s", idx_name, exc)
            continue
        for sym in symbols:
            sym_upper = sym.strip().upper()
            # Strip trailing "XD" — this is an ex-dividend flag shown by PSX,
            # not part of the actual ticker symbol.
            if sym_upper.endswith("XD") and len(sym_upper) > 2:
                sym_upper = sym_upper[:-2]
            if not sym_upper:
                continue
            if sym_upper in symbol_map:
                symbol_map[sym_upper]["indices"].append(idx_name)
            else:
                symbol_map[sym_upper] = {
                    "symbol": sym_upper,
                    "indices": [idx_name],
                    "frozen_date": today,
                }

    universe = sorted(symbol_map.values(), key=lambda x: x["symbol"])
    log.info("Unified universe: %d unique symbols from %d indices", len(universe), len(_INDEX_NAMES))
    return universe


def freeze_universe(
    universe: List[Dict],
    config_dir: Path | None = None,
) -> Path:
    """Write the universe list to ``symbol_universe.json`` and return the path."""
    cfg_dir = config_dir or _DEFAULT_CONFIG_DIR
    cfg_dir.mkdir(parents=True, exist_ok=True)
    out_path = cfg_dir / "symbol_universe.json"
    out_path.write_text(json.dumps(universe, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Frozen universe (%d symbols) -> %s", len(universe), out_path)
    return out_path


def load_frozen_universe(config_dir: Path | None = None) -> List[Dict]:
    """Load the previously frozen universe from disk.

    Raises ``FileNotFoundError`` if the file does not exist — caller should
    run ``fetch_symbol_universe()`` + ``freeze_universe()`` first.
    """
    cfg_dir = config_dir or _DEFAULT_CONFIG_DIR
    path = cfg_dir / "symbol_universe.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Symbol universe file not found at {path}. "
            "Run with --freeze-universe first to generate it."
        )
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    log.info("Loaded frozen universe: %d symbols from %s", len(data), path)
    return data


def get_active_symbols(config_dir: Path | None = None) -> List[Dict]:
    """Load the frozen universe and return only active (non-excluded) symbols.

    Symbols with ``"excluded": true`` in their entry are filtered out.
    This is the function downstream code (feature engineering, training)
    should use to get the working symbol list.
    """
    universe = load_frozen_universe(config_dir)
    active = [entry for entry in universe if not entry.get("excluded", False)]
    excluded_count = len(universe) - len(active)
    log.info("Active symbols: %d (excluded: %d)", len(active), excluded_count)
    return active
