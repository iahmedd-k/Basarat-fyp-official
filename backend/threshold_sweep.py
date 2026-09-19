"""
Threshold Sweep — find the label threshold that gives the best class balance.

Recomputes forward returns from features_daily.parquet and tests a range of
threshold values, printing the resulting class distribution for each.

Run:
    python threshold_sweep.py
    python threshold_sweep.py --thresholds 0.005 0.01 0.015 0.02 0.025
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

from app.data.features.labeling import label_from_return

FEATURES_PATH = Path("data/features/features_daily.parquet")

# Time-based split cutoffs (same as training)
TRAIN_CUTOFF = pd.Timestamp("2024-07-01")
VAL_CUTOFF = pd.Timestamp("2025-07-01")


def sweep(thresholds: list[float]) -> None:
    if not FEATURES_PATH.exists():
        print(f"ERROR: {FEATURES_PATH} not found. Run the feature pipeline first.")
        sys.exit(1)

    df = pd.read_parquet(FEATURES_PATH)
    df["date"] = pd.to_datetime(df["date"])

    # Compute forward returns (same as labeling.assign_labels)
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)
    df["forward_return"] = df.groupby("symbol")["close"].transform(
        lambda s: s.shift(-1) / s - 1
    )

    # Drop last row per symbol
    df = df.groupby("symbol", group_keys=False).apply(
        lambda g: g.iloc[:-1] if len(g) > 1 else g
    )
    df = df.dropna(subset=["forward_return"])

    total = len(df)
    dates = df["date"]

    train_mask = dates < TRAIN_CUTOFF
    val_mask = (dates >= TRAIN_CUTOFF) & (dates < VAL_CUTOFF)
    test_mask = dates >= VAL_CUTOFF

    split_masks = {
        "train": train_mask,
        "val": val_mask,
        "test": test_mask,
    }

    print("=" * 90)
    print("  THRESHOLD SWEEP — Class balance for different label thresholds")
    print(f"  Total labelled rows: {total:,}")
    print(f"  Train: {(~train_mask).sum():,}  |  Val: {val_mask.sum():,}  |  Test: {test_mask.sum():,}")
    print("=" * 90)

    for threshold in thresholds:
        labels = df["forward_return"].apply(lambda r: label_from_return(r, threshold))

        print(f"\n  threshold = {threshold:.3f}  ({threshold*100:.1f}%)")
        print(f"  {'':>10} {'bullish':>10} {'bearish':>10} {'sideways':>10}  {'dominant':>10} {'min':>8}")
        print(f"  {'':>10} {'-'*10} {'-'*10} {'-'*10}  {'-'*10} {'-'*8}")

        for split_name, mask in split_masks.items():
            split_labels = labels[mask]
            n = len(split_labels)
            if n == 0:
                print(f"  {split_name.upper():>8}   (no data)")
                continue
            dist = split_labels.value_counts(normalize=True).reindex(["bullish", "bearish", "sideways"], fill_value=0)
            pcts = (dist * 100).round(1)
            dominant_cls = pcts.idxmax()
            min_pct = pcts.min()
            print(
                f"  {split_name.upper():>8}  "
                f"{pcts['bullish']:>9.1f}% {pcts['bearish']:>9.1f}% {pcts['sideways']:>9.1f}%  "
                f"{dominant_cls:>8} {min_pct:>7.1f}%"
            )

        # Flag if any split has a class > 60%
        worst_overall = 0
        for split_name, mask in split_masks.items():
            split_labels = labels[mask]
            if len(split_labels) == 0:
                continue
            dist = split_labels.value_counts(normalize=True)
            worst_overall = max(worst_overall, dist.max())

        status = "  *** IMBALANCED (>60%)" if worst_overall > 0.60 else "  OK"
        print(f"  Max single-class across all splits: {worst_overall*100:.1f}%{status}")

    print("\n" + "=" * 90)
    print("  RECOMMENDATION: pick the threshold where no class exceeds ~55-60%")
    print("  in any split, and the three classes are as close to 33/33/33 as possible.")
    print("=" * 90)


def main():
    parser = argparse.ArgumentParser(
        description="Sweep label thresholds to find the best class balance."
    )
    parser.add_argument(
        "--thresholds", type=float, nargs="+",
        default=[0.005, 0.01, 0.015, 0.02, 0.025],
        help="Threshold values to test (default: 0.005 0.01 0.015 0.02 0.025)",
    )
    args = parser.parse_args()
    sweep(args.thresholds)


if __name__ == "__main__":
    main()
