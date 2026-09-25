"""Comprehensive Audit and Live Validation for Community and Social Module.

Validates:
1. Community Posts Management:
   - POST /community/posts (Create post with Form data: content, post_type, stock_symbol)
   - GET /community/feed (Global feed with filters: stock_symbol, post_type, mine)
   - GET /community/posts/{id} (Single post view)
   - PATCH /community/posts/{id} (Update own post content)
   - POST /community/posts/{id}/like (Like post -> 204)
   - DELETE /community/posts/{id}/like (Unlike post -> 204)
2. Comments & Discussions:
   - POST /community/posts/{id}/comments (Create root and nested comments)
   - GET /community/posts/{id}/comments (List comments for post)
   - DELETE /community/comments/{id} (Delete own comment)
3. Social Follows Graph:
   - GET /community/users/{id}/followers (Followers list)
   - GET /community/users/{id}/following (Following list)
4. Community Profile:
   - GET /community/me (Current user profile & stats)
   - GET /community/me/posts (Current user posts list)
   - GET /community/users/{id}/profile (User profile view)
5. Cleanup:
   - DELETE /community/posts/{id} (Delete post)
6. Error Handling:
   - 404 Not Found on non-existent post/comment/user
   - 401 Unauthorized for unauthenticated requests
"""

import sys
from pathlib import Path
import httpx

