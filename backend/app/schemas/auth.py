import re
from typing import Literal

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


_PASSWORD_COMPLEXITY_RE = re.compile(
    r"^(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?])"
)

_URL_RE = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)


from enum import Enum


class RiskTolerance(str, Enum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


class InvestmentHorizon(str, Enum):
    SHORT_TERM = "short_term"
    MEDIUM_TERM = "medium_term"
    LONG_TERM = "long_term"


class SectorPreference(str, Enum):
    ALL_SECTORS = "All Sectors"
    COMMERCIAL_BANKS = "Commercial Banks"
    OIL_GAS = "Oil & Gas"
    CEMENT = "Cement"
    FERTILIZER = "Fertilizer"
    TECHNOLOGY = "Technology"
    PHARMACEUTICALS = "Pharmaceuticals"
    AUTOMOBILE = "Automobile"
    TEXTILE = "Textile"
    POWER_ENERGY = "Power & Energy"
    CHEMICALS = "Chemicals"
    FOOD_PERSONAL_CARE = "Food & Personal Care"
    ENGINEERING = "Engineering"
    INSURANCE = "Insurance"
    PROPERTY_REAL_ESTATE = "Property / Real Estate"
    TELECOMMUNICATIONS = "Telecommunications"


# Valid sector preferences for risk profile
VALID_SECTORS: list[str] = [s.value for s in SectorPreference if s != SectorPreference.ALL_SECTORS]

# Special value to indicate "No preference" / "All sectors"
NO_PREFERENCE = SectorPreference.ALL_SECTORS.value


class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    username: str
    full_name: str | None = None


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str | None = Field(None, max_length=255)

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        if not _PASSWORD_COMPLEXITY_RE.match(v):
            raise ValueError(
                "Password must contain at least one uppercase letter, "
                "one digit, and one special character."
            )
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserSummary


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        if not _PASSWORD_COMPLEXITY_RE.match(v):
            raise ValueError(
                "Password must contain at least one uppercase letter, "
                "one digit, and one special character."
            )
        return v


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        if not _PASSWORD_COMPLEXITY_RE.match(v):
            raise ValueError(
                "Password must contain at least one uppercase letter, "
                "one digit, and one special character."
            )
        return v


class MessageResponse(BaseModel):
    message: str


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class UserProfileResponse(BaseModel):
    id: str
    email: str
    username: str
    full_name: str | None = None
    avatar_url: str | None = None
    is_active: bool
    is_verified: bool
    risk_tolerance: RiskTolerance | None = None
    sector_preferences: list[str] | None = None
    investment_horizon: InvestmentHorizon | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UpdateProfileRequest(BaseModel):
    full_name: str | None = Field(None, max_length=255)
    avatar_url: str | None = Field(None, max_length=500)
    risk_tolerance: RiskTolerance | None = None
    sector_preferences: list[SectorPreference] | None = Field(None, max_length=50)
    investment_horizon: InvestmentHorizon | None = None

    @field_validator("avatar_url")
    @classmethod
    def validate_avatar_url(cls, v: str | None) -> str | None:
        if v is not None and not _URL_RE.match(v):
            raise ValueError("avatar_url must be a valid HTTP or HTTPS URL.")
        return v

    @field_validator("sector_preferences")
    @classmethod
    def validate_sector_preferences(cls, v: list[SectorPreference] | None) -> list[str] | None:
        if v is None:
            return v
        str_values = [item.value if isinstance(item, Enum) else str(item) for item in v]
        if NO_PREFERENCE in str_values:
            if len(str_values) > 1:
                raise ValueError(f'"{NO_PREFERENCE}" cannot be combined with other sectors')
            return [NO_PREFERENCE]
        for sector in str_values:
            if sector not in VALID_SECTORS:
                raise ValueError(f'Invalid sector: "{sector}". Valid sectors: {", ".join(VALID_SECTORS)}')
        seen = set()
        unique_sectors = []
        for sector in str_values:
            if sector not in seen:
                seen.add(sector)
                unique_sectors.append(sector)
        return unique_sectors


UpdateRiskProfileRequest = UpdateProfileRequest
UpdateInvestmentProfileRequest = UpdateProfileRequest


class RiskProfileResponse(BaseModel):
    message: str = "Risk profile updated"
    risk_tolerance: RiskTolerance | None = None
    sector_preferences: list[str] | None = None
    investment_horizon: InvestmentHorizon | None = None


class UpdateNotificationPrefsRequest(BaseModel):
    channels: list[str] | None = Field(None, max_length=20)
    categories: list[str] | None = Field(None, max_length=50)


class DeviceRegisterRequest(BaseModel):
    fcm_token: str = Field(..., min_length=1, max_length=500)
    platform: str = Field(..., pattern="^(android|ios|web)$")
    device_name: str | None = Field(None, max_length=255)


class DeviceResponse(BaseModel):
    id: str
    fcm_token: str
    device_name: str | None = None
    platform: str | None = None
    is_active: bool
    created_at: str

    model_config = {"from_attributes": True}


class AlertRuleCreate(BaseModel):
    stock_id: str | None = None
    condition: str = Field(..., min_length=1, max_length=100)
    threshold: float


class AlertRuleUpdate(BaseModel):
    stock_id: str | None = None
    condition: str | None = Field(None, min_length=1, max_length=100)
    threshold: float | None = None
    is_active: bool | None = None


class AlertRuleResponse(BaseModel):
    id: str
    user_id: str
    stock_id: str | None = None
    condition: str
    threshold: float
    is_active: bool
    created_at: str

    model_config = {"from_attributes": True}


class AlertResponse(BaseModel):
    id: str
    user_id: str
    rule_id: str | None = None
    title: str
    message: str | None = None
    is_read: bool
    created_at: str

    model_config = {"from_attributes": True}


class NotificationResponse(BaseModel):
    id: str
    title: str
    message: str | None = None
    is_read: bool
    created_at: str

    model_config = {"from_attributes": True}


class NotificationsListResponse(BaseModel):
    notifications: list[AlertResponse]
    total: int
    page: int
    limit: int
    has_more: bool


class ForecastResponse(BaseModel):
    symbol: str
    direction: str
    bullish_pct: float
    bearish_pct: float
    sideways_pct: float
    top_class_probability: float
    horizon: str


class ForecastHistoryItem(BaseModel):
    forecast_date: str
    predicted_close: float
    confidence_lower: float | None = None
    confidence_upper: float | None = None
    actual_close: float | None = None


class ForecastHistoryResponse(BaseModel):
    symbol: str
    history: list[ForecastHistoryItem]


class NewsArticleResponse(BaseModel):
    id: str
    title: str
    url: str
    source: str | None = None
    summary: str | None = None
    sentiment_score: float | None = None
    published_at: str | None = None
    created_at: str


class NewsListResponse(BaseModel):
    articles: list[NewsArticleResponse]
    total: int
    page: int
    limit: int
    has_more: bool


class EventResponse(BaseModel):
    id: str
    title: str
    event_type: str
    symbol: str | None = None
    event_date: str
    description: str | None = None


class EventsCalendarResponse(BaseModel):
    events: list[EventResponse]
