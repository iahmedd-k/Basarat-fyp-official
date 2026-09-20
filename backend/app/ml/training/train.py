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
    # Use generator-based training to avoid memory issues with large arrays
    def train_generator():
        """Generator yielding batches from training data."""
        n_samples = len(X_train)
        indices = np.arange(n_samples)
        np.random.seed(42)
        while True:
            np.random.shuffle(indices)
            for i in range(0, n_samples, batch_size):
                batch_idx = indices[i:i + batch_size]
                if class_weight is not None:
                    batch_y = y_train[batch_idx]
                    sample_w = np.array([class_weight[int(y)] for y in batch_y], dtype=np.float32)
                    yield X_train[batch_idx], batch_y, sample_w
                else:
                    yield X_train[batch_idx], y_train[batch_idx]

    def val_generator():
        """Generator yielding batches from validation data."""
        n_samples = len(X_val)
        indices = np.arange(n_samples)
        while True:
            for i in range(0, n_samples, batch_size):
                batch_idx = indices[i:i + batch_size]
                yield X_val[batch_idx], y_val[batch_idx]

    steps_per_epoch = int(np.ceil(len(X_train) / batch_size))
    val_steps = int(np.ceil(len(X_val) / batch_size))

    history = model.fit(
        train_generator(),
        validation_data=val_generator(),
        epochs=max_epochs,
        steps_per_epoch=steps_per_epoch,
        validation_steps=val_steps,
        callbacks=callbacks,
        class_weight=None,
        verbose=1,
    )
    duration = time.time() - t0

    # ── Extract history & Task 7: True best model metrics by val_loss ──
    hist = {k: [float(v) for v in vals] for k, vals in history.history.items()}
    epochs_run = len(hist.get("loss", []))
    val_losses = hist.get("val_loss", [])
    val_accs = hist.get("val_accuracy", [])

    if val_losses:
        best_epoch_idx = int(np.argmin(val_losses))
        best_val_loss = round(float(val_losses[best_epoch_idx]), 6)
        val_acc_at_best_loss = round(float(val_accs[best_epoch_idx]), 4) if best_epoch_idx < len(val_accs) else None
        best_epoch = best_epoch_idx + 1
    else:
        best_val_loss = None
        val_acc_at_best_loss = None
        best_epoch = epochs_run

    log.info(
        "Training complete — epochs=%d, best_epoch=%d, best_val_loss=%s, val_acc_at_best_loss=%s, duration=%.1fs",
        epochs_run, best_epoch, best_val_loss, val_acc_at_best_loss, duration,
    )

    # ── Save history ────────────────────────────────────────────────────
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(json.dumps(hist, indent=2), encoding="utf-8")
    log.info("Training history saved -> %s", history_path)

    # ── Save metadata (Task 18 & Task 7 & Task 20) ──────────────────────
    meta = {
        "training_date": datetime.now().isoformat(),
        "epochs_run": epochs_run,
        "best_epoch": best_epoch,
        "best_val_loss": best_val_loss,
        "val_accuracy_at_best_val_loss": val_acc_at_best_loss,
        "training_duration_sec": round(duration, 1),
        "tensorflow_version": tf.__version__,
        "batch_size": batch_size,
        "max_epochs": max_epochs,
        "patience": patience,
        "class_weight": {int(k): float(v) for k, v in class_weight.items()} if isinstance(class_weight, dict) else class_weight,
        "model_save_path": str(model_save_path),
    }
    meta_path = metadata_path if metadata_path else model_save_path.parent / "metadata.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    log.info("Model metadata saved -> %s", meta_path)

    return {
        "history": hist,
        "best_epoch": best_epoch,
        "best_val_loss": best_val_loss,
        "val_accuracy_at_best_val_loss": val_acc_at_best_loss,
        "training_duration_sec": duration,
        "epochs_run": epochs_run,
        "model_save_path": str(model_save_path),
    }
