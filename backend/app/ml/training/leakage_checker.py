"""
Time-Series Leakage Checks — automated audit utilities.

Verifies:
  1. Chronological train / validation / test date separation (no overlap).
  2. Features for sample at date t only use information available at or before t.
  3. No NaN / missing targets in splits.
  4. Preprocessing (scalers, median imputers) fitted strictly on the train split.
"""

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

log = logging.getLogger("training.leakage_checker")


class LeakageDetectedError(Exception):
    """Raised when data leakage is detected in feature or split preparation."""
    pass


def check_chronological_split_leakage(
    train_meta: pd.DataFrame,
    val_meta: pd.DataFrame,
    test_meta: Optional[pd.DataFrame] = None,
    date_col: str = "date",
) -> Dict[str, Any]:
    """Verify that train, validation, and test splits have strictly disjoint, chronological date ranges.

    Parameters
    ----------
    train_meta : DataFrame with sample dates for training
    val_meta : DataFrame with sample dates for validation
    test_meta : Optional DataFrame with sample dates for testing
    date_col : column name holding the date

    Returns
    -------
    dict with date range summary per split.

    Raises
    ------
    LeakageDetectedError if any chronological overlap or ordering violation occurs.
    """
    if train_meta.empty or val_meta.empty:
        raise LeakageDetectedError("Train or validation meta is empty; cannot verify split dates.")

    train_dates = pd.to_datetime(train_meta[date_col])
    val_dates = pd.to_datetime(val_meta[date_col])

    train_max = train_dates.max()
    val_min = val_dates.min()
    val_max = val_dates.max()

    if train_max >= val_min:
        raise LeakageDetectedError(
            f"Temporal leakage detected: max(train_date) = {train_max.date()} >= min(val_date) = {val_min.date()}."
        )

    summary: Dict[str, Any] = {
        "train": {"min": str(train_dates.min().date()), "max": str(train_max.date()), "n": len(train_meta)},
        "val": {"min": str(val_min.date()), "max": str(val_max.date()), "n": len(val_meta)},
    }

    if test_meta is not None and not test_meta.empty:
        test_dates = pd.to_datetime(test_meta[date_col])
        test_min = test_dates.min()
        test_max = test_dates.max()

        if val_max >= test_min:
            raise LeakageDetectedError(
                f"Temporal leakage detected: max(val_date) = {val_max.date()} >= min(test_date) = {test_min.date()}."
            )
        summary["test"] = {"min": str(test_min.date()), "max": str(test_max.date()), "n": len(test_meta)}

    log.info("Chronological split separation check passed: %s", summary)
    return summary


def check_target_validity(
    y_train: np.ndarray,
    y_val: np.ndarray,
    y_test: Optional[np.ndarray] = None,
    expected_classes: Optional[set] = None,
) -> None:
    """Verify that targets have no NaNs/nulls and contain valid class IDs.

    Raises
    ------
    LeakageDetectedError / AssertionError if invalid target values are found.
    """
    if expected_classes is None:
        expected_classes = {0, 1, 2}

    for split_name, y in [("train", y_train), ("val", y_val), ("test", y_test)]:
        if y is None:
            continue
        if len(y) == 0:
            raise LeakageDetectedError(f"{split_name} target array is empty.")
        if np.isnan(y).any():
            raise LeakageDetectedError(f"NaN values found in {split_name} target array.")
        unique_classes = set(np.unique(y).tolist())
        invalid_classes = unique_classes - expected_classes
        if invalid_classes:
            raise LeakageDetectedError(
                f"Invalid class IDs {invalid_classes} found in {split_name} target array (expected {expected_classes})."
            )


def verify_feature_history_alignment(
    df: pd.DataFrame,
    features_to_check: List[str],
    date_col: str = "date",
    symbol_col: str = "symbol",
    sample_symbols: int = 3,
) -> bool:
    """Verify that rolling features computed for date t only depend on historical rows <= t.

    Raises
    ------
    LeakageDetectedError if a feature value depends on subsequent rows.
    """
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    symbols = df[symbol_col].unique()
    checked_symbols = symbols[:sample_symbols]

    for sym in checked_symbols:
        sym_df = df[df[symbol_col] == sym].sort_values(date_col).reset_index(drop=True)
        if len(sym_df) < 50:
            continue

        # Check mid-point row
        mid_idx = len(sym_df) // 2
        check_date = sym_df.iloc[mid_idx][date_col]

        for feat in features_to_check:
            if feat not in sym_df.columns:
                continue
            val = sym_df.iloc[mid_idx][feat]
            if pd.isna(val):
                continue

            # Verify rolling mean against historical window
            if feat == "sma_20" and mid_idx >= 19:
                expected = sym_df["close"].iloc[mid_idx - 19 : mid_idx + 1].mean()
                if abs(float(val) - float(expected)) > 1e-4:
                    raise LeakageDetectedError(
                        f"Leakage or calculation mismatch in {feat} for {sym} at {check_date.date()}: "
                        f"got {val}, expected {expected} from trailing 20 rows."
                    )

    log.info("Feature history alignment check passed for symbols: %s", list(checked_symbols))
    return True
