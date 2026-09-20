"""Comprehensive pytest test suite testing every single alert, notification, and device endpoint."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert, AlertRule
from app.models.community import CommunityNotification, NotificationType
from app.models.user import Device, User


@pytest.mark.asyncio
async def test_full_alert_and_notification_lifecycle(client: AsyncClient, auth_headers: dict, db_session: AsyncSession, test_user: User):
    # -------------------------------------------------------------
    # 1. Alert Rules Endpoints
    # -------------------------------------------------------------
    # GET rules initially
    resp = await client.get("/api/v1/alerts/rules", headers=auth_headers)
    assert resp.status_code == 200
    initial_rules = resp.json()
    assert isinstance(initial_rules, list)

    # POST create rule
    create_resp = await client.post(
        "/api/v1/alerts/rules",
        headers=auth_headers,
        json={"condition": "price_above", "threshold": 250.0, "stock_id": None},
    )
    assert create_resp.status_code == 201
    rule_data = create_resp.json()
    rule_id = rule_data["id"]
    assert rule_data["condition"] == "price_above"
    assert rule_data["threshold"] == 250.0
    assert rule_data["is_active"] is True

    # PATCH update rule
    patch_resp = await client.patch(
        f"/api/v1/alerts/rules/{rule_id}",
        headers=auth_headers,
        json={"threshold": 275.5, "is_active": False},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["threshold"] == 275.5
    assert patch_resp.json()["is_active"] is False

    # -------------------------------------------------------------
    # 2. Alerts (Financial / Risk) Endpoints
    # -------------------------------------------------------------
    # Seed an alert for user
    alert_obj = Alert(
        user_id=test_user.id,
        rule_id=rule_id,
        title="[HIGH] VaR Threshold Breach",
        message="VaR(95%) exceeded 3% threshold on portfolio",
        is_read=False,
    )
    db_session.add(alert_obj)
    await db_session.flush()

    # GET alerts
    alerts_resp = await client.get("/api/v1/alerts?limit=10", headers=auth_headers)
    assert alerts_resp.status_code == 200
    alerts_list = alerts_resp.json()
    assert len(alerts_list) >= 1
    found_alert = next((a for a in alerts_list if a["id"] == alert_obj.id), None)
    assert found_alert is not None
    assert found_alert["is_read"] is False

    # PATCH mark alert read
    mark_alert_resp = await client.patch(f"/api/v1/alerts/{alert_obj.id}/read", headers=auth_headers)
    assert mark_alert_resp.status_code == 204

    # -------------------------------------------------------------
    # 3. Notification Center Endpoints (/notifications)
    # -------------------------------------------------------------
    notif_resp = await client.get("/api/v1/notifications?limit=10", headers=auth_headers)
    assert notif_resp.status_code == 200
    notif_data = notif_resp.json()
    assert "notifications" in notif_data
    assert "total" in notif_data
    assert "has_more" in notif_data

    # Mark notification read via /notifications/{id}/read
    mark_notif_resp = await client.patch(f"/api/v1/notifications/{alert_obj.id}/read", headers=auth_headers)
    assert mark_notif_resp.status_code == 204

    # -------------------------------------------------------------
    # 4. User Notification Preferences Endpoint
    # -------------------------------------------------------------
    pref_resp = await client.patch(
        "/api/v1/users/me/notification-preferences",
        headers=auth_headers,
        json={
            "channels": ["push", "in_app"],
            "categories": ["price", "risk"],
        },
    )
    assert pref_resp.status_code == 200
    pref_data = pref_resp.json()
    assert "push" in pref_data["channels"]
    assert "risk" in pref_data["categories"]

    # -------------------------------------------------------------
    # 5. Device Registration Endpoints (FCM push token)
    # -------------------------------------------------------------
    device_resp = await client.post(
        "/api/v1/devices/register",
        headers=auth_headers,
        json={
            "fcm_token": "fcm_test_token_1234567890",
            "platform": "android",
            "device_name": "Pixel 7 Pro",
        },
    )
    assert device_resp.status_code == 201
    device_data = device_resp.json()
    device_id = device_data["id"]
    assert device_data["platform"] == "android"
    assert device_data["is_active"] is True

    # DELETE unregister device
    unreg_resp = await client.delete(f"/api/v1/devices/{device_id}", headers=auth_headers)
    assert unreg_resp.status_code == 204

    # -------------------------------------------------------------
    # 6. Community Social Notifications Endpoints
    # -------------------------------------------------------------
    # Seed community notification
    comm_notif = CommunityNotification(
        recipient_id=test_user.id,
        actor_id=None,
        type=NotificationType.POST_LIKED.value,
        title="New Like",
        message="Someone liked your post",
        is_read=False,
    )
    db_session.add(comm_notif)
    await db_session.flush()

    # GET community notifications
    comm_list_resp = await client.get("/api/v1/community/notifications", headers=auth_headers)
    assert comm_list_resp.status_code == 200
    comm_data = comm_list_resp.json()
    assert len(comm_data["notifications"]) >= 1

    # GET unread count
    unread_count_resp = await client.get("/api/v1/community/notifications/unread-count", headers=auth_headers)
    assert unread_count_resp.status_code == 200
    assert unread_count_resp.json()["unread_count"] >= 1

    # POST mark single community notification read
    mark_comm_resp = await client.post(f"/api/v1/community/notifications/{comm_notif.id}/read", headers=auth_headers)
    assert mark_comm_resp.status_code == 204

    # POST mark all read
    read_all_resp = await client.post("/api/v1/community/notifications/read-all", headers=auth_headers)
    assert read_all_resp.status_code == 204

    # -------------------------------------------------------------
    # 7. Cleanup & Rule Deletion
    # -------------------------------------------------------------
    del_rule_resp = await client.delete(f"/api/v1/alerts/rules/{rule_id}", headers=auth_headers)
    assert del_rule_resp.status_code == 204
