"""Unit tests for app.core.authorization dependencies."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.authorization import (
    get_current_admin,
    get_current_user,
    get_token_payload,
    require_roles,
)
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.models.user import User


@pytest.mark.asyncio
class TestGetTokenPayload:
    async def test_no_credentials_raises_unauthorized(self):
        with pytest.raises(UnauthorizedError):
            await get_token_payload(credentials=None)

    @patch("app.core.authorization.decode_token")
    async def test_invalid_token_raises_unauthorized(self, mock_decode):
        mock_decode.return_value = None
        creds = MagicMock(credentials="bad.token.here")
        with pytest.raises(UnauthorizedError):
            await get_token_payload(credentials=creds)

    @patch("app.core.authorization.decode_token")
    async def test_refresh_token_type_raises_unauthorized(self, mock_decode):
        mock_decode.return_value = {"sub": "u1", "type": "refresh"}
        creds = MagicMock(credentials="valid.token")
        with pytest.raises(UnauthorizedError):
            await get_token_payload(credentials=creds)

    @patch("app.core.authorization.decode_token")
    async def test_valid_access_token_returns_payload(self, mock_decode):
        mock_decode.return_value = {"sub": "u1", "type": "access"}
        creds = MagicMock(credentials="valid.token")
        result = await get_token_payload(credentials=creds)
        assert result["sub"] == "u1"


@pytest.mark.asyncio
class TestGetCurrentUser:
    async def test_missing_sub_raises_unauthorized(self):
        with pytest.raises(UnauthorizedError):
            await get_current_user(payload={"type": "access"}, db=AsyncMock())

    async def test_user_not_found_raises_unauthorized(self):
        mock_db = AsyncMock()
        mock_db.get.return_value = None
        with pytest.raises(UnauthorizedError):
            await get_current_user(payload={"sub": "nonexistent", "type": "access"}, db=mock_db)

    async def test_inactive_user_raises_forbidden(self):
        mock_user = MagicMock(spec=User)
        mock_user.is_active = False
        mock_db = AsyncMock()
        mock_db.get.return_value = mock_user
        with pytest.raises(ForbiddenError):
            await get_current_user(payload={"sub": "u1", "type": "access"}, db=mock_db)

    async def test_active_user_returns_user(self):
        mock_user = MagicMock(spec=User)
        mock_user.is_active = True
        mock_db = AsyncMock()
        mock_db.get.return_value = mock_user
        result = await get_current_user(payload={"sub": "u1", "type": "access"}, db=mock_db)
        assert result == mock_user


@pytest.mark.asyncio
class TestGetCurrentAdmin:
    async def test_non_admin_raises_forbidden(self):
        mock_user = MagicMock(spec=User)
        mock_user.is_admin = False
        with pytest.raises(ForbiddenError):
            await get_current_admin(current_user=mock_user)

    async def test_admin_returns_user(self):
        mock_user = MagicMock(spec=User)
        mock_user.is_admin = True
        result = await get_current_admin(current_user=mock_user)
        assert result == mock_user


class TestRequireRoles:
    def test_returns_coroutine(self):
        dep = require_roles("admin")
        assert callable(dep)

    @pytest.mark.asyncio
    async def test_admin_in_admin_role(self):
        mock_user = MagicMock(spec=User)
        mock_user.is_admin = True
        dep = require_roles("admin")
        result = await dep(current_user=mock_user)
        assert result == mock_user

    @pytest.mark.asyncio
    async def test_user_not_in_admin_role(self):
        mock_user = MagicMock(spec=User)
        mock_user.is_admin = False
        dep = require_roles("admin")
        with pytest.raises(ForbiddenError):
            await dep(current_user=mock_user)

    @pytest.mark.asyncio
    async def test_user_in_user_role(self):
        mock_user = MagicMock(spec=User)
        mock_user.is_admin = False
        dep = require_roles("user")
        result = await dep(current_user=mock_user)
        assert result == mock_user
