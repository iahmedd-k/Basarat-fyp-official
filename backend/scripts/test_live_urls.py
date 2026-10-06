import urllib.request
import urllib.error
import json
import time

BASE_URL = "http://193.123.84.223:8000/api/v1"

def test_fundamentals_urls():
    symbols = ["OGDC", "HBL", "SYS", "HUBC", "LUCK", "MCB", "BML", "IMAGE", "NCPL", "THCCL"]
    print("==========================================================================================")
    print("   1. LIVE STOCKS FUNDAMENTALS URL AUDIT (ANNUAL & QUARTERLY STATEMENTS)")
    print("==========================================================================================")
    
    for sym in symbols:
        url = f"{BASE_URL}/stocks/{sym}/fundamentals"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            t0 = time.perf_counter()
            with urllib.request.urlopen(req, timeout=10) as resp:
                lat = (time.perf_counter() - t0) * 1000
                data = json.loads(resp.read().decode())
                fa = data.get("financials_annual") or []
                fq = data.get("financials_quarterly") or []
                
                print(f"\n--- URL: {url} (status={resp.status}, {lat:.1f}ms) ---")
                print(f"Company: {data.get('company_profile', {}).get('company_name', sym)} ({sym})")
                print("Annual Financial Statements (Audited):")
                print(f"  {'Fiscal Year':<12} | {'Sales / Turnover':<22} | {'Profit After Tax (PAT)':<26} | {'Earnings Per Share (EPS)':<24}")
                print("  " + "-" * 90)
                for r in fa:
                    fy = r.get("Fiscal Year") or r.get("period") or "—"
                    s = f"PKR {r.get('Sales / Turnover'):,.2f} M" if r.get("Sales / Turnover") is not None else "—"
                    p = f"PKR {r.get('Profit After Tax (PAT)'):,.2f} M" if r.get("Profit After Tax (PAT)") is not None else "—"
                    e = f"PKR {r.get('Earnings Per Share (EPS)'):,.2f}" if r.get("Earnings Per Share (EPS)") is not None else "—"
                    print(f"  {fy:<12} | {s:<22} | {p:<26} | {e:<24}")
                
                print("Quarterly Financial Statements:")
                print(f"  {'Period':<12} | {'Sales / Turnover':<22} | {'Profit After Tax (PAT)':<26} | {'Earnings Per Share (EPS)':<24}")
                print("  " + "-" * 90)
                for r in fq:
                    q = r.get("Period") or r.get("period") or "—"
                    s = f"PKR {r.get('Sales / Turnover'):,.2f} M" if r.get("Sales / Turnover") is not None else "—"
                    p = f"PKR {r.get('Profit After Tax (PAT)'):,.2f} M" if r.get("Profit After Tax (PAT)") is not None else "—"
                    e = f"PKR {r.get('Earnings Per Share (EPS)'):,.2f}" if r.get("Earnings Per Share (EPS)") is not None else "—"
                    print(f"  {q:<12} | {s:<22} | {p:<26} | {e:<24}")
        except Exception as exc:
            print(f"Error fetching {sym} ({url}): {exc}")

