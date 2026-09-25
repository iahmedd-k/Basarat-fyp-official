"""API tests for recommendations endpoints."""

import pytest
from httpx import AsyncClient
from unittest.mock import patch


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
                "weights": {"gru": 0.4, "technical": 0.35, "fundamental": 0.25},
                "effective_weights": {"gru": 0.4, "technical": 0.35, "fundamental": 0.25},
                "data_as_of": "2026-09-18",
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
            assert rec["signal"] == "BUY"
            assert rec["target_price"] == 485.0
            assert rec["current_price"] == 450.0
            assert rec["sector"] == "Technology"
            assert rec["composite_score"] == 0.45
            assert rec["risk_reward_ratio"] == 1.75
            assert "summary" in rec
            assert rec["horizon"] == "5 trading days"
            assert rec["currency"] == "PKR"
            assert rec["data_as_of"] == "2026-09-18"
            assert rec["confidence_type"] == "heuristic_signal_strength"
            assert rec["source_weights"]["ml"] == 0.4
            assert rec["signals"]["ml"] == 0.6
            assert rec["signals"]["sentiment"] == -0.2
            assert rec["source_weights"]["sentiment"] == 0.0
            assert rec["decision_reason"].startswith("Composite score")
            assert "generated_at" in data

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
        assert "gru_weight" in data
        assert "technical_weight" in data
        assert "fundamental_weight" in data
        assert "sentiment_weight" in data

    async def test_set_weights_success(self, client: AsyncClient, auth_headers):
        payload = {
            "gru_weight": 0.5,
            "technical_weight": 0.3,
            "fundamental_weight": 0.2,
        }
        resp = await client.post("/api/v1/recommendations/engine-weights", json=payload, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["gru_weight"] == 0.5
        assert data["technical_weight"] == 0.3
        assert data["fundamental_weight"] == 0.2
        persisted = await client.get("/api/v1/recommendations/engine-weights", headers=auth_headers)
        assert persisted.json() == {**payload, "ml_weight": 0.5, "sentiment_weight": 0.0}

    async def test_set_four_source_weights(self, client: AsyncClient, auth_headers):
        payload = {
            "ml_weight": 0.3,
            "technical_weight": 0.25,
            "fundamental_weight": 0.25,
            "sentiment_weight": 0.2,
        }
        response = await client.post("/api/v1/recommendations/engine-weights", json=payload, headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == {**payload, "gru_weight": 0.3}

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
        assert response.json()["ml_weight"] == 0.5
        assert response.json()["gru_weight"] == 0.5


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
                "ml": {"signal": 0.6, "reason": "Positive momentum"},
                "technical": {"signal": 0.4, "reason": "MACD golden cross"},
                "fundamental": {"signal": 0.1, "reason": "Fair valuation"},
            },
            "data_as_of": "2026-09-18",
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
            assert data["signal"] == "BUY"
            assert "signals" in data
            assert data["signals"]["ml"] == 0.6
            assert data["signals"]["technical"] == 0.4
            assert data["signals"]["fundamental"] == 0.1
            assert data["signals"]["sentiment"] == 0.3
            assert data["target_price"] == 485.0
            assert data["current_price"] == 450.0
            assert data["risk_reward_ratio"] == 1.75
            assert data["risk_profile"] == "moderate"
            assert data["data_as_of"] == "2026-09-18"
            assert data["horizon"] == "5 trading days"
            assert data["currency"] == "PKR"
            assert data["confidence_type"] == "heuristic_signal_strength"
            assert data["source_weights"]["ml"] == 0.4
            assert data["decision_reason"].startswith("Composite score")
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
            "target_stop_method": "atr_band",
            "atr_14": 10.0,
            "data_as_of": "2026-09-18",
            "target_stop_reason": "ATR-based volatility levels.",
        }
        with patch("app.services.recommendation_service.RecommendationEngine.get_recommendation", return_value=sample_rec):
            resp = await client.get("/api/v1/recommendations/SYS/target-stop", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["symbol"] == "SYS"
            assert data["current_price"] == 450.0
            assert data["target_price"] == 480.0
            assert data["stop_loss"] == 435.0
            assert data["signal"] == "BUY"
            assert data["data_as_of"] == "2026-09-18"
            assert data["horizon"] == "5 trading days"
            assert data["currency"] == "PKR"
            assert data["target_stop_reason"] == "ATR-based volatility levels."
            assert "generated_at" in data
            assert data["upside_pct"] is not None
            assert data["downside_pct"] is not None
