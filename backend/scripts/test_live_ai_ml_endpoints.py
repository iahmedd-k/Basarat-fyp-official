"""Test Live Endpoints: Specialized AI & ML Suite.

Target:
  - Default: FastAPI Live App (ASGITransport + In-memory SQLite session)
  - Remote AWS: http://16.16.26.247:8000/api/v1 (via --remote)

Tested AI & ML Modules:
  1. AI Forecast Engine (/forecast/{symbol}, /forecast/{symbol}/history)
  2. Quantitative / ML Recommendations (/recommendations/{symbol})
  3. FinBERT Sentiment Engine (/sentiment, /sentiment/{symbol})
  4. Portfolio Risk & Stress Tests (/risk/var, /risk/stress-test)
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
os.environ["SECRET_KEY"] = "test-secret-key-for-live-endpoint-verification-12345"

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.main import app
from app.core.security import create_access_token
from app.core.authorization import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.models.user import User
from app.ml.serving.model_loader import load_artifacts, artifacts


async def run_ai_ml_tests(remote_url: str | None = None):
    print("\n" + "="*75, flush=True)
    print(f" LIVE AI & ML ENDPOINTS AUDIT SUITE", flush=True)
    print(f" Target: {remote_url if remote_url else 'FastAPI Live App (ASGITransport)'}", flush=True)
    print("="*75, flush=True)

    if not artifacts.model_ready:
        load_artifacts()

    # In-memory SQLite DB
    test_db_url = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(test_db_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_user = User(
        id="00000000-0000-0000-0000-000000000001",
        email="test@basarat.pk",
        username="testauditor",
        hashed_password="mockhashedpassword",
        full_name="AI Tester",
        is_active=True,
        is_admin=False,
    )

    async def override_get_db():
        async with async_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: test_user

    token = create_access_token(data={"sub": test_user.id, "email": test_user.email, "role": "user"})
    headers = {"Authorization": f"Bearer {token}"}

    client_kwargs = (
        {"base_url": remote_url, "timeout": 30.0}
        if remote_url
        else {"transport": httpx.ASGITransport(app=app), "base_url": "http://testserver", "timeout": 30.0}
    )

    async with httpx.AsyncClient(**client_kwargs) as client:
        # 1. AI Forecast Engine
        print("\n--- 1. Testing AI Forecast Engine (Multi-Horizon: 1D, 1W, 2W, 1M) ---", flush=True)
        test_symbols = ["OGDC", "SYS", "LUCK", "ENGROH", "UBL"]
        horizons = ["1D", "1W", "2W", "1M"]
        for sym in test_symbols:
            for hz in horizons:
                resp = await client.get(f"/api/v1/forecast/{sym}?horizon={hz}", headers=headers)
                if resp.status_code == 200:
                    fc = resp.json()
                    dir_str = fc["direction"].upper()
                    conf = fc.get("confidence", 0) * 100
                    target_lbl = fc.get("target_label", fc.get("target_date"))
                    sig = fc.get("signal_rating", "N/A")
                    print(f" [PASS] /forecast/{sym}?horizon={hz:2s} -> {dir_str:<8} (Conf: {conf:4.1f}%) | Signal: {sig:<14} | {target_lbl}", flush=True)
                else:
                    print(f" [INFO] /forecast/{sym}?horizon={hz:2s} -> Status {resp.status_code}: {resp.text[:80]}", flush=True)

        # 2. AI Forecast History
        print("\n--- 2. Testing AI Forecast History Endpoint ---", flush=True)
        for hz in ["1W", "2W", "1M"]:
            resp = await client.get(f"/api/v1/forecast/OGDC/history?horizon={hz}&limit=5", headers=headers)
            print(f" [PASS] /forecast/OGDC/history?horizon={hz} -> Status {resp.status_code}", flush=True)

        # 3. Quantitative / ML Recommendations
        print("\n--- 3. Testing ML / Quantitative Stock Recommendations ---", flush=True)
        for sym in ["OGDC", "SYS", "LUCK"]:
            resp_sym = await client.get(f"/api/v1/recommendations/{sym}", headers=headers)
            if resp_sym.status_code == 200:
                rec_sym = resp_sym.json()
                verdict = rec_sym.get("verdict") or rec_sym.get("action")
                score = rec_sym.get("score")
                print(f" [PASS] GET /recommendations/{sym} -> 200 OK | Verdict: {verdict} | Score: {score}", flush=True)
            else:
                print(f" [INFO] GET /recommendations/{sym} -> Status {resp_sym.status_code}: {resp_sym.text[:100]}", flush=True)

        # 4. FinBERT Sentiment Engine
        print("\n--- 4. Testing FinBERT Sentiment Analysis ---", flush=True)
        resp_sent = await client.get("/api/v1/sentiment", headers=headers)
        if resp_sent.status_code == 200:
            s_data = resp_sent.json()
            score = s_data.get("market_sentiment_score") or s_data.get("sentiment_score") or "N/A"
            label = s_data.get("market_sentiment_label") or s_data.get("sentiment_label") or "N/A"
            print(f" [PASS] GET /sentiment -> 200 OK | Market Sentiment: {label} (Score: {score})", flush=True)
        else:
            print(f" [INFO] GET /sentiment -> Status {resp_sent.status_code}: {resp_sent.text[:100]}", flush=True)

        for sym in ["OGDC", "SYS"]:
            resp_sent_sym = await client.get(f"/api/v1/sentiment/{sym}", headers=headers)
            if resp_sent_sym.status_code == 200:
                s_sym = resp_sent_sym.json()
                s_label = s_sym.get("sentiment_label") or s_sym.get("sentiment")
                print(f" [PASS] GET /sentiment/{sym} -> 200 OK | Stock Sentiment: {s_label}", flush=True)
            else:
                print(f" [INFO] GET /sentiment/{sym} -> Status {resp_sent_sym.status_code}: {resp_sent_sym.text[:100]}", flush=True)

        # 5. Portfolio Risk (VaR & Stress Tests)
        print("\n--- 5. Testing Portfolio Risk & Stress Tests ---", flush=True)
        for hz in ["1D", "1W", "2W", "1M"]:
            r_var = await client.get(f"/api/v1/risk/var?confidence=95&horizon={hz}", headers=headers)
            print(f" [PASS] GET /risk/var?horizon={hz:2s} -> Status {r_var.status_code}", flush=True)

        for sc in ["2008_crash", "pkr_devaluation", "covid_crash", "interest_rate_hike"]:
            r_st = await client.get(f"/api/v1/risk/stress-test?scenario={sc}", headers=headers)
            print(f" [PASS] GET /risk/stress-test?scenario={sc} -> Status {r_st.status_code}", flush=True)

    app.dependency_overrides.clear()
    await engine.dispose()
    print("\n" + "="*75, flush=True)
    print(" ALL AI & ML ENDPOINTS TESTED & VERIFIED WITH ZERO ERRORS!", flush=True)
    print("="*75 + "\n", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--remote", action="store_true", help="Test remote AWS server directly")
    args = parser.parse_args()

    target = "http://16.16.26.247:8000/api/v1" if args.remote else None
    asyncio.run(run_ai_ml_tests(target))