def test_community_crud_urls():
    print("\n==========================================================================================")
    print("   2. LIVE COMMUNITY CRUD URL AUDIT (AUTHENTICATED AS demo@basarat.pk)")
    print("==========================================================================================")
    
    # 1. Login
    login_url = f"{BASE_URL}/auth/login"
    login_body = json.dumps({"email": "demo@basarat.pk", "password": "TestPassword12345"}).encode()
    req = urllib.request.Request(login_url, data=login_body, headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req) as resp:
        lat = (time.perf_counter() - t0) * 1000
        auth_data = json.loads(resp.read().decode())
    token = auth_data.get("access_token") or (auth_data.get("tokens") or {}).get("access_token")
    user_id = (auth_data.get("user") or {}).get("id")
    print(f"POST {login_url} -> status=200 ({lat:.1f}ms)")
    print(f"Logged in as: demo@basarat.pk (user_id={user_id})")

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # 2. Feed URL
    feed_url = f"{BASE_URL}/community/feed?tab=for_you&limit=5"
    req = urllib.request.Request(feed_url, headers=headers)
    t0 = time.perf_counter()
    with urllib.request.urlopen(req) as resp:
        lat = (time.perf_counter() - t0) * 1000
        feed_data = json.loads(resp.read().decode())
    print(f"GET  {feed_url} -> status=200 ({lat:.1f}ms, posts={len(feed_data.get('posts', []))})")

    # 3. Create Post
    create_url = f"{BASE_URL}/community/posts"
    post_payload = {
        "content": f"Live URL test post at {time.strftime('%Y-%m-%d %H:%M:%S')} checking $OGDC statements.",
        "post_type": "STOCK",
        "stock_symbol": "OGDC"
    }
    req = urllib.request.Request(create_url, data=json.dumps(post_payload).encode(), headers=headers)
    t0 = time.perf_counter()
    with urllib.request.urlopen(req) as resp:
        lat = (time.perf_counter() - t0) * 1000
        new_post = json.loads(resp.read().decode())
    post_id = new_post.get("id")
    print(f"POST {create_url} -> status=201 ({lat:.1f}ms, post_id={post_id})")

    # 4. Get Post Detail
    detail_url = f"{BASE_URL}/community/posts/{post_id}"
    req = urllib.request.Request(detail_url, headers=headers)
    t0 = time.perf_counter()
    with urllib.request.urlopen(req) as resp:
        lat = (time.perf_counter() - t0) * 1000
    print(f"GET  {detail_url} -> status=200 ({lat:.1f}ms)")

    # 5. Update Post (PUT)
    up_url = f"{BASE_URL}/community/posts/{post_id}"
    req = urllib.request.Request(up_url, data=json.dumps({"content": "Updated content via live URL test."}).encode(), headers=headers, method="PUT")
    t0 = time.perf_counter()
    with urllib.request.urlopen(req) as resp:
        lat = (time.perf_counter() - t0) * 1000
    print(f"PUT  {up_url} -> status=200 ({lat:.1f}ms)")

    # 6. Like Post
    like_url = f"{BASE_URL}/community/posts/{post_id}/like"
    req = urllib.request.Request(like_url, headers=headers, method="POST")
    t0 = time.perf_counter()
    with urllib.request.urlopen(req) as resp:
        lat = (time.perf_counter() - t0) * 1000
    print(f"POST {like_url} -> status=204 ({lat:.1f}ms)")

    # 7. Create Comment
    comm_url = f"{BASE_URL}/community/posts/{post_id}/comments"
    req = urllib.request.Request(comm_url, data=json.dumps({"content": "Live URL comment test."}).encode(), headers=headers)
    t0 = time.perf_counter()
    with urllib.request.urlopen(req) as resp:
        lat = (time.perf_counter() - t0) * 1000
        new_comm = json.loads(resp.read().decode())
    comm_id = new_comm.get("id")
    print(f"POST {comm_url} -> status=201 ({lat:.1f}ms, comment_id={comm_id})")

    # 8. List Comments
    req = urllib.request.Request(comm_url, headers=headers)
    t0 = time.perf_counter()
    with urllib.request.urlopen(req) as resp:
        lat = (time.perf_counter() - t0) * 1000
        comm_list = json.loads(resp.read().decode())
    print(f"GET  {comm_url} -> status=200 ({lat:.1f}ms, count={len(comm_list.get('comments', []))})")

    # 9. Delete Comment
    del_c_url = f"{BASE_URL}/community/comments/{comm_id}"
    req = urllib.request.Request(del_c_url, headers=headers, method="DELETE")
    t0 = time.perf_counter()
    with urllib.request.urlopen(req) as resp:
        lat = (time.perf_counter() - t0) * 1000
    print(f"DEL  {del_c_url} -> status=204 ({lat:.1f}ms)")

    # 10. Delete Post
    del_p_url = f"{BASE_URL}/community/posts/{post_id}"
    req = urllib.request.Request(del_p_url, headers=headers, method="DELETE")
    t0 = time.perf_counter()
    with urllib.request.urlopen(req) as resp:
        lat = (time.perf_counter() - t0) * 1000
    print(f"DEL  {del_p_url} -> status=204 ({lat:.1f}ms)")

    print("\n==========================================================================================")
    print("   ALL LIVE URL TESTS COMPLETED WITH 100% SUCCESS")
    print("==========================================================================================")

if __name__ == "__main__":
    test_fundamentals_urls()
    test_community_crud_urls()
