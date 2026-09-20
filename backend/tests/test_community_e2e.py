"""Comprehensive E2E Test & Benchmark Suite for Community Module.

Tests the full interactive lifecycle across 2 distinct users:
1. User A & User B Signup & Login
2. User A Profile check: GET /community/me
3. User A Post Creation (STOCK): POST /community/posts (Form data)
4. User B Post Creation (GENERAL_MARKET): POST /community/posts
5. Feed Querying: GET /community/feed (all, mine, following, stock_symbol)
6. Get Single Post: GET /community/posts/{post_id}
7. User B Likes User A's Post: POST /community/posts/{post_id}/like
8. User B Comments on User A's Post: POST /community/posts/{post_id}/comments
9. User A Replies to User B's Comment: POST /community/posts/{post_id}/comments (parent_comment_id)
10. Get Post Comments: GET /community/posts/{post_id}/comments
11. User B Follows User A: POST /community/users/{user_id}/follow
12. Check Follow Status: GET /community/users/{user_id}/follow-status
13. Get Followers / Following: GET /community/users/{user_id}/followers, GET /community/users/{user_id}/following
14. User A Checks Notifications: GET /community/notifications, /community/notifications/unread-count
15. User A Marks Notification Read: POST /community/notifications/{id}/read & mark-all-read
16. User A Views User B's Profile & Posts: GET /community/users/{user_id}/profile, /community/users/{user_id}/posts
17. User A Updates Own Post: PATCH /community/posts/{post_id}
18. User B Unlikes Post: DELETE /community/posts/{post_id}/like
19. User B Unfollows User A: DELETE /community/users/{user_id}/follow
20. User A Deletes Comment: DELETE /community/comments/{comment_id}
21. User A Deletes Own Post: DELETE /community/posts/{post_id}
"""

import time
import uuid
import httpx

BASE_URL = "http://localhost:8000/api/v1"
results = []

def record(endpoint: str, method: str, status_code: int, duration_ms: float, passed: bool, notes: str = "", error_body: str = ""):
    results.append({
        "endpoint": endpoint,
        "method": method,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 2),
        "passed": passed,
        "notes": notes,
    })
    status_sym = "PASS" if passed else "FAIL"
    err_snippet = f" | ERR: {error_body[:120]}" if (not passed and error_body) else ""
    print(f"[{status_sym}] {method:6} {endpoint:45} | {duration_ms:6.1f}ms | HTTP {status_code} | {notes}{err_snippet}")

