# app/schemas/user.py
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from app.models.risk_profile import RiskTolerance


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        if not any(c.isalpha() for c in v):
            raise ValueError("Password must contain at least one letter")
        return v


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    username: str
    full_name: str | None
    phone: str | None
    avatar_url: str | None
    is_verified: bool
    created_at: datetime
    risk_profile: RiskProfileResponse | None = None
    notification_prefs: NotificationPrefsResponse | None = None

    model_config = {"from_attributes": True}


class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=20)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str




class RiskProfileRequest(BaseModel):
    risk_tolerance: RiskTolerance
    sector_preferences: list[str] = Field(default_factory=list, max_length=20)
    investment_horizon: str = Field(min_length=1, max_length=50)


class RiskProfileResponse(BaseModel):
    risk_tolerance: RiskTolerance
    sector_preferences: list[str]
    investment_horizon: str
    updated_at: datetime

    model_config = {"from_attributes": True}


ALLOWED_CHANNELS = {"push", "email", "in-app"}
ALLOWED_CATEGORIES = {"price", "forecast", "news", "risk"}


class NotificationPrefsRequest(BaseModel):
    channels: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)

    @field_validator("channels")
    @classmethod
    def validate_channels(cls, v: list[str]) -> list[str]:
        invalid = set(v) - ALLOWED_CHANNELS
        if invalid:
            raise ValueError(f"Invalid channel(s): {sorted(invalid)}. Allowed: {sorted(ALLOWED_CHANNELS)}")
        return v

    @field_validator("categories")
    @classmethod
    def validate_categories(cls, v: list[str]) -> list[str]:
        invalid = set(v) - ALLOWED_CATEGORIES
        if invalid:
            raise ValueError(f"Invalid category(ies): {sorted(invalid)}. Allowed: {sorted(ALLOWED_CATEGORIES)}")
        return v


class NotificationPrefsResponse(BaseModel):
    channels: list[str]
    categories: list[str]
    updated_at: datetime

    model_config = {"from_attributes": True}

class DeviceRegisterRequest(BaseModel):
    fcm_token: str = Field(min_length=1, max_length=500)
    platform: str = Field(min_length=1, max_length=50)

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, v: str) -> str:
        allowed = {"android", "ios"}
        if v.lower() not in allowed:
            raise ValueError(f"platform must be one of {sorted(allowed)}")
        return v.lower()


class DeviceResponse(BaseModel):
    id: str
    fcm_token: str
    platform: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        if not any(c.isalpha() for c in v):
            raise ValueError("Password must contain at least one letter")
        return v