import asyncio
import sys
import time
import json
import uuid
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from httpx import ASGITransport

from app.main import app
from app.core.security import create_access_token
from app.db.session import async_session_factory
from sqlalchemy import select
from app.models.user import User

async def get_real_auth():
    async with async_session_factory() as db:
        result = await db.execute(select(User).limit(1))
        user = result.scalars().first()
        if user:
            token = create_access_token(data={"sub": str(user.id), "email": user.email, "is_admin": getattr(user, "is_admin", False)})
            return token, str(user.id), user.email
    token = create_access_token(data={"sub": "demo-user-id", "email": "demo@basarat.pk", "is_admin": False})
    return token, "demo-user-id", "demo@basarat.pk"

async def run_benchmark():
    token, user_id, email = await get_real_auth()
    auth_headers = {"Authorization": f"Bearer {token}", "Host": "localhost", "Content-Type": "application/json"}
    public_headers = {"Host": "localhost", "Content-Type": "application/json"}

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost:8000", timeout=30.0) as client:
        print("\n" + "="*85, flush=True)
        print("  LATENCY AUDIT: IPOs, ETFs, and Community Comments Endpoints", flush=True)
        print(f"  Target User: {email} (ID: {user_id})", flush=True)
        print("="*85 + "\n", flush=True)

        results = []

        async def measure(category, name, method, path, payload=None, is_auth=False, expected_codes=(200, 201, 204)):
            headers = auth_headers if is_auth else public_headers
            
            # Cold call
            t0 = time.perf_counter()
            try:
                res_cold = await client.request(method, path, headers=headers, json=payload)
                t_cold = (time.perf_counter() - t0) * 1000.0
                cold_status = res_cold.status_code
            except Exception as e:
                t_cold = -1
                cold_status = 500
                res_cold = None

            # Warm call
            t1 = time.perf_counter()
            try:
                res_warm = await client.request(method, path, headers=headers, json=payload)
                t_warm = (time.perf_counter() - t1) * 1000.0
                warm_status = res_warm.status_code
            except Exception as e:
                t_warm = -1
                warm_status = 500
                res_warm = None

            status_str = "PASS" if warm_status in expected_codes or cold_status in expected_codes else f"ERR_{warm_status}"
            
            entry = {
                "category": category,
                "name": name,
                "method": method,
                "path": path,
                "cold_status": cold_status,
                "warm_status": warm_status,
                "status": status_str,
                "cold_ms": round(t_cold, 2),
                "warm_ms": round(t_warm, 2),
            }
            results.append(entry)
            print(f"[{status_str:<6}] | {category:<18} | {method:<6} {path:<48} | Cold: {t_cold:7.2f}ms | Warm: {t_warm:7.2f}ms", flush=True)
            return res_cold, res_warm

        # ─── 1. IPOs ENDPOINTS ────────────────────────────────────────────────
        res_ipos_cold, _ = await measure("IPOs", "List IPOs", "GET", "/api/v1/ipos", is_auth=False)
        await measure("IPOs", "IPO Calendar", "GET", "/api/v1/ipos/calendar", is_auth=False)
        await measure("IPOs", "IPO Performance", "GET", "/api/v1/ipos/performance", is_auth=False)
        
        sample_ipo_sym = "FFBL"
        if res_ipos_cold and res_ipos_cold.status_code == 200:
            ipo_items = res_ipos_cold.json().get("items", [])
            if ipo_items and ipo_items[0].get("symbol"):
                sample_ipo_sym = ipo_items[0]["symbol"]

        await measure("IPOs", f"IPO Detail ({sample_ipo_sym})", "GET", f"/api/v1/ipos/{sample_ipo_sym}", is_auth=False, expected_codes=(200, 404))

        # ─── 2. ETFs ENDPOINTS ────────────────────────────────────────────────
        res_etfs_cold, _ = await measure("ETFs", "List ETFs", "GET", "/api/v1/etfs", is_auth=False)
        
        sample_etf_sym = "MIIETF"
        if res_etfs_cold and res_etfs_cold.status_code == 200:
            etf_items = res_etfs_cold.json().get("items", [])
            if etf_items and etf_items[0].get("symbol"):
                sample_etf_sym = etf_items[0]["symbol"]

        await measure("ETFs", f"ETF Detail ({sample_etf_sym})", "GET", f"/api/v1/etfs/{sample_etf_sym}", is_auth=False, expected_codes=(200, 404))
        await measure("ETFs", f"ETF History ({sample_etf_sym})", "GET", f"/api/v1/etfs/{sample_etf_sym}/history?timeframe=1M", is_auth=False, expected_codes=(200, 404))
        await measure("ETFs", f"ETF Performance ({sample_etf_sym})", "GET", f"/api/v1/etfs/{sample_etf_sym}/performance", is_auth=False, expected_codes=(200, 404))

        # ─── 3. COMMUNITY COMMENTS ENDPOINTS ──────────────────────────────────
        # Create a test post for comment testing
        created_post_id = None
        res_post_c, res_post_w = await measure(
            "Community Posts", "Create Post For Comments", "POST", "/api/v1/community/posts",
            payload={"content": "Benchmark test post for comments audit #OGDC", "post_type": "GENERAL_MARKET"},
            is_auth=True, expected_codes=(200, 201)
        )
        if res_post_c and res_post_c.status_code in (200, 201):
            try:
                created_post_id = res_post_c.json().get("id")
            except Exception:
                pass

        if not created_post_id:
            # Fallback: fetch an existing post
            r_feed = await client.get("/api/v1/community/posts?limit=1", headers=auth_headers)
            if r_feed.status_code == 200:
                posts = r_feed.json().get("posts", [])
                if posts:
                    created_post_id = posts[0].get("id")

        if created_post_id:
            # GET Comments on post
            await measure("Community Comments", "Get Post Comments", "GET", f"/api/v1/community/posts/{created_post_id}/comments", is_auth=True)

            # POST Create Comment
            created_comment_id = None
            res_comm_c, res_comm_w = await measure(
                "Community Comments", "Create Comment", "POST", f"/api/v1/community/posts/{created_post_id}/comments",
                payload={"content": "Benchmark comment on post with solid volume support."},
                is_auth=True, expected_codes=(200, 201)
            )
            if res_comm_c and res_comm_c.status_code in (200, 201):
                try:
                    created_comment_id = res_comm_c.json().get("id")
                except Exception:
                    pass

            if created_comment_id:
                # GET Comment Replies
                await measure("Community Comments", "Get Comment Replies", "GET", f"/api/v1/community/comments/{created_comment_id}/replies", is_auth=True)

                # DELETE Comment
                await measure("Community Comments", "Delete Comment", "DELETE", f"/api/v1/community/comments/{created_comment_id}", is_auth=True, expected_codes=(200, 204))

            # Cleanup Post
            await client.delete(f"/api/v1/community/posts/{created_post_id}", headers=auth_headers)

        print("\n" + "="*85, flush=True)
        print(f"  BENCHMARK COMPLETED: {len(results)} Operations Tested", flush=True)
        print("="*85 + "\n", flush=True)

if __name__ == "__main__":
    asyncio.run(run_benchmark())
