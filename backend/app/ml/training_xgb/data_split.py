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

    # Assert no missing targets in the full dataset before splitting
    # Check for NaN in label column before encoding
    n_nan_labels = int(df["label"].isna().sum())
    if n_nan_labels > 0:
        raise AssertionError(
            f"Found {n_nan_labels} NaN labels in dataframe before splitting. "
            f"All missing forward_return rows should have been dropped in labeling."
        )

    # ── Identify feature columns (Task 2 / Task 13: Explicit versioned feature order) ──
    from app.ml.training_xgb.feature_prep import ALL_XGB_FEATURES
    feature_names = [c for c in ALL_XGB_FEATURES if c in df.columns]
    missing = set(ALL_XGB_FEATURES) - set(feature_names)
    if missing:
        raise ValueError(f"Missing required XGBoost features in dataframe: {sorted(missing)}")

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

    # Assert no missing targets in each split
    for name in ("train", "val", "test"):
        split_y = splits[name]["y"]
        n_nan_split = int(np.isnan(split_y).sum()) if split_y.dtype.kind == 'f' else 0
        if n_nan_split > 0:
            raise AssertionError(
                f"Found {n_nan_split} NaN targets in {name} split. "
                f"All missing forward_return rows should have been dropped in labeling."
            )

    # ── NaN fill using training-set statistics only ─────────────────────
    # Rolling/lag features have NaN at the start of each symbol's history.
    # We compute the fill median from the TRAINING split only, then apply
    # it to all splits.  This prevents future data from leaking into
    # training rows via imputation.
    X_train = splits["train"]["X"]
    n_features = X_train.shape[1]

    fill_medians = np.zeros(n_features, dtype=np.float32)
    for f_idx in range(n_features):
        col_train = X_train[:, f_idx]
        valid = col_train[~np.isnan(col_train)]
        fill_medians[f_idx] = float(np.median(valid)) if len(valid) > 0 else 0.0

    for name in ("train", "val", "test"):
        X_split = splits[name]["X"]
        n_nan_before = int(np.isnan(X_split).sum())
        for f_idx in range(n_features):
            mask_nan = np.isnan(X_split[:, f_idx])
            X_split[mask_nan, f_idx] = fill_medians[f_idx]
        n_nan_after = int(np.isnan(X_split).sum())
        if n_nan_before > 0:
            log.info(
                "  %s: filled %d NaN values using training-set medians (%d remaining)",
                name.upper(), n_nan_before - n_nan_after, n_nan_after,
            )

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

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log.info("Split report saved -> %s", report_path)

    return splits
