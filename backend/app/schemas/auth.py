import re
from typing import Literal

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


_PASSWORD_COMPLEXITY_RE = re.compile(
    r"^(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?])"
)

_URL_RE = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)


# Valid sector preferences for risk profile
VALID_SECTORS: list[str] = [
    "Commercial Banks",
    "Oil & Gas",
    "Cement",
    "Fertilizer",
    "Technology",
    "Pharmaceuticals",
    "Automobile",
    "Textile",
    "Power & Energy",
    "Chemicals",
    "Food & Personal Care",
    "Engineering",
    "Insurance",
    "Property / Real Estate",
    "Telecommunications",
]

# Special value to indicate "No preference" / "All sectors"
NO_PREFERENCE = "All Sectors"


class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    username: str
    full_name: str | None = None
    is_admin: bool = False


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
    token: str
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


class UserProfileResponse(BaseModel):
    id: str
    email: str
    username: str
    full_name: str | None = None
    avatar_url: str | None = None
    is_active: bool
    is_verified: bool
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UpdateProfileRequest(BaseModel):
    full_name: str | None = Field(None, max_length=255)
    avatar_url: str | None = Field(None, max_length=500)

    @field_validator("avatar_url")
    @classmethod
    def validate_avatar_url(cls, v: str | None) -> str | None:
        if v is not None and not _URL_RE.match(v):
            raise ValueError("avatar_url must be a valid HTTP or HTTPS URL.")
        return v


class UpdateRiskProfileRequest(BaseModel):
    risk_tolerance: str | None = Field(None, pattern="^(conservative|moderate|aggressive)$")
    sector_preferences: list[str] | None = Field(None, max_length=50)
    investment_horizon: str | None = None

    @field_validator("sector_preferences")
    @classmethod
    def validate_sector_preferences(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        # Allow "All Sectors" as a special value (mutually exclusive with other sectors)
        if NO_PREFERENCE in v:
            if len(v) > 1:
                raise ValueError(f'"{NO_PREFERENCE}" cannot be combined with other sectors')
            return [NO_PREFERENCE]
        # Validate each sector against the allowed list
        for sector in v:
            if sector not in VALID_SECTORS:
                raise ValueError(f'Invalid sector: "{sector}". Valid sectors: {", ".join(VALID_SECTORS)}')
        # Remove duplicates while preserving order
        seen = set()
        unique_sectors = []
        for sector in v:
            if sector not in seen:
                seen.add(sector)
                unique_sectors.append(sector)
        return unique_sectors


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
