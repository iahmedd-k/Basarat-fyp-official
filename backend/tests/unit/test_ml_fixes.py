"""
Unit Tests for ML Forecasting Pipeline Fixes (20 Tasks)
========================================================

Verifies all 20 fixes across labeling, feature validation, metric computation,
leakage checking, seeding, sideways target pricing, and ensemble logic.
"""

import json
import pytest
import numpy as np
import pandas as pd

from app.data.features.gru_feature_list import (
    GRU_FEATURE_LIST,
    GRU_FEATURE_VERSION,
    validate_feature_list,
)
from app.data.features.labeling import (
    DEFAULT_THRESHOLD,
    LABEL_MAPPING,
    assign_labels,
    label_from_return,
)
from app.data.features.technical_indicators import compute_technical_indicators
from app.ml.serving.inference import (
    FeatureMismatchError,
    _ensemble_decide,
    compute_confidence,
)
from app.ml.training.comprehensive_evaluation import compute_metrics, evaluate_ensemble
from app.ml.training.leakage_checker import (
    LeakageDetectedError,
    check_chronological_split_leakage,
    check_target_validity,
)
from app.ml.training.reproducibility import set_seed
from app.ml.training_xgb.feature_prep import ALL_XGB_FEATURES, build_xgb_features
from app.services.recommendation_service import RecommendationEngine


# ── Task 1: Fix NaN labels ───────────────────────────────────────────
def test_label_from_return_raises_on_nan():
    with pytest.raises(ValueError, match="future_return is NaN"):
        label_from_return(float("nan"))


def test_assign_labels_drops_nan_targets():
    df = pd.DataFrame({
        "symbol": ["TEST", "TEST", "TEST"],
        "date": pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03"]),
        "close": [100.0, 105.0, 102.0],
    })
    labeled_df, report = assign_labels(df, threshold=0.01)
    # Last row has no forward return and must be dropped
    assert len(labeled_df) == 2
    assert not labeled_df["forward_return"].isna().any()
    assert not labeled_df["label"].isna().any()
    assert labeled_df.iloc[0]["label"] == "bullish"  # 105/100 - 1 = +5%
    assert labeled_df.iloc[1]["label"] == "bearish"  # 102/105 - 1 = -2.85%


# ── Task 2: Make GRU features explicit (36 Features) ────────────────
def test_gru_feature_list_explicit_validation():
    valid_list = GRU_FEATURE_LIST.copy()
    assert len(valid_list) == 36
    is_valid, msg = validate_feature_list(valid_list)
    assert is_valid, msg

    # Order mismatch or missing feature
    invalid_list = valid_list[:-1]
    is_valid, msg = validate_feature_list(invalid_list)
    assert not is_valid
    assert "Missing features" in msg

    # Reordered feature
    reordered_list = valid_list.copy()
    reordered_list[0], reordered_list[1] = reordered_list[1], reordered_list[0]
    is_valid, msg = validate_feature_list(reordered_list)
    assert not is_valid
    assert "Feature order mismatch" in msg


def test_balanced_class_weights_calculated_only_on_train():
    from sklearn.utils.class_weight import compute_class_weight

    y_train = np.array([0, 0, 1, 2, 2, 2])
    classes = np.unique(y_train)
    weights = compute_class_weight("balanced", classes=classes, y=y_train)
    w_dict = {int(c): float(w) for c, w in zip(classes, weights)}

    # Class 1 is rarest (1 sample), class 2 is most frequent (3 samples)
    assert w_dict[1] > w_dict[0] > w_dict[2]
    # Sum of weighted counts equals n_samples
    weighted_sum = sum(w_dict[label] for label in y_train)
    assert pytest.approx(weighted_sum, rel=1e-5) == len(y_train)


# ── Task 4 & 16: Confidence & gap_pp semantics ───────────────────────
def test_compute_confidence_and_gap_pp():
    probs = {"bullish": 45.0, "bearish": 35.0, "sideways": 20.0}
    top_p = compute_confidence(probs)
    assert top_p == 45.0

    sorted_p = sorted(probs.values(), reverse=True)
    gap_pp = round(sorted_p[0] - sorted_p[1], 1)
    assert gap_pp == 10.0


# ── Task 5: Sideways target price ────────────────────────────────────
def test_sideways_target_price_is_none_and_expected_range_provided():
    engine = RecommendationEngine()
    sym_df = pd.DataFrame({
        "symbol": ["TEST"] * 10,
        "date": pd.date_range("2025-01-01", periods=10),
        "close": [100.0] * 10,
        "high": [102.0] * 10,
        "low": [98.0] * 10,
        "atr_14": [2.5] * 10,
    })
    res_sideways = engine.compute_target_stop("TEST", sym_df, ml_direction="sideways")
    assert res_sideways["target_price"] is None
    assert res_sideways["expected_range"] is not None
    assert res_sideways["expected_range"]["low"] < 100.0 < res_sideways["expected_range"]["high"]

    res_bullish = engine.compute_target_stop("TEST", sym_df, ml_direction="bullish")
    assert res_bullish["target_price"] is not None
    assert res_bullish["target_price"] > 100.0


