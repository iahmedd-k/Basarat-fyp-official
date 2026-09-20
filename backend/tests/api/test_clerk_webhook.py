"""API tests for Clerk webhook integration."""

import base64
import hashlib
import hmac
import json
import time
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import get_settings
from app.models.user import User


def _generate_svix_signature(secret: str, msg_id: str, timestamp: str, body: bytes) -> str:
    raw_secret = secret[6:] if secret.startswith("whsec_") else secret
    try:
        secret_bytes = base64.b64decode(raw_secret)
    except Exception:
        secret_bytes = raw_secret.encode("utf-8")

    to_sign = f"{msg_id}.{timestamp}.".encode("utf-8") + body
    sig = base64.b64encode(hmac.new(secret_bytes, to_sign, hashlib.sha256).digest()).decode("utf-8")
    return f"v1,{sig}"


@pytest.mark.api
class TestClerkWebhook:
    async def test_user_created_automatic_verification(self, client: AsyncClient, db_session):
        payload = {
            "type": "user.created",
            "data": {
                "id": "user_clerk_123",
                "email_addresses": [
                    {
                        "id": "idn_123",
                        "email_address": "clerkuser@example.com",
                        "verification": {"status": "verified"},
                    }
                ],
                "primary_email_address_id": "idn_123",
                "first_name": "Clerk",
                "last_name": "User",
                "username": "clerk_tester",
                "image_url": "https://img.clerk.com/avatar.png",
            },
        }

        resp = await client.post("/api/v1/webhooks/clerk", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["status"] == "synced"
        assert data["is_verified"] is True

        # Verify in DB
        res = await db_session.execute(select(User).where(User.email == "clerkuser@example.com"))
        user = res.scalars().first()
        assert user is not None
        assert user.is_verified is True
        assert user.full_name == "Clerk User"
        assert user.is_active is True
        assert user.is_admin is False

    async def test_user_created_unverified(self, client: AsyncClient, db_session):
        payload = {
            "type": "user.created",
            "data": {
                "id": "user_clerk_unverified",
                "email_addresses": [
                    {
                        "id": "idn_unver",
                        "email_address": "unverified@example.com",
                        "verification": {"status": "unverified"},
                    }
                ],
                "first_name": "Unverified",
                "last_name": "User",
            },
        }

        resp = await client.post("/api/v1/webhooks/clerk", json=payload)
        assert resp.status_code == 200
        assert resp.json()["is_verified"] is False

        res = await db_session.execute(select(User).where(User.email == "unverified@example.com"))
        user = res.scalars().first()
        assert user is not None
        assert user.is_verified is False

    async def test_user_updated(self, client: AsyncClient, db_session):
        # Create first
        create_payload = {
            "type": "user.created",
            "data": {
                "id": "user_clerk_update",
                "email_addresses": [
                    {
                        "id": "idn_up",
                        "email_address": "update_me@example.com",
                        "verification": {"status": "unverified"},
                    }
                ],
                "first_name": "Old",
                "last_name": "Name",
            },
        }
        await client.post("/api/v1/webhooks/clerk", json=create_payload)

        # Update event with verified status and new name
        update_payload = {
            "type": "user.updated",
            "data": {
                "id": "user_clerk_update",
                "email_addresses": [
                    {
                        "id": "idn_up",
                        "email_address": "update_me@example.com",
                        "verification": {"status": "verified"},
                    }
                ],
                "first_name": "New",
                "last_name": "Name",
                "image_url": "https://img.clerk.com/new.png",
            },
        }
        resp = await client.post("/api/v1/webhooks/clerk", json=update_payload)
        assert resp.status_code == 200
        assert resp.json()["is_verified"] is True

        res = await db_session.execute(select(User).where(User.email == "update_me@example.com"))
        user = res.scalars().first()
        assert user.full_name == "New Name"
        assert user.is_verified is True
        assert user.avatar_url == "https://img.clerk.com/new.png"

    async def test_user_deleted(self, client: AsyncClient, db_session):
        # Create user
        payload = {
            "type": "user.created",
            "data": {
                "id": "user_clerk_del",
                "email_addresses": [{"email_address": "to_delete@example.com", "verification": {"status": "verified"}}],
            },
        }
        await client.post("/api/v1/webhooks/clerk", json=payload)

        # Send user.deleted
        del_payload = {
            "type": "user.deleted",
            "data": {
                "id": "user_clerk_del",
                "email_addresses": [{"email_address": "to_delete@example.com"}],
            },
        }
        resp = await client.post("/api/v1/webhooks/clerk", json=del_payload)
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

        res = await db_session.execute(select(User).where(User.email == "to_delete@example.com"))
        user = res.scalars().first()
        assert user is not None
        assert user.is_active is False

    async def test_signature_verification(self, client: AsyncClient, monkeypatch):
        test_secret = "whsec_testsecret1234567890abcdef"
        settings = get_settings()
        monkeypatch.setattr(settings, "CLERK_WEBHOOK_SECRET", test_secret)

        body_dict = {
            "type": "user.created",
            "data": {
                "email_addresses": [{"email_address": "signed@example.com", "verification": {"status": "verified"}}],
            },
        }
        body_bytes = json.dumps(body_dict).encode("utf-8")
        msg_id = "msg_test_1"
        timestamp = str(int(time.time()))
        valid_sig = _generate_svix_signature(test_secret, msg_id, timestamp, body_bytes)

        # Valid signature succeeds
        resp = await client.post(
            "/api/v1/webhooks/clerk",
            content=body_bytes,
            headers={
                "Content-Type": "application/json",
                "svix-id": msg_id,
                "svix-timestamp": timestamp,
                "svix-signature": valid_sig,
            },
        )
        assert resp.status_code == 200

        # Invalid signature fails with 400
        resp_invalid = await client.post(
            "/api/v1/webhooks/clerk",
            content=body_bytes,
            headers={
                "Content-Type": "application/json",
                "svix-id": msg_id,
                "svix-timestamp": timestamp,
                "svix-signature": "v1,invalidsignature",
            },
        )
        assert resp_invalid.status_code == 400
