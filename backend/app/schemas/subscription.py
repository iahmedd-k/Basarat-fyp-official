from datetime import datetime
from pydantic import BaseModel, Field


class PlanItem(BaseModel):
    id: str = Field(..., example="pro_monthly")
    name: str = Field(..., example="Basarat Pro (Monthly)")
    description: str = Field(..., example="Full institutional AI, multi-horizon forecasts & Shariah scanner")
    price_pkr: int = Field(..., example=1499)
    price_formatted_pkr: str = Field(..., example="PKR 1,499 / month")
    price_usd: float = Field(..., example=4.99)
    price_formatted_usd: str = Field(..., example="$4.99 / month")
    interval: str = Field(..., example="month")
    interval_count: int = Field(1, example=1)
    is_popular: bool = False
    features: list[str]


class SubscriptionPlansResponse(BaseModel):
    plans: list[PlanItem]
    currency_default: str = "PKR"


class AiQueriesUsage(BaseModel):
    used: int
    limit: int
    remaining: int
    resets_at: datetime | None = None
    resets_in_days: int | None = None
    window: str = Field(..., example="weekly")


class ResourceCountUsage(BaseModel):
    count: int
    limit: int | None
    is_unlimited: bool


class FeatureAccess(BaseModel):
    shariah_scanner: bool
    multi_horizon_forecast: bool
    ai_assistant_unlimited: bool
    unlimited_portfolios: bool
    unlimited_watchlists: bool
    realtime_breakout_alerts: bool
    custom_engine_weights: bool


class UsageSummaryResponse(BaseModel):
    tier: str = Field(..., example="free")
    is_pro: bool = Field(..., example=False)
    subscription_expires_at: datetime | None = None
    ai_queries: AiQueriesUsage
    portfolios: ResourceCountUsage
    watchlists: ResourceCountUsage
    alerts: ResourceCountUsage
    features: FeatureAccess


class CreatePaymentIntentRequest(BaseModel):
    plan_id: str = Field("pro_monthly", pattern="^(pro_monthly|pro_annual)$", description="Subscription plan ID")
    currency: str = Field("pkr", pattern="^(pkr|usd)$", description="Billing currency: 'pkr' or 'usd'")


class CreatePaymentIntentResponse(BaseModel):
    client_secret: str
    customer_id: str | None = None
    ephemeral_key: str | None = None
    publishable_key: str
    amount: int
    currency: str
    plan_id: str


class MockUpgradeRequest(BaseModel):
    tier: str = Field("pro", pattern="^(free|pro)$", description="Tier to set: 'free' or 'pro'")
    duration_days: int = Field(30, ge=1, le=365, description="Subscription duration in days (for pro tier)")


class SubscriptionStatusResponse(BaseModel):
    success: bool
    message: str
    tier: str
    is_pro: bool
    expires_at: datetime | None = None
