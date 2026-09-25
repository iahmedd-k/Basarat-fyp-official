"""Model loading — loads Attention-BiGRU + XGBoost v3/v4 models + scaler + metadata once at startup.

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

ROOT_DIR = Path(__file__).resolve().parents[3]

PROD_V3_DIR = Path("models/final/final_v3") if Path("models/final/final_v3").exists() else ROOT_DIR / "models" / "final" / "final_v3"
DATA_DIR = Path("data/scalers") if Path("data/scalers").exists() else ROOT_DIR / "data" / "scalers"


def build_attention_bigru(input_shape: tuple[int, int]):
    """Instantiate the stationary Attention-BiGRU architecture."""
    import tensorflow as tf
    from tensorflow.keras import layers, models, optimizers

    inp = layers.Input(shape=input_shape, name="stationary_daily_sequence")
    x = layers.SpatialDropout1D(0.10)(inp)
    x = layers.Conv1D(filters=64, kernel_size=3, padding="same", activation="relu")(x)
    x = layers.LayerNormalization()(x)
    x = layers.Bidirectional(layers.GRU(64, return_sequences=True, dropout=0.15))(x)
    x = layers.LayerNormalization()(x)
    x = layers.Bidirectional(layers.GRU(32, return_sequences=True, dropout=0.15))(x)
    x = layers.LayerNormalization()(x)

    # Temporal Attention Pooling
    score = layers.Dense(1, activation="tanh")(x)
    weights = layers.Softmax(axis=1)(score)
    context = layers.Multiply()([x, weights])
    pooled = layers.Lambda(lambda z: tf.reduce_sum(z, axis=1))(context)

    dense = layers.Dense(32, activation="relu")(pooled)
    dense = layers.Dropout(0.20)(dense)
    dense = layers.Dense(16, activation="relu")(dense)
    dense = layers.Dropout(0.10)(dense)
    out = layers.Dense(1, activation="sigmoid", name="up_probability")(dense)
    model = models.Model(inp, out, name="psx_directional_attention_bigru")
    model.compile(optimizer=optimizers.Adam(learning_rate=4e-4),
                  loss="binary_crossentropy", metrics=["accuracy"])
    return model


@dataclass
class ModelArtifacts:
    # GRU artifacts
    model: object | None = None
    scaler: object | None = None
    feature_columns: list[str] = field(default_factory=list)
    label_mapping: dict[str, int] = field(default_factory=lambda: {"bearish": 0, "bullish": 1})
    label_names: dict[int, str] = field(default_factory=lambda: {0: "bearish", 1: "bullish"})
    window_size: int = 45
    n_features: int = 79
    model_version: str = "attention_bigru_v2_production"
    model_ready: bool = False

    # XGB artifacts
    xgb_model: object | None = None
    xgb_feature_names: list[str] = field(default_factory=list)
    xgb_data_path: Path = Path("data/features/features_daily.parquet")
    xgb_ready: bool = False
    xgb_model_version: str = "xgb_v4_event_fundamentals"


artifacts = ModelArtifacts()


def _load_xgb_artifacts() -> None:
    """Load XGBoost model and feature names. Called during startup."""
    try:
        from xgboost import XGBClassifier

        prod_model_path = PROD_V3_DIR / "xgb_model.ubj"

        if prod_model_path.exists():
            artifacts.xgb_model = XGBClassifier()
            artifacts.xgb_model.load_model(str(prod_model_path))
            log.info("Loaded Production XGBoost v4 model <- %s", prod_model_path)

            prod_meta_path = PROD_V3_DIR / "xgb_features.json"
            if prod_meta_path.exists():
                artifacts.xgb_feature_names = json.loads(prod_meta_path.read_text(encoding="utf-8"))
            log.info("Loaded XGB features <- %d features in exact training order", len(artifacts.xgb_feature_names))
            artifacts.xgb_ready = True
            artifacts.xgb_model_version = "xgb_v4_event_fundamentals"
            log.info("XGB artifacts loaded successfully — xgb_ready=True (xgb_v4_event_fundamentals)")
            return

        log.warning("Production XGBoost model artifact not found at %s", prod_model_path)

    except ImportError:
        log.warning("xgboost not installed — XGB ensemble disabled")
    except Exception:
        log.exception("Failed to load XGB artifacts")


def load_artifacts() -> None:
    """Load all ML artifacts into the module-level singleton.

    Called once during app startup. If anything fails, model_ready stays False.
    """
    # ── Load Attention-BiGRU Model (v2 Production) ────────────────────
    try:
        gru_weights_path = PROD_V3_DIR / "gru_best_weights.weights.h5"
        gru_features_path = PROD_V3_DIR / "gru_features.json"
        gru_scaler_path = PROD_V3_DIR / "gru_scaler.joblib"

        if gru_weights_path.exists() and gru_features_path.exists() and gru_scaler_path.exists():
            features = json.loads(gru_features_path.read_text(encoding="utf-8"))
            n_feat = len(features)
            window = 45

            model = build_attention_bigru((window, n_feat))
            model.load_weights(str(gru_weights_path))
            artifacts.model = model
            artifacts.scaler = joblib.load(gru_scaler_path)
            artifacts.feature_columns = features
            artifacts.window_size = window
            artifacts.n_features = n_feat
            artifacts.model_version = "attention_bigru_v2_production"
            artifacts.label_mapping = {"bearish": 0, "bullish": 1}
            artifacts.label_names = {0: "bearish", 1: "bullish"}
            artifacts.model_ready = True
            log.info("Loaded Production Attention-BiGRU v2 model <- %s (window=%d, features=%d)",
                     gru_weights_path, window, n_feat)
        else:
            # Legacy fallback if v3 weights not available
            import tensorflow as tf
            legacy_model_path = GRU_MODEL_DIR / "model.keras"
            legacy_meta_path = GRU_MODEL_DIR / "metadata.json"
            legacy_scaler_path = DATA_DIR / "scaler.pkl"
            if legacy_model_path.exists() and legacy_meta_path.exists() and legacy_scaler_path.exists():
                artifacts.model = tf.keras.models.load_model(str(legacy_model_path), safe_mode=False)
                artifacts.scaler = joblib.load(legacy_scaler_path)
                meta = json.loads(legacy_meta_path.read_text(encoding="utf-8"))
                artifacts.feature_columns = meta["feature_columns"]
                artifacts.label_mapping = meta["label_mapping"]
                artifacts.label_names = {v: k for k, v in meta["label_mapping"].items()}
                artifacts.window_size = meta["window_size"]
                artifacts.n_features = meta["n_features"]
                artifacts.model_version = GRU_MODEL_DIR.name
                artifacts.model_ready = True
                log.info("Loaded legacy GRU model <- %s", legacy_model_path)
            else:
                log.error("No valid GRU model found in %s or %s", PROD_V3_DIR, GRU_MODEL_DIR)
                artifacts.model_ready = False

    except Exception:
        log.exception("Failed to load Attention-BiGRU model")
        artifacts.model_ready = False

    # ── Load XGBoost Artifacts ────────────────────────────────────────
    _load_xgb_artifacts()

    # If XGB is ready but GRU had an issue, we can still serve predictions
    if artifacts.xgb_ready and not artifacts.model_ready:
        log.warning("XGBoost is ready; enabling single-model XGB serving mode")
        artifacts.model_ready = True
