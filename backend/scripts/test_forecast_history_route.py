"""Verification script for Forecast History API route and Database state."""

import asyncio
import sys
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

# Ensure backend root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from starlette.testclient import TestClient
from sqlalchemy import text, select

from app.main import app
from app.db.base import engine, async_session_factory
from app.core.security import create_access_token
from app.models.prediction import Prediction
from app.models.user import User


async def run_forecast_history_test():
    print("\n" + "=" * 75)
    print(" [*] TESTING FORECAST HISTORY ROUTE & DATABASE INTEGRATION")
    print("=" * 75)

    # 1. Check database connectivity and table schema
    print("\n[1] Checking Database connectivity & 'predictions' table...")
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'predictions'"))
        table_exists = res.scalar() > 0
        assert table_exists, "Table 'predictions' does not exist in database!"
        print("  [PASS] 'predictions' table exists in database.")

    # 2. Setup test data in DB
    print("\n[2] Seeding test predictions into database...")
    test_symbol = f"TESTSYM_{uuid.uuid4().hex[:4].upper()}"
    today = date.today()
    past_date_1 = today - timedelta(days=5)
    past_date_2 = today - timedelta(days=3)
    future_date = today + timedelta(days=2)

    async with async_session_factory() as session:
        # 2.1 Evaluated prediction (was correct)
        pred_1 = Prediction(
            symbol=test_symbol,
            horizon="1D",
            predicted_at=datetime.utcnow() - timedelta(days=5),
            predicted_direction="bullish",
            bullish_pct=68.5,
            bearish_pct=21.5,
            sideways_pct=10.0,
            top_class_probability=68.5,
            as_of_date=past_date_1,
            target_date=past_date_1 + timedelta(days=1),
            model_version="gru_v1",
            actual_direction="bullish",
            was_correct=True,
            gru_direction="bullish",
            gru_bullish_pct=70.0,
            gru_bearish_pct=20.0,
            gru_sideways_pct=10.0,
            gate_reason="High Confidence",
        )

        # 2.2 Evaluated prediction (was incorrect)
        pred_2 = Prediction(
            symbol=test_symbol,
            horizon="1D",
            predicted_at=datetime.utcnow() - timedelta(days=3),
            predicted_direction="bullish",
            bullish_pct=62.0,
            bearish_pct=28.0,
            sideways_pct=10.0,
            top_class_probability=62.0,
            as_of_date=past_date_2,
            target_date=past_date_2 + timedelta(days=1),
            model_version="gru_v1",
            actual_direction="bearish",
            was_correct=False,
            gru_direction="bullish",
            gru_bullish_pct=65.0,
            gru_bearish_pct=25.0,
            gru_sideways_pct=10.0,
            gate_reason="Standard Confidence",
        )

        # 2.3 Pending target date prediction (future)
        pred_3 = Prediction(
            symbol=test_symbol,
            horizon="1D",
            predicted_at=datetime.utcnow(),
            predicted_direction="bearish",
            bullish_pct=18.0,
            bearish_pct=72.0,
            sideways_pct=10.0,
            top_class_probability=72.0,
            as_of_date=today,
            target_date=future_date,
            model_version="gru_v1",
            actual_direction=None,
            was_correct=None,
            gru_direction="bearish",
            gru_bullish_pct=20.0,
            gru_bearish_pct=70.0,
            gru_sideways_pct=10.0,
            gate_reason="Bearish Trend Confirmation",
        )

        session.add_all([pred_1, pred_2, pred_3])
        await session.commit()
        print(f"  [PASS] Seeded 3 test predictions for symbol: {test_symbol}")

    # 3. Test API endpoints with httpx.AsyncClient (ASGITransport)
    print("\n[3] Testing API endpoints via AsyncClient...")
    token = create_access_token({"sub": "test-history-user-uuid", "type": "access"})
    auth_headers = {"Authorization": f"Bearer {token}"}

    # Ensure user exists in database for get_current_user
    async with async_session_factory() as session:
        user_res = await session.execute(select(User).where(User.id == "test-history-user-uuid"))
        if not user_res.scalar_one_or_none():
            test_user = User(
                id="test-history-user-uuid",
                email="test_history_user@basarat.pk",
                username="history_tester",
                hashed_password="hashedpassword123",
                full_name="History Tester",
                is_active=True,
            )
            session.add(test_user)
            await session.commit()

    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 3.1 Test 401 Unauthorized
        r_unauth = await client.get(f"/api/v1/forecast/{test_symbol}/history")
        assert r_unauth.status_code in (401, 403), f"Expected 401/403, got {r_unauth.status_code}"
        print("  [PASS] 401 Unauthorized enforced when Authorization header is missing.")

        # 3.2 Test 422 Invalid Horizon
        r_bad_hz = await client.get(f"/api/v1/forecast/{test_symbol}/history?horizon=99DAYS", headers=auth_headers)
        assert r_bad_hz.status_code == 422, f"Expected 422, got {r_bad_hz.status_code}"
        print("  [PASS] 422 Validation Error properly returned on invalid horizon parameter.")

        # 3.3 Test 422 Invalid Limit (out of range)
        r_bad_limit = await client.get(f"/api/v1/forecast/{test_symbol}/history?limit=500", headers=auth_headers)
        assert r_bad_limit.status_code == 422, f"Expected 422, got {r_bad_limit.status_code}"
        print("  [PASS] 422 Validation Error properly returned when limit exceeds maximum (100).")

        # 3.4 Test 404 Not Found for non-existent symbol
        r_404 = await client.get("/api/v1/forecast/NONEXISTENT999/history", headers=auth_headers)
        assert r_404.status_code == 404, f"Expected 404, got {r_404.status_code}"
        print("  [PASS] 404 Not Found properly returned for symbol with no prediction history.")

        # 3.5 Test 200 OK with complete history payload
        r_200 = await client.get(f"/api/v1/forecast/{test_symbol}/history?horizon=1D&limit=10", headers=auth_headers)
        assert r_200.status_code == 200, f"Expected 200, got {r_200.status_code}: {r_200.text}"
        data = r_200.json()

        assert data["symbol"] == test_symbol
        assert data["horizon"] == "1D"
        assert data["count"] == 3
        assert data["scored_count"] == 2
        assert data["pending_count"] == 1
        assert data["accuracy"] == 0.5  # 1 correct out of 2 scored = 50%
        assert "50.0%" in data["accuracy_summary"]
        assert len(data["history"]) == 3

        # Validate item schemas
        first_item = data["history"][0]
        assert "predicted_direction" in first_item
        assert "probabilities" in first_item
        assert "confidence" in first_item
        assert "as_of_date" in first_item
        assert "target_date" in first_item
        assert "actual" in first_item
        assert first_item["actual"]["status"] in ("evaluated", "pending_target_date", "pending_evaluation")

        print(f"  [PASS] 200 OK: Retrieved {data['count']} predictions for {test_symbol}.")
        print(f"    - Accuracy: {data['accuracy_summary']}")
        print(f"    - Latest Item Status: {first_item['actual']['status']} (Direction: {first_item['predicted_direction']})")

    # 4. Clean up seeded test records
    print("\n[4] Cleaning up test records from database...")
    async with async_session_factory() as session:
        await session.execute(text(f"DELETE FROM predictions WHERE symbol = '{test_symbol}'"))
        await session.execute(text("DELETE FROM users WHERE id = 'test-history-user-uuid'"))
        await session.commit()
        print(f"  [PASS] Cleaned up test symbol records for {test_symbol} and test user.")

    print("\n" + "=" * 75)
    print(" [ALL PASSED] ALL FORECAST HISTORY ROUTE & DATABASE TESTS PASSED 100%!")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    asyncio.run(run_forecast_history_test())
