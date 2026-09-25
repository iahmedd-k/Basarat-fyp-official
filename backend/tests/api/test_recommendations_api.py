"""API tests for recommendations endpoints."""

import pytest
from datetime import date
from httpx import AsyncClient
from unittest.mock import patch

from app.api.v1.recommendations import _apply_freshness_guard, _market_data_freshness, _summarize


def test_summary_does_not_mistake_unavailable_ml_for_decision_reason():
    rec = {
        "signal": "hold",
        "data_as_of": "2026-09-18",
        "signals": {"ml": 0.0, "technical": -0.0224, "fundamental": 0.0, "sentiment": 0.0},
        "weights": {"gru": 0.3, "technical": 0.25, "fundamental": 0.25, "sentiment": 0.2},
        "effective_weights": {"technical": 1.0},
        "reasoning": {
            "ml": {"status": "unavailable", "reason": "production model unavailable"},
            "technical": {"status": "available"},
            "fundamental": {"status": "unavailable"},
            "sentiment": {"status": "unavailable"},
        },
    }
    summary = _summarize(rec)
    assert "Technicals are the only available input (-0.022)" in summary
    assert "ML forecast, fundamentals, sentiment unavailable" in summary
    assert "production model unavailable" not in summary


def test_market_data_freshness_uses_weekdays_and_marks_old_data():
    fresh = _market_data_freshness("2026-09-24", today=date(2026, 9, 25))
    assert fresh["data_freshness"] == "fresh"
    stale = _market_data_freshness("2026-09-18", today=date(2026, 9, 25))
    assert stale == {
        "data_freshness": "stale",
        "data_age_calendar_days": 7,
        "data_age_trading_days": 5,
    }


def test_stale_data_suppresses_actionable_signal_and_price_levels():
    rec = _apply_freshness_guard({
        "signal": "buy", "confidence": 1.0, "composite_score": 0.64,
        "data_as_of": "2026-09-18", "target_price": 7714.36, "stop_loss": 7194.08,
        "expected_range": None, "upside_pct": 4.22, "downside_pct": -2.81,
        "risk_reward_ratio": 1.5,
    }, today=date(2026, 9, 25))
    assert rec["signal"] == "hold"
    assert rec["signal_suppressed"] is True
    assert rec["confidence"] == 0.0
    assert rec["target_price"] is None
    assert rec["stop_loss"] is None
    assert "5 trading days old" in rec["suppression_reason"]


