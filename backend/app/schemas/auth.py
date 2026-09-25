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

    id: str = Field(..., description="Unique user identifier (UUID)", examples=["usr_9f8e7d6c5b4a"])
    email: str = Field(..., description="User email address", examples=["investor@example.com"])
    username: str = Field(..., description="Unique username", examples=["user_abc123"])
    full_name: str | None = Field(None, description="Full name of user", examples=["Ahmed Khan"])


class SignupRequest(BaseModel):
    """Request body for user registration."""
    email: EmailStr = Field(..., description="Valid email address for registration", examples=["investor@example.com"])
    password: str = Field(..., min_length=8, max_length=128, description="Password (min 8 chars, 1 uppercase, 1 digit, 1 special char)", examples=["SecurePass123!"])
    full_name: str | None = Field(None, max_length=255, description="Full name of the user", examples=["Ahmed Khan"])

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
    """Request body for email/password authentication."""
    email: EmailStr = Field(..., description="Registered email address", examples=["investor@example.com"])
    password: str = Field(..., description="User password", examples=["SecurePass123!"])


class GoogleAuthRequest(BaseModel):
    """Request body for 'Continue with Google' OAuth authentication."""
    id_token: str = Field(
        ...,
        description="Google OAuth ID token (JWT) obtained from Google Sign-In SDK on Mobile/Web.",
        examples=["eyJhbGciOiJSUzI1NiIsImtpZCI6Ij..."],
    )
    access_token: str | None = Field(
        None,
        description="Optional Google OAuth access token for profile/avatar fetching fallback.",
    )


class AppleAuthRequest(BaseModel):
    """Request body for 'Continue with Apple' OAuth authentication."""
    id_token: str = Field(
        ...,
        description="Apple identity token (JWT) obtained from Sign In with Apple SDK.",
        examples=["eyJraWQiOiJhYmMxMjMiLCJhbGciOiJSUzI1NiJ9..."],
    )
    full_name: str | None = Field(
        None,
        description="User's full name (transmitted by Apple client only on initial authorization).",
        examples=["Ahmed Khan"],
    )


class RefreshRequest(BaseModel):
    """Request body for token refresh."""
    refresh_token: str = Field(..., description="Valid refresh token received from login or verify-email", examples=["eyJhbGciOi..."])


class LogoutRequest(BaseModel):
    """Request body for logout."""
    refresh_token: str = Field(..., description="Refresh token to invalidate", examples=["eyJhbGciOi..."])


class TokenResponse(BaseModel):
    """Response containing JWT access & refresh tokens and user summary."""
    access_token: str = Field(..., description="Short-lived JWT access token for Authorization header", examples=["eyJhbGciOi..."])
    refresh_token: str = Field(..., description="Rotating refresh token to exchange for new access tokens", examples=["eyJhbGciOi..."])
    token_type: str = Field("bearer", description="Token authorization scheme type", examples=["bearer"])
    user: UserSummary


class ForgotPasswordRequest(BaseModel):
    """Step 1 of 3: Request password reset OTP code via email."""
    email: EmailStr = Field(..., description="Email address associated with the account", examples=["investor@example.com"])


class VerifyResetCodeRequest(BaseModel):
    """Step 2 of 3: Verify the 6-digit reset code received in email."""
    email: EmailStr = Field(..., description="Email address where the reset code was sent", examples=["investor@example.com"])
    code: str = Field(..., min_length=6, max_length=6, description="6-digit reset code from email", examples=["123456"])


class VerifyResetCodeResponse(BaseModel):
    """Step 2 Response: Returns temporary reset_token grant to set new password."""
    reset_token: str = Field(..., description="Short-lived (15 min) grant token required in Step 3 (reset-password)", examples=["eyJhbGciOi..."])
    expires_in: int = Field(900, description="Token validity duration in seconds (15 minutes)", examples=[900])
    token_type: str = Field("bearer", description="Token type", examples=["bearer"])
    message: str = Field("Code verified successfully. Please proceed to set your new password.", description="Status message")


class ResetPasswordRequest(BaseModel):
    """Step 3 of 3: Set new password using reset_token (or email+code fallback)."""
    reset_token: str | None = Field(None, description="Temporary grant token received from Step 2 (/verify-reset-code)", examples=["eyJhbGciOi..."])
    email: EmailStr | None = Field(None, description="Email address (optional fallback if reset_token is not used)", examples=["investor@example.com"])
    code: str | None = Field(None, min_length=6, max_length=6, description="6-digit reset code (optional fallback if reset_token is not used)", examples=["123456"])
    new_password: str = Field(..., min_length=8, max_length=128, description="New password (min 8 chars, 1 uppercase, 1 digit, 1 special char)", examples=["NewSecurePass123!"])
    confirm_password: str | None = Field(None, min_length=8, max_length=128, description="Confirmation of new password (must match new_password)", examples=["NewSecurePass123!"])

    @field_validator("new_password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        if not _PASSWORD_COMPLEXITY_RE.match(v):
            raise ValueError(
                "Password must contain at least one uppercase letter, "
                "one digit, and one special character."
            )
        return v

    @field_validator("confirm_password")
    @classmethod
    def validate_passwords_match(cls, v: str | None, info) -> str | None:
        if v is not None and "new_password" in info.data and v != info.data["new_password"]:
            raise ValueError("Passwords do not match.")
        return v


class ChangePasswordRequest(BaseModel):
    """Request body to change password while logged in."""
    current_password: str = Field(..., description="Current account password", examples=["OldSecurePass123!"])
    new_password: str = Field(..., min_length=8, max_length=128, description="New password", examples=["NewSecurePass123!"])
    confirm_password: str | None = Field(None, min_length=8, max_length=128, description="Confirmation of new password", examples=["NewSecurePass123!"])

    @field_validator("new_password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        if not _PASSWORD_COMPLEXITY_RE.match(v):
            raise ValueError(
                "Password must contain at least one uppercase letter, "
                "one digit, and one special character."
            )
        return v

    @field_validator("confirm_password")
    @classmethod
    def validate_passwords_match(cls, v: str | None, info) -> str | None:
        if v is not None and "new_password" in info.data and v != info.data["new_password"]:
            raise ValueError("Passwords do not match.")
        return v


class MessageResponse(BaseModel):
    """Generic status/message response."""
    message: str = Field(..., description="Informational message", examples=["Operation completed successfully."])


class VerifyEmailRequest(BaseModel):
    """Request body to verify email with 6-digit code after signup."""
    email: EmailStr = Field(..., description="Registered email address", examples=["investor@example.com"])
    code: str = Field(..., min_length=6, max_length=6, description="6-digit verification code from email", examples=["123456"])


class ResendVerificationRequest(BaseModel):
    """Request body to resend the verification code."""
    email: EmailStr = Field(..., description="Registered email address", examples=["investor@example.com"])


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
