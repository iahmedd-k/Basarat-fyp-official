"""Unit tests for Pydantic schema validation."""

import pytest
from pydantic import ValidationError

from app.schemas.auth import (
    AlertRuleCreate,
    AlertRuleUpdate,
    ChangePasswordRequest,
    DeviceRegisterRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    ResetPasswordRequest,
    SignupRequest,
    UpdateNotificationPrefsRequest,
    UpdateProfileRequest,
    UpdateRiskProfileRequest,
)
from app.schemas.stock import StockSearchResult
from app.schemas.community import PostCreate, VoteRequest, CommentCreate
from app.schemas.market import (
    ConstituentItem,
    GainersResponse,
    IndexConstituentsResponse,
    LosersResponse,
    MarketQuoteItem,
    VolumeSpikesResponse,
)
from app.schemas.portfolio import HoldingCreate, HoldingUpdate


# ── Auth schemas ────────────────────────────────────────────────────────────

class TestSignupRequest:
    def test_valid_signup(self):
        s = SignupRequest(email="a@b.com", password="ValidPass1!")
        assert s.email == "a@b.com"

    def test_invalid_email(self):
        with pytest.raises(ValidationError):
            SignupRequest(email="not-an-email", password="ValidPass1!")

    def test_short_password(self):
        with pytest.raises(ValidationError):
            SignupRequest(email="a@b.com", password="ab")

    def test_optional_full_name(self):
        s = SignupRequest(email="a@b.com", password="ValidPass1!")
        assert s.full_name is None

    def test_weak_password_rejected(self):
        with pytest.raises(ValidationError):
            SignupRequest(email="a@b.com", password="validpass1")

    def test_password_no_uppercase_rejected(self):
        with pytest.raises(ValidationError):
            SignupRequest(email="a@b.com", password="validpass1!")

    def test_password_no_special_char_rejected(self):
        with pytest.raises(ValidationError):
            SignupRequest(email="a@b.com", password="ValidPass1")


class TestLoginRequest:
    def test_valid_login(self):
        s = LoginRequest(email="a@b.com", password="pass")
        assert s.email == "a@b.com"


class TestRefreshRequest:
    def test_valid_refresh(self):
        s = RefreshRequest(refresh_token="abc.def.ghi")
        assert s.refresh_token == "abc.def.ghi"


class TestChangePasswordRequest:
    def test_valid_change(self):
        s = ChangePasswordRequest(
            current_password="old", new_password="NewPass1!"
        )
        assert s.current_password == "old"

    def test_short_new_password(self):
        with pytest.raises(ValidationError):
            ChangePasswordRequest(current_password="old", new_password="ab")


class TestUpdateProfileRequest:
    def test_all_optional(self):
        s = UpdateProfileRequest()
        assert s.full_name is None
        assert s.avatar_url is None

    def test_valid_update(self):
        s = UpdateProfileRequest(full_name="Ahmed", avatar_url="https://example.com/a.png")
        assert s.full_name == "Ahmed"


class TestUpdateRiskProfileRequest:
    def test_valid_risk_tolerance(self):
        s = UpdateRiskProfileRequest(risk_tolerance="aggressive")
        assert s.risk_tolerance == "aggressive"

    def test_invalid_risk_tolerance(self):
        with pytest.raises(ValidationError):
            UpdateRiskProfileRequest(risk_tolerance="invalid")


class TestDeviceRegisterRequest:
    def test_valid_device(self):
        s = DeviceRegisterRequest(
            fcm_token="abc123", platform="android", device_name="Pixel"
        )
        assert s.platform == "android"

    def test_invalid_platform(self):
        with pytest.raises(ValidationError):
            DeviceRegisterRequest(fcm_token="abc", platform="windows")


class TestAlertRuleCreate:
    def test_valid_alert(self):
        s = AlertRuleCreate(condition="price_above", threshold=100.0)
        assert s.threshold == 100.0

    def test_empty_condition(self):
        with pytest.raises(ValidationError):
            AlertRuleCreate(condition="", threshold=100.0)


# ── Stock schemas ───────────────────────────────────────────────────────────

class TestStockSearchResult:
    def test_valid_result(self):
        s = StockSearchResult(symbol="HBL", name="Habib Bank")
        assert s.symbol == "HBL"


# ── Community schemas ───────────────────────────────────────────────────────

class TestPostCreate:
    def test_valid_post(self):
        s = PostCreate(symbol="HBL", stance="bullish", rationale_text="Strong fundamentals and growth")
        assert s.symbol == "HBL"

    def test_missing_fields(self):
        with pytest.raises(ValidationError):
            PostCreate(content="Hello world")


class TestVoteRequest:
    def test_valid_vote(self):
        s = VoteRequest(direction="up")
        assert s.direction == "up"

    def test_invalid_direction(self):
        with pytest.raises(ValidationError):
            VoteRequest(direction="sideways")


class TestCommentCreate:
    def test_valid_comment(self):
        s = CommentCreate(text="Nice post!")
        assert s.text == "Nice post!"


# ── Market schemas ──────────────────────────────────────────────────────────

class TestMarketSchemas:
    def test_market_quote_item(self):
        item = MarketQuoteItem(
            symbol="HBL", sector="Banking", ldcp=150.0, open=152.0,
            high=155.0, low=149.0, current=154.0, change=4.0,
            change_pct=2.67, volume=1000000,
        )
        assert item.symbol == "HBL"

    def test_gainers_response(self):
        resp = GainersResponse(gainers=[])
        assert resp.gainers == []

    def test_losers_response(self):
        resp = LosersResponse(losers=[])
        assert resp.losers == []

    def test_volume_spikes_response(self):
        resp = VolumeSpikesResponse(volume_spikes=[])
        assert resp.volume_spikes == []

    def test_constituent_item(self):
        item = ConstituentItem(
            symbol="HBL", name="Habib Bank", ldcp=150.0, current=154.0,
            change=4.0, change_pct=2.67, weight_pct=8.5,
            index_points=12.5, volume=1000000, freefloat_m=500.0,
            market_cap_m=5000.0,
        )
        assert item.symbol == "HBL"

    def test_index_constituents_response(self):
        resp = IndexConstituentsResponse(
            index="KSE-100", code="KSE100", constituents=[]
        )
        assert resp.index == "KSE-100"
        assert resp.shariah_compliant is None


# ── Portfolio schemas ───────────────────────────────────────────────────────

class TestPortfolioSchemas:
    def test_holding_create(self):
        h = HoldingCreate(symbol="HBL", quantity=100, avg_buy_price=150.0, purchase_date="2025-01-01")
        assert h.symbol == "HBL"
        assert h.quantity == 100

    def test_holding_update_all_optional(self):
        h = HoldingUpdate()
        assert h.quantity is None
        assert h.avg_buy_price is None

    def test_holding_update_partial(self):
        h = HoldingUpdate(quantity=200)
        assert h.quantity == 200
        assert h.avg_buy_price is None
