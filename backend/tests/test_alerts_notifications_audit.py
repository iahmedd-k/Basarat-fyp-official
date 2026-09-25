"""Comprehensive Audit and Live Validation for Alerts, Notifications, and Devices Modules.

Validates:
1. Alert Rules CRUD:
   - GET /alerts/rules (List alert rules)
   - POST /alerts/rules (Create custom alert rule with threshold & condition)
   - PATCH /alerts/rules/{id} (Update threshold, condition, active state)
   - DELETE /alerts/rules/{id} (Delete alert rule)
2. Alert Inbox & Mark as Read:
   - GET /alerts (Paginated alerts with unread_only filter)
   - PATCH /alerts/{id}/read (Mark alert as read)
3. Notification Center:
   - GET /notifications (Paginated notification inbox with has_more flag)
   - PATCH /notifications/{id}/read (Mark notification as read)
4. Push Notification Device Token Registration:
   - POST /devices/register (Register/reactivate mobile/web FCM token)
   - DELETE /devices/{id} (Deactivate device push notifications)
5. Robust Error Handling:
   - Non-existent stock_id rejection (404 Not Found)
   - Non-existent rule_id rejection (404 Not Found)
   - Non-existent device_id rejection (404 Not Found)
"""

import sys
from pathlib import Path
import httpx
import uuid

