from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.db.session import get_db
from app.models.alert import Alert, AlertRule
from app.models.user import User
from app.schemas.auth import (
    AlertResponse,
    AlertRuleCreate,
    AlertRuleResponse,
    AlertRuleUpdate,
)

router = APIRouter()


@router.get(
    "/alerts/rules",
    response_model=list[AlertRuleResponse],
    summary="Get user's alert rules",
)
async def get_alert_rules(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(
            select(AlertRule)
            .where(AlertRule.user_id == user.id)
            .order_by(AlertRule.created_at.desc())
        )
        rules = result.scalars().all()
        return [
            AlertRuleResponse(
                id=r.id,
                user_id=r.user_id,
                stock_id=r.stock_id,
                condition=r.condition,
                threshold=float(r.threshold),
                is_active=r.is_active,
                created_at=r.created_at.isoformat() if r.created_at else "",
            )
            for r in rules
        ]
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to fetch alert rules: {exc}")


@router.post(
    "/alerts/rules",
    response_model=AlertRuleResponse,
    status_code=201,
    summary="Create a new alert rule",
)
async def create_alert_rule(
    data: AlertRuleCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        rule = AlertRule(
            user_id=user.id,
            stock_id=data.stock_id,
            condition=data.condition,
            threshold=data.threshold,
        )
        db.add(rule)
        await db.flush()
        await db.refresh(rule)

        return AlertRuleResponse(
            id=rule.id,
            user_id=rule.user_id,
            stock_id=rule.stock_id,
            condition=rule.condition,
            threshold=float(rule.threshold),
            is_active=rule.is_active,
            created_at=rule.created_at.isoformat() if rule.created_at else "",
        )
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to create alert rule: {exc}")


@router.patch(
    "/alerts/rules/{rule_id}",
    response_model=AlertRuleResponse,
    summary="Update an alert rule",
)
async def update_alert_rule(
    rule_id: str,
    data: AlertRuleUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(
            select(AlertRule).where(
                AlertRule.id == rule_id,
                AlertRule.user_id == user.id,
            )
        )
        rule = result.scalars().first()
        if rule is None:
            raise NotFoundError(f"Alert rule '{rule_id}' not found.")

        if data.stock_id is not None:
            rule.stock_id = data.stock_id
        if data.condition is not None:
            rule.condition = data.condition
        if data.threshold is not None:
            rule.threshold = data.threshold
        if data.is_active is not None:
            rule.is_active = data.is_active

        await db.flush()
        await db.refresh(rule)

        return AlertRuleResponse(
            id=rule.id,
            user_id=rule.user_id,
            stock_id=rule.stock_id,
            condition=rule.condition,
            threshold=float(rule.threshold),
            is_active=rule.is_active,
            created_at=rule.created_at.isoformat() if rule.created_at else "",
        )
    except NotFoundError:
        raise
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to update alert rule: {exc}")


@router.delete(
    "/alerts/rules/{rule_id}",
    status_code=204,
    summary="Delete an alert rule",
)
async def delete_alert_rule(
    rule_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(
            select(AlertRule).where(
                AlertRule.id == rule_id,
                AlertRule.user_id == user.id,
            )
        )
        rule = result.scalars().first()
        if rule is None:
            raise NotFoundError(f"Alert rule '{rule_id}' not found.")

        await db.delete(rule)
        await db.flush()
    except NotFoundError:
        raise
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to delete alert rule: {exc}")


@router.get(
    "/alerts",
    response_model=list[AlertResponse],
    summary="Get user's alerts",
)
async def get_alerts(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        query = select(Alert).where(Alert.user_id == user.id)
        if unread_only:
            query = query.where(Alert.is_read == False)

        query = query.order_by(Alert.created_at.desc())
        query = query.offset((page - 1) * limit).limit(limit)

        result = await db.execute(query)
        alerts = result.scalars().all()

        return [
            AlertResponse(
                id=a.id,
                user_id=a.user_id,
                rule_id=a.rule_id,
                title=a.title,
                message=a.message,
                is_read=a.is_read,
                created_at=a.created_at.isoformat() if a.created_at else "",
            )
            for a in alerts
        ]
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to fetch alerts: {exc}")


@router.patch(
    "/alerts/{alert_id}/read",
    status_code=204,
    summary="Mark an alert as read",
)
async def mark_alert_read(
    alert_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(
            select(Alert).where(
                Alert.id == alert_id,
                Alert.user_id == user.id,
            )
        )
        alert = result.scalars().first()
        if alert is None:
            raise NotFoundError(f"Alert '{alert_id}' not found.")

        alert.is_read = True
        await db.flush()
    except NotFoundError:
        raise
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to mark alert as read: {exc}")
