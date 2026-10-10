"""Tests for Alert Evaluation Engine, Watchlist Target Monitoring, and Push Dispatching."""

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.alert import Alert, AlertRule
from app.models.assistant import AssistantConversation, AssistantMessage
from app.models.community import (
    CommunityComment,
    CommunityModerationAction,
    CommunityNotification,
    CommunityPost,
    CommunityPostLike,
    CommunityReport,
)
from app.models.portfolio import PortfolioTransaction, TransactionType
from app.models.stock import Stock, StockPrice
from app.models.user import (
    Device,
    EmailVerificationToken,
    PasswordResetToken,
    RefreshToken,
    User,
)
from app.models.watchlist import Watchlist, WatchlistItem
from app.tasks.alert_tasks import _is_in_cooldown, evaluate_alert_rules_task
from app.tasks.risk_tasks import check_all_portfolios_risk_breaches

TEST_TABLES = [
    User.__table__,
    Device.__table__,
    RefreshToken.__table__,
    PasswordResetToken.__table__,
    EmailVerificationToken.__table__,
    Stock.__table__,
    StockPrice.__table__,
    Alert.__table__,
    AlertRule.__table__,
    Watchlist.__table__,
    WatchlistItem.__table__,
    PortfolioTransaction.__table__,
    CommunityPost.__table__,
    CommunityComment.__table__,
    CommunityNotification.__table__,
    CommunityPostLike.__table__,
    CommunityReport.__table__,
    CommunityModerationAction.__table__,
    AssistantConversation.__table__,
    AssistantMessage.__table__,
]


