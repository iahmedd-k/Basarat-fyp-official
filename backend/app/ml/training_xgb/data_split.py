"""
Time-based train / validation / test split for XGBoost.

Uses the EXACT SAME cutoff dates as gru_v1 for a fair, apples-to-apples
comparison:
  train < 2024-07-01, val [2024-07-01, 2025-07-01), test >= 2025-07-01

KEY DIFFERENCE FROM GRU SPLIT:
  The GRU pipeline loses the first ~30 rows per symbol to windowing
  (sequence builder requires 30 days of history before producing a
  sample). XGBoost does NOT use sequences, so it retains all rows
  after indicator warm-up (~50 rows for SMA-50). This means XGBoost
  may have slightly more samples in each split, which is reported below.
"""

import json
import logging
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger("training_xgb.split")

# ── Same cutoffs as GRU v1 ────────────────────────────────────────────
TRAIN_CUTOFF = pd.Timestamp("2024-07-01")
VAL_CUTOFF = pd.Timestamp("2025-07-01")

REPORT_PATH = Path("data/reports/split_xgb.json")


def time_split_xgb(
    df: pd.DataFrame,
    label_mapping: dict | None = None,
    train_cutoff: pd.Timestamp = TRAIN_CUTOFF,
    val_cutoff: pd.Timestamp = VAL_CUTOFF,
    report_path: Path = REPORT_PATH,
) -> dict:
    """Split a flat DataFrame into train / val / test by date.

    Parameters
    ----------
    df : DataFrame with at least a 'date' column and a 'label' column
    label_mapping : dict mapping label name -> int (for class counting)
    train_cutoff, val_cutoff : split boundaries (same as GRU)
    report_path : where to save the split report JSON

    Returns
    -------
    dict with keys "train", "val", "test", each mapping to
    {"X": np.ndarray, "y": np.ndarray, "meta": pd.DataFrame,
     "feature_names": list[str]}.
    """
    if label_mapping is None:
        label_mapping = {"bullish": 0, "bearish": 1, "sideways": 2}

    dates = pd.to_datetime(df["date"])

    train_mask = dates < train_cutoff
    val_mask = (dates >= train_cutoff) & (dates < val_cutoff)
    test_mask = dates >= val_cutoff

    # ── Identify feature columns ────────────────────────────────────────
    exclude_cols = {"symbol", "date", "forward_return", "label"}
    feature_names = sorted([c for c in df.columns if c not in exclude_cols])

    # ── Encode labels ────────────────────────────────────────────────────
    y_full = df["label"].map(label_mapping).values
    X_full = df[feature_names].values.astype(np.float32)

    meta = df[["symbol", "date"]].copy()

    splits = {}
    for name, mask in [("train", train_mask), ("val", val_mask), ("test", test_mask)]:
        idx = np.where(mask)[0]
        splits[name] = {
            "X": X_full[idx],
            "y": y_full[idx],
            "meta": meta.iloc[idx].reset_index(drop=True),
            "feature_names": feature_names,
        }

    # ── Logging & report ───────────────────────────────────────────────
    total = len(df)
    label_names = {v: k for k, v in label_mapping.items()}
    report: dict = {
        "cutoffs": {
            "train_before": str(train_cutoff.date()),
            "val_range": f"[{train_cutoff.date()}, {val_cutoff.date()})",
            "test_from": str(val_cutoff.date()),
        },
        "note": (
            "XGBoost split uses the SAME cutoff dates as GRU v1. "
            "Sample counts may differ slightly because XGBoost does not "
            "lose rows to 30-day windowing (only to ~50-row indicator warm-up)."
        ),
        "splits": {},
    }

    for name in ("train", "val", "test"):
        n = len(splits[name]["y"])
        pct = n / total * 100 if total else 0
        counts = Counter(splits[name]["y"].tolist())
        dist = {label_names.get(int(k), str(k)): counts.get(k, 0) for k in sorted(label_names)}
        dist_pct = {k: round(v / n * 100, 1) if n else 0.0 for k, v in dist.items()}

        log.info(
            "%-5s  %7d samples (%5.1f%%)  dist=%s",
            name.upper(), n, pct, dist_pct,
        )
        report["splits"][name] = {
            "n_samples": n,
            "pct_of_total": round(pct, 1),
            "class_distribution": dist,
            "class_distribution_pct": dist_pct,
        }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log.info("Split report saved -> %s", report_path)

    return splits
