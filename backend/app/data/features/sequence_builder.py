"""
Sequence Builder — create sliding window sequences for time-series models.

Produces fixed-length windows of indicator/macro features paired with the
label at the window's final date.  Windows never cross symbol boundaries.

Output shapes:
    X:  [n_samples, window_size, n_features]
    y:  [n_samples]  (integer labels)

No scaling is applied — raw sequences are saved; scaling belongs in the
training script on the train split only.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

DEFAULT_WINDOW_SIZE = 30


def build_sequences(
    df: pd.DataFrame,
    feature_columns: List[str],
    label_mapping: Dict[str, int],
    window_size: int = DEFAULT_WINDOW_SIZE,
) -> Tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    """Build sliding-window sequences from the feature DataFrame.

    Parameters
    ----------
    df : DataFrame with columns [symbol, date, *feature_columns, label]
    feature_columns : ordered list of numeric feature columns to include
    label_mapping : mapping from label string to integer
    window_size : number of time steps per window

    Returns
    -------
    X : np.ndarray, shape (n_samples, window_size, n_features)
    y : np.ndarray, shape (n_samples,), dtype int
    meta : DataFrame with columns [symbol, date] for traceability
    """
    if df.empty:
        log.warning("Empty DataFrame — returning empty arrays")
        return np.array([]), np.array([]), pd.DataFrame(columns=["symbol", "date"])

    # Pre-count total sequences to pre-allocate memory without np.stack spikes
    total_seqs = 0
    for _, grp in df.groupby("symbol"):
        if len(grp) >= window_size:
            total_seqs += len(grp) - window_size

    if total_seqs == 0:
        log.warning("No sequences built")
        return np.array([]), np.array([]), pd.DataFrame(columns=["symbol", "date"])

    n_symbols = df["symbol"].nunique()
    log.info("Building sequences (pre-allocated): window_size=%d, symbols=%d, features=%d, total_seqs=%d",
             window_size, n_symbols, len(feature_columns), total_seqs)

    X = np.empty((total_seqs, window_size, len(feature_columns)), dtype=np.float32)
    y = np.empty(total_seqs, dtype=np.int32)
    meta_symbols = []
    meta_dates = []

    curr_idx = 0
    for sym, grp in df.groupby("symbol"):
        grp = grp.sort_values("date").reset_index(drop=True)
        if len(grp) < window_size:
            log.debug("  %s: only %d rows, skipping (need %d)", sym, len(grp), window_size)
            continue

        values = grp[feature_columns].values.astype(np.float32)  # (T, F) in float32
        labels = grp["label"].map(label_mapping).values  # (T,)
        dates = grp["date"].values

        for i in range(window_size, len(grp)):
            label = labels[i - 1]
            if np.isnan(label):
                raise AssertionError(
                    f"Missing target label at {sym} date {dates[i-1]} (index {i-1}). "
                    f"All forward_return NaN rows should have been dropped in labeling.assign_labels()."
                )

            X[curr_idx] = values[i - window_size : i]
            y[curr_idx] = int(label)
            meta_symbols.append(sym)
            meta_dates.append(dates[i - 1])
            curr_idx += 1

    meta = pd.DataFrame({"symbol": meta_symbols, "date": meta_dates})

    # ── Integrity assertion ────────────────────────────────────────────
    # Each sequence corresponds to one (symbol, date) pair.  The max number
    # of sequences is bounded by: total_rows - (window_size - 1) * num_symbols,
    # because each symbol loses (window_size - 1) rows to window warm-up.
    # If this assertion fails, it means meta has duplicate (symbol, date)
    # pairs or the windowing logic is broken.
    n_symbols_in_features = df["symbol"].nunique()
    max_possible = len(df) - (window_size - 1) * n_symbols_in_features
    if len(X) > max_possible:
        dupes = meta.duplicated(subset=["symbol", "date"]).sum()
        raise AssertionError(
            f"Sequence count ({len(X)}) exceeds theoretical max ({max_possible}). "
            f"This means meta has {dupes} duplicate (symbol, date) pairs. "
            f"Check merge_asof scoping in macro_features.py — it must be per-symbol."
        )

    log.info("Sequences built: X=%s, y=%s, meta=%d rows", X.shape, y.shape, len(meta))
    return X, y, meta


def save_sequences(
    X: np.ndarray,
    y: np.ndarray,
    meta: pd.DataFrame,
    output_dir: Optional[Path] = None,
    prefix: str = "",
) -> Dict[str, Path]:
    """Save sequences and metadata to disk.

    Parameters
    ----------
    prefix : str
        Optional prefix for file names (e.g. "thresh05" -> sequences_thresh05.npz).
        Empty string uses the default names (sequences.npz, etc.).
    """
    out_dir = output_dir or Path("data/sequences")
    out_dir.mkdir(parents=True, exist_ok=True)

    suffix = f"_{prefix}" if prefix else ""

    paths = {}

    npz_path = out_dir / f"sequences{suffix}.npz"
    np.savez_compressed(npz_path, X=X, y=y)
    paths["sequences"] = npz_path
    log.info("Saved sequences -> %s  X=%s  y=%s", npz_path, X.shape, y.shape)

    meta_path = out_dir / f"sequences_meta{suffix}.parquet"
    meta.to_parquet(meta_path, index=False)
    paths["meta"] = meta_path
    log.info("Saved meta -> %s (%d rows)", meta_path, len(meta))

    return paths
