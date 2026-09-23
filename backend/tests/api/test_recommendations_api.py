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


@pytest.mark.api
class TestRecommendationDetailEndpoint:
    async def test_detail_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/recommendations/SYS")
        assert resp.status_code in (401, 403)

    async def test_detail_success(self, client: AsyncClient, auth_headers):
        sample_rec = {
            "symbol": "SYS",
            "signal": "buy",
            "confidence": 0.82,
            "composite_score": 0.38,
            "signals": {"ml": 0.6, "technical": 0.4, "fundamental": 0.1},
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
        }

        with patch("app.services.recommendation_service.RecommendationEngine.get_recommendation", return_value=sample_rec):
            resp = await client.get("/api/v1/recommendations/SYS", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["symbol"] == "SYS"
            assert data["signal"] == "BUY"
            assert "signals" in data
            assert data["signals"]["ml"] == 0.6
            assert data["signals"]["technical"] == 0.4
            assert data["signals"]["fundamental"] == 0.1
            assert data["target_price"] == 485.0
            assert data["current_price"] == 450.0
            assert data["risk_reward_ratio"] == 1.75
            assert data["risk_profile"] == "moderate"


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

        with patch("app.services.recommendation_service.RecommendationEngine.compute_target_stop", return_value=sample_ts):
            resp = await client.get("/api/v1/recommendations/SYS/target-stop", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["symbol"] == "SYS"
            assert data["current_price"] == 450.0
            assert data["target_price"] == 480.0
            assert data["stop_loss"] == 435.0
            assert data["upside_pct"] is not None
            assert data["downside_pct"] is not None
