import urllib.request
import urllib.error
import json
import time

BASE_URL = "http://193.123.84.223:8000/api/v1"

def http_request(method, path, data=None, token=None):
    url = f"{BASE_URL}{path}"
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            latency_ms = (time.perf_counter() - t0) * 1000
            res_body = resp.read().decode("utf-8")
            res_json = json.loads(res_body) if res_body else {}
            return resp.status, latency_ms, res_json, None
    except urllib.error.HTTPError as e:
        latency_ms = (time.perf_counter() - t0) * 1000
        err_body = e.read().decode("utf-8")
        try:
            err_json = json.loads(err_body)
        except Exception:
            err_json = {"raw": err_body}
        return e.code, latency_ms, None, err_json
    except Exception as e:
        latency_ms = (time.perf_counter() - t0) * 1000
        return 0, latency_ms, None, str(e)

if __name__ == "__main__":
    print("==========================================================================")
    print("   COMMUNITY ENDPOINTS & FULL CRUD LIFECYCLE LATENCY BENCHMARK")
    print("==========================================================================")
    
    print("\n--- 1. Authenticating Demo User ---")
    status, lat, res, err = http_request("POST", "/auth/login", {
        "email": "demo@basarat.pk",
        "password": "TestPassword12345"
    })
    print(f"POST /auth/login -> status={status}, latency={lat:6.2f}ms")
    
    token = None
    user_id = None
    if status == 200 and res:
        token = res.get("access_token") or (res.get("tokens") or {}).get("access_token")
        user = res.get("user") or {}
        user_id = user.get("id")
        print(f"Logged in: {user.get('email')} (id: {user_id}, username: {user.get('username')})")
    else:
        print(f"Login failed: {err}")
        exit(1)

    print("\n--- 2. Benchmarking Community Read Endpoints Latency ---")
    endpoints_to_test = [
        ("GET", "/community/feed?tab=for_you&limit=20", None, "Feed (For You Tab)"),
        ("GET", "/community/posts?limit=20", None, "Posts / Feed Alias"),
        ("GET", "/community/feed?tab=following&limit=20", None, "Feed (Following Tab)"),
        ("GET", "/community/feed?ticker=OGDC&limit=20", None, "Feed (Ticker Tab: OGDC)"),
        ("GET", "/community/posts/stock/OGDC?limit=20", None, "Stock Filtered Posts (OGDC)"),
        ("GET", "/community/posts/market?limit=20", None, "General Market Posts"),
        ("GET", "/community/posts/search?q=OGDC", None, "Search Posts (q=OGDC)"),
        ("GET", "/community/trending", None, "Community Trending (Tickers & Posts)"),
        ("GET", "/community/me", None, "My Community Profile"),
        ("GET", "/community/me/posts?limit=20", None, "My Posts"),
        ("GET", f"/community/users/{user_id}", None, "User Public Profile"),
        ("GET", f"/community/users/{user_id}/profile", None, "User Unified Profile (Hydrated)"),
        ("GET", f"/community/users/{user_id}/posts?limit=20", None, "User Posts"),
        ("GET", f"/community/users/{user_id}/followers", None, "User Followers"),
        ("GET", f"/community/users/{user_id}/following", None, "User Following"),
        ("GET", f"/community/users/{user_id}/follow-status", None, "User Follow Status"),
        ("GET", "/community/notifications?page=1&limit=20", None, "Community Notifications"),
        ("GET", "/community/notifications/unread-count", None, "Notifications Unread Count"),
    ]

    for method, path, data, name in endpoints_to_test:
        st, l_ms, r_j, er = http_request(method, path, data, token=token)
        status_str = f"status={st}"
        print(f"[{method:4}] {path:48} -> {status_str:12} | {l_ms:7.2f}ms | {name}")
        if er and st not in (200, 201, 204):
            print(f"       ERROR: {er}")

    print("\n--- 3. Benchmarking Complete Community CRUD Lifecycle Latency ---")
    
    # 3.1 Create Post (JSON payload)
    post_payload = {
        "content": f"Automated benchmark post testing community latency at {time.strftime('%Y-%m-%d %H:%M:%S')}. Analyzing $OGDC and #PPL fundamentals.",
        "post_type": "STOCK",
        "stock_symbol": "OGDC"
    }
    st, l_ms, post_res, er = http_request("POST", "/community/posts", post_payload, token=token)
    print(f"[POST] /community/posts                                 -> status={st}     | {l_ms:7.2f}ms | Create Post (JSON)")
    created_post_id = (post_res or {}).get("id")
    if not created_post_id:
        print("Failed to create post:", er)
        exit(1)
    print(f"       Created Post ID: {created_post_id}")

    # 3.2 Get Post Detail
    st, l_ms, detail_res, er = http_request("GET", f"/community/posts/{created_post_id}", token=token)
    print(f"[GET ] /community/posts/{created_post_id[:8]}...             -> status={st}     | {l_ms:7.2f}ms | Get Post Detail")

    # 3.3 Update Post (PUT)
    update_payload = {
        "content": f"Updated benchmark post content at {time.strftime('%Y-%m-%d %H:%M:%S')}. Strong growth in OGDC."
    }
    st, l_ms, up_res, er = http_request("PUT", f"/community/posts/{created_post_id}", update_payload, token=token)
    print(f"[PUT ] /community/posts/{created_post_id[:8]}...             -> status={st}     | {l_ms:7.2f}ms | Update Post (PUT)")

    # 3.4 Update Post (PATCH)
    patch_payload = {
        "content": f"Patched benchmark post content at {time.strftime('%Y-%m-%d %H:%M:%S')}. Bullish outlook."
    }
    st, l_ms, patch_res, er = http_request("PATCH", f"/community/posts/{created_post_id}", patch_payload, token=token)
    print(f"[PATC] /community/posts/{created_post_id[:8]}...             -> status={st}     | {l_ms:7.2f}ms | Update Post (PATCH)")

    # 3.5 Like Post
    st, l_ms, like_res, er = http_request("POST", f"/community/posts/{created_post_id}/like", token=token)
    print(f"[POST] /community/posts/{created_post_id[:8]}.../like        -> status={st}     | {l_ms:7.2f}ms | Like Post")

    # 3.6 Bookmark Post
    st, l_ms, bm_res, er = http_request("POST", f"/community/posts/{created_post_id}/bookmark", token=token)
    print(f"[POST] /community/posts/{created_post_id[:8]}.../bookmark    -> status={st}     | {l_ms:7.2f}ms | Bookmark Post")

    # 3.7 Unbookmark Post
    st, l_ms, ubm_res, er = http_request("DELETE", f"/community/posts/{created_post_id}/bookmark", token=token)
    print(f"[DEL ] /community/posts/{created_post_id[:8]}.../bookmark    -> status={st}     | {l_ms:7.2f}ms | Unbookmark Post")

    # 3.8 Unlike Post
    st, l_ms, unlike_res, er = http_request("DELETE", f"/community/posts/{created_post_id}/like", token=token)
    print(f"[DEL ] /community/posts/{created_post_id[:8]}.../like        -> status={st}     | {l_ms:7.2f}ms | Unlike Post")

    # 3.9 Create Comment
    comment_payload = {
        "content": "Benchmarking community comments response time and performance."
    }
    st, l_ms, comm_res, er = http_request("POST", f"/community/posts/{created_post_id}/comments", comment_payload, token=token)
    print(f"[POST] /community/posts/{created_post_id[:8]}.../comments    -> status={st}     | {l_ms:7.2f}ms | Create Comment")
    created_comment_id = (comm_res or {}).get("id")

    # 3.10 List Comments
    st, l_ms, list_comm_res, er = http_request("GET", f"/community/posts/{created_post_id}/comments", token=token)
    print(f"[GET ] /community/posts/{created_post_id[:8]}.../comments    -> status={st}     | {l_ms:7.2f}ms | List Comments")

    # 3.11 Create Reply to Comment
    if created_comment_id:
        reply_payload = {
            "content": "This is a nested benchmark reply to test thread latency.",
            "parent_comment_id": created_comment_id
        }
        st, l_ms, reply_res, er = http_request("POST", f"/community/posts/{created_post_id}/comments", reply_payload, token=token)
        print(f"[POST] /community/posts/.../comments (Reply)       -> status={st}     | {l_ms:7.2f}ms | Create Comment Reply")
        created_reply_id = (reply_res or {}).get("id")

        # 3.12 Get Comment Replies
        st, l_ms, get_replies_res, er = http_request("GET", f"/community/comments/{created_comment_id}/replies", token=token)
        print(f"[GET ] /community/comments/{created_comment_id[:8]}.../replies -> status={st}     | {l_ms:7.2f}ms | Get Comment Replies")

        # 3.13 Delete Reply Comment
        if created_reply_id:
            st, l_ms, del_r_res, er = http_request("DELETE", f"/community/comments/{created_reply_id}", token=token)
            print(f"[DEL ] /community/comments/{created_reply_id[:8]}...         -> status={st}     | {l_ms:7.2f}ms | Delete Comment Reply")

        # 3.14 Delete Parent Comment
        st, l_ms, del_c_res, er = http_request("DELETE", f"/community/comments/{created_comment_id}", token=token)
        print(f"[DEL ] /community/comments/{created_comment_id[:8]}...         -> status={st}     | {l_ms:7.2f}ms | Delete Parent Comment")

    # 3.15 Delete Post
    st, l_ms, del_res, er = http_request("DELETE", f"/community/posts/{created_post_id}", token=token)
    print(f"[DEL ] /community/posts/{created_post_id[:8]}...             -> status={st}     | {l_ms:7.2f}ms | Delete Post")

    print("\n==========================================================================")
    print("   BENCHMARK COMPLETED SUCCESSFULLY")
    print("==========================================================================")
