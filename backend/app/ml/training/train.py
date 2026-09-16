"""
Training loop — early stopping, checkpointing, history logging.
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import tensorflow as tf

log = logging.getLogger("training.train")

MODELS_DIR = Path("models")
HISTORY_PATH = Path("data/reports/training_history.json")


def train_model(
    model: tf.keras.Model,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    batch_size: int = 32,
    max_epochs: int = 50,
    patience: int = 5,
    model_save_path: Path = MODELS_DIR / "gru_v1" / "model.keras",
    history_path: Path = HISTORY_PATH,
    class_weight: dict | None = None,
    metadata_path: Path | None = None,
) -> dict:
    """Train the model with early stopping.

    Returns
    -------
    dict with keys: history, best_val_accuracy, training_duration_sec, epochs_run.
    """
    model_save_path.parent.mkdir(parents=True, exist_ok=True)

    callbacks = [
        tf.keras.callbacks.EarlyStopping(
            monitor="val_loss",
            patience=patience,
            restore_best_weights=True,
            verbose=1,
        ),
        tf.keras.callbacks.ModelCheckpoint(
            filepath=str(model_save_path),
            monitor="val_loss",
            save_best_only=True,
            verbose=0,
        ),
    ]

    log.info(
        "Training started — max_epochs=%d, batch_size=%d, patience=%d, class_weight=%s",
        max_epochs, batch_size, patience,
        "balanced" if class_weight else "None",
    )
    log.info("Train samples: %d | Val samples: %d", len(X_train), len(X_val))

    t0 = time.time()
    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=max_epochs,
        batch_size=batch_size,
        callbacks=callbacks,
        class_weight=class_weight,
        verbose=1,
    )
    duration = time.time() - t0

    # ── Extract history ─────────────────────────────────────────────────
    hist = {k: [float(v) for v in vals] for k, vals in history.history.items()}
    best_val_acc = max(hist.get("val_accuracy", [0]))
    epochs_run = len(hist.get("loss", []))

    log.info(
        "Training complete — epochs=%d, best_val_acc=%.4f, duration=%.1fs",
        epochs_run, best_val_acc, duration,
    )

    # ── Save history ────────────────────────────────────────────────────
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(json.dumps(hist, indent=2), encoding="utf-8")
    log.info("Training history saved -> %s", history_path)

    # ── Save metadata ───────────────────────────────────────────────────
    meta = {
        "training_date": datetime.now().isoformat(),
        "epochs_run": epochs_run,
        "best_val_accuracy": round(best_val_acc, 4),
        "training_duration_sec": round(duration, 1),
        "tensorflow_version": tf.__version__,
        "batch_size": batch_size,
        "max_epochs": max_epochs,
        "patience": patience,
        "class_weight": "balanced" if class_weight else None,
        "model_save_path": str(model_save_path),
    }
    meta_path = metadata_path if metadata_path else model_save_path.parent / "metadata.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    log.info("Model metadata saved -> %s", meta_path)

    return {
        "history": hist,
        "best_val_accuracy": best_val_acc,
        "training_duration_sec": duration,
        "epochs_run": epochs_run,
        "model_save_path": str(model_save_path),
    }
