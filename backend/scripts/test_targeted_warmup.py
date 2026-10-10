import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from httpx import ASGITransport
from app.main import app
from app.core.security import create_access_token
from app.db.session import async_session_factory
from sqlalchemy import select
from app.models.user import User
from app.ml.serving.model_loader import load_artifacts

async def get_real_auth():
    async with async_session_factory() as db:
        result = await db.execute(select(User).limit(1))
        user = result.scalars().first()
        if user:
            token = create_access_token(data={"sub": str(user.id), "email": user.email, "is_admin": getattr(user, "is_admin", False)})
            return token, str(user.id)
    return "", ""

async def main():
    load_artifacts()
    token, user_id = await get_real_auth()
    auth_headers = {"Authorization": f"Bearer {token}", "Host": "localhost", "Content-Type": "application/json"}
    public_headers = {"Host": "localhost", "Content-Type": "application/json"}

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost:8000", timeout=30.0) as client:
        targets = [
            ("Health Readiness", "GET", "/api/v1/health/ready", public_headers),
            ("AI Forecast OGDC", "GET", "/api/v1/forecast/OGDC?horizon=1W", auth_headers),
            ("Community Posts Feed", "GET", "/api/v1/community/posts?limit=10", auth_headers),
            ("Portfolio Allocation", "GET", "/api/v1/portfolio/allocation", auth_headers),
            ("Alerts Rules", "GET", "/api/v1/alerts/rules", auth_headers),
            ("Market Live", "GET", "/api/v1/market/live", public_headers),
            ("Stock Overview", "GET", "/api/v1/stocks/OGDC/overview", public_headers),
        ]

        print("\n" + "="*70, flush=True)
        print(f"{'Endpoint':<25} | {'Cold (ms)':<10} | {'Warm (ms)':<10} | {'Status'}", flush=True)
        print("="*70, flush=True)

        for name, method, path, headers in targets:
            # Cold
            t0 = time.perf_counter()
            r_cold = await client.request(method, path, headers=headers)
            t_cold = (time.perf_counter() - t0) * 1000.0

            # Warm
            t1 = time.perf_counter()
            r_warm = await client.request(method, path, headers=headers)
            t_warm = (time.perf_counter() - t1) * 1000.0

            status_str = f"PASS ({r_warm.status_code})" if r_warm.status_code == 200 else f"ERR ({r_warm.status_code})"
            print(f"{name:<25} | {t_cold:8.2f}ms | {t_warm:8.2f}ms | {status_str}", flush=True)
        print("="*70 + "\n", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