def run_community_audit():
    print("=" * 110)
    print("STARTING FULL COMMUNITY MODULE AUDIT & BENCHMARK")
    print("=" * 110)
    
    client = httpx.Client(timeout=30.0)
    
    # 1. Setup Two Users
    email_a = f"comm_user_a_{uuid.uuid4().hex[:6]}@test.com"
    email_b = f"comm_user_b_{uuid.uuid4().hex[:6]}@test.com"
    pwd = "CommunityPassword123!"
    
    client.post(f"{BASE_URL}/auth/signup", json={"email": email_a, "password": pwd, "full_name": "User Alpha"})
    res_a = client.post(f"{BASE_URL}/auth/login", json={"email": email_a, "password": pwd}).json()
    token_a = res_a["access_token"]
    user_a_id = res_a["user"]["id"]
    headers_a = {"Authorization": f"Bearer {token_a}"}
    
    client.post(f"{BASE_URL}/auth/signup", json={"email": email_b, "password": pwd, "full_name": "User Beta"})
    res_b = client.post(f"{BASE_URL}/auth/login", json={"email": email_b, "password": pwd}).json()
    token_b = res_b["access_token"]
    user_b_id = res_b["user"]["id"]
    headers_b = {"Authorization": f"Bearer {token_b}"}
    
    print(f"-> User A ID: {user_a_id}, User B ID: {user_b_id}")
    
    # 2. User A Profile: GET /community/me
    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/community/me", headers=headers_a)
    d = (time.perf_counter() - t0) * 1000
    record("/community/me", "GET", r.status_code, d, r.status_code == 200, f"username={r.json().get('username') if r.status_code==200 else ''}", r.text)

    # 3. User A creates a STOCK post: POST /community/posts (multipart/form-data)
    t0 = time.perf_counter()
    r = client.post(
        f"{BASE_URL}/community/posts",
        headers=headers_a,
        data={
            "content": "OGDC looking strong after breaking 200-day MA with high volume. Thoughts?",
            "post_type": "STOCK",
            "stock_symbol": "OGDC",
        }
    )
    d = (time.perf_counter() - t0) * 1000
    post_a_id = r.json().get("id") if r.status_code == 201 else None
    record("/community/posts", "POST", r.status_code, d, r.status_code == 201 and bool(post_a_id), f"post_id={post_a_id}", r.text)

    # 4. User B creates a GENERAL_MARKET post: POST /community/posts
    t0 = time.perf_counter()
    r = client.post(
        f"{BASE_URL}/community/posts",
        headers=headers_b,
        data={
            "content": "KSE-100 benchmark index crosses 80,000 points today. Great milestone for PSX!",
            "post_type": "GENERAL_MARKET",
        }
    )
    d = (time.perf_counter() - t0) * 1000
    post_b_id = r.json().get("id") if r.status_code == 201 else None
    record("/community/posts (General)", "POST", r.status_code, d, r.status_code == 201 and bool(post_b_id), f"post_id={post_b_id}", r.text)

    # 5. User A Feed: GET /community/feed
    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/community/feed", headers=headers_a)
    d = (time.perf_counter() - t0) * 1000
    record("/community/feed", "GET", r.status_code, d, r.status_code == 200, f"count={len(r.json().get('posts', [])) if r.status_code==200 else 0}", r.text)

    # Filtered feed: stock_symbol=OGDC
    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/community/feed?stock_symbol=OGDC", headers=headers_a)
    d = (time.perf_counter() - t0) * 1000
    record("/community/feed?stock_symbol=OGDC", "GET", r.status_code, d, r.status_code == 200, "", r.text)

    # 6. Get Single Post: GET /community/posts/{post_id}
    if post_a_id:
        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/community/posts/{post_a_id}", headers=headers_b)
        d = (time.perf_counter() - t0) * 1000
        record(f"/community/posts/{post_a_id}", "GET", r.status_code, d, r.status_code == 200, "", r.text)

    # 7. User B Likes User A's Post: POST /community/posts/{post_id}/like
    if post_a_id:
        t0 = time.perf_counter()
        r = client.post(f"{BASE_URL}/community/posts/{post_a_id}/like", headers=headers_b)
        d = (time.perf_counter() - t0) * 1000
        record(f"/community/posts/{post_a_id}/like", "POST", r.status_code, d, r.status_code == 204, "", r.text)

    # 8. User B Comments on User A's Post: POST /community/posts/{post_id}/comments
    comment_b_id = None
    if post_a_id:
        t0 = time.perf_counter()
        r = client.post(
            f"{BASE_URL}/community/posts/{post_a_id}/comments",
            headers=headers_b,
            json={"content": "Agreed! P/E ratio is also looking very attractive below 4.5."}
        )
        d = (time.perf_counter() - t0) * 1000
        comment_b_id = r.json().get("id") if r.status_code == 201 else None
        record(f"/community/posts/{post_a_id}/comments", "POST", r.status_code, d, r.status_code == 201 and bool(comment_b_id), f"comment_id={comment_b_id}", r.text)

    # 9. User A Replies to User B's Comment: POST /community/posts/{post_id}/comments
    reply_a_id = None
    if post_a_id and comment_b_id:
        t0 = time.perf_counter()
        r = client.post(
            f"{BASE_URL}/community/posts/{post_a_id}/comments",
            headers=headers_a,
            json={"content": "Exactly, plus healthy dividend yields.", "parent_comment_id": comment_b_id}
        )
        d = (time.perf_counter() - t0) * 1000
        reply_a_id = r.json().get("id") if r.status_code == 201 else None
        record(f"/community/posts/{post_a_id}/comments (reply)", "POST", r.status_code, d, r.status_code == 201 and bool(reply_a_id), "", r.text)

    # 10. Get Post Comments: GET /community/posts/{post_id}/comments
    if post_a_id:
        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/community/posts/{post_a_id}/comments", headers=headers_a)
        d = (time.perf_counter() - t0) * 1000
        record(f"/community/posts/{post_a_id}/comments", "GET", r.status_code, d, r.status_code == 200, f"comments={len(r.json().get('comments', [])) if r.status_code==200 else 0}", r.text)

    # 11. User B Follows User A: POST /community/users/{user_id}/follow
    t0 = time.perf_counter()
    r = client.post(f"{BASE_URL}/community/users/{user_a_id}/follow", headers=headers_b)
    d = (time.perf_counter() - t0) * 1000
    record(f"/community/users/{user_a_id}/follow", "POST", r.status_code, d, r.status_code == 204, "", r.text)

    # 12. Check Follow Status: GET /community/users/{user_id}/follow-status
    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/community/users/{user_a_id}/follow-status", headers=headers_b)
    d = (time.perf_counter() - t0) * 1000
    is_following = r.json().get("is_following") if r.status_code == 200 else False
    record(f"/community/users/{user_a_id}/follow-status", "GET", r.status_code, d, r.status_code == 200 and is_following, f"is_following={is_following}", r.text)

    # 13. Get Followers / Following
    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/community/users/{user_a_id}/followers", headers=headers_a)
    d = (time.perf_counter() - t0) * 1000
    record(f"/community/users/{user_a_id}/followers", "GET", r.status_code, d, r.status_code == 200, "", r.text)

    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/community/users/{user_b_id}/following", headers=headers_b)
    d = (time.perf_counter() - t0) * 1000
    record(f"/community/users/{user_b_id}/following", "GET", r.status_code, d, r.status_code == 200, "", r.text)

    # 14. User A Checks Notifications: GET /community/notifications & unread-count
    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/community/notifications", headers=headers_a)
    d = (time.perf_counter() - t0) * 1000
    notifs = r.json().get("notifications", []) if r.status_code == 200 else []
    first_notif_id = notifs[0].get("id") if notifs else None
    record("/community/notifications", "GET", r.status_code, d, r.status_code == 200, f"notif_count={len(notifs)}", r.text)

    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/community/notifications/unread-count", headers=headers_a)
    d = (time.perf_counter() - t0) * 1000
    record("/community/notifications/unread-count", "GET", r.status_code, d, r.status_code == 200, f"unread={r.json().get('unread_count') if r.status_code==200 else 0}", r.text)

    # 15. User A Marks Notification Read
    if first_notif_id:
        t0 = time.perf_counter()
        r = client.post(f"{BASE_URL}/community/notifications/{first_notif_id}/read", headers=headers_a)
        d = (time.perf_counter() - t0) * 1000
        record(f"/community/notifications/{first_notif_id}/read", "POST", r.status_code, d, r.status_code == 204, "", r.text)

    t0 = time.perf_counter()
    r = client.post(f"{BASE_URL}/community/notifications/read-all", headers=headers_a)
    d = (time.perf_counter() - t0) * 1000
    record("/community/notifications/read-all", "POST", r.status_code, d, r.status_code == 204, "", r.text)

    # 16. User A Views User B Profile & Posts
    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/community/users/{user_b_id}", headers=headers_a)
    d = (time.perf_counter() - t0) * 1000
    record(f"/community/users/{user_b_id}", "GET", r.status_code, d, r.status_code == 200, "", r.text)

    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/community/users/{user_b_id}/posts", headers=headers_a)
    d = (time.perf_counter() - t0) * 1000
    record(f"/community/users/{user_b_id}/posts", "GET", r.status_code, d, r.status_code == 200, "", r.text)

    # 17. User A Views Own Posts
    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/community/me/posts", headers=headers_a)
    d = (time.perf_counter() - t0) * 1000
    record("/community/me/posts", "GET", r.status_code, d, r.status_code == 200, "", r.text)

    # 18. User A Updates Own Post: PATCH /community/posts/{post_id}
    if post_a_id:
        t0 = time.perf_counter()
        r = client.patch(
            f"{BASE_URL}/community/posts/{post_a_id}",
            headers=headers_a,
            json={"content": "Updated: OGDC closed strong at Rs. 142.50 today with bullish momentum."}
        )
        d = (time.perf_counter() - t0) * 1000
        record(f"/community/posts/{post_a_id}", "PATCH", r.status_code, d, r.status_code == 200, "", r.text)

    # 19. User B Unlikes Post: DELETE /community/posts/{post_id}/like
    if post_a_id:
        t0 = time.perf_counter()
        r = client.delete(f"{BASE_URL}/community/posts/{post_a_id}/like", headers=headers_b)
        d = (time.perf_counter() - t0) * 1000
        record(f"/community/posts/{post_a_id}/like", "DELETE", r.status_code, d, r.status_code == 204, "", r.text)

    # 20. User B Unfollows User A: DELETE /community/users/{user_id}/follow
    t0 = time.perf_counter()
    r = client.delete(f"{BASE_URL}/community/users/{user_a_id}/follow", headers=headers_b)
    d = (time.perf_counter() - t0) * 1000
    record(f"/community/users/{user_a_id}/follow", "DELETE", r.status_code, d, r.status_code == 204, "", r.text)

    # 21. User A Deletes Reply: DELETE /community/comments/{comment_id}
    if reply_a_id:
        t0 = time.perf_counter()
        r = client.delete(f"{BASE_URL}/community/comments/{reply_a_id}", headers=headers_a)
        d = (time.perf_counter() - t0) * 1000
        record(f"/community/comments/{reply_a_id}", "DELETE", r.status_code, d, r.status_code == 204, "", r.text)

    # 22. User A Deletes Own Post: DELETE /community/posts/{post_id}
    if post_a_id:
        t0 = time.perf_counter()
        r = client.delete(f"{BASE_URL}/community/posts/{post_a_id}", headers=headers_a)
        d = (time.perf_counter() - t0) * 1000
        record(f"/community/posts/{post_a_id}", "DELETE", r.status_code, d, r.status_code == 204, "", r.text)

    print("=" * 110)
    passed_count = sum(1 for x in results if x["passed"])
    total_count = len(results)
    avg_latency = sum(x["duration_ms"] for x in results) / total_count if total_count else 0
    print(f"COMMUNITY AUDIT SUMMARY: {passed_count}/{total_count} PASSED ({passed_count/total_count*100:.1f}%) | Avg Latency: {avg_latency:.1f}ms")
    print("=" * 110)

if __name__ == "__main__":
    run_community_audit()
