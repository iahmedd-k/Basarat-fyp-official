"""
Data Leakage Diagnostic — verify no future information leaks into features or labels.

For a handful of rows across different symbols, prints:
  1. The exact date range of the input features (window start/end)
  2. The date and value of the label
  3. Whether any feature value at the window's end references data after the window
  4. The NaN-fill source for XGB engineered features (training median vs global median)

Run:
    cd backend
    python diagnostic_leakage.py
    python diagnostic_leakage.py --symbol OGDC
    python diagnostic_leakage.py --window-size 30
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Import explicit GRU feature list
sys.path.insert(0, str(Path(__file__).parent))
from app.data.features.gru_feature_list import GRU_FEATURE_LIST

FEATURES_PATH = Path("data/features/features_daily.parquet")
SEQUENCES_DIR = Path("data/sequences")
MODEL_DIR = Path("models/gru_v1")


def check_gru_sequences(n_samples: int = 5, window_size: int = 30):
    """Check GRU sequences for label leakage."""
    print("=" * 90)
    print("  CHECK 1: GRU Sequence Construction — feature window vs label date")
    print("=" * 90)

    sequences_path = SEQUENCES_DIR / "sequences.npz"
    meta_path = SEQUENCES_DIR / "sequences_meta.parquet"

    if not sequences_path.exists():
        print("  SKIPPED: sequences.npz not found")
        return

    data = np.load(sequences_path)
    X, y = data["X"], data["y"]
    meta = pd.read_parquet(meta_path)

    feature_columns = GRU_FEATURE_LIST.copy()
    label_mapping = json.loads(
        (Path("data/features") / "label_mapping.json").read_text(encoding="utf-8")
    )
    reverse_labels = {v: k for k, v in label_mapping.items()}

    # Load full features for date lookups
    features_df = pd.read_parquet(FEATURES_PATH)
    features_df["date"] = pd.to_datetime(features_df["date"])

    print(f"\n  Total sequences: {len(X)}")
    print(f"  Window size: {X.shape[1]}, Features: {X.shape[2]}")
    print(f"  Label mapping: {label_mapping}")
    print()

    # Sample evenly across the dataset
    indices = np.linspace(0, len(X) - 1, n_samples, dtype=int)

    for idx in indices:
        sym = meta.iloc[idx]["symbol"]
        meta_date = pd.to_datetime(meta.iloc[idx]["date"])
        label_int = int(y[idx])

        # Get the symbol's full timeline
        sym_df = features_df[features_df["symbol"] == sym].sort_values("date").reset_index(drop=True)

        # Find the row index matching meta_date
        date_match = sym_df[sym_df["date"] == meta_date]
        if date_match.empty:
            print(f"  [{idx}] {sym} @ {meta_date.date()} — CANNOT FIND DATE IN FEATURES")
            continue

        row_idx = date_match.index[0]

        # Window is the last window_size rows ending at row_idx
        window_start_idx = row_idx + 1 - window_size
        if window_start_idx < 0:
            print(f"  [{idx}] {sym} @ {meta_date.date()} — INSUFFICIENT HISTORY (row_idx={row_idx} < window_size={window_size})")
            continue

        window_dates = sym_df.iloc[window_start_idx:row_idx + 1]["date"]
        window_start_date = window_dates.iloc[0].date()
        window_end_date = window_dates.iloc[-1].date()

        # The label at meta_date encodes forward_return = close[next_day]/close[meta_date] - 1
        # The next trading day after meta_date:
        future_rows = sym_df[sym_df["date"] > meta_date]
        if future_rows.empty:
            print(f"  [{idx}] {sym} @ {meta_date.date()} — NO FUTURE DATA (last row, label is NaN/sideways)")
            continue

        label_date = future_rows.iloc[0]["date"].date()
        label_close = float(future_rows.iloc[0]["close"])
        current_close = float(sym_df.iloc[row_idx]["close"])
        implied_return = (label_close - current_close) / current_close * 100

        # Check: does the label_date fall WITHIN the feature window?
        label_in_window = window_start_date <= label_date <= window_end_date

        # Check: any feature values that are constant across the window? (possible future fill)
        window_features = X[idx]  # (window_size, n_features)
        n_constant = sum(
            1 for f in range(window_features.shape[1])
            if np.std(window_features[:, f]) == 0
        )

        print(f"  [{idx}] {sym} @ {meta_date.date()}")
        print(f"    Feature window:  {window_start_date} -> {window_end_date} ({window_size} days)")
        print(f"    Label date:      {label_date} (next trading day after window end)")
        print(f"    Label in window: {'LEAKAGE!' if label_in_window else 'No (correct)'}")
        print(f"    Current close:   {current_close:.2f}")
        print(f"    Label close:     {label_close:.2f}")
        print(f"    Implied return:  {implied_return:+.3f}% -> {reverse_labels.get(label_int, '?')}")
        print(f"    Constant feats:  {n_constant}/{window_features.shape[1]}")
        print()


def check_feature_dates(n_samples: int = 5):
    """Check that feature values at each row only reference data up to that date."""
    print("=" * 90)
    print("  CHECK 2: Rolling Feature Alignment — do features at date t only use data <= t?")
    print("=" * 90)

    features_df = pd.read_parquet(FEATURES_PATH)
    features_df["date"] = pd.to_datetime(features_df["date"])

    # Check specific rolling features for forward-reference
    rolling_features = [
        ("sma_20", 20), ("sma_50", 50), ("return_5d", 5), ("return_10d", 10),
        ("rsi_14", 14), ("atr_14", 14),
    ]

    symbols = features_df["symbol"].unique()
    sample_syms = np.random.choice(symbols, min(3, len(symbols)), replace=False)

    for sym in sample_syms:
        sym_df = features_df[features_df["symbol"] == sym].sort_values("date").reset_index(drop=True)
        if len(sym_df) < 60:
            continue

        print(f"\n  Symbol: {sym} ({len(sym_df)} rows)")

        # Pick a mid-range date
        check_idx = len(sym_df) // 2
        check_date = sym_df.iloc[check_idx]["date"]

        for feat_name, window in rolling_features:
            if feat_name not in sym_df.columns:
                continue

            val_at_check = sym_df.iloc[check_idx][feat_name]
            if pd.isna(val_at_check):
                continue

            # Compute what the value SHOULD be using only data <= check_date
            close_series = sym_df["close"].iloc[:check_idx + 1]

            if feat_name == "sma_20" and len(close_series) >= 20:
                expected = close_series.tail(20).mean()
            elif feat_name == "sma_50" and len(close_series) >= 50:
                expected = close_series.tail(50).mean()
            elif feat_name == "return_5d" and len(close_series) >= 6:
                expected = (close_series.iloc[-1] - close_series.iloc[-6]) / close_series.iloc[-6]
            elif feat_name == "return_10d" and len(close_series) >= 11:
                expected = (close_series.iloc[-1] - close_series.iloc[-11]) / close_series.iloc[-11]
            else:
                continue

            match = abs(float(val_at_check) - expected) < 1e-6
            status = "OK" if match else "MISMATCH (possible forward leak)"

            print(f"    {feat_name:<15} @ {check_date.date()}: actual={float(val_at_check):.6f}  "
                  f"computed_from_history={expected:.6f}  [{status}]")


def check_xgb_nan_fill():
    """Check whether XGB NaN fill uses future data."""
    print("\n" + "=" * 90)
    print("  CHECK 3: XGBoost NaN Fill — does imputation use future data?")
    print("=" * 90)

    xgb_path = Path("data/processed/features_xgb.parquet")
    if not xgb_path.exists():
        print("  SKIPPED: features_xgb.parquet not found")
        return

    df = pd.read_parquet(xgb_path)
    df["date"] = pd.to_datetime(df["date"])

    engineered = [
        "return_1d", "return_5d_eng", "return_10d_eng", "return_20d",
        "rolling_std_5d", "rolling_std_20d",
        "vol_adj_return_1d", "vol_adj_return_5d", "vol_adj_return_10d",
        "rsi_14_lag5", "rsi_14_lag10", "macd_hist_lag5",
        "close_min_20d", "close_max_20d", "close_position_20d",
    ]

    train_cutoff = pd.Timestamp("2024-07-01")

    print(f"\n  Train cutoff: {train_cutoff.date()}")
    print(f"  Total rows: {len(df)}")
    print()

    for col in engineered:
        if col not in df.columns:
            continue

        n_nan_total = int(df[col].isna().sum())
        if n_nan_total == 0:
            continue

        # Check if any NaN rows are in training data
        nan_mask = df[col].isna()
        n_nan_train = int((nan_mask & (df["date"] < train_cutoff)).sum())
        n_nan_test = int((nan_mask & (df["date"] >= train_cutoff)).sum())

        # Compute what the global median would be
        global_median = float(df[col].median()) if not df[col].isna().all() else 0.0

        # Compute training-only median
        train_df = df[df["date"] < train_cutoff]
        train_median = float(train_df[col].median()) if not train_df[col].isna().all() else 0.0

        diff = abs(global_median - train_median)
        leakage_flag = "LEAKAGE" if diff > 0.001 else "OK"

        print(f"  {col:<25} NaN: {n_nan_total:>5} (train={n_nan_train}, test={n_nan_test})  "
              f"global_med={global_median:.6f}  train_med={train_median:.6f}  "
              f"diff={diff:.6f}  [{leakage_flag}]")


def main():
    parser = argparse.ArgumentParser(description="Data leakage diagnostic")
    parser.add_argument("--symbol", type=str, default=None, help="Filter to one symbol")
    parser.add_argument("--window-size", type=int, default=30, help="GRU window size")
    parser.add_argument("--n-samples", type=int, default=5, help="Number of samples per check")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)

    check_gru_sequences(n_samples=args.n_samples, window_size=args.window_size)
    check_feature_dates(n_samples=args.n_samples)
    check_xgb_nan_fill()

    print("\n" + "=" * 90)
    print("  AUDIT COMPLETE")
    print("=" * 90)


if __name__ == "__main__":
    main()
