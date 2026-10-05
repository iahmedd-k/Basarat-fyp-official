import asyncio
import time
import uuid
import sys
from pathlib import Path
from decimal import Decimal
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.security import create_access_token
from app.db.session import async_session_factory
from app.models.user import User
from sqlalchemy import select

async def run_benchmark():
    print("=" * 80)
    print("BASARAT BACKEND: WATCHLIST & PORTFOLIO LATENCY BENCHMARK")
    print("=" * 80)

    async with async_session_factory() as session:
        user_res = await session.execute(select(User).where(User.email == "demo@basarat.pk"))
        u = user_res.scalars().first()
        if not u:
            print("Demo user not found in DB")
            return
        demo_user_id = u.id
        token = create_access_token(data={"sub": str(demo_user_id), "email": u.email, "role": "user"})

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        print(f"\nUser: demo@basarat.pk (id={demo_user_id})")
        print("-" * 80)
        print(f"{'Endpoint':<45} | {'Method':<6} | {'1st Call':<10} | {'2nd Call (Cached)':<18}")
        print("-" * 80)

        # 1. Watchlists List
        t0 = time.perf_counter()
        r1 = await client.get("/api/v1/watchlists", headers=headers)
        dt1 = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        r2 = await client.get("/api/v1/watchlists", headers=headers)
        dt2 = (time.perf_counter() - t0) * 1000
        print(f"{'/api/v1/watchlists':<45} | GET    | {dt1:8.1f}ms | {dt2:8.1f}ms (hit)")

        # 2. Watchlist Default
        t0 = time.perf_counter()
        r1 = await client.get("/api/v1/watchlists/default", headers=headers)
        dt1 = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        r2 = await client.get("/api/v1/watchlists/default", headers=headers)
        dt2 = (time.perf_counter() - t0) * 1000
        print(f"{'/api/v1/watchlists/default':<45} | GET    | {dt1:8.1f}ms | {dt2:8.1f}ms (hit)")

        # 3. Watchlist Symbol Check
        t0 = time.perf_counter()
        r1 = await client.get("/api/v1/watchlists/check/OGDC", headers=headers)
        dt1 = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        r2 = await client.get("/api/v1/watchlists/check/OGDC", headers=headers)
        dt2 = (time.perf_counter() - t0) * 1000
        print(f"{'/api/v1/watchlists/check/OGDC':<45} | GET    | {dt1:8.1f}ms | {dt2:8.1f}ms (hit)")

        # 4. Watchlist Create / Item Add / Update / Delete
        t0 = time.perf_counter()
        r_create = await client.post("/api/v1/watchlists", json={"name": f"WL_{uuid.uuid4().hex[:4]}", "symbols": ["SYS"]}, headers=headers)
        dt_create = (time.perf_counter() - t0) * 1000
        wl_data = r_create.json()
        wl_id = wl_data.get("id")
        print(f"{'/api/v1/watchlists':<45} | POST   | {dt_create:8.1f}ms | -")

        if wl_id:
            # Get Watchlist by ID
            t0 = time.perf_counter()
            r1 = await client.get(f"/api/v1/watchlists/{wl_id}", headers=headers)
            dt1 = (time.perf_counter() - t0) * 1000

            t0 = time.perf_counter()
            r2 = await client.get(f"/api/v1/watchlists/{wl_id}", headers=headers)
            dt2 = (time.perf_counter() - t0) * 1000
            print(f"{'/api/v1/watchlists/{id}':<45} | GET    | {dt1:8.1f}ms | {dt2:8.1f}ms (hit)")

            # Add Item
            t0 = time.perf_counter()
            r_add = await client.post(f"/api/v1/watchlists/{wl_id}/items", json={"symbol": "TRG", "target_price": 90.0}, headers=headers)
            dt_add = (time.perf_counter() - t0) * 1000
            item_data = r_add.json()
            item_id = item_data.get("id") or "TRG"
            print(f"{'/api/v1/watchlists/{id}/items':<45} | POST   | {dt_add:8.1f}ms | -")

            # Patch Item
            t0 = time.perf_counter()
            r_patch = await client.patch(f"/api/v1/watchlists/{wl_id}/items/{item_id}", json={"target_price": 95.0}, headers=headers)
            dt_patch = (time.perf_counter() - t0) * 1000
            print(f"{'/api/v1/watchlists/{id}/items/{item_id}':<45} | PATCH  | {dt_patch:8.1f}ms | -")

            # Delete Item
            t0 = time.perf_counter()
            r_del_item = await client.delete(f"/api/v1/watchlists/{wl_id}/items/{item_id}", headers=headers)
            dt_del_item = (time.perf_counter() - t0) * 1000
            print(f"{'/api/v1/watchlists/{id}/items/{item_id}':<45} | DELETE | {dt_del_item:8.1f}ms | -")

            # Delete Watchlist
            t0 = time.perf_counter()
            r_del_wl = await client.delete(f"/api/v1/watchlists/{wl_id}", headers=headers)
            dt_del_wl = (time.perf_counter() - t0) * 1000
            print(f"{'/api/v1/watchlists/{id}':<45} | DELETE | {dt_del_wl:8.1f}ms | -")

        print("-" * 80)
        print("PORTFOLIO ENDPOINTS")
        print("-" * 80)

        # 5. Get Portfolio Summary & Holdings
        t0 = time.perf_counter()
        r1 = await client.get("/api/v1/portfolio", headers=headers)
        dt1 = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        r2 = await client.get("/api/v1/portfolio", headers=headers)
        dt2 = (time.perf_counter() - t0) * 1000
        print(f"{'/api/v1/portfolio':<45} | GET    | {dt1:8.1f}ms | {dt2:8.1f}ms (hit)")

        # 6. Get Holdings
        t0 = time.perf_counter()
        r1 = await client.get("/api/v1/portfolio/holdings", headers=headers)
        dt1 = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        r2 = await client.get("/api/v1/portfolio/holdings", headers=headers)
        dt2 = (time.perf_counter() - t0) * 1000
        print(f"{'/api/v1/portfolio/holdings':<45} | GET    | {dt1:8.1f}ms | {dt2:8.1f}ms (hit)")

        # 7. Get PnL
        t0 = time.perf_counter()
        r1 = await client.get("/api/v1/portfolio/pnl", headers=headers)
        dt1 = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        r2 = await client.get("/api/v1/portfolio/pnl", headers=headers)
        dt2 = (time.perf_counter() - t0) * 1000
        print(f"{'/api/v1/portfolio/pnl':<45} | GET    | {dt1:8.1f}ms | {dt2:8.1f}ms (hit)")

        # 8. Get Allocation
        t0 = time.perf_counter()
        r1 = await client.get("/api/v1/portfolio/allocation", headers=headers)
        dt1 = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        r2 = await client.get("/api/v1/portfolio/allocation", headers=headers)
        dt2 = (time.perf_counter() - t0) * 1000
        print(f"{'/api/v1/portfolio/allocation':<45} | GET    | {dt1:8.1f}ms | {dt2:8.1f}ms (hit)")

        # 9. Get Performance
        t0 = time.perf_counter()
        r1 = await client.get("/api/v1/portfolio/performance?period=1M", headers=headers)
        dt1 = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        r2 = await client.get("/api/v1/portfolio/performance?period=1M", headers=headers)
        dt2 = (time.perf_counter() - t0) * 1000
        print(f"{'/api/v1/portfolio/performance':<45} | GET    | {dt1:8.1f}ms | {dt2:8.1f}ms (hit)")

        # 10. Get Transactions
        t0 = time.perf_counter()
        r_txns = await client.get("/api/v1/portfolio/transactions", headers=headers)
        dt_txns = (time.perf_counter() - t0) * 1000
        print(f"{'/api/v1/portfolio/transactions':<45} | GET    | {dt_txns:8.1f}ms | -")

        # 11. Single Holding Detail
        holdings_list = r1.json() if isinstance(r1.json(), list) else []
        sym = "SYS"
        t0 = time.perf_counter()
        r1 = await client.get(f"/api/v1/portfolio/holdings/{sym}", headers=headers)
        dt1 = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        r2 = await client.get(f"/api/v1/portfolio/holdings/{sym}", headers=headers)
        dt2 = (time.perf_counter() - t0) * 1000
        print(f"{f'/api/v1/portfolio/holdings/{sym}':<45} | GET    | {dt1:8.1f}ms | {dt2:8.1f}ms (hit)")

        # 12. Create, Update, Delete Transaction
        t0 = time.perf_counter()
        r_create_t = await client.post("/api/v1/portfolio/transactions", json={
            "symbol": "ENGRO",
            "transaction_type": "BUY",
            "quantity": 50,
            "price": 300.0,
            "fee": 5.0,
            "transaction_date": "2026-02-01"
        }, headers=headers)
        dt_create_t = (time.perf_counter() - t0) * 1000
        t_data = r_create_t.json()
        t_id = t_data.get("id")
        print(f"{'/api/v1/portfolio/transactions':<45} | POST   | {dt_create_t:8.1f}ms | -")

        if t_id:
            t0 = time.perf_counter()
            r_get_t = await client.get(f"/api/v1/portfolio/transactions/{t_id}", headers=headers)
            dt_get_t = (time.perf_counter() - t0) * 1000
            print(f"{'/api/v1/portfolio/transactions/{id}':<45} | GET    | {dt_get_t:8.1f}ms | -")

            t0 = time.perf_counter()
            r_patch_t = await client.patch(f"/api/v1/portfolio/transactions/{t_id}", json={"quantity": 60}, headers=headers)
            dt_patch_t = (time.perf_counter() - t0) * 1000
            print(f"{'/api/v1/portfolio/transactions/{id}':<45} | PATCH  | {dt_patch_t:8.1f}ms | -")

            t0 = time.perf_counter()
            r_del_t = await client.delete(f"/api/v1/portfolio/transactions/{t_id}", headers=headers)
            dt_del_t = (time.perf_counter() - t0) * 1000
            print(f"{'/api/v1/portfolio/transactions/{id}':<45} | DELETE | {dt_del_t:8.1f}ms | -")

        print("=" * 80)
        print("BENCHMARK COMPLETE")
        print("=" * 80)

if __name__ == "__main__":
    asyncio.run(run_benchmark())
