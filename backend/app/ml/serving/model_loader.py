"""Model loading — loads model + scaler + metadata once at startup.

Stores everything in a module-level singleton that inference.py reads from.
If any artifact is missing, model_ready stays False and endpoints return 503.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np

log = logging.getLogger(__name__)

MODEL_DIR = Path("models")
DATA_DIR = Path("data/processed")


@dataclass
class ModelArtifacts:
    model: object | None = None
    scaler: object | None = None
    feature_columns: list[str] = field(default_factory=list)
    label_mapping: dict[str, int] = field(default_factory=dict)
    label_names: dict[int, str] = field(default_factory=dict)
    window_size: int = 30
    n_features: int = 20
    model_version: str = "gru_v1"
    model_ready: bool = False


artifacts = ModelArtifacts()


def load_artifacts() -> None:
    """Load all ML artifacts into the module-level singleton.

    Called once during app startup. If anything fails, model_ready stays False.
    """
    import tensorflow as tf

    try:
        # ── Model ───────────────────────────────────────────────────────
        model_path = MODEL_DIR / "gru_v1.keras"
        if not model_path.exists():
            log.error("Model file not found: %s", model_path)
            return
        artifacts.model = tf.keras.models.load_model(str(model_path))
        log.info("Loaded model <- %s", model_path)

        # ── Scaler ──────────────────────────────────────────────────────
        scaler_path = DATA_DIR / "scaler.pkl"
        if not scaler_path.exists():
            log.error("Scaler file not found: %s", scaler_path)
            return
        artifacts.scaler = joblib.load(scaler_path)
        log.info("Loaded scaler <- %s", scaler_path)

        # ── Metadata ────────────────────────────────────────────────────
        meta_path = MODEL_DIR / "metadata.json"
        if not meta_path.exists():
            log.error("Metadata file not found: %s", meta_path)
            return
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        artifacts.feature_columns = meta["feature_columns"]
        artifacts.label_mapping = meta["label_mapping"]
        artifacts.label_names = {v: k for k, v in meta["label_mapping"].items()}
        artifacts.window_size = meta["window_size"]
        artifacts.n_features = meta["n_features"]
        artifacts.model_version = Path(meta.get("model_save_path", "gru_v1")).stem
        log.info("Loaded metadata <- %s (window=%d, features=%d)",
                 meta_path, artifacts.window_size, artifacts.n_features)

        # ── Validate shapes ─────────────────────────────────────────────
        expected_shape = (None, artifacts.window_size, artifacts.n_features)
        actual_shape = artifacts.model.input_shape
        if actual_shape[1:] != (artifacts.window_size, artifacts.n_features):
            log.error("Model input shape %s does not match metadata %s",
                      actual_shape, expected_shape)
            return

        artifacts.model_ready = True
        log.info("All ML artifacts loaded successfully — model_ready=True")

    except Exception:
        log.exception("Failed to load ML artifacts")
        artifacts.model_ready = False
