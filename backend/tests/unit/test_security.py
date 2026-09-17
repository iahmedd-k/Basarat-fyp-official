"""Unit tests for app.core.security — password hashing and JWT tokens."""

from datetime import timedelta

import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


# ── Password hashing ────────────────────────────────────────────────────────

class TestPasswordHashing:
    def test_hash_password_returns_string(self):
        result = hash_password("mypassword")
        assert isinstance(result, str)

    def test_hash_password_is_bcrypt_format(self):
        result = hash_password("mypassword")
        assert result.startswith("$2b$")

    def test_verify_password_correct(self):
        hashed = hash_password("secret123")
        assert verify_password("secret123", hashed) is True

    def test_verify_password_incorrect(self):
        hashed = hash_password("secret123")
        assert verify_password("wrongpassword", hashed) is False

    def test_different_hashes_for_same_password(self):
        h1 = hash_password("samepassword")
        h2 = hash_password("samepassword")
        assert h1 != h2

    def test_hash_empty_password(self):
        result = hash_password("")
        assert isinstance(result, str)
        assert verify_password("", result) is True

    def test_hash_unicode_password(self):
        result = hash_password("pässwörd123")
        assert verify_password("pässwörd123", result) is True


# ── JWT access tokens ───────────────────────────────────────────────────────

class TestAccessToken:
    def test_create_access_token_returns_string(self):
        token = create_access_token({"sub": "user123"})
        assert isinstance(token, str)

    def test_access_token_decodes_correctly(self):
        token = create_access_token({"sub": "user123"})
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user123"
        assert payload["type"] == "access"

    def test_access_token_with_custom_expiry(self):
        token = create_access_token(
            {"sub": "user123"}, expires_delta=timedelta(hours=2)
        )
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user123"

    def test_access_token_with_empty_data(self):
        token = create_access_token({})
        payload = decode_token(token)
        assert payload is not None
        assert payload["type"] == "access"

    def test_access_token_preserves_extra_claims(self):
        token = create_access_token({"sub": "u1", "role": "admin"})
        payload = decode_token(token)
        assert payload["role"] == "admin"


# ── JWT refresh tokens ──────────────────────────────────────────────────────

class TestRefreshToken:
    def test_create_refresh_token_returns_string(self):
        token = create_refresh_token({"sub": "user123"})
        assert isinstance(token, str)

    def test_refresh_token_decodes_correctly(self):
        token = create_refresh_token({"sub": "user123"})
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user123"
        assert payload["type"] == "refresh"

    def test_refresh_token_has_jti(self):
        token = create_refresh_token({"sub": "user123"})
        payload = decode_token(token)
        assert "jti" in payload
        assert isinstance(payload["jti"], str)

    def test_refresh_tokens_have_unique_jti(self):
        t1 = create_refresh_token({"sub": "u1"})
        t2 = create_refresh_token({"sub": "u1"})
        p1 = decode_token(t1)
        p2 = decode_token(t2)
        assert p1["jti"] != p2["jti"]


# ── Token decode edge cases ─────────────────────────────────────────────────

class TestDecodeToken:
    def test_decode_invalid_token(self):
        assert decode_token("not.a.valid.token") is None

    def test_decode_empty_string(self):
        assert decode_token("") is None

    def test_decode_tampered_token(self):
        token = create_access_token({"sub": "user1"})
        tampered = token[:-5] + "XXXXX"
        assert decode_token(tampered) is None

    def test_decode_with_wrong_secret(self):
        from jose import jwt
        token = jwt.encode(
            {"sub": "user1", "type": "access"},
            "wrong-secret",
            algorithm="HS256",
        )
        assert decode_token(token) is None
