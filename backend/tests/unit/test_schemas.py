"""Unit tests for Pydantic schema validation."""

import pytest
from pydantic import ValidationError

from app.schemas.auth import (
    AlertRuleCreate,
    ChangePasswordRequest,
    DeviceRegisterRequest,
    LoginRequest,
    RefreshRequest,
    SignupRequest,
    UpdateProfileRequest,
    UpdateRiskProfileRequest,
)
from app.schemas.stock import StockSearchResult
from app.schemas.community import CommentCreate, PostCreate, ReportCreate
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
        s = PostCreate(
            content="Banks look cheap right now",
            symbols=["hbl", " ubl "],
            sentiment="BULLISH",
        )
        assert s.content == "Banks look cheap right now"
        assert s.symbols == ["HBL", "UBL"]
        assert s.sentiment == "BULLISH"

    def test_symbols_optional(self):
        s = PostCreate(content="No ticker validation here")
        assert s.symbols == []

    def test_missing_content_rejected(self):
        with pytest.raises(ValidationError):
            PostCreate(symbols=["HBL"])

    def test_blank_content_rejected(self):
        with pytest.raises(ValidationError):
            PostCreate(content="   ", symbols=["HBL"])

    def test_empty_ticker_rejected(self):
        with pytest.raises(ValidationError):
            PostCreate(content="Hello", symbols=["   "])

    def test_invalid_sentiment_rejected(self):
        with pytest.raises(ValidationError):
            PostCreate(content="Hello", symbols=["HBL"], sentiment="HOLD")

    def test_media_url_must_be_cloudinary(self):
        with pytest.raises(ValidationError):
            PostCreate(content="Hello", symbols=["HBL"], mediaUrl="https://cdn.example.com/a.png")
        with pytest.raises(ValidationError):
            PostCreate(content="Hello", symbols=["HBL"], mediaUrl="https://yourapp.com/x.jpg")

    def test_valid_media_url(self):
        s = PostCreate(
            content="Hello",
            symbols=["HBL"],
            mediaUrl="https://res.cloudinary.com/basarat/image/upload/v1720000000000/community/abc.jpg",
        )
        assert s.mediaUrl.startswith("https://res.cloudinary.com/")


class TestReportCreate:
    def test_valid_report(self):
        r = ReportCreate(targetType="POST", targetId="post-1", reason="SPAM")
        assert r.targetType == "POST"
        assert r.reason == "SPAM"

    def test_invalid_target_type(self):
        with pytest.raises(ValidationError):
            ReportCreate(targetType="USER", targetId="p", reason="SPAM")

    def test_invalid_reason(self):
        with pytest.raises(ValidationError):
            ReportCreate(targetType="POST", targetId="p", reason="BAD")


class TestCommentCreate:
    def test_valid_comment(self):
        s = CommentCreate(content="Nice post!")
        assert s.content == "Nice post!"

    def test_blank_comment_rejected(self):
        with pytest.raises(ValidationError):
            CommentCreate(content="   ")

    def test_reply_allows_parent(self):
        s = CommentCreate(content="Reply", parentCommentId="abc")
        assert s.parentCommentId == "abc"


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
