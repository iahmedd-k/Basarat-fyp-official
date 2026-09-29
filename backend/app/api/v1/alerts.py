from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.db.session import get_db
from app.models.alert import Alert, AlertRule
from app.models.stock import Stock
from app.models.user import User
from app.schemas.auth import (
    AlertResponse,
    AlertRuleCreate,
    AlertRuleResponse,
    AlertRuleUpdate,
)

router = APIRouter()


async def _resolve_stock(
    db: AsyncSession,
    stock_id: str | None = None,
    symbol: str | None = None,
    stock_name: str | None = None,
) -> Stock | None:
    """Resolve a Stock entity by stock_id, ticker symbol, or company name."""
    if stock_id:
        stock = await db.get(Stock, stock_id)
        if stock is None:
            raise NotFoundError(f"Stock with id '{stock_id}' not found.")
        return stock

    if symbol:
        clean_symbol = symbol.strip().upper()
        stmt = select(Stock).where(func.upper(Stock.symbol) == clean_symbol)
        result = await db.execute(stmt)
        stock = result.scalars().first()
        if stock is None:
            raise NotFoundError(f"Stock with symbol '{symbol}' not found.")
        return stock

    if stock_name:
        clean_name = stock_name.strip()
        stmt = (
            select(Stock)
            .where(
                Stock.is_active == True,
                or_(
                    func.lower(Stock.name) == clean_name.lower(),
                    Stock.name.ilike(f"%{clean_name}%"),
                ),
            )
            .order_by(
                case(
                    (func.lower(Stock.name) == clean_name.lower(), 1),
                    (Stock.name.ilike(f"{clean_name}%"), 2),
                    else_=3,
                )
            )
        )
        result = await db.execute(stmt)
        stock = result.scalars().first()
        if stock is None:
            raise NotFoundError(f"Stock with name '{stock_name}' not found.")
        return stock

    return None


@router.get(
    "/alerts/rules",
    response_model=list[AlertRuleResponse],
    summary="Get user's alert rules",
)
async def get_alert_rules(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all custom alert rules configured by the authenticated user.

    Returns a list of alert rule configurations including target stock ticker & name, condition string,
    threshold value, and active toggle state.
    """
    try:
        stmt = (
            select(AlertRule, Stock)
            .outerjoin(Stock, AlertRule.stock_id == Stock.id)
            .where(AlertRule.user_id == user.id)
            .order_by(AlertRule.created_at.desc())
        )
        result = await db.execute(stmt)
        rows = result.all()
        return [
            AlertRuleResponse(
                id=r.id,
                user_id=r.user_id,
                stock_id=r.stock_id,
                symbol=s.symbol if s else None,
                stock_name=s.name if s else None,
                condition=r.condition,
                threshold=float(r.threshold),
                is_active=r.is_active,
                created_at=r.created_at.isoformat() if r.created_at else "",
            )
            for r, s in rows
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
    """Create a new custom alert rule for market conditions or stock triggers.

    - **symbol** *(optional)*: Ticker symbol (e.g. `SYS`, `OGDC`, `LUCK`).
    - **stock_name** *(optional)*: Company name (e.g. `Systems Limited`).
    - **stock_id** *(optional)*: UUID of an existing stock, or `null` for general rules.
    - **condition**: Trigger identifier (e.g. `price_above`, `price_below`, `var_threshold`).
    - **threshold**: Target numeric trigger value (e.g. `250.0`).
    """
    try:
        stock = await _resolve_stock(db, data.stock_id, data.symbol, data.stock_name)

        rule = AlertRule(
            user_id=user.id,
            stock_id=stock.id if stock else None,
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
            symbol=stock.symbol if stock else None,
            stock_name=stock.name if stock else None,
            condition=rule.condition,
            threshold=float(rule.threshold),
            is_active=rule.is_active,
            created_at=rule.created_at.isoformat() if rule.created_at else "",
        )
    except NotFoundError:
        raise
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
    """Partially update an existing alert rule.

    Allows modifying threshold, trigger condition, target stock (by symbol, name, or UUID), or toggling active status.
    """
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

        if data.stock_id is not None or data.symbol is not None or data.stock_name is not None:
            stock = await _resolve_stock(db, data.stock_id, data.symbol, data.stock_name)
            rule.stock_id = stock.id if stock else None

        if data.condition is not None:
            rule.condition = data.condition
        if data.threshold is not None:
            rule.threshold = data.threshold
        if data.is_active is not None:
            rule.is_active = data.is_active

        await db.flush()
        await db.refresh(rule)

        stock = None
        if rule.stock_id:
            stock = await db.get(Stock, rule.stock_id)

        return AlertRuleResponse(
            id=rule.id,
            user_id=rule.user_id,
            stock_id=rule.stock_id,
            symbol=stock.symbol if stock else None,
            stock_name=stock.name if stock else None,
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
    """Permanently delete an alert rule owned by the authenticated user."""
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
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    unread_only: bool = Query(False, description="Filter for unread alerts only"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve financial, portfolio, and risk alerts generated for the user.

    Returns alert records with severity headers (e.g. `[HIGH] VaR Breach`), message details,
    timestamps, and read state.
    """
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
    "/alerts/read-all",
    status_code=204,
    summary="Mark all alerts as read",
)
async def mark_all_alerts_read(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark all unread alerts for the authenticated user as read."""
    try:
        await db.execute(
            update(Alert)
            .where(Alert.user_id == user.id, Alert.is_read == False)
            .values(is_read=True)
        )
        await db.flush()
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to mark all alerts as read: {exc}")


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
    """Mark a specific financial or risk alert as read (`is_read = true`)."""
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
