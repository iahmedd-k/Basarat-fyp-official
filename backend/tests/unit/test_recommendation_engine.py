import pandas as pd
import pytest

from app.services.recommendation_service import RecommendationEngine


def test_ml_signal_uses_shared_forecast_probabilities(monkeypatch):
    monkeypatch.setattr(
        "app.ml.serving.inference.get_forecast",
        lambda symbol, horizon, sym_df: {
            "symbol": symbol, "direction": "uncertain", "horizon": horizon,
            "bullish_pct": 47.3, "bearish_pct": 52.7, "sideways_pct": 0,
            "model_version": "ensemble", "gate_reason": "near_tie",
            "as_of_date": "2026-09-18",
        },
    )
    frame = pd.DataFrame({"symbol": ["UBL"], "date": ["2026-09-18"]})

    signal, reasoning = RecommendationEngine()._ml_signal(frame, "UBL")

    assert signal == pytest.approx(-0.054)
    assert reasoning["prob_bearish"] == pytest.approx(0.527)
    assert reasoning["prob_bullish"] == pytest.approx(0.473)
    assert reasoning["model_version"] == "ensemble"
    assert reasoning["gate_reason"] == "near_tie"


def test_ml_signal_reports_forecast_failure_reason(monkeypatch):
    monkeypatch.setattr(
        "app.ml.serving.inference.get_forecast",
        lambda symbol, horizon, sym_df: (_ for _ in ()).throw(RuntimeError("model assets missing")),
    )
    signal, reasoning = RecommendationEngine()._ml_signal(pd.DataFrame({"date": ["2026-09-18"]}), "UBL")
    assert signal == 0.0
    assert reasoning["status"] == "unavailable"
    assert "model assets missing" in reasoning["reason"]


def test_composite_renormalizes_only_over_available_components(monkeypatch):
    engine = RecommendationEngine()
    monkeypatch.setattr(engine, "_ml_signal", lambda frame, **kwargs: (0.0, {"status": "unavailable"}))
    monkeypatch.setattr(engine, "_technical_signal", lambda frame, **kwargs: (0.4, {"status": "available"}))
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
