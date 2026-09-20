"""
Explicit GRU Feature List — Versioned
=======================================

This module defines the exact, ordered feature list used by the GRU model.
Do NOT dynamically include all dataframe columns — only features explicitly
listed here are used.

Update the VERSION and FEATURE_LIST together when changing features.
After any change, retrain the model and update metadata.
"""

# Increment this when FEATURE_LIST changes
GRU_FEATURE_VERSION = "2025.09.18.v2"

# Exact ordered feature list for GRU v2 (36 features)
# Order matters: model expects features in this exact order
GRU_FEATURE_LIST = [
    # OHLCV raw (5)
    "open",
    "high",
    "low",
    "close",
    "volume",
    # Trend / momentum (6)
    "sma_20",
    "sma_50",
    "ema_12",
    "ema_26",
    "return_5d",
    "return_10d",
    # Volatility / bands (5)
    "atr_14",
    "bb_lower",
    "bb_mid",
    "bb_upper",
    "volume_zscore_20",
    # Oscillators (6)
    "rsi_14",
    "rsi_roc",
    "macd",
    "macd_signal",
    "macd_hist",
    "adx_14",
    # Pattern / regime (2)
    "consecutive_up_days",
    "consecutive_down_days",
    # Macro (2)
    "pkr_usd_rate",
    "policy_rate",
    # Normalized price & volume features (6)
    "close_to_sma20_ratio",
    "close_to_sma50_ratio",
    "ema_cross_ratio",
    "bollinger_pos",
    "daily_range_pct",
    "volume_change_1d",
    # Market-relative features (4)
    "market_return_5d",
    "market_return_20d",
    "stock_return_20d",
    "stock_relative_return_20d",
]

# Expected feature count
EXPECTED_GRU_FEATURE_COUNT = len(GRU_FEATURE_LIST)  # 36

# Feature groups for documentation/analysis
GRU_FEATURE_GROUPS = {
    "ohlcv_raw": ["open", "high", "low", "close", "volume"],
    "trend_momentum": ["sma_20", "sma_50", "ema_12", "ema_26", "return_5d", "return_10d"],
    "volatility_bands": ["atr_14", "bb_lower", "bb_mid", "bb_upper", "volume_zscore_20"],
    "oscillators": ["rsi_14", "rsi_roc", "macd", "macd_signal", "macd_hist", "adx_14"],
    "pattern_regime": ["consecutive_up_days", "consecutive_down_days"],
    "macro": ["pkr_usd_rate", "policy_rate"],
    "normalized_ratios": [
        "close_to_sma20_ratio",
        "close_to_sma50_ratio",
        "ema_cross_ratio",
        "bollinger_pos",
        "daily_range_pct",
        "volume_change_1d",
    ],
    "market_relative": [
        "market_return_5d",
        "market_return_20d",
        "stock_return_20d",
        "stock_relative_return_20d",
    ],
}


def get_gru_feature_list() -> list[str]:
    """Return the explicit ordered GRU feature list."""
    return GRU_FEATURE_LIST.copy()


def get_gru_feature_version() -> str:
    """Return the feature list version string."""
    return GRU_FEATURE_VERSION


def validate_feature_list(actual: list[str]) -> tuple[bool, str]:
    """Validate that actual feature list matches expected GRU feature list exactly.

    Returns (is_valid, error_message).
    """
    expected = GRU_FEATURE_LIST

    if actual != expected:
        missing = set(expected) - set(actual)
        extra = set(actual) - set(expected)
        order_mismatch = [i for i, (a, e) in enumerate(zip(actual, expected)) if a != e]

        errors = []
        if missing:
            errors.append(f"Missing features: {sorted(missing)}")
        if extra:
            errors.append(f"Unexpected extra features: {sorted(extra)}")
        if order_mismatch and not missing and not extra:
            errors.append(f"Feature order mismatch at indices: {order_mismatch}")

        return False, "; ".join(errors)

    return True, ""


def validate_feature_count(n_features: int) -> tuple[bool, str]:
    """Validate feature count matches expected."""
    if n_features != EXPECTED_GRU_FEATURE_COUNT:
        return False, f"Expected {EXPECTED_GRU_FEATURE_COUNT} features, got {n_features}"
    return True, ""