@pytest.fixture
def sync_db():
    """In-memory SQLite database for synchronous Celery task testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=TEST_TABLES)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session, engine
    session.close()
    Base.metadata.drop_all(engine, tables=TEST_TABLES)


def test_cooldown_helper_redis():
    mock_redis = MagicMock()
    mock_redis.set.return_value = True
    assert _is_in_cooldown(None, mock_redis, "test_key", rule_id="rule1", ttl_seconds=1800) is False
    mock_redis.set.assert_called_with("test_key", "1", nx=True, ex=1800)

    mock_redis.set.return_value = False
    assert _is_in_cooldown(None, mock_redis, "test_key", rule_id="rule1", ttl_seconds=1800) is True


def test_cooldown_helper_db_fallback(sync_db):
    session, engine = sync_db
    user_id = uuid4().hex
    rule_id = uuid4().hex

    # No existing alert -> not in cooldown
    assert _is_in_cooldown(session, None, "key", rule_id=rule_id, ttl_seconds=1800) is False

    # Create alert for this rule
    alert = Alert(
        id=uuid4().hex,
        user_id=user_id,
        rule_id=rule_id,
        title="Test Alert",
        created_at=datetime.utcnow(),
    )
    session.add(alert)
    session.commit()

    # Now DB fallback detects existing recent alert -> in cooldown
    assert _is_in_cooldown(session, None, "key", rule_id=rule_id, ttl_seconds=1800) is True


def test_evaluate_alert_rules_price_above_and_watchlist(sync_db, monkeypatch):
    session, engine = sync_db
    monkeypatch.setattr(
        "app.services.news_pipeline.market_schedule.is_market_hours",
        AsyncMock(return_value=True),
    )

    # 1. Seed user, device, stock, alert rule, and watchlist
    user = User(
        id=uuid4().hex,
        email="trader@basarat.com",
        username="trader1",
        hashed_password="hashed_pw_123",
    )
    device = Device(
        id=uuid4().hex,
        user_id=user.id,
        fcm_token="sample_fcm_token_123",
        platform="android",
        is_active=True,
    )
    stock_ogdc = Stock(
        id=uuid4().hex,
        symbol="OGDC",
        name="Oil and Gas Development Company",
    )
    stock_sys = Stock(
        id=uuid4().hex,
        symbol="SYS",
        name="Systems Limited",
    )
    # Rule 1: OGDC price_above 150.0 (Should trigger because quote will be 155.0)
    rule_ogdc = AlertRule(
        id=uuid4().hex,
        user_id=user.id,
        stock_id=stock_ogdc.id,
        condition="price_above",
        threshold=150.0,
        is_active=True,
    )
    # Rule 2: SYS price_above 500.0 (Should NOT trigger because quote is 420.0)
    rule_sys = AlertRule(
        id=uuid4().hex,
        user_id=user.id,
        stock_id=stock_sys.id,
        condition="price_above",
        threshold=500.0,
        is_active=True,
    )
    # Watchlist Item: SYS target_price 400.0 (Should trigger because quote is 420.0 >= 400.0)
    watchlist = Watchlist(
        id=uuid4().hex,
        user_id=user.id,
        name="Main Watchlist",
        is_default=True,
    )
    wl_item = WatchlistItem(
        id=uuid4().hex,
        watchlist_id=watchlist.id,
        symbol="SYS",
        target_price=Decimal("400.00"),
    )

    session.add_all([user, device, stock_ogdc, stock_sys, rule_ogdc, rule_sys, watchlist, wl_item])
    session.commit()

    # Mock DB session in evaluate_alert_rules_task to use test sync_db
    monkeypatch.setattr("app.tasks.alert_tasks._get_sync_session", lambda: sessionmaker(bind=engine)())

    # Mock StockService quotes
    mock_quotes = [
        {"symbol": "OGDC", "current": 155.0, "change": 5.0, "change_pct": 3.33},
        {"symbol": "SYS", "current": 420.0, "change": -2.0, "change_pct": -0.47},
    ]
    monkeypatch.setattr("app.services.stock_service.StockService.get_quote_batch", lambda self, syms: mock_quotes)

    # Track dispatched push notifications
    dispatched_pushes = []

    def mock_dispatch(task, *args, **kwargs):
        dispatched_pushes.append((args, kwargs))

    monkeypatch.setattr("app.core.task_runner.dispatch_task", mock_dispatch)

    # Execute task
    result = evaluate_alert_rules_task()

    assert result["status"] == "success"
    assert result["evaluated_rules"] == 2
    assert result["evaluated_watchlist_items"] == 1
    # 1 rule triggered (OGDC) + 1 watchlist item triggered (SYS) = 2
    assert result["triggered_alerts"] == 2
    assert len(dispatched_pushes) == 2

    # Verify Alert records in database
    with Session(engine) as check_session:
        alerts = list(check_session.scalars(select(Alert).where(Alert.user_id == user.id)))
        assert len(alerts) == 2
        titles = [a.title for a in alerts]
        assert "Price Alert: OGDC" in titles
        assert "Watchlist Target: SYS" in titles


def test_evaluate_alert_rules_cooldown_suppresses_duplicates(sync_db, monkeypatch):
    session, engine = sync_db
    monkeypatch.setattr(
        "app.services.news_pipeline.market_schedule.is_market_hours",
        AsyncMock(return_value=True),
    )

    user = User(
        id=uuid4().hex,
        email="cooldown_user@basarat.com",
        username="cd_user",
        hashed_password="pw",
    )
    stock = Stock(
        id=uuid4().hex,
        symbol="LUCK",
        name="Lucky Cement",
    )
    rule = AlertRule(
        id=uuid4().hex,
        user_id=user.id,
        stock_id=stock.id,
        condition="price_above",
        threshold=800.0,
        is_active=True,
    )
    session.add_all([user, stock, rule])
    session.commit()

    monkeypatch.setattr("app.tasks.alert_tasks._get_sync_session", lambda: sessionmaker(bind=engine)())
    monkeypatch.setattr("app.services.stock_service.StockService.get_quote_batch", lambda self, syms: [
        {"symbol": "LUCK", "current": 905.0, "change": 10.0, "change_pct": 1.12}
    ])

    mock_redis = MagicMock()
    # First call to set returns True (new key set), second returns False (key exists)
    mock_redis.set.side_effect = [True, False]
    monkeypatch.setattr("app.core.redis.get_sync_redis_client", lambda: mock_redis)

    dispatched = []
    monkeypatch.setattr("app.core.task_runner.dispatch_task", lambda t, *a, **k: dispatched.append(a))

    # First run: Should trigger
    res1 = evaluate_alert_rules_task()
    assert res1["triggered_alerts"] == 1
    assert len(dispatched) == 1

    # Second run immediately after: Should be suppressed by cooldown
    res2 = evaluate_alert_rules_task()
    assert res2["triggered_alerts"] == 0
    assert len(dispatched) == 1  # No new push dispatched


def test_evaluate_alert_rules_db_cooldown_fallback(sync_db, monkeypatch):
    """Verify that when Redis is completely down (None), DB fallback suppresses duplicate alerts."""
    session, engine = sync_db
    monkeypatch.setattr(
        "app.services.news_pipeline.market_schedule.is_market_hours",
        AsyncMock(return_value=True),
    )

    user = User(
        id=uuid4().hex,
        email="db_cd_user@basarat.com",
        username="db_cd_user",
        hashed_password="pw",
    )
    stock = Stock(
        id=uuid4().hex,
        symbol="MCB",
        name="MCB Bank Limited",
    )
    rule = AlertRule(
        id=uuid4().hex,
        user_id=user.id,
        stock_id=stock.id,
        condition="price_above",
        threshold=200.0,
        is_active=True,
    )
    session.add_all([user, stock, rule])
    session.commit()

    monkeypatch.setattr("app.tasks.alert_tasks._get_sync_session", lambda: sessionmaker(bind=engine)())
    monkeypatch.setattr("app.services.stock_service.StockService.get_quote_batch", lambda self, syms: [
        {"symbol": "MCB", "current": 215.0, "change": 5.0, "change_pct": 2.38}
    ])
    # Redis is completely unavailable
    monkeypatch.setattr("app.core.redis.get_sync_redis_client", lambda: None)

    dispatched = []
    monkeypatch.setattr("app.core.task_runner.dispatch_task", lambda t, *a, **k: dispatched.append(a))

    # First run: Triggers and commits Alert record to DB
    res1 = evaluate_alert_rules_task()
    assert res1["triggered_alerts"] == 1

    # Second run: DB fallback detects existing Alert record created < 30 mins ago -> suppresses duplicate
    res2 = evaluate_alert_rules_task()
    assert res2["triggered_alerts"] == 0
    assert len(dispatched) == 1


def test_evaluate_alert_rules_percentage_drop_normalization(sync_db, monkeypatch):
    """Test percentage drop threshold normalization (user specifies positive 3.0 -> triggers on -3.5%, not +1.0%)."""
    session, engine = sync_db
    monkeypatch.setattr(
        "app.services.news_pipeline.market_schedule.is_market_hours",
        AsyncMock(return_value=True),
    )

    user = User(
        id=uuid4().hex,
        email="pct_user@basarat.com",
        username="pct_user",
        hashed_password="pw",
    )
    stock_drop = Stock(id=uuid4().hex, symbol="TRG", name="TRG Pakistan")
    stock_rise = Stock(id=uuid4().hex, symbol="HUBC", name="Hub Power Company")

    # User configured threshold=3.0 (representing a 3% drop)
    rule_drop = AlertRule(
        id=uuid4().hex,
        user_id=user.id,
        stock_id=stock_drop.id,
        condition="pct_change_down",
        threshold=3.0,
        is_active=True,
    )
    rule_rise = AlertRule(
        id=uuid4().hex,
        user_id=user.id,
        stock_id=stock_rise.id,
        condition="pct_change_down",
        threshold=3.0,
        is_active=True,
    )
    session.add_all([user, stock_drop, stock_rise, rule_drop, rule_rise])
    session.commit()

    monkeypatch.setattr("app.tasks.alert_tasks._get_sync_session", lambda: sessionmaker(bind=engine)())
    # TRG dropped -4.2% (should trigger); HUBC rose +1.5% (should NOT trigger)
    mock_quotes = [
        {"symbol": "TRG", "current": 80.0, "change": -3.5, "change_pct": -4.20},
        {"symbol": "HUBC", "current": 130.0, "change": 2.0, "change_pct": 1.50},
    ]
    monkeypatch.setattr("app.services.stock_service.StockService.get_quote_batch", lambda self, syms: mock_quotes)
    monkeypatch.setattr("app.core.redis.get_sync_redis_client", lambda: None)

    dispatched = []
    monkeypatch.setattr("app.core.task_runner.dispatch_task", lambda t, *a, **k: dispatched.append(a))

    res = evaluate_alert_rules_task()
    assert res["status"] == "success"
    assert res["triggered_alerts"] == 1
    assert len(dispatched) == 1
    # Check alert details in DB
    with Session(engine) as check_session:
        alert = check_session.scalars(select(Alert).where(Alert.rule_id == rule_drop.id)).first()
        assert alert is not None
        assert "TRG" in alert.title
        assert "down -4.20%" in alert.message


def test_check_all_portfolios_risk_breaches(sync_db, monkeypatch):
    session, engine = sync_db

    user1_id = uuid4().hex
    user2_id = uuid4().hex
    user1 = User(id=user1_id, email="u1@b.com", username="u1", hashed_password="pw")
    user2 = User(id=user2_id, email="u2@b.com", username="u2", hashed_password="pw")
    session.add_all([user1, user2])
    session.commit()

    monkeypatch.setattr("app.tasks.risk_tasks._get_sync_db", lambda: sessionmaker(bind=engine)())

    called_users = []

    def mock_check(uid):
        called_users.append(uid)
        return {"status": "checked", "breaches": []}

    monkeypatch.setattr("app.tasks.risk_tasks.check_threshold_breaches_task", mock_check)

    txn1 = PortfolioTransaction(
        id=uuid4().hex,
        user_id=user1_id,
        symbol="OGDC",
        transaction_type=TransactionType.BUY,
        quantity=Decimal("100"),
        price=Decimal("150.0"),
        transaction_date=date.today(),
    )
    session.add(txn1)
    session.commit()

    res = check_all_portfolios_risk_breaches()
    assert res["status"] == "completed"
    assert res["evaluated_users"] == 1
    assert user1_id in called_users


def test_community_push_dispatch(sync_db, monkeypatch):
    session, engine = sync_db

    from app.models.community import NotificationType
    from app.services.community_service import CommunityService

    # Create mock AsyncSession for CommunityService
    import asyncio
    from unittest.mock import AsyncMock

    mock_db = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.first.return_value = None
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_db.execute.return_value = mock_result

    dispatched = []
    monkeypatch.setattr("app.core.task_runner.dispatch_task", lambda t, *a, **k: dispatched.append((a, k)))

    service = CommunityService(mock_db)
    notif = asyncio.run(service._create_notification(
        recipient_id="user_recipient_1",
        type=NotificationType.POST_COMMENTED,
        title="New Comment",
        message="Someone commented on your post",
        post_id="post_123",
        actor_id="user_actor_2",
    ))

    assert notif.recipient_id == "user_recipient_1"
    assert len(dispatched) == 1
    args, kwargs = dispatched[0]
    # args: (recipient_id, title, message, data_dict)
    assert args[0] == "user_recipient_1"
    assert args[1] == "New Comment"
    assert args[3]["type"] == "community_notification"
    assert args[3]["post_id"] == "post_123"

