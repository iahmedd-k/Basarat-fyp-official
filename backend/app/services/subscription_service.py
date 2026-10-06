import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import (
    BadRequestError,
    ForbiddenError,
    NotFoundError,
    ServiceUnavailableError,
)
from app.core.redis import cache_get, cache_invalidate, cache_set
from app.models.alert import Alert, AlertRule
from app.models.portfolio import PortfolioTransaction
from app.models.user import User
from app.models.watchlist import Watchlist
from app.schemas.subscription import (
    AiQueriesUsage,
    CreatePaymentIntentResponse,
    FeatureAccess,
    PlanItem,
    ResourceCountUsage,
    SubscriptionPlansResponse,
    UsageSummaryResponse,
)

try:
    import stripe
except ImportError:
    stripe = None

log = logging.getLogger(__name__)
settings = get_settings()

if stripe and getattr(settings, "STRIPE_SECRET_KEY", ""):
    stripe.api_key = settings.STRIPE_SECRET_KEY


class SubscriptionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def get_plans() -> SubscriptionPlansResponse:
        """Return available subscription plans with pricing in PKR and USD."""
        monthly_pkr = int(getattr(settings, "STRIPE_PRICE_MONTHLY_PKR", 149900) / 100)
        annual_pkr = int(getattr(settings, "STRIPE_PRICE_ANNUAL_PKR", 1299900) / 100)
        monthly_usd = float(getattr(settings, "STRIPE_PRICE_MONTHLY_USD", 499) / 100)
        annual_usd = float(getattr(settings, "STRIPE_PRICE_ANNUAL_USD", 4499) / 100)

        return SubscriptionPlansResponse(
            plans=[
                PlanItem(
                    id="pro_monthly",
                    name="Basarat Pro (Monthly)",
                    description="Full institutional AI, multi-horizon forecasts & Shariah scanner",
                    price_pkr=monthly_pkr,
                    price_formatted_pkr=f"PKR {monthly_pkr:,} / month",
                    price_usd=monthly_usd,
                    price_formatted_usd=f"${monthly_usd:.2f} / month",
                    interval="month",
                    interval_count=1,
                    is_popular=False,
                    features=[
                        "All 4 ML Forecast Horizons (1D, 1W, 2W, 1M)",
                        "Full KSE-100 Dual-Model Ensemble Signals",
                        "50 AI Stock Assistant Questions / Day",
                        "Full PSX Shariah Compliance Scanner",
                        "Unlimited Portfolios & Watchlists",
                        "Unlimited Real-Time Push Alerts (FCM)",
                        "Custom Engine Model Weight Synthesizer",
                    ],
                ),
                PlanItem(
                    id="pro_annual",
                    name="Basarat Pro (Annual)",
                    description="Best value: 12 months access with 28% discount",
                    price_pkr=annual_pkr,
                    price_formatted_pkr=f"PKR {annual_pkr:,} / year",
                    price_usd=annual_usd,
                    price_formatted_usd=f"${annual_usd:.2f} / year",
                    interval="year",
                    interval_count=1,
                    is_popular=True,
                    features=[
                        "Save 28% compared to monthly billing",
                        "All 4 ML Forecast Horizons (1D, 1W, 2W, 1M)",
                        "Full KSE-100 Dual-Model Ensemble Signals",
                        "50 AI Stock Assistant Questions / Day",
                        "Full PSX Shariah Compliance Scanner",
                        "Unlimited Portfolios & Watchlists",
                        "Unlimited Real-Time Push Alerts (FCM)",
                        "Priority Server Inference & Early Feature Access",
                    ],
                ),
            ],
            currency_default="PKR",
        )

    async def get_usage_summary(self, user: User) -> UsageSummaryResponse:
        """Calculate real-time resource usage vs tier limits."""
        is_pro = user.is_pro
        tier = "pro" if is_pro else "free"

        # 1. AI Assistant Query Quota
        now = datetime.now(timezone.utc)
        if is_pro:
            # Pro: 50 queries / day
            day_key = now.strftime("%Y-%m-%d")
            redis_key = f"usage:ai:{user.id}:{day_key}"
            limit = 50
            window = "daily"
            tomorrow = datetime(now.year, now.month, now.day, tzinfo=timezone.utc) + timedelta(days=1)
            resets_at = tomorrow
            resets_in_days = 1
        else:
            # Free: 5 queries / week (resets every Monday)
            year, week_num, weekday = now.isocalendar()
            redis_key = f"usage:ai:{user.id}:{year}-W{week_num}"
            limit = 5
            window = "weekly"
            days_until_monday = (7 - (weekday - 1)) % 7 or 7
            next_monday = datetime(now.year, now.month, now.day, tzinfo=timezone.utc) + timedelta(days=days_until_monday)
            resets_at = next_monday
            resets_in_days = days_until_monday

        cached_ai_count = await cache_get(redis_key)
        used_ai = int(cached_ai_count) if cached_ai_count is not None else 0
        remaining_ai = max(0, limit - used_ai)

        ai_usage = AiQueriesUsage(
            used=used_ai,
            limit=limit,
            remaining=remaining_ai,
            resets_at=resets_at,
            resets_in_days=resets_in_days,
            window=window,
        )

        # 2. Watchlists Count
        res_wl = await self.db.execute(
            select(func.count(Watchlist.id)).where(Watchlist.user_id == user.id)
        )
        wl_count = res_wl.scalar() or 0
        wl_limit = None if is_pro else 1
        wl_usage = ResourceCountUsage(
            count=wl_count,
            limit=wl_limit,
            is_unlimited=is_pro,
        )

        # 3. Portfolios Count
        res_port = await self.db.execute(
            select(func.count(func.distinct(PortfolioTransaction.symbol))).where(
                PortfolioTransaction.user_id == user.id
            )
        )
        port_count = 1 if (res_port.scalar() or 0) > 0 else 0
        port_limit = None if is_pro else 1
        port_usage = ResourceCountUsage(
            count=port_count,
            limit=port_limit,
            is_unlimited=is_pro,
        )

        # 4. Active Price Alerts Count
        res_alerts = await self.db.execute(
            select(func.count(AlertRule.id)).where(
                AlertRule.user_id == user.id,
                AlertRule.is_active == True,
            )
        )
        alerts_count = res_alerts.scalar() or 0
        alerts_limit = None if is_pro else 2
        alerts_usage = ResourceCountUsage(
            count=alerts_count,
            limit=alerts_limit,
            is_unlimited=is_pro,
        )

        # 5. Features Access
        features = FeatureAccess(
            shariah_scanner=is_pro,
            multi_horizon_forecast=True,
            ai_assistant_unlimited=is_pro,
            unlimited_portfolios=is_pro,
            unlimited_watchlists=is_pro,
            realtime_breakout_alerts=is_pro,
            custom_engine_weights=is_pro,
        )

        return UsageSummaryResponse(
            tier=tier,
            is_pro=is_pro,
            subscription_expires_at=user.subscription_expires_at,
            ai_queries=ai_usage,
            portfolios=port_usage,
            watchlists=wl_usage,
            alerts=alerts_usage,
            features=features,
        )

    async def check_and_increment_ai_quota(self, user: User) -> None:
        """Verify user has remaining AI Assistant queries; increments counter upon success."""
        is_pro = user.is_pro
        now = datetime.now(timezone.utc)

        if is_pro:
            day_key = now.strftime("%Y-%m-%d")
            redis_key = f"usage:ai:{user.id}:{day_key}"
            limit = 50
            ttl = 86400 * 2
            period = "today"
        else:
            year, week_num, _ = now.isocalendar()
            redis_key = f"usage:ai:{user.id}:{year}-W{week_num}"
            limit = 5
            ttl = 86400 * 8
            period = "this week"

        cached = await cache_get(redis_key)
        current = int(cached) if cached is not None else 0

        if current >= limit:
            raise ForbiddenError(
                f"You have reached your {period} AI Assistant query limit ({limit} questions). "
                "Upgrade to Basarat Pro for expanded daily institutional AI queries.",
                code="AI_QUOTA_EXCEEDED",
            )

        # Increment quota
        await cache_set(redis_key, current + 1, ttl_seconds=ttl)

    async def create_payment_intent(
        self,
        user: User,
        plan_id: str = "pro_monthly",
        currency: str = "pkr",
    ) -> CreatePaymentIntentResponse:
        """Create a Stripe PaymentIntent for Android / iOS / Web PaymentSheet."""
        currency = currency.lower()
        if plan_id == "pro_annual":
            amount = getattr(settings, "STRIPE_PRICE_ANNUAL_PKR", 1299900) if currency == "pkr" else getattr(settings, "STRIPE_PRICE_ANNUAL_USD", 4499)
        else:
            amount = getattr(settings, "STRIPE_PRICE_MONTHLY_PKR", 149900) if currency == "pkr" else getattr(settings, "STRIPE_PRICE_MONTHLY_USD", 499)

        pub_key = getattr(settings, "STRIPE_PUBLISHABLE_KEY", "") or "pk_test_sample_basarat"

        if stripe and getattr(settings, "STRIPE_SECRET_KEY", ""):
            try:
                # 1. Ensure customer exists in Stripe
                customer_id = user.stripe_customer_id
                if not customer_id:
                    customer = stripe.Customer.create(
                        email=user.email,
                        name=user.full_name or user.username,
                        metadata={"user_id": user.id},
                    )
                    customer_id = customer.id
                    user.stripe_customer_id = customer_id
                    await self.db.flush()

                # 2. Ephemeral Key for mobile SDK
                ephemeral_key = stripe.EphemeralKey.create(
                    customer=customer_id,
                    stripe_version="2024-06-20",
                )

                # 3. Create PaymentIntent
                intent = stripe.PaymentIntent.create(
                    amount=amount,
                    currency=currency,
                    customer=customer_id,
                    metadata={
                        "user_id": user.id,
                        "plan_id": plan_id,
                    },
                    automatic_payment_methods={"enabled": True},
                )

                return CreatePaymentIntentResponse(
                    client_secret=intent.client_secret,
                    customer_id=customer_id,
                    ephemeral_key=ephemeral_key.secret,
                    publishable_key=pub_key,
                    amount=amount,
                    currency=currency,
                    plan_id=plan_id,
                )
            except Exception as exc:
                log.warning("Stripe PaymentIntent generation failed; falling back to sandbox: %s", exc)

        # Sandbox / Mock fallback when Stripe credentials are not configured
        mock_secret = f"pi_mock_{user.id}_{plan_id}_secret_test"
        return CreatePaymentIntentResponse(
            client_secret=mock_secret,
            customer_id=f"cus_mock_{user.id}",
            ephemeral_key="ek_mock_test_secret",
            publishable_key=pub_key,
            amount=amount,
            currency=currency,
            plan_id=plan_id,
        )

    async def upgrade_user(self, user_id: str, tier: str = "pro", duration_days: int = 30) -> User:
        """Upgrade user subscription tier in PostgreSQL and invalidate/update cache."""
        now = datetime.now(timezone.utc)
        new_expiry = now + timedelta(days=duration_days)
        user = None

        try:
            user = await self.db.get(User, user_id)
            if user:
                if user.subscription_expires_at and user.subscription_expires_at > now:
                    new_expiry = user.subscription_expires_at + timedelta(days=duration_days)
                user.subscription_tier = tier
                user.subscription_expires_at = new_expiry
                await self.db.flush()
        except Exception as exc:
            log.debug("DB flush in upgrade_user skipped: %s", exc)

        if not user:
            user = User(
                id=user_id,
                subscription_tier=tier,
                subscription_expires_at=new_expiry,
                email=f"user_{user_id}@example.com",
                username=f"user_{user_id}",
                hashed_password="",
            )

        # Update cached user
        cached_user = await cache_get(f"auth:user:{user_id}")
        if isinstance(cached_user, dict):
            cached_user["subscription_tier"] = tier
            cached_user["subscription_expires_at"] = new_expiry.isoformat()
            await cache_set(f"auth:user:{user_id}", cached_user, ttl_seconds=300)
        else:
            await cache_invalidate(f"auth:user:{user_id}")

        return user

    async def downgrade_user(self, user_id: str) -> User:
        """Revert user to free subscription tier."""
        user = None
        try:
            user = await self.db.get(User, user_id)
            if user:
                user.subscription_tier = "free"
                user.subscription_expires_at = None
                await self.db.flush()
        except Exception as exc:
            log.debug("DB flush in downgrade_user skipped: %s", exc)

        if not user:
            user = User(
                id=user_id,
                subscription_tier="free",
                subscription_expires_at=None,
                email=f"user_{user_id}@example.com",
                username=f"user_{user_id}",
                hashed_password="",
            )

        cached_user = await cache_get(f"auth:user:{user_id}")
        if isinstance(cached_user, dict):
            cached_user["subscription_tier"] = "free"
            cached_user["subscription_expires_at"] = None
            await cache_set(f"auth:user:{user_id}", cached_user, ttl_seconds=300)
        else:
            await cache_invalidate(f"auth:user:{user_id}")

        return user

    async def handle_stripe_webhook(self, payload: bytes, sig_header: str | None) -> dict:
        """Process incoming Stripe webhooks to automate subscription activation."""
        if not stripe or not getattr(settings, "STRIPE_WEBHOOK_SECRET", ""):
            return {"status": "ignored", "reason": "Webhook secret not configured"}

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except Exception as exc:
            log.warning("Stripe webhook verification failed: %s", exc)
            raise BadRequestError(f"Webhook signature verification failed: {exc}")

        event_type = event.get("type")
        data_obj = event.get("data", {}).get("object", {})

        if event_type == "payment_intent.succeeded":
            metadata = data_obj.get("metadata", {})
            user_id = metadata.get("user_id")
            plan_id = metadata.get("plan_id", "pro_monthly")
            days = 365 if plan_id == "pro_annual" else 30
            if user_id:
                await self.upgrade_user(user_id, tier="pro", duration_days=days)
                await self.db.commit()
                log.info("Upgraded user %s to pro via payment_intent.succeeded", user_id)

        elif event_type in ("customer.subscription.deleted", "customer.subscription.paused"):
            metadata = data_obj.get("metadata", {})
            user_id = metadata.get("user_id")
            if user_id:
                await self.downgrade_user(user_id)
                await self.db.commit()
                log.info("Downgraded user %s to free via %s", user_id, event_type)

        return {"status": "success", "event": event_type}