@pytest.mark.api
class TestRecommendationsListEndpoint:
    async def test_recommendations_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/recommendations")
        assert resp.status_code in (401, 403)

    async def test_recommendations_invalid_risk_profile(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/recommendations?risk_profile=extreme", headers=auth_headers)
        assert resp.status_code == 422

    async def test_recommendations_success(self, client: AsyncClient, auth_headers):
        sample_recs = [
            {
                "symbol": "SYS",
                "signal": "buy",
                "confidence": 0.85,
                "composite_score": 0.45,
                "name": "SYS",
                "sector": "Technology",
                "current_price": 450.0,
                "target_price": 485.0,
                "stop_loss": 430.0,
                "upside_pct": 7.78,
                "downside_pct": -4.44,
                "risk_reward_ratio": 1.75,
                "reasoning": {
                    "ml": {"reason": "Bullish trend forecast"},
                    "technical": {"reason": "RSI oversold rebound"},
                },
                "signals": {"ml": 0.6, "technical": 0.4, "fundamental": 0.1, "sentiment": -0.2},
                "weights": {"gru": 0.3, "technical": 0.25, "fundamental": 0.25, "sentiment": 0.2},
                "effective_weights": {"gru": 0.3, "technical": 0.25, "fundamental": 0.25, "sentiment": 0.2},
                "reasoning": {
                    "ml": {"status": "available"}, "technical": {"status": "available"},
                    "fundamental": {"status": "available"}, "sentiment": {"status": "available"},
                },
                "data_as_of": "2026-09-24",
                "decision_reason": "Composite score 0.450 crossed the BUY threshold (0.15).",
                "target_stop_method": "atr_band",
                "target_stop_reason": "ATR-based volatility levels.",
            }
        ]

        with patch("app.services.recommendation_service.get_cached_recommendations", return_value=sample_recs):
            resp = await client.get("/api/v1/recommendations?risk_profile=moderate&limit=10", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert "recommendations" in data
            assert data["count"] == 1
            assert data["risk_profile"] == "moderate"
            rec = data["recommendations"][0]
            assert rec["symbol"] == "SYS"
            assert rec["decision"]["signal"] == "BUY"
            assert rec["risk"]["target_price"] == 485.0
            assert rec["market_data"]["current_price"] == 450.0
            assert rec["sector"] == "Technology"
            assert rec["decision"]["composite_score"] == 0.45
            assert rec["risk"]["risk_reward_ratio"] == 1.75
            assert "summary" in rec
            assert rec["decision"]["horizon"] == "5 trading days"
            assert rec["market_data"]["currency"] == "PKR"
            assert rec["market_data"]["as_of"] == "2026-09-24"
            assert rec["market_data"]["freshness"] == "fresh"
            assert rec["components"]["ml"]["score"] == 0.6
            assert rec["components"]["sentiment"]["score"] == -0.2
            assert rec["components"]["sentiment"]["configured_weight"] == 0.2
            assert rec["decision"]["reason"].startswith("Composite score")
            assert "generated_at" in data

    async def test_stale_cached_buy_is_returned_as_suppressed_hold(self, client: AsyncClient, auth_headers):
        stale_rec = {
            "symbol": "SYS", "signal": "buy", "confidence": 1.0, "composite_score": 0.64,
            "signals": {"technical": 0.64}, "weights": {"technical": 1.0},
            "effective_weights": {"technical": 1.0},
            "reasoning": {"technical": {"status": "available"}},
            "data_as_of": "2026-09-18", "target_price": 485.0, "stop_loss": 430.0,
            "target_stop_method": "atr_band",
        }
        with patch("app.services.recommendation_service.get_cached_recommendations", return_value=[stale_rec]):
            response = await client.get("/api/v1/recommendations", headers=auth_headers)
        assert response.status_code == 200
        item = response.json()["recommendations"][0]
        assert item["decision"]["signal"] == "HOLD"
        assert item["decision"]["confidence"] == 0
        assert item["decision"]["suppressed"] is True
        assert item["risk"]["target_price"] is None
        assert "5 trading days old" in item["decision"]["suppression_reason"]

    async def test_list_uses_persisted_custom_weights(self, client: AsyncClient, auth_headers):
        weights = {"gru_weight": 0.5, "technical_weight": 0.3, "fundamental_weight": 0.2}
        await client.post("/api/v1/recommendations/engine-weights", json=weights, headers=auth_headers)
        with patch("app.services.recommendation_service.RecommendationEngine.get_all_recommendations", return_value=[] ) as get_all:
            response = await client.get("/api/v1/recommendations", headers=auth_headers)
        assert response.status_code == 200
        assert get_all.call_args.kwargs["weights"] == {"gru": 0.5, "technical": 0.3, "fundamental": 0.2, "sentiment": 0.0}


@pytest.mark.api
class TestEngineWeightsEndpoint:
    async def test_weights_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/recommendations/engine-weights")
        assert resp.status_code in (401, 403)

    async def test_get_weights_success(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/recommendations/engine-weights", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert set(data["weights"]) == {"ml", "technical", "fundamental", "sentiment"}

    async def test_set_weights_success(self, client: AsyncClient, auth_headers):
        payload = {
            "gru_weight": 0.5,
            "technical_weight": 0.3,
            "fundamental_weight": 0.2,
        }
        resp = await client.post("/api/v1/recommendations/engine-weights", json=payload, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["weights"] == {"ml": 0.5, "technical": 0.3, "fundamental": 0.2, "sentiment": 0.0}
        persisted = await client.get("/api/v1/recommendations/engine-weights", headers=auth_headers)
        assert persisted.json() == data

    async def test_set_four_source_weights(self, client: AsyncClient, auth_headers):
        payload = {
            "ml_weight": 0.3,
            "technical_weight": 0.25,
            "fundamental_weight": 0.25,
            "sentiment_weight": 0.2,
        }
        response = await client.post("/api/v1/recommendations/engine-weights", json=payload, headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == {"weights": {"ml": 0.3, "technical": 0.25, "fundamental": 0.25, "sentiment": 0.2}}

    async def test_set_weights_rejects_values_that_do_not_sum_to_one(self, client: AsyncClient, auth_headers):
        response = await client.post(
            "/api/v1/recommendations/engine-weights",
            json={"gru_weight": 0.5, "technical_weight": 0.3, "fundamental_weight": 0.3},
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_set_weights_accepts_canonical_ml_weight(self, client: AsyncClient, auth_headers):
        response = await client.post(
            "/api/v1/recommendations/engine-weights",
            json={"ml_weight": 0.5, "technical_weight": 0.3, "fundamental_weight": 0.2},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["weights"]["ml"] == 0.5


@pytest.mark.api
class TestRecommendationDetailEndpoint:
    async def test_detail_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/recommendations/SYS")
        assert resp.status_code in (401, 403)

    async def test_detail_success(self, client: AsyncClient, auth_headers):
        sample_rec = {
            "symbol": "SYS",
            "name": "Systems Limited",
            "sector": "Technology",
            "signal": "buy",
            "confidence": 0.82,
            "composite_score": 0.38,
            "signals": {"ml": 0.6, "technical": 0.4, "fundamental": 0.1, "sentiment": 0.3},
            "weights": {"gru": 0.4, "technical": 0.35, "fundamental": 0.25},
            "effective_weights": {"gru": 0.4, "technical": 0.35, "fundamental": 0.25},
            "current_price": 450.0,
            "target_price": 485.0,
            "stop_loss": 430.0,
            "expected_range": None,
            "upside_pct": 7.78,
            "downside_pct": -4.44,
            "risk_reward_ratio": 1.75,
            "target_stop_method": "atr_band",
            "atr_14": 12.5,
            "reasoning": {
                "ml": {"status": "available"},
                "technical": {"status": "available"},
                "fundamental": {"status": "available"},
                "sentiment": {"status": "available"},
            },
            "data_as_of": "2026-09-24",
            "decision_reason": "Composite score 0.380 crossed the BUY threshold (0.15).",
            "target_stop_reason": "ATR-based volatility levels.",
        }

        with patch("app.services.recommendation_service.RecommendationEngine.get_recommendation", return_value=sample_rec):
            resp = await client.get("/api/v1/recommendations/SYS", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["symbol"] == "SYS"
            assert data["name"] == "Systems Limited"
            assert data["sector"] == "Technology"
            assert data["decision"]["signal"] == "BUY"
            assert data["components"]["ml"]["score"] == 0.6
            assert data["components"]["technical"]["score"] == 0.4
            assert data["components"]["fundamental"]["score"] == 0.1
            assert data["components"]["sentiment"]["score"] == 0.3
            assert data["risk"]["target_price"] == 485.0
            assert data["market_data"]["current_price"] == 450.0
            assert data["risk"]["risk_reward_ratio"] == 1.75
            assert data["risk_profile"] == "moderate"
            assert data["market_data"]["as_of"] == "2026-09-24"
            assert data["market_data"]["freshness"] == "fresh"
            assert data["decision"]["horizon"] == "5 trading days"
            assert data["market_data"]["currency"] == "PKR"
            assert data["decision"]["reason"].startswith("Composite score")
            assert "reasoning" not in data
            assert "generated_at" in data

    async def test_detail_uses_persisted_custom_weights(self, client: AsyncClient, auth_headers):
        await client.post(
            "/api/v1/recommendations/engine-weights",
            json={"gru_weight": 0.5, "technical_weight": 0.3, "fundamental_weight": 0.2},
            headers=auth_headers,
        )
        sample = {
            "signal": "hold", "confidence": 0.0, "composite_score": 0.0,
            "signals": {"ml": 0.0, "technical": 0.0, "fundamental": 0.0},
        }
        with patch("app.services.recommendation_service.RecommendationEngine.get_recommendation", return_value=sample) as get_rec:
            response = await client.get("/api/v1/recommendations/SYS", headers=auth_headers)
        assert response.status_code == 200
        assert get_rec.call_args.kwargs["weights"] == {"gru": 0.5, "technical": 0.3, "fundamental": 0.2, "sentiment": 0.0}


@pytest.mark.api
class TestTargetStopEndpoint:
    async def test_target_stop_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/recommendations/SYS/target-stop")
        assert resp.status_code in (401, 403)

    async def test_target_stop_success(self, client: AsyncClient, auth_headers):
        sample_ts = {
            "symbol": "SYS",
            "current_price": 450.0,
            "target_price": 480.0,
            "stop_loss": 435.0,
            "method": "atr_band",
            "atr_14": 10.0,
        }

        sample_rec = {
            "signal": "buy",
            "status": "available",
            "current_price": 450.0,
            "target_price": 480.0,
            "stop_loss": 435.0,
            "expected_range": None,
            "upside_pct": 6.7,
            "downside_pct": -3.3,
            "target_stop_method": "atr_band",
            "atr_14": 10.0,
            "data_as_of": "2026-09-24",
            "target_stop_reason": "ATR-based volatility levels.",
        }
        with patch("app.services.recommendation_service.RecommendationEngine.get_recommendation", return_value=sample_rec):
            resp = await client.get("/api/v1/recommendations/SYS/target-stop", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["symbol"] == "SYS"
            assert data["market_data"]["current_price"] == 450.0
            assert data["risk"]["target_price"] == 480.0
            assert data["risk"]["stop_loss"] == 435.0
            assert data["decision"]["signal"] == "BUY"
            assert data["market_data"]["as_of"] == "2026-09-24"
            assert data["decision"]["horizon"] == "5 trading days"
            assert data["market_data"]["currency"] == "PKR"
            assert data["risk"]["explanation"] == "ATR-based volatility levels."
            assert "generated_at" in data
            assert data["risk"]["upside_pct"] is not None
            assert data["risk"]["downside_pct"] is not None
