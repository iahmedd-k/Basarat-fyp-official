"""
Ensemble Engine v2 for Basarat PSX Forecasting.
Combines GRU-v2 deep sequence model with XGBoost-v2 tabular model
using temperature-scaled probability blending and directional conviction gating.
"""

from pathlib import Path
import json
import logging
import joblib
import numpy as np
import pandas as pd
import tensorflow as tf
import xgboost as xgb

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
log = logging.getLogger("ensemble_v2")

ROOT_DIR = Path(__file__).resolve().parents[3]
MODELS_V2_DIR = ROOT_DIR / "models" / "final" / "final_v2"


class EnsembleV2Predictor:
    def __init__(self, model_dir: Path = MODELS_V2_DIR):
        self.model_dir = model_dir
        self._load_artifacts()

    def _load_artifacts(self):
        log.info("Loading v2 ensemble models from %s", self.model_dir)
        # Load config
        with open(self.model_dir / "config.json", "r") as f:
            self.config = json.load(f)

        # Load GRU
        self.gru_model = tf.keras.models.load_model(self.model_dir / "gru_model.keras")
        self.gru_scaler = joblib.load(self.model_dir / "gru_scaler.pkl")
        with open(self.model_dir / "gru_features.json", "r") as f:
            self.gru_features = json.load(f)
        with open(self.model_dir / "gru_train_medians.json", "r") as f:
            self.gru_medians = json.load(f)

        # Load XGBoost
        self.xgb_model = xgb.XGBClassifier()
        self.xgb_model.load_model(str(self.model_dir / "xgb_model.ubj"))
        with open(self.model_dir / "xgb_features.json", "r") as f:
            self.xgb_features = json.load(f)
        with open(self.model_dir / "xgb_train_medians.json", "r") as f:
            self.xgb_medians = json.load(f)

        self.class_labels = ["bullish", "bearish", "sideways"]
        self.temperature = self.config.get("confidence_temperature", 0.75)
        log.info("Ensemble v2 loaded successfully (Temperature=%.2f)", self.temperature)

    def predict_single(self, gru_seq: np.ndarray, xgb_row: np.ndarray) -> dict:
        """
        Predict for a single stock observation.
        gru_seq: shape (45, 36)
        xgb_row: shape (34,)
        """
        # GRU inference
        scaled_seq = self.gru_scaler.transform(gru_seq).reshape(1, 45, -1)
        gru_probs = self.gru_model.predict(scaled_seq, verbose=0)[0]  # (3,)

        # XGB inference
        xgb_probs = self.xgb_model.predict_proba(xgb_row.reshape(1, -1))[0]  # (3,)

        # Temperature scaling
        gru_logits = np.log(np.clip(gru_probs, 1e-6, 1.0)) / self.temperature
        xgb_logits = np.log(np.clip(xgb_probs, 1e-6, 1.0)) / self.temperature

        def softmax(z):
            e_z = np.exp(z - np.max(z))
            return e_z / e_z.sum()

        scaled_gru_p = softmax(gru_logits)
        scaled_xgb_p = softmax(xgb_logits)

        # 50/50 Blending
        blended_p = 0.50 * scaled_gru_p + 0.50 * scaled_xgb_p
        pred_class_id = int(np.argmax(blended_p))
        confidence = float(blended_p[pred_class_id])

        # Directional Agreement
        gru_class_id = int(np.argmax(gru_probs))
        xgb_class_id = int(np.argmax(xgb_probs))
        models_agree = (gru_class_id == xgb_class_id)

        # Conviction Gating
        is_high_conviction = (confidence >= 0.60) or (models_agree and pred_class_id != 2 and confidence >= 0.45)

        return {
            "predicted_class": self.class_labels[pred_class_id],
            "predicted_class_id": pred_class_id,
            "confidence": confidence,
            "bullish_probability": float(blended_p[0]),
            "bearish_probability": float(blended_p[1]),
            "sideways_probability": float(blended_p[2]),
            "gru_probabilities": [float(p) for p in gru_probs],
            "xgb_probabilities": [float(p) for p in xgb_probs],
            "models_agree": bool(models_agree),
            "is_high_conviction": bool(is_high_conviction)
        }