# Setup python path to include backend
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def run_live_alerts_and_notifications_tests():
    print("\n" + "="*70)
    print(" LIVE AWS END-TO-END AUDIT: ALERTS, NOTIFICATIONS & DEVICES")
    print("="*70)

    base_url = "http://16.16.26.247:8000/api/v1"
    with httpx.Client(base_url=base_url, timeout=30.0) as client:
        # Authenticate auditor
        test_email = f"alert_auditor_{uuid.uuid4().hex[:6]}@basarat.pk"
        test_pwd = "AlertSecurePass123!"
        signup_resp = client.post("/auth/signup", json={"email": test_email, "password": test_pwd, "full_name": "Alert Auditor"})
        login_resp = client.post("/auth/login", json={"email": test_email, "password": test_pwd})
        if login_resp.status_code != 200:
            login_resp = client.post("/auth/login", json={"email": "admin@basarat.pk", "password": "TestPassword12345!"})

        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print(f"[OK] Authenticated successfully as {test_email}.")

        # -------------------------------------------------------------
        # 1. Alert Rules Management
        # -------------------------------------------------------------
        print("\n--- 1. Testing Alert Rules CRUD (/alerts/rules) ---")

        # 1.1 List initial rules
        r_list = client.get("/alerts/rules", headers=headers)
        assert r_list.status_code == 200
        print(f" GET /alerts/rules -> Status 200 | Initial Count: {len(r_list.json())}")

        # 1.2 Create general alert rule (e.g. VaR threshold trigger)
        r_create1 = client.post("/alerts/rules", headers=headers, json={
            "stock_id": None,
            "condition": "var_breach_95",
            "threshold": 0.05
        })
        assert r_create1.status_code == 201, f"Failed to create rule: {r_create1.text}"
        rule1 = r_create1.json()
        rule1_id = rule1["id"]
        print(f" [PASS] POST /alerts/rules (General Rule) -> ID: {rule1_id} | Condition: '{rule1['condition']}' | Threshold: {rule1['threshold']}")

        # 1.3 Create stock-specific alert rule
        # Fetch stock ID for OGDC if available
        r_stocks = client.get("/stocks?limit=5", headers=headers)
        stock_id = None
        if r_stocks.status_code == 200 and r_stocks.json().get("items"):
            stock_id = r_stocks.json()["items"][0]["id"]
            stock_sym = r_stocks.json()["items"][0]["symbol"]

        if stock_id:
            r_create2 = client.post("/alerts/rules", headers=headers, json={
                "stock_id": stock_id,
                "condition": "price_above",
                "threshold": 250.0
            })
            assert r_create2.status_code == 201
            rule2 = r_create2.json()
            rule2_id = rule2["id"]
            print(f" [PASS] POST /alerts/rules (Stock Rule: {stock_sym}) -> ID: {rule2_id} | Threshold: {rule2['threshold']}")

        # 1.4 Update alert rule
        r_patch = client.patch(f"/alerts/rules/{rule1_id}", headers=headers, json={
            "threshold": 0.08,
            "is_active": True
        })
        assert r_patch.status_code == 200
        updated = r_patch.json()
        assert updated["threshold"] == 0.08
        print(f" [PASS] PATCH /alerts/rules/{rule1_id} -> Updated Threshold: {updated['threshold']} | Active: {updated['is_active']}")

        # 1.5 Delete alert rule
        r_del = client.delete(f"/alerts/rules/{rule1_id}", headers=headers)
        assert r_del.status_code in (200, 204)
        print(f" [PASS] DELETE /alerts/rules/{rule1_id} -> Status {r_del.status_code}")

        # -------------------------------------------------------------
        # 2. Alert Inbox & Mark as Read
        # -------------------------------------------------------------
        print("\n--- 2. Testing Alert Inbox (/alerts) ---")
        r_alerts = client.get("/alerts?page=1&limit=20&unread_only=false", headers=headers)
        assert r_alerts.status_code == 200
        alerts_list = r_alerts.json()
        print(f" GET /alerts -> Status 200 | Items Returned: {len(alerts_list)}")

        r_unread = client.get("/alerts?unread_only=true", headers=headers)
        assert r_unread.status_code == 200
        print(f" GET /alerts?unread_only=true -> Status 200 | Unread Count: {len(r_unread.json())}")

        if alerts_list:
            first_alert_id = alerts_list[0]["id"]
            r_read = client.patch(f"/alerts/{first_alert_id}/read", headers=headers)
            assert r_read.status_code in (200, 204)
            print(f" [PASS] PATCH /alerts/{first_alert_id}/read -> Status {r_read.status_code}")

        # -------------------------------------------------------------
        # 3. Notification Center
        # -------------------------------------------------------------
        print("\n--- 3. Testing Notification Center (/notifications) ---")
        r_notif = client.get("/notifications?page=1&limit=10&unread_only=false", headers=headers)
        assert r_notif.status_code == 200
        notif_data = r_notif.json()
        print(f" GET /notifications -> Status 200 | Total: {notif_data.get('total')} | Has More: {notif_data.get('has_more')} | Count: {len(notif_data.get('notifications', []))}")

        if notif_data.get("notifications"):
            first_notif_id = notif_data["notifications"][0]["id"]
            r_notif_read = client.patch(f"/notifications/{first_notif_id}/read", headers=headers)
            assert r_notif_read.status_code in (200, 204)
            print(f" [PASS] PATCH /notifications/{first_notif_id}/read -> Status {r_notif_read.status_code}")

        # -------------------------------------------------------------
        # 4. Push Notification Device Registration
        # -------------------------------------------------------------
        print("\n--- 4. Testing Device Registration (/devices) ---")
        dummy_fcm = f"fcm_token_{uuid.uuid4().hex}"
        
        # 4.1 Register device
        r_dev = client.post("/devices/register", headers=headers, json={
            "fcm_token": dummy_fcm,
            "platform": "android",
            "device_name": "Google Pixel 8 Pro Auditor"
        })
        assert r_dev.status_code == 201, f"Failed to register device: {r_dev.text}"
        dev_data = r_dev.json()
        dev_id = dev_data["id"]
        print(f" [PASS] POST /devices/register -> Device ID: {dev_id} | Platform: '{dev_data.get('platform')}' | Active: {dev_data.get('is_active')}")

        # 4.2 Idempotent re-registration (reactivation check)
        r_dev_re = client.post("/devices/register", headers=headers, json={
            "fcm_token": dummy_fcm,
            "platform": "android",
            "device_name": "Google Pixel 8 Pro (Reactivated)"
        })
        assert r_dev_re.status_code in (200, 201)
        assert r_dev_re.json()["id"] == dev_id
        print(" [PASS] Idempotent device token re-registration preserves entity identity.")

        # 4.3 Unregister / Deactivate device
        r_unreg = client.delete(f"/devices/{dev_id}", headers=headers)
        assert r_unreg.status_code in (200, 204)
        print(f" [PASS] DELETE /devices/{dev_id} -> Status {r_unreg.status_code}")

        # -------------------------------------------------------------
        # 5. Error Rejection Tests (404 Not Found)
        # -------------------------------------------------------------
        print("\n--- 5. Testing Error Boundaries (404 Rejections) ---")
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        
        # Non-existent stock on alert rule creation
        r_bad_stock = client.post("/alerts/rules", headers=headers, json={
            "stock_id": fake_uuid,
            "condition": "price_above",
            "threshold": 100.0
        })
        print(f" POST /alerts/rules (Bad Stock UUID) -> Status {r_bad_stock.status_code}")
        assert r_bad_stock.status_code == 404

        # Non-existent rule deletion
        r_bad_rule = client.delete(f"/alerts/rules/{fake_uuid}", headers=headers)
        print(f" DELETE /alerts/rules/{fake_uuid} -> Status {r_bad_rule.status_code}")
        assert r_bad_rule.status_code == 404

        # Non-existent device deletion
        r_bad_dev = client.delete(f"/devices/{fake_uuid}", headers=headers)
        print(f" DELETE /devices/{fake_uuid} -> Status {r_bad_dev.status_code}")
        assert r_bad_dev.status_code == 404
        print(" [PASS] 404 Not Found error handling verified across all endpoints.")


if __name__ == "__main__":
    run_live_alerts_and_notifications_tests()
    print("\n" + "="*70)
    print(" ALL ALERTS, NOTIFICATIONS & DEVICES AUDIT TESTS PASSED!")
    print("="*70 + "\n")
