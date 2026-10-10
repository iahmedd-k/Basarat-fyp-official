"""API tests for alerts and notifications endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


@pytest.mark.api
class TestAlertRules:
    async def test_get_rules_empty(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/alerts/rules", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    async def test_create_rule(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/alerts/rules",
            headers=auth_headers,
            json={"condition": "price_above", "threshold": 200.0},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["condition"] == "price_above"
        assert data["threshold"] == 200.0

    async def test_create_duplicate_rule_deduplication(self, client: AsyncClient, auth_headers):
        # Create rule first time
        resp1 = await client.post(
            "/api/v1/alerts/rules",
            headers=auth_headers,
            json={"condition": "pct_change_up", "threshold": 5.0},
        )
        assert resp1.status_code == 201
        rule1_id = resp1.json()["id"]

        # Duplicate submission with identical parameters should return existing rule
        resp2 = await client.post(
            "/api/v1/alerts/rules",
            headers=auth_headers,
            json={"condition": "pct_change_up", "threshold": 5.0},
        )
        assert resp2.status_code == 201
        assert resp2.json()["id"] == rule1_id

    async def test_create_rule_invalid(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/alerts/rules",
            headers=auth_headers,
            json={"condition": "", "threshold": 200.0},
        )
        assert resp.status_code == 422

    async def test_update_rule(self, client: AsyncClient, auth_headers, db_session: AsyncSession, test_user: User):
        from app.models.alert import AlertRule
        rule = AlertRule(
            user_id=test_user.id, condition="price_above",
            threshold=200.0, is_active=True,
        )
        db_session.add(rule)
        await db_session.flush()

        resp = await client.patch(
            f"/api/v1/alerts/rules/{rule.id}",
            headers=auth_headers,
            json={"threshold": 250.0},
        )
        assert resp.status_code == 200
        assert resp.json()["threshold"] == 250.0

    async def test_delete_rule(self, client: AsyncClient, auth_headers, db_session: AsyncSession, test_user: User):
        from app.models.alert import AlertRule
        rule = AlertRule(
            user_id=test_user.id, condition="price_above",
            threshold=200.0, is_active=True,
        )
        db_session.add(rule)
        await db_session.flush()

        resp = await client.delete(
            f"/api/v1/alerts/rules/{rule.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 204

    async def test_rules_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/alerts/rules")
        assert resp.status_code in (401, 403)


@pytest.mark.api
class TestAlerts:
    async def test_get_alerts(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/alerts", headers=auth_headers)
        assert resp.status_code == 200

    async def test_mark_alert_read(self, client: AsyncClient, auth_headers, db_session: AsyncSession, test_user: User):
        from app.models.alert import Alert
        alert = Alert(
            user_id=test_user.id, title="Test Alert",
            message="test", is_read=False,
        )
        db_session.add(alert)
        await db_session.flush()

        resp = await client.patch(
            f"/api/v1/alerts/{alert.id}/read",
            headers=auth_headers,
        )
        assert resp.status_code == 204

    async def test_mark_all_alerts_read(self, client: AsyncClient, auth_headers, db_session: AsyncSession, test_user: User):
        from app.models.alert import Alert
        a1 = Alert(user_id=test_user.id, title="A1", message="m1", is_read=False)
        a2 = Alert(user_id=test_user.id, title="A2", message="m2", is_read=False)
        db_session.add_all([a1, a2])
        await db_session.flush()

        resp = await client.patch("/api/v1/alerts/read-all", headers=auth_headers)
        assert resp.status_code == 204


@pytest.mark.api
class TestNotifications:
    async def test_get_notifications(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/notifications", headers=auth_headers)
        assert resp.status_code == 200

    async def test_mark_notification_read(self, client: AsyncClient, auth_headers, db_session: AsyncSession, test_user: User):
        from app.models.alert import Alert
        notification = Alert(
            user_id=test_user.id, title="Notification",
            message="test", is_read=False,
        )
        db_session.add(notification)
        await db_session.flush()

        resp = await client.patch(
            f"/api/v1/notifications/{notification.id}/read",
            headers=auth_headers,
        )
        assert resp.status_code == 204

    async def test_mark_all_notifications_read(self, client: AsyncClient, auth_headers, db_session: AsyncSession, test_user: User):
        from app.models.alert import Alert
        n1 = Alert(user_id=test_user.id, title="N1", message="nm1", is_read=False)
        n2 = Alert(user_id=test_user.id, title="N2", message="nm2", is_read=False)
        db_session.add_all([n1, n2])
        await db_session.flush()

        resp = await client.patch("/api/v1/notifications/read-all", headers=auth_headers)
        assert resp.status_code == 204
