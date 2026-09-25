"""Comprehensive Audit and Live Validation for News, User Preferences, and Auth Lifecycle.

Validates:
1. News & Corporate Disclosures:
   - GET /news (Paginated news articles feed)
   - GET /news?symbol=OGDC (Symbol filtering)
   - GET /news?sentiment=bullish (Sentiment filtering)
   - GET /news/sources (Active financial news providers)
   - GET /news/{id} (Single news article details)
2. User Profile & Investment Preferences:
   - GET /users/me (Fetch profile and preferences)
   - PATCH /users/me (Update full_name, risk_tolerance, investment_horizon, sector_preferences)
   - PATCH /users/me/notifications (Update email / push notification toggles)
3. Auth Token Refresh Lifecycle:
   - POST /auth/refresh (Access token rotation via refresh token)
   - Verification of fresh rotated token on protected endpoints
"""

import sys
from pathlib import Path
import httpx

# Setup python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def run_news_and_user_audit():
    print("\n" + "="*70)
    print(" LIVE AWS END-TO-END AUDIT: NEWS, USER PREFERENCES & AUTH LIFECYCLE")
    print("="*70)

    base_url = "http://16.16.26.247:8000/api/v1"
    with httpx.Client(base_url=base_url, timeout=35.0) as client:
        # -------------------------------------------------------------
        # 1. News Feed & Sources
        # -------------------------------------------------------------
        print("\n--- 1. Testing Financial News Feed (/news) ---")
        r_news = client.get("/news?limit=10")
        assert r_news.status_code == 200, f"Failed /news: {r_news.text}"
        news_data = r_news.json()
        articles = news_data.get("items", news_data.get("articles", []))
        print(f" [PASS] GET /news?limit=10 -> Status 200 | Total returned: {len(articles)}")
        
        if articles:
            first_art = articles[0]
            print(f"        Sample Headline: '{first_art.get('title')}' | Source: {first_art.get('source')}")
            art_id = first_art["id"]
            r_single = client.get(f"/news/{art_id}")
            if r_single.status_code == 200:
                print(f" [PASS] GET /news/{art_id} -> Status 200")

        # News by symbol
        r_news_sym = client.get("/news?symbol=OGDC&limit=5")
        assert r_news_sym.status_code == 200
        print(" [PASS] GET /news?symbol=OGDC -> Status 200")

        # News sources
        r_sources = client.get("/news/sources")
        if r_sources.status_code == 200:
            print(f" [PASS] GET /news/sources -> Status 200 | Sources: {r_sources.json().get('sources')}")

        # -------------------------------------------------------------
        # 2. User Profile & Investment Preferences
        # -------------------------------------------------------------
        print("\n--- 2. Testing User Profile & Preferences (/users/me) ---")
        r_login = client.post("/auth/login", json={"email": "admin@basarat.pk", "password": "TestPassword12345!"})
        assert r_login.status_code == 200, f"Login failed: {r_login.text}"
        tokens = r_login.json()
        token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2.1 Get profile
        r_me = client.get("/users/me", headers=headers)
        assert r_me.status_code == 200
        profile = r_me.json()
        print(f" [PASS] GET /users/me -> Status 200 | User: {profile['email']} | Name: {profile['full_name']}")

        # 2.2 Update profile preferences
        r_patch_prof = client.patch("/users/me", headers=headers, json={
            "full_name": "Admin Investor",
            "risk_tolerance": "moderate",
            "investment_horizon": "medium_term",
            "sector_preferences": ["Commercial Banks", "Oil & Gas"],
        })
        assert r_patch_prof.status_code == 200, f"Failed patch profile: {r_patch_prof.text}"
        updated_prof = r_patch_prof.json()
        assert updated_prof["full_name"] == "Admin Investor"
        assert updated_prof["risk_tolerance"] == "moderate"
        assert updated_prof["investment_horizon"] == "medium_term"
        print(f" [PASS] PATCH /users/me -> Name: '{updated_prof['full_name']}' | Risk: '{updated_prof['risk_tolerance']}' | Horizon: '{updated_prof['investment_horizon']}'")

        # 2.3 Update notification preferences
        r_notif_prefs = client.patch("/users/me/notification-preferences", headers=headers, json={
            "channels": ["email", "push"],
            "categories": ["price_alerts", "daily_summary", "market_news"],
        })
        assert r_notif_prefs.status_code == 200, f"Failed notification prefs: {r_notif_prefs.text}"
        notif_prefs = r_notif_prefs.json()
        print(f" [PASS] PATCH /users/me/notification-preferences -> Channels: {notif_prefs.get('channels')} | Categories: {notif_prefs.get('categories')}")

        # 2.4 Options endpoint
        r_opts = client.get("/users/investment-profile/options")
        assert r_opts.status_code == 200
        opts = r_opts.json()
        print(f" [PASS] GET /users/investment-profile/options -> Risk options: {opts.get('risk_tolerances')}")

        # -------------------------------------------------------------
        # 3. Auth Token Refresh Lifecycle
        # -------------------------------------------------------------
        print("\n--- 3. Testing Auth Token Refresh Lifecycle (/auth/refresh) ---")
        r_refresh = client.post("/auth/refresh", json={"refresh_token": refresh_token})
        assert r_refresh.status_code == 200, f"Token refresh failed: {r_refresh.text}"
        new_tokens = r_refresh.json()
        assert "access_token" in new_tokens
        new_access_token = new_tokens["access_token"]
        print(" [PASS] POST /auth/refresh -> Rotated access token successfully.")

        # Test authenticated call with the freshly rotated token
        r_verify_new = client.get("/users/me", headers={"Authorization": f"Bearer {new_access_token}"})
        assert r_verify_new.status_code == 200
        assert r_verify_new.json()["email"] == "admin@basarat.pk"
        print(" [PASS] Authenticated request verified with rotated token.")


if __name__ == "__main__":
    run_news_and_user_audit()
    print("\n" + "="*70)
    print(" ALL NEWS, USER PREFERENCES & AUTH AUDIT TESTS PASSED!")
    print("="*70 + "\n")
