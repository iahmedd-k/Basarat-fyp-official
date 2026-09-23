"""
XGBoost Model Training Module - v3 Institutional Cross-Sectional Alpha Pipeline.

Key architectural improvements:
1. Zero continuous symbol_id leakage - pure relative cross-sectional rank features.
2. min_child_weight=100 - enforces at least 100 observations per leaf to prevent memorizing single-day noise.
3. Shallow tree depth (max_depth=4) + high regularization (reg_lambda=10.0, reg_alpha=1.0).
4. Trained on extreme signals (Top 30% Buy vs Bottom 30% Avoid) for clean signal separation.
"""

from pathlib import Path
import json
import logging
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import accuracy_score, roc_auc_score, f1_score

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
log = logging.getLogger("train_xgb_v3")

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_DATA_PATH = ROOT_DIR / "data" / "processed_v3" / "features_v3.parquet"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "models" / "experiments" / "v3_extremes_binary"


def get_v3_feature_columns(df: pd.DataFrame) -> list:
    """Return all cross-sectional rank feature columns."""
    cs_features = [c for c in df.columns if c.endswith("_csrank")]
    return sorted(cs_features)


def build_xgb_v3_classifier(
    n_estimators: int = 1500,
    learning_rate: float = 0.02,
    max_depth: int = 4,
    min_child_weight: int = 100,
    subsample: float = 0.8,
    colsample_bytree: float = 0.6,
    reg_lambda: float = 10.0,
    reg_alpha: float = 1.0,
    random_state: int = 42,
) -> xgb.XGBClassifier:
    """Build institutional-grade regularized XGBoost classifier for noisy financial return data."""
    return xgb.XGBClassifier(
        n_estimators=n_estimators,
        learning_rate=learning_rate,
        max_depth=max_depth,
        min_child_weight=min_child_weight,
        subsample=subsample,
        colsample_bytree=colsample_bytree,
        reg_lambda=reg_lambda,
        reg_alpha=reg_alpha,
        eval_metric="logloss",
        early_stopping_rounds=40,
        random_state=random_state,
        tree_method="hist",
        n_jobs=-1,
    )


def train_model(
    data_path: Path = DEFAULT_DATA_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    val_split_date: str = "2024-07-01",
    test_split_date: str = "2025-07-01",
):
    """
    Train final v3 XGBoost model on full dataset up to test_split_date,
    and save all production deployment artifacts.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    log.info("Loading v3 features dataset from %s", data_path)
    df = pd.read_parquet(data_path)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["date", "symbol"]).reset_index(drop=True)

    feature_cols = get_v3_feature_columns(df)
    log.info("Identified %d cross-sectional rank feature columns.", len(feature_cols))

    # Split train, val, test
    train_mask = (df["date"] < val_split_date) & (df["is_extreme_signal"] == True)
    val_mask = (df["date"] >= val_split_date) & (df["date"] < test_split_date) & (df["is_extreme_signal"] == True)
    test_mask = (df["date"] >= test_split_date) & (df["is_extreme_signal"] == True)

    X_train = df.loc[train_mask, feature_cols].fillna(0.5).astype(np.float32)
    y_train = df.loc[train_mask, "target_cs_class"].astype(int)

    X_val = df.loc[val_mask, feature_cols].fillna(0.5).astype(np.float32)
    y_val = df.loc[val_mask, "target_cs_class"].astype(int)

    X_test = df.loc[test_mask, feature_cols].fillna(0.5).astype(np.float32)
    y_test = df.loc[test_mask, "target_cs_class"].astype(int)

    log.info(
        "Train set: %d samples | Val set: %d samples | Out-of-sample Test set: %d samples",
        len(X_train),
        len(X_val),
        len(X_test),
    )

    clf = build_xgb_v3_classifier()
    log.info("Fitting XGBoost v3 with early stopping on validation set...")
    clf.fit(
        X_train,
        y_train,
        eval_set=[(X_train, y_train), (X_val, y_val)],
        verbose=100,
    )

    # Evaluate out-of-sample
    test_preds_proba = clf.predict_proba(X_test)[:, 0]  # Probability of class 0 (Buy / Outperform)
    test_preds = (test_preds_proba < 0.5).astype(int)  # 0 if prob(0) >= 0.5, else 1

    test_acc = accuracy_score(y_test, test_preds)
    test_f1 = f1_score(y_test, test_preds, average="macro")
    # For ROC AUC, positive class is 0 (Buy)
    test_auc = roc_auc_score((y_test == 0).astype(int), test_preds_proba)

    log.info("=== OUT-OF-SAMPLE TEST METRICS (from %s) ===", test_split_date)
    log.info("Buy vs Avoid Directional Accuracy: %.4f (%.2f%%)", test_acc, test_acc * 100)
    log.info("Macro F1-Score: %.4f", test_f1)
    log.info("ROC-AUC: %.4f", test_auc)

    # Feature importances
    importances = pd.Series(clf.feature_importances_, index=feature_cols).sort_values(ascending=False)
    log.info("Top 10 Feature Importances (Gain):\n%s", importances.head(10).to_string())

    # Save artifacts
    model_path = output_dir / "xgb_model.ubj"
    clf.save_model(str(model_path))
    log.info("Saved XGBoost v3 model -> %s", model_path)

    features_meta_path = output_dir / "xgb_features.json"
    with open(features_meta_path, "w") as f:
        json.dump(feature_cols, f, indent=2)

    metadata = {
        "model_type": "XGBoost v3 (Cross-Sectional Rank-Normalized)",
        "features": feature_cols,
        "feature_count": len(feature_cols),
        "classes": ["buy", "avoid"],
        "label_mapping": {"buy": 0, "avoid": 1},
        "probabilities_calibrated": False,
        "min_child_weight": 100,
        "max_depth": 4,
        "best_iteration": int(clf.best_iteration),
        "test_split_date": test_split_date,
        "test_accuracy": float(test_acc),
        "test_macro_f1": float(test_f1),
        "test_auc": float(test_auc),
        "top_features": importances.head(10).to_dict(),
    }
    with open(output_dir / "v3_model_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
    log.info("Saved v3 model metadata -> %s", output_dir / "v3_model_metadata.json")

    return clf, metadata


if __name__ == "__main__":
    train_model()
