from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str | None = Field(None, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


class UserProfileResponse(BaseModel):
    id: str
    email: str
    username: str
    full_name: str | None = None
    avatar_url: str | None = None
    is_active: bool
    is_verified: bool
    is_admin: bool
    created_at: str

    model_config = {"from_attributes": True}


class UpdateProfileRequest(BaseModel):
    full_name: str | None = Field(None, max_length=255)
    avatar_url: str | None = Field(None, max_length=500)


class UpdateRiskProfileRequest(BaseModel):
    risk_tolerance: str | None = Field(None, pattern="^(conservative|moderate|aggressive)$")
    sector_preferences: list[str] | None = None
    investment_horizon: str | None = None


class UpdateNotificationPrefsRequest(BaseModel):
    channels: list[str] | None = None
    categories: list[str] | None = None


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


class ShariahScreeningResponse(BaseModel):
    symbol: str
    is_shariah_compliant: bool
    overall_score: float | None = None
    screening_method: str | None = None
    screened_at: str | None = None


class ShariahCriteriaResponse(BaseModel):
    symbol: str
    criteria: list[dict]


class ShariahPurificationResponse(BaseModel):
    symbol: str
    holding_qty: int
    holding_value: float
    purification_amount: float
    purification_rate: float


class ShariahKMI30Response(BaseModel):
    index: str
    constituents: list[dict]


class AssistantChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)
    conversation_id: str | None = None


class AssistantChatResponse(BaseModel):
    conversation_id: str
    message: str
    role: str = "assistant"


class ConversationResponse(BaseModel):
    id: str
    title: str | None = None
    created_at: str


class ConversationsListResponse(BaseModel):
    conversations: list[ConversationResponse]


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: str


class ConversationDetailResponse(BaseModel):
    id: str
    title: str | None = None
    messages: list[MessageResponse]
    created_at: str


class QuickPromptResponse(BaseModel):
    id: str
    text: str
    category: str


class QuickPromptsResponse(BaseModel):
    prompts: list[QuickPromptResponse]


class EventResponse(BaseModel):
    id: str
    title: str
    event_type: str
    symbol: str | None = None
    event_date: str
    description: str | None = None


class EventsCalendarResponse(BaseModel):
    events: list[EventResponse]
