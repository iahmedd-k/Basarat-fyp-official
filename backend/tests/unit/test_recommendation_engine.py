import json
import pandas as pd
import pytest
from datetime import date, datetime, timedelta

from app.services import recommendation_service
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


def test_cached_recommendations_reject_snapshot_older_than_latest_features(
    monkeypatch, tmp_path
):
    cache_file = tmp_path / "recommendations.json"
    yesterday = date.today() - timedelta(days=1)
    snapshot = {
        "timestamp": datetime.utcnow().isoformat(),
        "cache_version": 5,
        "count": 1,
        "recommendations": [
            {
                "symbol": "TEST",
                "data_as_of": yesterday.isoformat(),
                "composite_score": 0.0,
                "signals": {},
                "weights": {},
            }
        ],
    }
    cache_file.write_text(json.dumps(snapshot), encoding="utf-8")
    monkeypatch.setattr(recommendation_service, "RECOMMENDATIONS_CACHE", cache_file)
    monkeypatch.setattr("app.core.redis.cache_get_sync", lambda _key: None)
    monkeypatch.setattr(
        "app.data.scraper.symbol_universe.get_active_symbols",
        lambda: [{"symbol": "TEST"}],
    )
    monkeypatch.setattr(
        recommendation_service.pd,
        "read_parquet",
        lambda *_args, **_kwargs: pd.DataFrame(
            {"symbol": ["TEST"], "date": [date.today()]}
        ),
    )

    assert recommendation_service.get_cached_recommendations() is None


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


def test_minimum_coverage_gate_holds_direction_on_single_component(monkeypatch):
    engine = RecommendationEngine()
    monkeypatch.setattr(engine, "_ml_signal", lambda frame, **kwargs: (0.0, {"status": "unavailable"}))
    monkeypatch.setattr(engine, "_technical_signal", lambda frame, **kwargs: (0.8, {"status": "available"}))
    monkeypatch.setattr(engine, "_fundamental_signal", lambda symbol, overview_data=None: (0.0, {"status": "unavailable"}))
    monkeypatch.setattr(engine, "_sentiment_signal", lambda symbol, sentiment_data=None: (0.0, {"status": "unavailable"}))

    result = engine.compute_composite("TEST", pd.DataFrame({"close": [100.0]}))
    assert result["verdict"] == "hold"
    assert result["confidence"] == 0.0
    assert "Insufficient signal coverage" in result["decision_reason"]
    assert result["status"] == "partial"


def test_consensus_aware_confidence_penalizes_high_dispersion(monkeypatch):
    engine = RecommendationEngine()
    # High disagreement: ML +0.8, Technicals -0.8
    monkeypatch.setattr(engine, "_ml_signal", lambda frame, **kwargs: (0.8, {"status": "available"}))
    monkeypatch.setattr(engine, "_technical_signal", lambda frame, **kwargs: (-0.8, {"status": "available"}))
    monkeypatch.setattr(engine, "_fundamental_signal", lambda symbol, overview_data=None: (0.0, {"status": "unavailable"}))
    monkeypatch.setattr(engine, "_sentiment_signal", lambda symbol, sentiment_data=None: (0.0, {"status": "unavailable"}))

    res_disagree = engine.compute_composite("TEST", pd.DataFrame({"close": [100.0]}))

    # High agreement: ML +0.4, Technicals +0.4
    monkeypatch.setattr(engine, "_ml_signal", lambda frame, **kwargs: (0.4, {"status": "available"}))
    monkeypatch.setattr(engine, "_technical_signal", lambda frame, **kwargs: (0.4, {"status": "available"}))

    res_agree = engine.compute_composite("TEST", pd.DataFrame({"close": [100.0]}))

    assert res_agree["verdict"] == "buy"
    assert res_agree["confidence"] > res_disagree["confidence"]


def test_four_sources_unanimous_agreement_gives_highest_confidence(monkeypatch):
    engine = RecommendationEngine()
    monkeypatch.setattr(engine, "_ml_signal", lambda frame, **kwargs: (0.5, {"status": "available"}))
    monkeypatch.setattr(engine, "_technical_signal", lambda frame, **kwargs: (0.5, {"status": "available"}))
    monkeypatch.setattr(engine, "_fundamental_signal", lambda symbol, overview_data=None: (0.5, {"status": "available"}))
    monkeypatch.setattr(engine, "_sentiment_signal", lambda symbol, sentiment_data=None: (0.5, {"status": "available"}))

    res = engine.compute_composite("TEST", pd.DataFrame({"close": [100.0]}))
    assert res["verdict"] == "buy"
    assert res["composite_score"] == 0.5
    assert res["status"] == "available"
    assert res["confidence"] == 1.0  # Perfect consensus & full coverage


def test_sentiment_requires_minimum_article_threshold(monkeypatch):
    engine = RecommendationEngine()
    # 1 article should be marked unavailable
    sig, reason = engine._sentiment_signal("TEST", sentiment_data={"score": 0.8, "article_count": 1, "status": "available"})
    assert sig == 0.0
    assert reason["status"] == "unavailable"
    assert "fewer than 2" in reason["reason"]

    # 3 articles should be accepted
    sig, reason = engine._sentiment_signal("TEST", sentiment_data={"score": 0.8, "article_count": 3, "status": "available"})
    assert sig == 0.8
    assert reason["status"] == "available"


def test_directional_rrr_matches_risk_multipliers():
    engine = RecommendationEngine()
    frame = pd.DataFrame({"close": [100.0], "atr_14": [5.0]})

    # Moderate BUY: target = +3.0*ATR (115), stop = -2.0*ATR (90) -> RRR = 15/10 = 1.5
    res_buy = engine.compute_target_stop("TEST", frame, risk_tolerance="moderate", ml_direction="buy")
    assert res_buy["target_price"] == 115.0
    assert res_buy["stop_loss"] == 90.0
    assert res_buy["risk_reward_ratio"] == 1.5

    # Conservative BUY: target = +2.0*ATR (110), stop = -1.5*ATR (92.5) -> RRR = 10/7.5 = 1.33
    res_cons = engine.compute_target_stop("TEST", frame, risk_tolerance="conservative", ml_direction="buy")
    assert res_cons["risk_reward_ratio"] == 1.33

    # Aggressive BUY: target = +4.0*ATR (120), stop = -2.5*ATR (87.5) -> RRR = 20/12.5 = 1.6
    res_agg = engine.compute_target_stop("TEST", frame, risk_tolerance="aggressive", ml_direction="buy")
    assert res_agg["risk_reward_ratio"] == 1.6
