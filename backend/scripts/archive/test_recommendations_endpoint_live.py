"""Test recommendation API endpoints thoroughly with local test client."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.security import create_access_token
from app.db.base import get_sync_session_factory
from app.models.user import User


async def run_endpoint_checks():
    print("Testing Recommendation Endpoints Live...")

    # Get a test user token
    with get_sync_session_factory()() as s:
        u = s.query(User).filter(User.email == "admin@basarat.pk").first()
        if not u:
            u = s.query(User).first()
        if u:
            token = create_access_token(data={"sub": str(u.id), "email": u.email, "role": getattr(u, "role", "admin")})
        else:
            token = create_access_token(data={"sub": "1", "email": "test@basarat.pk", "role": "admin"})

    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost:8000") as client:
        # 1. GET /api/v1/recommendations
        print("\n1. Testing GET /api/v1/recommendations")
        r1 = await client.get("/api/v1/recommendations", headers=headers)
        print(f"Status: {r1.status_code}")
        assert r1.status_code == 200, f"Expected 200, got {r1.status_code}: {r1.text}"
        d1 = r1.json()
        print(f"Count: {d1.get('count')}, Total: {d1.get('total_count')}, Risk Profile: {d1.get('risk_profile')}")
        if d1.get("recommendations"):
            first = d1["recommendations"][0]
            print(f"Sample Rec: {first['symbol']} -> Signal: {first['decision']['signal']}, Score: {first['decision']['composite_score']}, Conf: {first['decision']['confidence']}")
            print(f"Summary: {first['summary']}")
            assert "decision" in first
            assert "components" in first
            assert "market_data" in first
            assert "risk" in first

        # 2. GET /api/v1/recommendations/engine-weights
        print("\n2. Testing GET /api/v1/recommendations/engine-weights")
        r2 = await client.get("/api/v1/recommendations/engine-weights", headers=headers)
        print(f"Status: {r2.status_code}")
        assert r2.status_code == 200, f"Expected 200, got {r2.status_code}: {r2.text}"
        d2 = r2.json()
        print(f"Engine Weights: {d2.get('weights')}")
        assert set(d2["weights"].keys()) == {"ml", "technical", "fundamental", "sentiment"}

        # 3. POST /api/v1/recommendations/engine-weights
        print("\n3. Testing POST /api/v1/recommendations/engine-weights")
        post_payload = {
            "gru_weight": 0.35,
            "technical_weight": 0.25,
            "fundamental_weight": 0.25,
            "sentiment_weight": 0.15,
        }
        r3 = await client.post("/api/v1/recommendations/engine-weights", json=post_payload, headers=headers)
        print(f"Status: {r3.status_code}")
        assert r3.status_code == 200, f"Expected 200, got {r3.status_code}: {r3.text}"
        d3 = r3.json()
        print(f"Updated Weights: {d3.get('weights')}")
        assert d3["weights"]["ml"] == 0.35

        # 4. GET /api/v1/recommendations/{symbol}
        print("\n4. Testing GET /api/v1/recommendations/OGDC")
        r4 = await client.get("/api/v1/recommendations/OGDC", headers=headers)
        print(f"Status: {r4.status_code}")
        assert r4.status_code == 200, f"Expected 200, got {r4.status_code}: {r4.text}"
        d4 = r4.json()
        print(f"OGDC Detail: Signal = {d4['decision']['signal']}, Score = {d4['decision']['composite_score']}, Target = {d4['risk']['target_price']}, Stop = {d4['risk']['stop_loss']}")

        # 5. GET /api/v1/recommendations/{symbol}/target-stop
        print("\n5. Testing GET /api/v1/recommendations/OGDC/target-stop")
        r5 = await client.get("/api/v1/recommendations/OGDC/target-stop", headers=headers)
        print(f"Status: {r5.status_code}")
        assert r5.status_code == 200, f"Expected 200, got {r5.status_code}: {r5.text}"
        d5 = r5.json()
        print(f"OGDC Target-Stop: TP = {d5['risk']['target_price']}, SL = {d5['risk']['stop_loss']}, RRR = {d5['risk']['risk_reward_ratio']}")

        # Reset weights back to default
        reset_payload = {
            "gru_weight": 0.30,
            "technical_weight": 0.25,
            "fundamental_weight": 0.25,
            "sentiment_weight": 0.20,
        }
        await client.post("/api/v1/recommendations/engine-weights", json=reset_payload, headers=headers)

    print("\nALL RECOMMENDATION ENDPOINTS TESTED AND PASSED 100% WITH 0 ERRORS!")


if __name__ == "__main__":
    asyncio.run(run_endpoint_checks())
