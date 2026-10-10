import logging
from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import BadRequestError, ServiceUnavailableError
from app.core.rate_limiter import limiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.subscription import (
    CreatePaymentIntentRequest,
    CreatePaymentIntentResponse,
    MockUpgradeRequest,
    SubscriptionPlansResponse,
    SubscriptionStatusResponse,
    UsageSummaryResponse,
)
from app.services.subscription_service import SubscriptionService

router = APIRouter()
log = logging.getLogger(__name__)


def _get_service(db: AsyncSession = Depends(get_db)) -> SubscriptionService:
    return SubscriptionService(db)


@router.get(
    "/subscriptions/plans",
    response_model=SubscriptionPlansResponse,
    summary="Get subscription plans & pricing",
    description=(
        "**Subscription Plans:**\n\n"
        "- Returns monthly and annual pricing in PKR and USD.\n"
        "- Lists all feature entitlements for Free vs Pro tiers."
    ),
)
async def get_plans():
    return SubscriptionService.get_plans()


from app.core.redis import cache_get, cache_set

@router.get(
    "/subscriptions/usage",
    response_model=UsageSummaryResponse,
    summary="Get current user resource usage & tier limits",
    description=(
        "**Usage Summary:**\n\n"
        "- Returns real-time AI Assistant queries used vs remaining quota.\n"
        "- Returns watchlists, portfolios, and active alerts count vs tier limits.\n"
        "- Returns feature entitlement flags for the Android UI."
    ),
)
async def get_usage(
    user: User = Depends(get_current_user),
    service: SubscriptionService = Depends(_get_service),
):
    try:
        cache_key = f"subscriptions:usage:{user.id}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return UsageSummaryResponse(**cached)

        usage = await service.get_usage_summary(user)
        await cache_set(cache_key, usage.model_dump(mode="json"), ttl_seconds=30)
        return usage
    except Exception as exc:
        log.exception("Failed to fetch usage summary for %s", user.id)
        raise ServiceUnavailableError("Failed to fetch subscription usage")


@router.post(
    "/subscriptions/create-payment-intent",
    response_model=CreatePaymentIntentResponse,
    summary="Initiate Stripe PaymentSheet checkout",
    description=(
        "**Stripe Payment Intent:**\n\n"
        "- Creates a Stripe PaymentIntent and mobile EphemeralKey.\n"
        "- Returns `client_secret` and `publishable_key` for Kotlin Android `PaymentSheet`."
    ),
)
@limiter.limit("10/minute")
async def create_payment_intent(
    request: Request,
    data: CreatePaymentIntentRequest,
    user: User = Depends(get_current_user),
    service: SubscriptionService = Depends(_get_service),
    db: AsyncSession = Depends(get_db),
):
    try:
        res = await service.create_payment_intent(
            user=user,
            plan_id=data.plan_id,
            currency=data.currency,
        )
        await db.commit()
        return res
    except Exception as exc:
        log.exception("PaymentIntent creation failed for %s", user.id)
        raise ServiceUnavailableError("Failed to initialize checkout")


@router.post(
    "/subscriptions/webhook",
    status_code=status.HTTP_200_OK,
    summary="Stripe automated subscription webhook",
    description=(
        "**Stripe Webhook:**\n\n"
        "- Listens for `payment_intent.succeeded` and `customer.subscription.*` events.\n"
        "- Automatically activates and upgrades the user in PostgreSQL."
    ),
)
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(None, alias="stripe-signature"),
    service: SubscriptionService = Depends(_get_service),
):
    payload = await request.body()
    try:
        return await service.handle_stripe_webhook(payload, stripe_signature)
    except BadRequestError:
        raise
    except Exception as exc:
        log.exception("Stripe webhook processing error: %s", exc)
        raise ServiceUnavailableError("Webhook processing failed")


@router.post(
    "/subscriptions/mock-upgrade",
    response_model=SubscriptionStatusResponse,
    summary="Sandbox / 1-Click instant test upgrade (FYP Evaluations)",
    description=(
        "**Instant Test Upgrade:**\n\n"
        "- Instantly grants Pro status for evaluations and demo testing without credit card entry.\n"
        "- Can also downgrade back to free to test free-tier quota limits."
    ),
)
async def mock_upgrade(
    data: MockUpgradeRequest,
    user: User = Depends(get_current_user),
    service: SubscriptionService = Depends(_get_service),
):
    try:
        if data.tier == "pro":
            updated_user = await service.upgrade_user(user.id, tier="pro", duration_days=data.duration_days)
            msg = f"Account upgraded to Basarat Pro for {data.duration_days} days."
        else:
            updated_user = await service.downgrade_user(user.id)
            msg = "Account reverted to Free tier."

        return SubscriptionStatusResponse(
            success=True,
            message=msg,
            tier=updated_user.subscription_tier,
            is_pro=updated_user.is_pro,
            expires_at=updated_user.subscription_expires_at,
        )
    except Exception as exc:
        log.exception("Mock upgrade failed for %s", user.id)
        raise ServiceUnavailableError("Failed to update subscription status")
