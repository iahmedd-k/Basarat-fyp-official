"""
Training pipeline for XGBoost-v2 tabular model on stationary PSX features.
Features: 34 scale-invariant technical, market-regime, and volatility features.
"""

from pathlib import Path
import json
import logging
import numpy as np
import pandas as pd
import xgboost as xgb

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
log = logging.getLogger("train_xgb_v2")

ROOT_DIR = Path(__file__).resolve().parents[3]
FEATURES_PARQUET = ROOT_DIR / "data" / "processed_v2" / "features_v2.parquet"
METADATA_JSON = ROOT_DIR / "data" / "processed_v2" / "v2_features_metadata.json"
MODELS_V2_DIR = ROOT_DIR / "models" / "final" / "final_v2"

SPLIT_TRAIN_DATE = "2025-01-01"
SPLIT_VAL_DATE = "2025-09-01"


def compute_sample_weight_fast(y):
    classes, counts = np.unique(y, return_counts=True)
    total = len(y)
    n_classes = len(classes)
    weight_map = {c: total / (n_classes * cnt) for c, cnt in zip(classes, counts)}
    return np.array([weight_map[val] for val in y], dtype=np.float32)


def load_and_prepare_tabular():
    log.info("Loading v2 tabular features from %s", FEATURES_PARQUET)
    with open(METADATA_JSON, "r") as f:
        meta = json.load(f)
    feature_cols = meta["xgb_features"]
    log.info("XGBoost v2 feature count: %d", len(feature_cols))

    needed_cols = ["symbol", "date", "target_fixed_class", "actual_5d_return"] + feature_cols
    df = pd.read_parquet(FEATURES_PARQUET, columns=needed_cols)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

    # Drop last 5 rows per symbol where target is nan
    df = df.dropna(subset=["actual_5d_return"]).copy()

    # Split masks
    train_mask = df["date"] < SPLIT_TRAIN_DATE
    val_mask = (df["date"] >= SPLIT_TRAIN_DATE) & (df["date"] < SPLIT_VAL_DATE)
    test_mask = df["date"] >= SPLIT_VAL_DATE

    log.info("Date splits: Train < %s (%d rows), Val %s to %s (%d rows), Test >= %s (%d rows)",
             SPLIT_TRAIN_DATE, train_mask.sum(),
             SPLIT_TRAIN_DATE, SPLIT_VAL_DATE, val_mask.sum(),
             SPLIT_VAL_DATE, test_mask.sum())

    # Impute missing values with train medians
    train_medians = df.loc[train_mask, feature_cols].median().to_dict()
    for col in feature_cols:
        df[col] = df[col].fillna(train_medians[col]).astype(np.float32)

    X_train = df.loc[train_mask, feature_cols].values
    y_train = df.loc[train_mask, "target_fixed_class"].values.astype(int)
    w_train = compute_sample_weight_fast(y_train)

    X_val = df.loc[val_mask, feature_cols].values
    y_val = df.loc[val_mask, "target_fixed_class"].values.astype(int)
    w_val = compute_sample_weight_fast(y_val)

    X_test = df.loc[test_mask, feature_cols].values
    y_test = df.loc[test_mask, "target_fixed_class"].values.astype(int)

    return (X_train, y_train, w_train), (X_val, y_val, w_val), (X_test, y_test), train_medians, feature_cols


def train_and_export():
    (X_train, y_train, w_train), (X_val, y_val, w_val), (X_test, y_test), train_medians, feature_cols = load_and_prepare_tabular()

    log.info("Configuring XGBoost-v2 Classifier...")
    model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.04,
        subsample=0.80,
        colsample_bytree=0.80,
        objective="multi:softprob",
        num_class=3,
        eval_metric="mlogloss",
        early_stopping_rounds=15,
        random_state=42,
        n_jobs=-1
    )

    log.info("Fitting XGBoost-v2 on %d training rows...", len(X_train))
    model.fit(
        X_train, y_train,
        sample_weight=w_train,
        eval_set=[(X_val, y_val)],
        sample_weight_eval_set=[w_val],
        verbose=20
    )

    # Evaluate on Test
    test_preds = model.predict_proba(X_test)
    test_pred_classes = np.argmax(test_preds, axis=1)
    test_acc = (test_pred_classes == y_test).mean()
    log.info("XGBoost-v2 Out-of-sample Test Accuracy: %.4f (N=%d)", test_acc, len(y_test))

    # Export to models/final/final_v2/
    MODELS_V2_DIR.mkdir(parents=True, exist_ok=True)
    model_export_path = MODELS_V2_DIR / "xgb_model.ubj"
    model.save_model(str(model_export_path))

    with open(MODELS_V2_DIR / "xgb_train_medians.json", "w") as f:
        json.dump(train_medians, f, indent=2)
    with open(MODELS_V2_DIR / "xgb_features.json", "w") as f:
        json.dump(feature_cols, f, indent=2)

    # Export v2 package config
    v2_config = {
        "version": "final_v2",
        "description": "High-Conviction Quantitative Ensemble on Stationary Features",
        "date_trained": "2026-09-19",
        "horizon": "5D",
        "thresholds": "+-1.0%",
        "classes": ["bullish", "bearish", "sideways"],
        "class_mapping": {"bullish": 0, "bearish": 1, "sideways": 2},
        "gru_sequence_length": 45,
        "gru_features_count": 36,
        "xgb_features_count": len(feature_cols),
        "ensemble_weights": {"gru": 0.50, "xgb": 0.50},
        "confidence_temperature": 0.75
    }
    with open(MODELS_V2_DIR / "config.json", "w") as f:
        json.dump(v2_config, f, indent=2)

    log.info("Saved all XGBoost-v2 artifacts and config to %s", MODELS_V2_DIR)
    return test_acc


if __name__ == "__main__":
    train_and_export()