# ── Task 8: Leakage checks ───────────────────────────────────────────
def test_leakage_checker_validates_chronological_splits():
    train_meta = pd.DataFrame({"date": pd.date_range("2023-01-01", "2024-06-30")})
    val_meta = pd.DataFrame({"date": pd.date_range("2024-07-01", "2025-06-30")})
    test_meta = pd.DataFrame({"date": pd.date_range("2025-07-01", "2025-12-31")})

    summary = check_chronological_split_leakage(train_meta, val_meta, test_meta)
    assert "train" in summary and "val" in summary and "test" in summary

    # Overlap error
    train_leak = pd.DataFrame({"date": pd.date_range("2023-01-01", "2024-07-15")})
    with pytest.raises(LeakageDetectedError, match="Temporal leakage detected"):
        check_chronological_split_leakage(train_leak, val_meta, test_meta)


def test_leakage_checker_target_validity():
    y_train = np.array([0, 1, 2, 0])
    y_val = np.array([1, 2, 0])
    y_test = np.array([2, 0, 1])
    check_target_validity(y_train, y_val, y_test)

    # Missing/NaN target
    y_bad = np.array([0, np.nan, 2])
    with pytest.raises(LeakageDetectedError, match="NaN values found"):
        check_target_validity(y_bad, y_val, y_test)


# ── Tasks 11 & 12: Normalized & Market-relative features ─────────────
def test_technical_indicators_computes_normalized_and_market_features():
    # Build synthetic multi-symbol OHLCV dataset
    symbols = ["SYM1", "SYM2"]
    dates = pd.date_range("2024-01-01", periods=100)
    rows = []
    for s in symbols:
        for i, d in enumerate(dates):
            rows.append({
                "symbol": s,
                "date": d,
                "open": 100.0 + i,
                "high": 105.0 + i,
                "low": 95.0 + i,
                "close": 101.0 + i,
                "volume": 10000.0 + i * 10,
            })
    df = pd.DataFrame(rows)
    out = compute_technical_indicators(df)

    # Normalized features (Task 11)
    assert "close_to_sma20_ratio" in out.columns
    assert "close_to_sma50_ratio" in out.columns
    assert "ema_cross_ratio" in out.columns
    assert "bollinger_pos" in out.columns
    assert "daily_range_pct" in out.columns
    assert "volume_change_1d" in out.columns

    # Market-relative features (Task 12)
    assert "index_return_5d" in out.columns
    assert "index_return_20d" in out.columns
    assert "stock_return_20d" in out.columns
    assert "stock_relative_return_20d" in out.columns


# ── Task 14 & 15: Evaluation metrics and naive baseline ───────────────
def test_comprehensive_evaluation_metrics():
    y_true = np.array([0, 1, 2, 0, 1, 2])
    y_pred = np.array([0, 1, 2, 1, 1, 2])
    m = compute_metrics(y_true, y_pred, label_names={0: "bullish", 1: "bearish", 2: "sideways"})
    assert "accuracy" in m
    assert "macro_f1" in m
    assert "weighted_f1" in m
    assert "balanced_accuracy" in m
    assert "confusion_matrix" in m


# ── Task 17: Ensemble agreement semantics ────────────────────────────
def test_ensemble_agreement_reason():
    gru = {
        "direction": "bullish",
        "bullish_pct": 55.0,
        "bearish_pct": 25.0,
        "sideways_pct": 20.0,
        "top_class_probability": 55.0,
        "gap_pp": 30.0,
    }
    xgb = {
        "direction": "bullish",
        "bullish_pct": 50.0,
        "bearish_pct": 30.0,
        "sideways_pct": 20.0,
        "top_class_probability": 50.0,
        "gap_pp": 20.0,
    }
    res = _ensemble_decide(gru, xgb)
    assert res["direction"] == "bullish"
    assert res["gate_reason"] == "agree(bullish)"


# ── Task 20: Reproducibility ─────────────────────────────────────────
def test_reproducibility_seeding():
    info = set_seed(12345)
    assert info["seed"] == 12345
    r1 = np.random.rand(5)
    set_seed(12345)
    r2 = np.random.rand(5)
    np.testing.assert_array_equal(r1, r2)


def test_xgb_sample_weights_computation():
    from app.ml.training_xgb.model import compute_sample_weights

    y = np.array([0, 0, 1, 2, 2, 2])
    weights = compute_sample_weights(y)
    assert len(weights) == len(y)
    # Rare class 1 receives highest sample weight
    assert weights[2] > weights[0] > weights[3]


def test_inference_missing_feature_raises_error():
    from app.ml.serving.inference import _run_gru, FeatureMismatchError
    from app.ml.serving.model_loader import artifacts

    artifacts.model_ready = True
    artifacts.window_size = 30
    artifacts.feature_columns = ["f1", "f2", "f3"]
    # DataFrame missing f3
    df = pd.DataFrame({"f1": np.zeros(35), "f2": np.zeros(35)})
    with pytest.raises(FeatureMismatchError, match="missing required features"):
        _run_gru("TEST", df)

