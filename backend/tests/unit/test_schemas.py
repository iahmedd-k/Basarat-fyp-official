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
from app.schemas.community import (
    CommunityPostCreate,
    CommunityPostUpdate,
    CommunityCommentCreate,
    CommunityReportCreate,
    PostType,
    ReportReason,
)
from app.schemas.market import (
    ConstituentItem,
    GainersResponse,
    IndexConstituentsResponse,
    LosersResponse,
    MarketQuoteItem,
    VolumeSpikesResponse,
)
from app.schemas.portfolio import TransactionCreate, TransactionUpdate


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


class TestCommunityPostCreate:
    def test_valid_stock_post(self):
        s = CommunityPostCreate(
            content="Banks look cheap right now",
            post_type=PostType.STOCK,
            stock_symbol="HBL",
        )
        assert s.content == "Banks look cheap right now"
        assert s.post_type == PostType.STOCK
        assert s.stock_symbol == "HBL"

    def test_valid_general_market_post(self):
        s = CommunityPostCreate(
            content="Market is bullish today",
            post_type=PostType.GENERAL_MARKET,
        )
        assert s.content == "Market is bullish today"
        assert s.post_type == PostType.GENERAL_MARKET
        assert s.stock_symbol is None

    def test_missing_content_rejected(self):
        with pytest.raises(ValidationError):
            CommunityPostCreate(post_type=PostType.STOCK, stock_symbol="HBL")

    def test_blank_content_rejected(self):
        with pytest.raises(ValidationError):
            CommunityPostCreate(content="   ", post_type=PostType.STOCK, stock_symbol="HBL")

    def test_stock_post_requires_stock_symbol(self):
        with pytest.raises(ValidationError):
            CommunityPostCreate(content="Hello", post_type=PostType.STOCK)

    def test_general_market_rejects_stock_symbol(self):
        with pytest.raises(ValidationError):
            CommunityPostCreate(content="Hello", post_type=PostType.GENERAL_MARKET, stock_symbol="HBL")

    def test_stock_symbol_normalized_to_uppercase(self):
        s = CommunityPostCreate(content="Hello", post_type=PostType.STOCK, stock_symbol="hbl")
        assert s.stock_symbol == "HBL"


class TestCommunityPostUpdate:
    def test_valid_update(self):
        s = CommunityPostUpdate(content="Updated content")
        assert s.content == "Updated content"

    def test_blank_content_rejected(self):
        with pytest.raises(ValidationError):
            CommunityPostUpdate(content="   ")


class TestCommunityReportCreate:
    def test_valid_post_report(self):
        r = CommunityReportCreate(reason=ReportReason.SPAM, post_id="post-1")
        assert r.reason == ReportReason.SPAM
        assert r.post_id == "post-1"
        assert r.comment_id is None

    def test_valid_comment_report(self):
        r = CommunityReportCreate(reason=ReportReason.ABUSIVE, comment_id="comment-1")
        assert r.reason == ReportReason.ABUSIVE
        assert r.comment_id == "comment-1"
        assert r.post_id is None

    def test_exactly_one_target_required(self):
        with pytest.raises(ValidationError):
            CommunityReportCreate(reason=ReportReason.SPAM)

        with pytest.raises(ValidationError):
            CommunityReportCreate(reason=ReportReason.SPAM, post_id="p1", comment_id="c1")


class TestCommunityCommentCreate:
    def test_valid_comment(self):
        s = CommunityCommentCreate(content="Nice post!")
        assert s.content == "Nice post!"
        assert s.parent_comment_id is None

    def test_blank_comment_rejected(self):
        with pytest.raises(ValidationError):
            CommunityCommentCreate(content="   ")

    def test_reply_allows_parent(self):
        s = CommunityCommentCreate(content="Reply", parent_comment_id="abc")
        assert s.parent_comment_id == "abc"


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
    def test_transaction_create(self):
        t = TransactionCreate(symbol="HBL", transaction_type="BUY", quantity=100, price=150.0, transaction_date="2025-01-01")
        assert t.symbol == "HBL"
        assert t.transaction_type == "BUY"
        assert t.quantity == 100

    def test_transaction_update_all_optional(self):
        t = TransactionUpdate()
        assert t.quantity is None
        assert t.price is None

    def test_transaction_update_partial(self):
        t = TransactionUpdate(quantity=200)
        assert t.quantity == 200
        assert t.price is None
