"""
Time-based train / validation / test split.

Splits sequences by the *end-date* of each window (the date stored in
sequences_meta.parquet) to prevent any future data leaking into training.

Cutoff dates are configurable constants — adjust them if a split ends up
too small or imbalanced.
"""

import json
import logging
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger("training.split")

# ── Configurable cutoff dates ──────────────────────────────────────────
# The *end-date* of a sequence determines which split it belongs to.
TRAIN_CUTOFF = pd.Timestamp("2024-07-01")   # train: before this date
VAL_CUTOFF = pd.Timestamp("2025-07-01")     # val:   [TRAIN_CUTOFF, VAL_CUTOFF)
# test:  >= VAL_CUTOFF

DATA_DIR = Path("data/sequences")
REPORT_PATH = Path("data/reports/split.json")


def time_split(
    X: np.ndarray,
    y: np.ndarray,
    meta: pd.DataFrame,
    train_cutoff: pd.Timestamp = TRAIN_CUTOFF,
    val_cutoff: pd.Timestamp = VAL_CUTOFF,
    report_path: Path = REPORT_PATH,
) -> dict:
    """Split X, y, meta into train / val / test by date.

    Returns
    -------
    dict with keys "train", "val", "test", each mapping to
    {"X": np.ndarray, "y": np.ndarray, "meta": pd.DataFrame}.
    """
    dates = pd.to_datetime(meta["date"])

    train_mask = dates < train_cutoff
    val_mask = (dates >= train_cutoff) & (dates < val_cutoff)
    test_mask = dates >= val_cutoff

    # Assert no missing targets in the full dataset before splitting
    n_nan_y = int(np.isnan(y).sum()) if y.dtype.kind == 'f' else 0
    if n_nan_y > 0:
        raise AssertionError(
            f"Found {n_nan_y} NaN targets in y before splitting. "
            f"All missing forward_return rows should have been dropped in labeling and sequence building."
        )

    splits = {}
    for name, mask in [("train", train_mask), ("val", val_mask), ("test", test_mask)]:
        idx = np.where(mask)[0]
        splits[name] = {
            "X": X[idx],
            "y": y[idx],
            "meta": meta.iloc[idx].reset_index(drop=True),
        }

    # Assert no missing targets in each split
    for name in ("train", "val", "test"):
        split_y = splits[name]["y"]
        n_nan_split = int(np.isnan(split_y).sum()) if split_y.dtype.kind == 'f' else 0
        if n_nan_split > 0:
            raise AssertionError(
                f"Found {n_nan_split} NaN targets in {name} split. "
                f"All missing forward_return rows should have been dropped in labeling and sequence building."
            )

    # ── Logging & report ───────────────────────────────────────────────
    total = len(X)
    label_names = {0: "bullish", 1: "bearish", 2: "sideways"}
    report: dict = {
        "cutoffs": {
            "train_before": str(train_cutoff.date()),
            "val_range": f"[{train_cutoff.date()}, {val_cutoff.date()})",
            "test_from": str(val_cutoff.date()),
        },
        "splits": {},
    }

    for name in ("train", "val", "test"):
        n = len(splits[name]["y"])
        pct = n / total * 100 if total else 0
        counts = Counter(splits[name]["y"].tolist())
        dist = {label_names.get(int(k), str(k)): counts.get(k, 0) for k in sorted(label_names)}
        dist_pct = {k: round(v / n * 100, 1) if n else 0.0 for k, v in dist.items()}

        flag = ""
        if pct < 5:
            flag = f"WARNING: {name} has only {pct:.1f}% of total samples (< 5%)"
            log.warning(flag)
        log.info(
            "%-5s  %7d samples (%5.1f%%)  dist=%s",
            name.upper(), n, pct, dist_pct,
        )

        # Per-split class balance check
        max_class = max(dist_pct.values()) if dist_pct else 0
        if max_class > 60:
            dominant = [cls for cls, p in dist_pct.items() if p == max_class][0]
            warn_msg = f"Class imbalance in {name}: {dominant}={max_class:.1f}% (>60%)"
            log.warning(warn_msg)
            report.setdefault("class_balance_warnings", []).append(warn_msg)

        report["splits"][name] = {
            "n_samples": n,
            "pct_of_total": round(pct, 1),
            "class_distribution": dist,
            "class_distribution_pct": dist_pct,
        }
        if flag:
            report["splits"][name]["warning"] = flag

    # Check balance: biggest split should be < 3x the smallest
    counts = [len(splits[s]["y"]) for s in ("train", "val", "test")]
    if min(counts) > 0:
        ratio = max(counts) / min(counts)
        if ratio > 3:
            msg = f"Imbalance warning: largest split is {ratio:.1f}x the smallest"
            log.warning(msg)
            report["imbalance_warning"] = msg

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log.info("Split report saved -> %s", report_path)

    return splits
