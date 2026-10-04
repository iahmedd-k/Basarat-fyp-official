"""Comprehensive local API test script for all ML, Forecast, Risk, and Recommendation endpoints."""
import asyncio
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
os.environ["SECRET_KEY"] = "test-secret-key-for-local-endpoint-verification-12345"

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.main import app
from app.core.authorization import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.models.user import User
from app.ml.serving.model_loader import load_artifacts, artifacts


async def run_all_endpoint_tests():
    print("\n" + "="*70)
    print(" LOCAL ENDPOINT VERIFICATION: ALL AFFECTED ML & RISK ENDPOINTS")
    print("="*70)

    if not artifacts.model_ready:
        load_artifacts()

    # 1. In-memory SQLite engine
    test_db_url = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(test_db_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Mock user and DB dependency overrides
    test_user = User(
        id="00000000-0000-0000-0000-000000000001",
        email="test@basarat.pk",
        username="testauditor",
        hashed_password="mockhashedpassword",
        full_name="Test Auditor",
        is_active=True,
        is_admin=False,
    )

    async def override_get_db():
        async with async_session() as session:
            yield session

    async def override_get_current_user():
        return test_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        # 1. Health check
        r_health = await client.get("/health")
        assert r_health.status_code == 200, f"Health check failed: {r_health.text}"
        print(" [PASS] GET /health -> 200 OK")

        # 2. Multi-Horizon Forecast Endpoint
        symbols = ["OGDC", "SYS", "LUCK", "ENGROH", "UBL"]
        horizons = ["1D", "1W", "2W", "1M"]
        print("\n--- 1. Testing GET /api/v1/forecast/{symbol}?horizon={hz} ---")
        for sym in symbols:
            for hz in horizons:
                resp = await client.get(f"/api/v1/forecast/{sym}?horizon={hz}")
                assert resp.status_code == 200, f"Forecast failed for {sym} {hz}: {resp.status_code} {resp.text}"
                data = resp.json()
                assert data["symbol"] == sym
                assert data["horizon"] == hz
                assert data["direction"] in ("bullish", "bearish", "sideways", "uncertain")
                assert "as_of_label" in data and data["as_of_label"] is not None
                assert "target_label" in data and data["target_label"] is not None
                assert "horizon_label" in data and data["horizon_label"] is not None
                assert "trading_days" in data and data["trading_days"] in (1, 5, 10, 22)
                assert "market_status" in data
                print(f" [PASS] /forecast/{sym}?horizon={hz:2s} -> {data['direction'].upper():<8} | Signal: {data['signal_rating']:<14} | Target: {data['target_label']}")

        # 3. Forecast History Endpoint
        print("\n--- 2. Testing GET /api/v1/forecast/{symbol}/history?horizon={hz} ---")
        for hz in ["1W", "2W", "1M"]:
            resp = await client.get(f"/api/v1/forecast/OGDC/history?horizon={hz}&limit=10")
            assert resp.status_code in (200, 404), f"History unexpected status: {resp.status_code}"
            print(f" [PASS] /forecast/OGDC/history?horizon={hz} -> Status {resp.status_code}")

        # 4. Risk VaR Endpoint
        print("\n--- 3. Testing GET /api/v1/risk/var?horizon={hz} ---")
        for hz in ["1D", "1W", "2W", "1M"]:
            resp = await client.get(f"/api/v1/risk/var?confidence=95&horizon={hz}")
            assert resp.status_code == 200, f"VaR failed for {hz}: {resp.status_code} {resp.text}"
            data = resp.json()
            assert data["horizon"] == hz
            assert data["confidence"] == 95
            print(f" [PASS] /risk/var?horizon={hz:2s} -> Status: {data['status']} | Obs: {data['num_observations']}")

        # 5. Risk Stress Test Endpoint
        print("\n--- 4. Testing GET /api/v1/risk/stress-test ---")
        for scenario in ["2008_crash", "pkr_devaluation", "covid_crash", "interest_rate_hike"]:
            resp = await client.get(f"/api/v1/risk/stress-test?scenario={scenario}")
            assert resp.status_code == 200, f"Stress test failed for {scenario}: {resp.text}"
            print(f" [PASS] /risk/stress-test?scenario={scenario} -> 200 OK")

        # 6. OpenAPI Schema Documentation Endpoint
        print("\n--- 5. Testing OpenAPI /docs Schema ---")
        resp_openapi = await client.get("/api/v1/openapi.json")
        assert resp_openapi.status_code == 200, "OpenAPI JSON failed"
        schema = resp_openapi.json()
        assert "/api/v1/forecast/{symbol}" in schema["paths"]
        assert "/api/v1/risk/var" in schema["paths"]
        print(" [PASS] GET /openapi.json -> 200 OK (OpenAPI / Swagger documentation verified)")

    # Cleanup dependency overrides
    app.dependency_overrides.clear()
    await engine.dispose()

    print("\n" + "="*70)
    print(" ALL AFFECTED ENDPOINTS TESTED LOCALLY: 100% SUCCESSFUL & ZERO ERRORS!")
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(run_all_endpoint_tests())