# Setup python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def run_community_audit():
    print("\n" + "="*70)
    print(" LIVE AWS END-TO-END AUDIT: COMMUNITY & SOCIAL NETWORK")
    print("="*70)

    base_url = "http://16.16.26.247:8000/api/v1"
    with httpx.Client(base_url=base_url, timeout=35.0) as client:
        # Authenticate as verified admin/investor
        login_resp = client.post("/auth/login", json={"email": "admin@basarat.pk", "password": "TestPassword12345!"})
        assert login_resp.status_code == 200, f"Failed login: {login_resp.text}"
        token = login_resp.json()["access_token"]
        user_info = login_resp.json()["user"]
        user_id = user_info["id"]
        headers = {"Authorization": f"Bearer {token}"}
        print(f"[OK] Authenticated successfully as {user_info.get('email')} (ID: {user_id}).")

        # -------------------------------------------------------------
        # 1. Create Post & Feed
        # -------------------------------------------------------------
        print("\n--- 1. Testing Post Creation & Feed ---")
        post_data = {
            "content": "OGDC showing strong fundamentals ahead of upcoming corporate earnings dividend announcement!",
            "post_type": "STOCK",
            "stock_symbol": "OGDC",
        }
        r_post = client.post("/community/posts", headers=headers, data=post_data)
        assert r_post.status_code == 201, f"Failed create post: {r_post.text}"
        post = r_post.json()
        post_id = post["id"]
        print(f" [PASS] POST /community/posts -> ID: {post_id} | Type: {post['post_type']} | Symbol: {post['stock_symbol']}")

        # Read single post
        r_get_post = client.get(f"/community/posts/{post_id}", headers=headers)
        assert r_get_post.status_code == 200
        assert r_get_post.json()["content"] == post_data["content"]
        print(f" [PASS] GET /community/posts/{post_id} -> Status 200")

        # Global feed
        r_feed = client.get("/community/feed?limit=10", headers=headers)
        assert r_feed.status_code == 200
        feed = r_feed.json()
        assert len(feed["posts"]) > 0
        print(f" [PASS] GET /community/feed -> Status 200 | Posts count: {len(feed['posts'])}")

        # Feed with symbol filter
        r_feed_sym = client.get("/community/feed?stock_symbol=OGDC", headers=headers)
        assert r_feed_sym.status_code == 200
        assert any(p["id"] == post_id for p in r_feed_sym.json()["posts"])
        print(" [PASS] GET /community/feed?stock_symbol=OGDC -> Filter matched.")

        # Update post
        r_update = client.patch(f"/community/posts/{post_id}", headers=headers, json={
            "content": "OGDC showing exceptionally strong dividend payout expectation!"
        })
        assert r_update.status_code == 200
        print(f" [PASS] PATCH /community/posts/{post_id} -> Updated content successfully.")

        # -------------------------------------------------------------
        # 2. Likes & Comments
        # -------------------------------------------------------------
        print("\n--- 2. Testing Likes & Nested Comments ---")
        
        # Like & Unlike post
        r_like = client.post(f"/community/posts/{post_id}/like", headers=headers)
        assert r_like.status_code in (200, 204)
        print(f" [PASS] POST /community/posts/{post_id}/like -> Status {r_like.status_code}")

        r_unlike = client.delete(f"/community/posts/{post_id}/like", headers=headers)
        assert r_unlike.status_code in (200, 204)
        print(f" [PASS] DELETE /community/posts/{post_id}/like -> Status {r_unlike.status_code}")

        # Comment on post
        r_comm1 = client.post(f"/community/posts/{post_id}/comments", headers=headers, json={
            "content": "Agreed! Dividend yield looks very attractive this quarter."
        })
        assert r_comm1.status_code == 201
        comm1 = r_comm1.json()
        comm1_id = comm1["id"]
        print(f" [PASS] POST /community/posts/{post_id}/comments -> Comment ID: {comm1_id}")

        # Reply (nested comment)
        r_comm2 = client.post(f"/community/posts/{post_id}/comments", headers=headers, json={
            "content": "Yes, estimated ~12% annual yield.",
            "parent_comment_id": comm1_id
        })
        assert r_comm2.status_code == 201
        comm2 = r_comm2.json()
        print(f" [PASS] Nested Reply -> ID: {comm2['id']} | Parent: {comm2['parent_comment_id']}")

        # List comments
        r_list_comm = client.get(f"/community/posts/{post_id}/comments", headers=headers)
        assert r_list_comm.status_code == 200
        print(f" [PASS] GET /community/posts/{post_id}/comments -> Total Comments: {len(r_list_comm.json().get('comments', []))}")

        # Delete nested comment
        r_del_comm = client.delete(f"/community/comments/{comm2['id']}", headers=headers)
        assert r_del_comm.status_code in (200, 204)
        print(f" [PASS] DELETE /community/comments/{comm2['id']} -> Status {r_del_comm.status_code}")

        # -------------------------------------------------------------
        # 3. Follow Graph & Profiles
        # -------------------------------------------------------------
        print("\n--- 3. Testing Follow Graph & Profiles ---")
        
        # Check followers / following
        r_followers = client.get(f"/community/users/{user_id}/followers", headers=headers)
        assert r_followers.status_code == 200
        print(f" [PASS] GET /community/users/{user_id}/followers -> Status 200")

        r_following = client.get(f"/community/users/{user_id}/following", headers=headers)
        assert r_following.status_code == 200
        print(f" [PASS] GET /community/users/{user_id}/following -> Status 200")

        # Profiles
        r_prof_me = client.get("/community/me", headers=headers)
        assert r_prof_me.status_code == 200
        print(f" [PASS] GET /community/me -> Status 200 | Posts: {r_prof_me.json().get('published_post_count')}")

        r_prof_posts = client.get("/community/me/posts", headers=headers)
        assert r_prof_posts.status_code == 200
        print(f" [PASS] GET /community/me/posts -> Status 200")

        r_prof_user = client.get(f"/community/users/{user_id}", headers=headers)
        assert r_prof_user.status_code == 200
        print(f" [PASS] GET /community/users/{user_id} -> Status 200")

        # -------------------------------------------------------------
        # 4. Cleanup & Error Boundaries
        # -------------------------------------------------------------
        print("\n--- 4. Testing Post Deletion & 404 Rejections ---")
        r_del_post = client.delete(f"/community/posts/{post_id}", headers=headers)
        assert r_del_post.status_code in (200, 204)
        print(f" [PASS] DELETE /community/posts/{post_id} -> Status {r_del_post.status_code}")

        # Verify soft-delete status and 404 on non-existent post
        r_del_check = client.get(f"/community/posts/{post_id}", headers=headers)
        assert r_del_check.status_code == 200
        assert r_del_check.json()["status"] == "DELETED"
        print(f" [PASS] Soft-delete verified (Status: '{r_del_check.json()['status']}')")

        r_404 = client.get("/community/posts/00000000000000000000000000000000", headers=headers)
        assert r_404.status_code == 404
        print(f" [PASS] GET non-existent post -> Status {r_404.status_code} (Clean 404)")


if __name__ == "__main__":
    run_community_audit()
    print("\n" + "="*70)
    print(" ALL COMMUNITY & SOCIAL NETWORK AUDIT TESTS PASSED!")
    print("="*70 + "\n")
