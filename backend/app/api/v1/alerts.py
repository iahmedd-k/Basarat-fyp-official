import asyncio
from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.db.session import get_db
from app.models.alert import Alert, AlertRule
from app.models.stock import Stock, StockPrice
from app.models.user import User
from app.services.stock_service import StockService
from app.schemas.auth import (
    AlertResponse,
    AlertRuleCreate,
    AlertRuleResponse,
    AlertRuleUpdate,
    AlertStockCheckResponse,
    QuickAlertRuleCreate,
    QuickAlertRuleResponse,
)

from uuid import uuid4

router = APIRouter()


async def _get_current_stock_price(db: AsyncSession, stock: Stock) -> float:
    """Fetch current market price or latest close price for a stock."""
    try:
        service = StockService()
        quotes = await asyncio.to_thread(service.get_quote_batch, [stock.symbol])
        if quotes and isinstance(quotes, list):
            q = quotes[0]
            if isinstance(q, dict) and q.get("current") is not None:
                curr = float(q["current"])
                if curr > 0:
                    return curr
    except Exception:
        pass

    stmt = (
        select(StockPrice.close)
        .where(StockPrice.stock_id == stock.id)
        .order_by(StockPrice.date.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    latest_close = result.scalar()
    if latest_close is not None and float(latest_close) > 0:
        return float(latest_close)

    raise NotFoundError(f"Could not retrieve live price or price history for '{stock.symbol}'.")


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


@router.post(
    "/alerts/quick-rule",
    response_model=QuickAlertRuleResponse,
    status_code=201,
    summary="1-Click automatic price alert for a stock",
)
async def create_quick_alert_rule(
    data: QuickAlertRuleCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """1-Click setup: Stores current market price and sets smart +/- % swing alert rules.

    - **symbol** / **stock_name** / **stock_id**: Target stock identifier.
    - **percent_threshold**: Movement percentage (default: 3.0%).
    - **direction**: 'both' (default), 'up', or 'down'.
    """
    try:
        stock = await _resolve_stock(db, data.stock_id, data.symbol, data.stock_name)
        if not stock:
            raise NotFoundError("Stock symbol or name is required for 1-click alert.")

        base_price = await _get_current_stock_price(db, stock)
        pct = float(data.percent_threshold)
        direction = str(data.direction).lower().strip()

        # Deactivate previous active rules for this user + stock
        await db.execute(
            update(AlertRule)
            .where(AlertRule.user_id == user.id, AlertRule.stock_id == stock.id, AlertRule.is_active == True)
            .values(is_active=False)
        )

        created_rules = []
        messages = []

        if direction in ("both", "up"):
            upper_threshold = round(base_price * (1.0 + pct / 100.0), 2)
            r_up = AlertRule(
                id=uuid4().hex,
                user_id=user.id,
                stock_id=stock.id,
                condition="price_above",
                threshold=upper_threshold,
                is_active=True,
            )
            db.add(r_up)
            created_rules.append(r_up)
            messages.append(f"above PKR {upper_threshold:.2f} (+{pct:.1f}%)")

        if direction in ("both", "down"):
            lower_threshold = round(base_price * (1.0 - pct / 100.0), 2)
            r_down = AlertRule(
                id=uuid4().hex,
                user_id=user.id,
                stock_id=stock.id,
                condition="price_below",
                threshold=lower_threshold,
                is_active=True,
            )
            db.add(r_down)
            created_rules.append(r_down)
            messages.append(f"below PKR {lower_threshold:.2f} (-{pct:.1f}%)")

        await db.flush()
        for r in created_rules:
            await db.refresh(r)
        await cache_invalidate(f"alerts:rules:{user.id}")

        rule_responses = [
            AlertRuleResponse(
                id=r.id,
                user_id=r.user_id,
                stock_id=r.stock_id,
                symbol=stock.symbol,
                stock_name=stock.name,
                condition=r.condition,
                threshold=float(r.threshold),
                is_active=r.is_active,
                created_at=r.created_at.isoformat() if r.created_at else "",
            )
            for r in created_rules
        ]

        msg = f"Alert set for {stock.symbol} (Base: PKR {base_price:.2f}). You will be notified if price moves {' or '.join(messages)}."

        return QuickAlertRuleResponse(
            symbol=stock.symbol,
            stock_name=stock.name,
            stock_id=stock.id,
            base_price=base_price,
            percent_threshold=pct,
            direction=direction,
            rules=rule_responses,
            message=msg,
        )
    except NotFoundError:
        raise
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to set quick alert: {exc}")


@router.get(
    "/alerts/rules/check/{symbol}",
    response_model=AlertStockCheckResponse,
    summary="Check active alert rules for a specific stock",
)
async def check_stock_alerts(
    symbol: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns active alert rules configured for a stock symbol."""
    try:
        clean_sym = symbol.strip().upper()
        stmt = (
            select(AlertRule, Stock)
            .join(Stock, AlertRule.stock_id == Stock.id)
            .where(
                AlertRule.user_id == user.id,
                AlertRule.is_active == True,
                func.upper(Stock.symbol) == clean_sym,
            )
        )
        result = await db.execute(stmt)
        rows = result.all()

        rules = [
            AlertRuleResponse(
                id=r.id,
                user_id=r.user_id,
                stock_id=r.stock_id,
                symbol=s.symbol,
                stock_name=s.name,
                condition=r.condition,
                threshold=float(r.threshold),
                is_active=r.is_active,
                created_at=r.created_at.isoformat() if r.created_at else "",
            )
            for r, s in rows
        ]

        return AlertStockCheckResponse(
            symbol=clean_sym,
            has_active_alert=len(rules) > 0,
            rules=rules,
        )
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to check stock alerts: {exc}")


@router.delete(
    "/alerts/rules/stock/{symbol}",
    status_code=204,
    summary="Delete / disable all alert rules for a stock",
)
async def delete_stock_alerts(
    symbol: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Deletes all alert rules for a given stock symbol owned by the authenticated user."""
    try:
        clean_sym = symbol.strip().upper()
        stock_res = await db.execute(select(Stock.id).where(func.upper(Stock.symbol) == clean_sym))
        stock_id = stock_res.scalar()
        if stock_id:
            from sqlalchemy import delete
            await db.execute(
                delete(AlertRule).where(
                    AlertRule.user_id == user.id,
                    AlertRule.stock_id == stock_id,
                )
            )
            await db.flush()
            await cache_invalidate(f"alerts:rules:{user.id}")
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to delete stock alerts: {exc}")


from app.core.redis import cache_get, cache_set, cache_invalidate

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
        cache_key = f"alerts:rules:{user.id}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return [AlertRuleResponse(**item) for item in cached]

        stmt = (
            select(AlertRule, Stock)
            .outerjoin(Stock, AlertRule.stock_id == Stock.id)
            .where(AlertRule.user_id == user.id)
            .order_by(AlertRule.created_at.desc())
        )
        result = await db.execute(stmt)
        rows = result.all()
        rule_responses = [
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
        await cache_set(cache_key, [r.model_dump(mode="json") for r in rule_responses], ttl_seconds=60)
        return rule_responses
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
    """Create a new custom alert rule for market conditions or stock triggers."""
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
        await cache_invalidate(f"alerts:rules:{user.id}")

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
        await cache_invalidate(f"alerts:rules:{user.id}")

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
        await cache_invalidate(f"alerts:rules:{user.id}")
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
    """Retrieve financial, portfolio, and risk alerts generated for the user."""
    try:
        cache_key = f"alerts:list:{user.id}:{page}:{limit}:{unread_only}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return [AlertResponse(**item) for item in cached]

        query = select(Alert).where(Alert.user_id == user.id)
        if unread_only:
            query = query.where(Alert.is_read == False)

        query = query.order_by(Alert.created_at.desc())
        query = query.offset((page - 1) * limit).limit(limit)

        result = await db.execute(query)
        alerts = result.scalars().all()

        alert_responses = [
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
        await cache_set(cache_key, [r.model_dump(mode="json") for r in alert_responses], ttl_seconds=30)
        return alert_responses
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
        await cache_invalidate(f"alerts:list:{user.id}:*")
        await cache_invalidate(f"notifications:list:{user.id}:*")
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
        await cache_invalidate(f"alerts:list:{user.id}:*")
        await cache_invalidate(f"notifications:list:{user.id}:*")
    except NotFoundError:
        raise
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to mark alert as read: {exc}")
