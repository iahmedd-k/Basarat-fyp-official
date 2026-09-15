"""
Parquet Writers — write per-symbol and combined OHLCV files.

Output layout::

    data/raw/ohlcv/{symbol}.parquet     — one file per symbol
    data/raw/ohlcv/all_symbols.parquet  — combined file with ``symbol`` column
"""

import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

_DEFAULT_OUTPUT_DIR = Path("data/raw/ohlcv")


def write_symbol_parquet(
    df: pd.DataFrame,
    symbol: str,
    output_dir: Path | None = None,
) -> Path:
    """Write a single symbol's OHLCV to ``{symbol}.parquet``."""
    out_dir = output_dir or _DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{symbol}.parquet"
    df.to_parquet(path, index=False, engine="pyarrow")
    log.info("Wrote %d rows -> %s", len(df), path)
    return path


def write_combined_parquet(
    frames: dict[str, pd.DataFrame],
    output_dir: Path | None = None,
) -> Path:
    """Write all symbols into a single ``all_symbols.parquet`` with a ``symbol`` column."""
    out_dir = output_dir or _DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    parts = []
    for sym, frame in sorted(frames.items()):
        if frame.empty:
            continue
        tmp = frame.copy()
        tmp.insert(0, "symbol", sym)
        parts.append(tmp)

    if not parts:
        log.warning("No data to write for combined parquet")
        return out_dir / "all_symbols.parquet"

    combined = pd.concat(parts, ignore_index=True)
    path = out_dir / "all_symbols.parquet"
    combined.to_parquet(path, index=False, engine="pyarrow")
    log.info("Wrote %d rows (%d symbols) -> %s", len(combined), len(parts), path)
    return path
