import numpy as np
import pandas as pd
import pytest

from app.services.recommendation_service import RecommendationEngine


class StubClassifier:
    classes_ = np.array([0, 1, 2])

    def predict_proba(self, features):
        return np.array([[0.70, 0.20, 0.10]])


class BinaryDownUpClassifier:
    classes_ = np.array([0, 1])

    def predict_proba(self, features):
        return np.array([[0.70, 0.30]])


def test_ml_signal_uses_manifest_class_ids_not_probability_position(monkeypatch):
    monkeypatch.setattr(
        "app.services.recommendation_service._get_production_model",
        lambda: (
            StubClassifier(),
            ["ranked_feature"],
            {"label_mapping": {"bearish": 0, "bullish": 1, "sideways": 2}},
        ),
    )
    frame = pd.DataFrame({"ranked_feature": [0.5], "is_primary_universe": [True]})

    signal, reasoning = RecommendationEngine()._ml_signal(frame)

    assert signal == pytest.approx(-0.5)
    assert reasoning["prob_bearish"] == 0.7
    assert reasoning["prob_bullish"] == 0.2


def test_ml_signal_maps_production_down_up_class_names(monkeypatch):
    monkeypatch.setattr(
        "app.services.recommendation_service._get_production_model",
        lambda: (BinaryDownUpClassifier(), ["ranked_feature"], {"classes": ["down", "up"]}),
    )
    frame = pd.DataFrame({"ranked_feature": [0.5], "is_primary_universe": [True]})

    signal, reasoning = RecommendationEngine()._ml_signal(frame)

    assert signal == pytest.approx(-0.4)
    assert reasoning["prob_bearish"] == 0.7
    assert reasoning["prob_bullish"] == 0.3


def test_ml_signal_does_not_replace_missing_cross_sectional_features(monkeypatch):
    monkeypatch.setattr(
        "app.services.recommendation_service._get_production_model",
        lambda: (StubClassifier(), ["ranked_feature"], {"label_mapping": {"bearish": 0, "bullish": 1, "sideways": 2}}),
    )

    signal, reasoning = RecommendationEngine()._ml_signal(
        pd.DataFrame({"raw_feature": [0.5], "is_primary_universe": [True]})
    )

    assert signal == 0.0
    assert reasoning["status"] == "unavailable"
    assert "missing model features" in reasoning["reason"]


def test_ml_signal_is_disabled_outside_training_liquidity_universe(monkeypatch):
    monkeypatch.setattr(
        "app.services.recommendation_service._get_production_model",
        lambda: (StubClassifier(), ["ranked_feature"], {"label_mapping": {"bearish": 0, "bullish": 1, "sideways": 2}}),
    )

    signal, reasoning = RecommendationEngine()._ml_signal(
        pd.DataFrame({"ranked_feature": [0.5], "is_primary_universe": [False]})
    )

    assert signal == 0.0
    assert reasoning["status"] == "unavailable"
    assert "primary liquidity universe" in reasoning["reason"]


def test_composite_renormalizes_only_over_available_components(monkeypatch):
    engine = RecommendationEngine()
    monkeypatch.setattr(engine, "_ml_signal", lambda frame: (0.0, {"status": "unavailable"}))
    monkeypatch.setattr(engine, "_technical_signal", lambda frame: (0.4, {"status": "available"}))
    monkeypatch.setattr(engine, "_fundamental_signal", lambda symbol, overview_data=None: (0.0, {"status": "unavailable"}))

    result = engine.compute_composite("TEST", pd.DataFrame({"close": [1.0]}))

    assert result["composite_score"] == 0.4
    assert result["effective_weights"] == {"technical": 1.0}
    assert result["status"] == "partial"


def test_neutral_atr_envelope_has_no_directional_stop():
    frame = pd.DataFrame({"close": [100.0], "atr_14": [2.0]})

    result = RecommendationEngine().compute_target_stop("TEST", frame, ml_direction="hold")

    assert result["target_price"] is None
    assert result["stop_loss"] is None
    assert result["expected_range"]["low"] < 100 < result["expected_range"]["high"]
