"""API tests for forecasting endpoints."""

import pytest
import pandas as pd
from datetime import date, datetime, timedelta
from httpx import AsyncClient
from unittest.mock import patch

from app.models.prediction import Prediction


@pytest.mark.api
class TestForecastEndpoint:
    async def test_forecast_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/forecast/SYS")
        assert resp.status_code in (401, 403)

    async def test_forecast_invalid_horizon(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/forecast/SYS?horizon=INVALID", headers=auth_headers)
        assert resp.status_code == 422

    async def test_forecast_model_not_ready(self, client: AsyncClient, auth_headers):
        with patch("app.api.v1.forecast.artifacts") as mock_artifacts:
            mock_artifacts.model_ready = False
            resp = await client.get("/api/v1/forecast/SYS?horizon=1D", headers=auth_headers)
            assert resp.status_code == 503

    async def test_forecast_serves_daily_prediction_without_model_inference(
        self, client: AsyncClient, auth_headers, db_session
    ):
        today = date.today()
        db_session.add(
            Prediction(
                symbol="BATCHTEST",
                horizon="1D",
                predicted_at=datetime.utcnow(),
                predicted_direction="sideways",
                bullish_pct=35.0,
                bearish_pct=30.0,
                sideways_pct=35.0,
                top_class_probability=35.0,
                as_of_date=today,
                target_date=today + timedelta(days=1),
                model_version="daily-ensemble",
                gru_direction="sideways",
                gru_bullish_pct=36.0,
                gru_bearish_pct=29.0,
                gru_sideways_pct=35.0,
                gru_gap_pp=1.0,
            )
        )
        await db_session.flush()

        with patch("app.data.scraper.symbol_universe.get_active_symbols", return_value=[{"symbol": "BATCHTEST"}]), \
             patch("app.api.v1.forecast.artifacts") as mock_artifacts, \
             patch("app.api.v1.forecast.dataset_refresh_ready", return_value=True), \
             patch("app.api.v1.forecast.get_forecast") as mock_get_forecast, \
             patch(
                 "app.ml.serving.inference.get_features_dataframe",
                 return_value=pd.DataFrame(
                     {"symbol": ["BATCHTEST"], "date": [pd.Timestamp(today)]}
                 ),
             ):
            mock_artifacts.model_ready = False
            resp = await client.get(
                "/api/v1/forecast/BATCHTEST?horizon=1D",
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["direction"] == "sideways"
        assert data["as_of_date"] == today.isoformat()
        assert data["models"]["gru"]["direction"] == "sideways"
        mock_get_forecast.assert_not_called()

    async def test_forecast_uses_manual_inference_when_redis_is_unavailable(
        self, client: AsyncClient, auth_headers, db_session
    ):
        as_of = date(2026, 10, 9)
        db_session.add(
            Prediction(
                symbol="REDISDOWN",
                horizon="1D",
                predicted_at=datetime.utcnow(),
                predicted_direction="sideways",
                bullish_pct=35.0,
                bearish_pct=30.0,
                sideways_pct=35.0,
                top_class_probability=35.0,
                as_of_date=as_of,
                target_date=as_of + timedelta(days=1),
                model_version="daily-ensemble",
            )
        )
        await db_session.flush()
        live_result = {
            "symbol": "REDISDOWN",
            "horizon": "1D",
            "direction": "bullish",
            "bullish_pct": 70.0,
            "bearish_pct": 20.0,
            "sideways_pct": 10.0,
            "top_class_probability": 70.0,
            "as_of_date": as_of,
            "predicted_for_date": as_of + timedelta(days=1),
            "model_version": "live",
        }

        with patch("app.data.scraper.symbol_universe.get_active_symbols", return_value=[{"symbol": "REDISDOWN"}]), \
             patch("app.api.v1.forecast.artifacts") as mock_artifacts, \
             patch("app.api.v1.forecast.dataset_refresh_ready", return_value=False), \
             patch("app.api.v1.forecast.cache_get", return_value={"stale": "response"}), \
             patch("app.api.v1.forecast.cache_set") as mock_cache_set, \
             patch("app.api.v1.forecast.get_forecast", return_value=live_result) as mock_get_forecast, \
             patch("app.api.v1.forecast.log_prediction"), \
             patch(
                 "app.ml.serving.inference.get_features_dataframe",
                 return_value=pd.DataFrame(
                     {"symbol": ["REDISDOWN"], "date": [pd.Timestamp(as_of)]}
                 ),
             ):
            mock_artifacts.model_ready = True
            response = await client.get(
                "/api/v1/forecast/REDISDOWN?horizon=1D",
                headers=auth_headers,
            )

        assert response.status_code == 200
        assert response.json()["direction"] == "bullish"
        mock_get_forecast.assert_called_once_with("REDISDOWN", horizon="1D")
        mock_cache_set.assert_not_awaited()

    async def test_forecast_uses_manual_inference_when_saved_prediction_is_stale(
        self, client: AsyncClient, auth_headers, db_session
    ):
        old_as_of = date(2026, 10, 8)
        latest_as_of = date(2026, 10, 9)
        db_session.add(
            Prediction(
                symbol="STALEDB",
                horizon="1D",
                predicted_at=datetime.utcnow(),
                predicted_direction="bearish",
                bullish_pct=20.0,
                bearish_pct=70.0,
                sideways_pct=10.0,
                top_class_probability=70.0,
                as_of_date=old_as_of,
                target_date=old_as_of + timedelta(days=1),
                model_version="daily-ensemble",
            )
        )
        await db_session.flush()
        live_result = {
            "symbol": "STALEDB",
            "horizon": "1D",
            "direction": "bullish",
            "bullish_pct": 70.0,
            "bearish_pct": 20.0,
            "sideways_pct": 10.0,
            "top_class_probability": 70.0,
            "as_of_date": latest_as_of,
            "predicted_for_date": latest_as_of + timedelta(days=1),
            "model_version": "live",
        }

        with patch("app.data.scraper.symbol_universe.get_active_symbols", return_value=[{"symbol": "STALEDB"}]), \
             patch("app.api.v1.forecast.artifacts") as mock_artifacts, \
             patch("app.api.v1.forecast.dataset_refresh_ready", return_value=True), \
             patch("app.api.v1.forecast.cache_get", return_value=None), \
             patch("app.api.v1.forecast.get_forecast", return_value=live_result) as mock_get_forecast, \
             patch("app.api.v1.forecast.log_prediction"), \
             patch(
                 "app.ml.serving.inference.get_features_dataframe",
                 return_value=pd.DataFrame(
                     {"symbol": ["STALEDB"], "date": [pd.Timestamp(latest_as_of)]}
                 ),
             ):
            mock_artifacts.model_ready = True
            response = await client.get(
                "/api/v1/forecast/STALEDB?horizon=1D",
                headers=auth_headers,
            )

        assert response.status_code == 200
        assert response.json()["direction"] == "bullish"
        mock_get_forecast.assert_called_once_with("STALEDB", horizon="1D")

    async def test_forecast_symbol_not_found(self, client: AsyncClient, auth_headers):
        with patch("app.api.v1.forecast.artifacts") as mock_artifacts, \
             patch("app.api.v1.forecast.get_forecast") as mock_get_forecast:
            mock_artifacts.model_ready = True
            from app.ml.serving.inference import SymbolNotFoundError
            mock_get_forecast.side_effect = SymbolNotFoundError("Symbol 'NONEXISTENT' not found")

            resp = await client.get("/api/v1/forecast/NONEXISTENT", headers=auth_headers)
            assert resp.status_code == 404
            data = resp.json()
            assert "error" in data or "message" in data or "detail" in data

    async def test_forecast_success_mocked(self, client: AsyncClient, auth_headers):
        sample_result = {
            "symbol": "UBL",
            "horizon": "1W",
            "direction": "bullish",
            "confidence": 0.72,
            "top_class_probability": 72.0,
            "bullish_pct": 72.0,
            "bearish_pct": 18.0,
            "sideways_pct": 10.0,
            "as_of_date": "2026-09-18",
            "predicted_for_date": "2026-09-25",
            "current_price": 154.2,
            "volatility_14d": 0.012,
            "rsi": 38.5,
            "macd_hist": 0.78,
            "model_version": "v1.0",
            "gate_reason": "Confidence threshold met",
            "model_details": {
                "gru": {
                    "direction": "bullish",
                    "bullish_pct": 75.0,
                    "bearish_pct": 15.0,
                    "sideways_pct": 10.0,
                    "top_class_probability": 75.0,
                    "gap_pp": 60.0,
                },
                "xgb": {
                    "direction": "bullish",
                    "bullish_pct": 69.0,
                    "bearish_pct": 21.0,
                    "sideways_pct": 10.0,
                    "top_class_probability": 69.0,
                    "gap_pp": 48.0,
                },
            },
            "market_context": {
                "stock_return_5d": -0.012,
                "stock_return_20d": -0.05,
                "market_return_5d": -0.015,
                "market_return_20d": -0.038,
            }
        }

        with patch("app.api.v1.forecast.artifacts") as mock_artifacts, \
             patch("app.api.v1.forecast.get_forecast", return_value=sample_result) as mock_get_forecast, \
             patch("app.api.v1.forecast.log_prediction"):
            mock_artifacts.model_ready = True

            resp = await client.get("/api/v1/forecast/UBL", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()

            assert data["symbol"] == "UBL"
            assert data["horizon"] == "1W"
            assert data["direction"] == "bullish"
            assert data["signal_rating"] == "Strong Buy"
            assert "probabilities" in data
            assert data["probabilities"]["bullish"] == 72.0
            assert "models" in data
            assert "gru" in data["models"]
            assert "xgb" in data["models"]
            assert data["model_version"] == "v1.0"
            assert data["gate_reason"] == "Confidence threshold met"
            mock_get_forecast.assert_called_once_with("UBL", horizon="1W")

    async def test_neutral_forecast_has_no_directional_target_or_stop(self, client: AsyncClient, auth_headers):
        neutral_result = {
            "symbol": "SYS",
            "horizon": "1D",
            "direction": "sideways",
            "confidence": 0.5,
            "top_class_probability": 50.0,
            "bullish_pct": 33.0,
            "bearish_pct": 33.0,
            "sideways_pct": 34.0,
            "as_of_date": "2026-09-18",
            "predicted_for_date": "2026-09-19",
            "model_version": "ensemble",
            "gate_reason": "neutral_regime",
        }

        with patch("app.api.v1.forecast.artifacts") as mock_artifacts, \
             patch("app.api.v1.forecast.get_forecast", return_value=neutral_result), \
             patch("app.api.v1.forecast.log_prediction"), \
             patch("app.ml.serving.inference.FEATURES_PATH") as features_path, \
             patch("app.services.stock_service.StockService.get_quote") as get_quote:
            mock_artifacts.model_ready = True
            features_path.exists.return_value = False

            resp = await client.get("/api/v1/forecast/SYS?horizon=1D", headers=auth_headers)

            assert resp.status_code == 200
            payload = resp.json()
            assert payload["target_price"] is None
            assert payload["stop_loss"] is None
            assert payload["signal_rating"] == "Neutral / Hold"
            get_quote.assert_not_called()


@pytest.mark.api
class TestForecastHistoryEndpoint:
    async def test_history_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/forecast/SYS/history")
        assert resp.status_code in (401, 403)

    async def test_history_not_found(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/forecast/UNKNOWN_SYM/history", headers=auth_headers)
        assert resp.status_code == 404

    async def test_history_limit_validation(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/forecast/SYS/history?limit=150", headers=auth_headers)
        assert resp.status_code == 422
