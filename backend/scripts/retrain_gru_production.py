"""
Production Retraining Script for GRU v1 Deep Sequence Model.
Trains on all historical PSX market sequences up to September 17, 2026 using the 36
standardized technical, oscillator, pattern, and macro features.

Exports:
1. backend/models/gru_v1/model.keras
2. backend/models/gru_v1/metadata.json
3. backend/data/scalers/scaler.pkl
"""

import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_class_weight
import tensorflow as tf
from tensorflow.keras import callbacks, layers, models, optimizers

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
log = logging.getLogger("retrain_gru_production")

ROOT_DIR = Path(__file__).resolve().parents[1]
FEATURES_PATH = ROOT_DIR / "data" / "features" / "features_daily.parquet"
MODEL_DIR = ROOT_DIR / "models" / "gru_v1"
SCALER_DIR = ROOT_DIR / "data" / "scalers"

WINDOW_SIZE = 30
LABEL_MAPPING = {"bullish": 0, "bearish": 1, "sideways": 2}


def retrain_and_export_gru():
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    SCALER_DIR.mkdir(parents=True, exist_ok=True)

    from app.data.features.gru_feature_list import GRU_FEATURE_LIST, GRU_FEATURE_VERSION

    log.info("Loading feature dataset from %s", FEATURES_PATH)
    df = pd.read_parquet(FEATURES_PATH)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

    log.info("Total rows: %d | Symbols: %d | Date span: %s to %s",
             len(df), df["symbol"].nunique(), str(df["date"].min())[:10], str(df["date"].max())[:10])

    # Clean missing values
    for col in GRU_FEATURE_LIST:
        if col not in df.columns:
            raise ValueError(f"Required GRU feature missing: {col}")
        df[col] = df[col].fillna(df[col].median()).astype(np.float32)

    # Filter out rows with invalid labels
    df = df[df["label"].isin(LABEL_MAPPING.keys())].copy().reset_index(drop=True)

    # Chronological Split: 85% Train, 15% Validation (most recent data up to Sep 2026)
    unique_dates = df["date"].drop_duplicates().sort_values().values
    split_idx = int(len(unique_dates) * 0.85)
    val_cutoff_date = pd.Timestamp(unique_dates[split_idx])

    log.info("Validation cutoff date: %s (Train: %s to %s, Val: %s to %s)",
             str(val_cutoff_date)[:10],
             str(df["date"].min())[:10], str(val_cutoff_date)[:10],
             str(val_cutoff_date)[:10], str(df["date"].max())[:10])

    # Build sequence index list per symbol
    log.info("Constructing sliding sequence windows (window_size=%d)...", WINDOW_SIZE)
    feature_matrix = df[GRU_FEATURE_LIST].values.astype(np.float32)
    labels_arr = df["label"].map(LABEL_MAPPING).values.astype(np.int32)
    dates_arr = df["date"].values

    train_X, train_y = [], []
    val_X, val_y = [], []

    val_cutoff_np = np.datetime64(val_cutoff_date)

    for sym, grp in df.groupby("symbol"):
        indices = grp.index.values
        n = len(indices)
        if n <= WINDOW_SIZE:
            continue
        for i in range(WINDOW_SIZE - 1, n):
            idx_end = indices[i]
            idx_start = indices[i - WINDOW_SIZE + 1]
            seq_x = feature_matrix[idx_start: idx_end + 1]
            lbl = labels_arr[idx_end]
            dt = dates_arr[idx_end]

            if dt < val_cutoff_np:
                train_X.append(seq_x)
                train_y.append(lbl)
            else:
                val_X.append(seq_x)
                val_y.append(lbl)

    X_train = np.array(train_X, dtype=np.float32)
    y_train = np.array(train_y, dtype=np.int32)
    X_val = np.array(val_X, dtype=np.float32)
    y_val = np.array(val_y, dtype=np.int32)

    log.info("Sequences built: Train=%d samples, Val=%d samples", len(X_train), len(X_val))

    # Fit Scaler strictly on Train set
    log.info("Fitting StandardScaler on %d training time-steps...", len(X_train) * WINDOW_SIZE)
    N_tr, T_tr, F_tr = X_train.shape
    flat_train = X_train.reshape(N_tr * T_tr, F_tr)
    scaler = StandardScaler()
    scaler.fit(flat_train)

    # Transform Train and Val
    X_train_scaled = scaler.transform(flat_train).reshape(N_tr, T_tr, F_tr)

    N_val, T_val, F_val = X_val.shape
    flat_val = X_val.reshape(N_val * T_val, F_val)
    X_val_scaled = scaler.transform(flat_val).reshape(N_val, T_val, F_val)

    # Balanced Class Weights to prevent sideways bias
    class_weights_arr = compute_class_weight("balanced", classes=np.array([0, 1, 2]), y=y_train)
    class_weight_dict = {i: float(w) for i, w in enumerate(class_weights_arr)}
    log.info("Balanced Class Weights: Bullish(0)=%.3f, Bearish(1)=%.3f, Sideways(2)=%.3f",
             class_weight_dict[0], class_weight_dict[1], class_weight_dict[2])

    # Build Deep GRU Architecture
    log.info("Building Deep GRU Architecture...")
    inputs = layers.Input(shape=(WINDOW_SIZE, len(GRU_FEATURE_LIST)))
    x = layers.SpatialDropout1D(0.10)(inputs)
    x = layers.Bidirectional(layers.GRU(64, return_sequences=True))(x)
    x = layers.LayerNormalization()(x)
    x = layers.GRU(48, return_sequences=False)(x)
    x = layers.Dropout(0.20)(x)
    x = layers.Dense(32, activation="relu")(x)
    x = layers.Dropout(0.15)(x)
    outputs = layers.Dense(3, activation="softmax")(x)

    model = models.Model(inputs=inputs, outputs=outputs, name="gru_production_v2")
    opt = optimizers.Adam(learning_rate=0.001)
    model.compile(
        optimizer=opt,
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"]
    )
    model.summary(print_fn=log.info)

    # Callbacks
    model_save_path = MODEL_DIR / "model.keras"
    cb_list = [
        callbacks.EarlyStopping(monitor="val_loss", patience=5, restore_best_weights=True, verbose=1),
        callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=2, min_lr=1e-5, verbose=1),
    ]

    log.info("Training GRU model on all modern data...")
    t0 = time.time()
    history = model.fit(
        X_train_scaled, y_train,
        validation_data=(X_val_scaled, y_val),
        epochs=25,
        batch_size=128,
        class_weight=class_weight_dict,
        callbacks=cb_list,
        verbose=1
    )
    duration = time.time() - t0
    log.info("Training completed in %.1f seconds", duration)

    # Save Model
    log.info("Saving trained model to %s", model_save_path)
    model.save(str(model_save_path))

    # Save Scaler
    scaler_path = SCALER_DIR / "scaler.pkl"
    joblib.dump(scaler, scaler_path)
    log.info("Saved scaler to %s", scaler_path)

    # Compute validation metrics
    val_probs = model.predict(X_val_scaled, batch_size=256)
    val_preds = np.argmax(val_probs, axis=1)
    val_acc = float(np.mean(val_preds == y_val))
    log.info("Validation Accuracy on modern test period: %.2f%%", val_acc * 100)

    # Save Metadata
    metadata = {
        "model_version": "gru_v1_production_retrained",
        "feature_version": GRU_FEATURE_VERSION,
        "feature_columns": GRU_FEATURE_LIST,
        "n_features": len(GRU_FEATURE_LIST),
        "window_size": WINDOW_SIZE,
        "label_mapping": LABEL_MAPPING,
        "class_weights": class_weight_dict,
        "train_date_range": {
            "min": str(df["date"].min())[:10],
            "max": str(val_cutoff_date)[:10],
            "n": int(len(X_train))
        },
        "val_date_range": {
            "min": str(val_cutoff_date)[:10],
            "max": str(df["date"].max())[:10],
            "n": int(len(X_val))
        },
        "scaler_version": "StandardScaler_v2026",
        "training_duration_sec": duration,
        "val_accuracy": val_acc,
        "training_timestamp": datetime.utcnow().isoformat()
    }

    meta_path = MODEL_DIR / "metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    log.info("Saved metadata to %s", meta_path)

    print("\n=======================================================")
    print("GRU RETRAINING COMPLETE (All data up to Sep 17, 2026)")
    print(f"Validation Accuracy: {val_acc*100:.2f}%")
    print(f"Model saved: {model_save_path}")
    print(f"Scaler saved: {scaler_path}")
    print("=======================================================\n")


if __name__ == "__main__":
    retrain_and_export_gru()
