"""Webhooks handler for external services (Clerk Auth, etc.)."""

import base64
import hashlib
import hmac
import json
import logging
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import get_db
from app.models.user import User

log = logging.getLogger(__name__)
router = APIRouter()


def _verify_clerk_webhook(
    body: bytes,
    headers: dict[str, str],
    webhook_secret: str,
) -> bool:
    """Verify Svix / Clerk webhook signature using HMAC-SHA256.

    Clerk webhooks pass:
      - svix-id: Message ID
      - svix-timestamp: Unix epoch timestamp in seconds
      - svix-signature: comma-separated signatures (e.g. v1,g0hM...)
    """
    if not webhook_secret:
        # If no secret configured, skip in dev/test with a warning
        log.warning("CLERK_WEBHOOK_SECRET is not configured; skipping signature verification.")
        return True

    msg_id = headers.get("svix-id")
    msg_timestamp = headers.get("svix-timestamp")
    msg_signature = headers.get("svix-signature")

    if not msg_id or not msg_timestamp or not msg_signature:
        log.error("Missing Svix signature headers in Clerk webhook request.")
        return False

    # Secret may start with "whsec_"
    raw_secret = webhook_secret
    if raw_secret.startswith("whsec_"):
        raw_secret = raw_secret[6:]

    try:
        secret_bytes = base64.b64decode(raw_secret)
    except Exception:
        secret_bytes = raw_secret.encode("utf-8")

    to_sign = f"{msg_id}.{msg_timestamp}.".encode("utf-8") + body
    expected_sig = base64.b64encode(
        hmac.new(secret_bytes, to_sign, hashlib.sha256).digest()
    ).decode("utf-8")

    # msg_signature can be space or comma separated (e.g. "v1,signature1 v1,signature2")
    signatures = [
        s.split(",", 1)[1] if "," in s else s
        for s in msg_signature.replace(" ", ",").split(",")
        if s
    ]

    for sig in signatures:
        if hmac.compare_digest(sig.strip(), expected_sig.strip()):
            return True

    log.error("Clerk webhook signature mismatch.")
    return False


@router.post(
    "/webhooks/clerk",
    status_code=status.HTTP_200_OK,
    summary="Clerk Authentication Webhook",
    description="Synchronize users and automatic verification status from Clerk events (user.created, user.updated, user.deleted).",
)
async def clerk_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    svix_id: str | None = Header(None, alias="svix-id"),
    svix_timestamp: str | None = Header(None, alias="svix-timestamp"),
    svix_signature: str | None = Header(None, alias="svix-signature"),
) -> dict[str, Any]:
    settings = get_settings()
    body_bytes = await request.body()

    # ── 1. Signature Verification ──────────────────────────────────────────
    headers = {
        "svix-id": svix_id or "",
        "svix-timestamp": svix_timestamp or "",
        "svix-signature": svix_signature or "",
    }
    if settings.CLERK_WEBHOOK_SECRET:
        if not _verify_clerk_webhook(body_bytes, headers, settings.CLERK_WEBHOOK_SECRET):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid webhook signature",
            )

    # ── 2. Parse Event ─────────────────────────────────────────────────────
    try:
        payload = json.loads(body_bytes.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Malformed JSON payload: {exc}",
        )

    event_type = payload.get("type")
    data = payload.get("data") or {}

    log.info("Received Clerk webhook event: %s for user ID: %s", event_type, data.get("id"))

    if not event_type or not data:
        return {"success": True, "status": "ignored", "reason": "empty_event"}

    # ── 3. Handle Events ───────────────────────────────────────────────────
    if event_type in ("user.created", "user.updated"):
        clerk_user_id = data.get("id")
        email_addresses = data.get("email_addresses", [])
        primary_email_id = data.get("primary_email_address_id")

        # Determine primary email and verification status
        primary_email = None
        is_verified = False

        for email_item in email_addresses:
            email_val = email_item.get("email_address")
            verification = email_item.get("verification") or {}
            ver_status = verification.get("status")

            if email_item.get("id") == primary_email_id or not primary_email:
                primary_email = email_val
                is_verified = (ver_status == "verified")

        if not primary_email and email_addresses:
            primary_email = email_addresses[0].get("email_address")
            ver_status = (email_addresses[0].get("verification") or {}).get("status")
            is_verified = (ver_status == "verified")

        if not primary_email:
            log.warning("Clerk user %s has no email addresses; skipping sync.", clerk_user_id)
            return {"success": True, "status": "skipped", "reason": "no_email"}

        primary_email = primary_email.strip().lower()

        # Extract names & username
        first_name = (data.get("first_name") or "").strip()
        last_name = (data.get("last_name") or "").strip()
        full_name = f"{first_name} {last_name}".strip() or None
        username = data.get("username") or primary_email.split("@")[0]
        avatar_url = data.get("image_url") or data.get("profile_image_url")

        # Find existing user in database
        stmt = select(User).where((User.email == primary_email) | (User.username == username))
        res = await db.execute(stmt)
        user = res.scalars().first()

        if user:
            # Update user info and automatic verification
            user.email = primary_email
            if full_name:
                user.full_name = full_name
            if avatar_url:
                user.avatar_url = avatar_url
            user.is_verified = is_verified
            user.is_active = True
            log.info("Updated existing user %s via Clerk (is_verified=%s)", user.id, is_verified)
        else:
            # Create new user provisioned via Clerk
            user = User(
                id=str(uuid4().hex),
                email=primary_email,
                username=username,
                full_name=full_name,
                avatar_url=avatar_url,
                hashed_password=hash_password(uuid4().hex),  # Random unusable password for OAuth/Clerk users
                is_active=True,
                is_verified=is_verified,
                is_admin=False,
            )
            db.add(user)
            log.info("Created new user %s via Clerk (is_verified=%s)", user.id, is_verified)

        await db.commit()
        return {"success": True, "status": "synced", "user_id": user.id, "is_verified": is_verified}

    elif event_type == "user.deleted":
        clerk_user_id = data.get("id")
        email_addresses = data.get("email_addresses", [])
        primary_email = email_addresses[0].get("email_address") if email_addresses else None

        if primary_email:
            stmt = select(User).where(User.email == primary_email.strip().lower())
            res = await db.execute(stmt)
            user = res.scalars().first()
            if user:
                user.is_active = False
                await db.commit()
                log.info("Deactivated user %s via Clerk user.deleted", user.id)

        return {"success": True, "status": "deleted"}

    return {"success": True, "status": "ignored", "event": event_type}
