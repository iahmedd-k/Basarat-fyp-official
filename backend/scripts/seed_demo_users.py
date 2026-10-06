"""Comprehensive Demo User & Database Seeding Script for Basarat FYP.

This script creates and fully populates all platform features for a primary demo user
(and supporting accounts) so that during live FYP defense / evaluation, logging in
with `demo@basarat.pk` (or `admin@basarat.pk`) showcases a fully active, realistic,
and verified production state across every domain.

Features Seeded:
1. User Profiles (Verified & Active):
   - Primary Demo User: demo@basarat.pk / TestPassword12345!
   - System Admin:      admin@basarat.pk / TestPassword12345!
   - Secondary Trader:  trader2@basarat.pk / TestPassword12345!
2. 5-Sector Diversified Portfolio (SYS, ENGRO, MEBL, OGDC, HUBC, LUCK) with transactions & fees
3. Custom Watchlist with 7 PSX stocks, target prices, and notes
4. Alert Rules & In-App Notification Inbox
5. Realistic Multi-Turn AI Assistant Conversations (Grounded in PSX context, ML forecasts, & Shariah rules)
6. Community Social Layer (Stock posts, macro market posts, comments, likes, follower relationships)

Usage:
    python -m scripts.seed_demo_users
"""

import asyncio
import logging
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import or_, select

from app.core.security import hash_password
from app.db.base import async_session_factory
from app.models.alert import Alert, AlertRule
from app.models.assistant import AssistantConversation, AssistantMessage
from app.models.community import (
    CommentStatus,
    CommunityComment,
    CommunityFollow,
    CommunityPost,
    CommunityPostLike,
    PostStatus,
    PostType,
)
from app.models.portfolio import PortfolioTransaction, TransactionType
from app.models.stock import Stock
from app.models.user import User
from app.models.watchlist import Watchlist, WatchlistItem

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("seed_demo_users")


async def seed_all_demo_data():
    """Seed comprehensive demo data across all platform modules."""
    log.info("==> Starting Comprehensive Demo Data Seeding...")

    async with async_session_factory() as session:
        # -------------------------------------------------------------
        # 1. CORE PSX STOCKS FIXTURES
        # -------------------------------------------------------------
        stocks_fixtures = [
            ("SYS", "Systems Limited", "Technology"),
            ("OGDC", "Oil & Gas Development Co", "Oil & Gas Exploration"),
            ("HUBC", "Hub Power Company", "Power Generation & Distribution"),
            ("LUCK", "Lucky Cement", "Cement"),
            ("ENGRO", "Engro Corporation", "Fertilizer / Conglomerates"),
            ("MEBL", "Meezan Bank Limited", "Commercial Banks"),
            ("MARI", "Mari Energies Limited", "Oil & Gas Exploration"),
            ("EFERT", "Engro Fertilizers Limited", "Fertilizer"),
        ]
        stock_map = {}
        for sym, name, sec in stocks_fixtures:
            res = await session.execute(select(Stock).where(Stock.symbol == sym))
            stk = res.scalars().first()
            if not stk:
                stk = Stock(
                    symbol=sym,
                    name=name,
                    sector=sec,
                    market="PSX",
                    is_active=True,
                )
                session.add(stk)
                await session.flush()
                await session.refresh(stk)
            stock_map[sym] = stk

        # -------------------------------------------------------------
        # 2. SEED USERS (ADMIN, PRIMARY DEMO INVESTOR, SECONDARY TRADER)
        # -------------------------------------------------------------
        async def upsert_user(email: str, username: str, full_name: str, is_admin: bool = False) -> User:
            res = await session.execute(
                select(User).where(or_(User.email == email, User.username == username))
            )
            u = res.scalars().first()
            if not u:
                u = User(email=email.lower(), username=username)
                session.add(u)
            u.email = email.lower()
            u.username = username
            u.full_name = full_name
            u.hashed_password = hash_password("TestPassword12345!")
            u.is_active = True
            u.is_verified = True
            u.is_admin = is_admin
            u.subscription_tier = "pro"
            u.subscription_expires_at = datetime.now(timezone.utc) + timedelta(days=3650)
            u.risk_tolerance = "moderate"
            u.investment_horizon = "medium_term"
            u.sector_preferences = {
                "Technology": 0.25,
                "Fertilizer": 0.20,
                "Commercial Banks": 0.20,
                "Oil & Gas Exploration": 0.20,
                "Power Generation & Distribution": 0.15,
            }
            return u

        admin = await upsert_user("admin@basarat.pk", "admin_master", "System Administrator", is_admin=True)
        demo_user = await upsert_user("demo@basarat.pk", "demo_investor", "Hamza Farooq (Demo Investor)", is_admin=False)
        trader1 = await upsert_user("trader1@basarat.pk", "trader_one", "Ahmed Khan (Trader 1)", is_admin=False)
        trader2 = await upsert_user("trader2@basarat.pk", "trader_two", "Ali Raza (Trader 2)", is_admin=False)

        await session.commit()
        await session.refresh(admin)
        await session.refresh(demo_user)
        await session.refresh(trader1)
        await session.refresh(trader2)

        # -------------------------------------------------------------
        # 3. DIVERSIFIED 5-SECTOR PORTFOLIO FOR demo_user
        # -------------------------------------------------------------
        tx_check = await session.execute(
            select(PortfolioTransaction).where(PortfolioTransaction.user_id == demo_user.id)
        )
        if not tx_check.scalars().first():
            today = date.today()
            portfolio_txs = [
                ("SYS", TransactionType.BUY, Decimal("300.0"), Decimal("435.00"), Decimal("20.0"), today - timedelta(days=30)),
                ("ENGRO", TransactionType.BUY, Decimal("400.0"), Decimal("305.50"), Decimal("25.0"), today - timedelta(days=25)),
                ("MEBL", TransactionType.BUY, Decimal("500.0"), Decimal("220.00"), Decimal("20.0"), today - timedelta(days=20)),
                ("OGDC", TransactionType.BUY, Decimal("1200.0"), Decimal("142.00"), Decimal("30.0"), today - timedelta(days=15)),
                ("HUBC", TransactionType.BUY, Decimal("800.0"), Decimal("115.00"), Decimal("15.0"), today - timedelta(days=10)),
                ("LUCK", TransactionType.BUY, Decimal("150.0"), Decimal("890.00"), Decimal("25.0"), today - timedelta(days=5)),
            ]
            for sym, t_type, qty, prc, fee, dt in portfolio_txs:
                session.add(
                    PortfolioTransaction(
                        user_id=demo_user.id,
                        symbol=sym,
                        transaction_type=t_type,
                        quantity=qty,
                        price=prc,
                        fee=fee,
                        transaction_date=dt,
                    )
                )
            await session.commit()
            log.info("✓ Seeded 6-stock diversified portfolio for '%s'", demo_user.email)

        # -------------------------------------------------------------
        # 4. WATCHLIST & TARGET BOUNDS
        # -------------------------------------------------------------
        wl_check = await session.execute(
            select(Watchlist).where(Watchlist.user_id == demo_user.id)
        )
        wl = wl_check.scalars().first()
        if not wl:
            wl = Watchlist(
                user_id=demo_user.id,
                name="Top PSX Growth & Value",
                description="Core high-conviction Pakistani equities with strong fundamentals and bullish ML signals.",
                is_default=True,
            )
            session.add(wl)
            await session.flush()
            await session.refresh(wl)

            items_to_add = [
                ("SYS", Decimal("480.00"), "Key export tech leader; monitor IT export figures and 5D GRU/XGB forecast."),
                ("ENGRO", Decimal("340.00"), "Strong dividend yield and petrochemical expansion upside."),
                ("MEBL", Decimal("250.00"), "Premier Islamic bank beneficiary of high net interest margins."),
                ("OGDC", Decimal("165.00"), "Circular debt resolution play with robust dividend yield."),
                ("MARI", Decimal("2800.00"), "Exploration success at Ghazij & Mari field production boost."),
                ("EFERT", Decimal("170.00"), "High cash dividend yield and stable gas supply agreements."),
            ]
            for sym, tgt, note in items_to_add:
                stk_obj = stock_map.get(sym)
                session.add(
                    WatchlistItem(
                        watchlist_id=wl.id,
                        symbol=sym,
                        stock_id=stk_obj.id if stk_obj else None,
                        target_price=tgt,
                        notes=note,
                    )
                )
            await session.commit()
            log.info("✓ Seeded Watchlist with 6 stocks for '%s'", demo_user.email)

        # -------------------------------------------------------------
        # 5. ALERTS & IN-APP NOTIFICATIONS INBOX
        # -------------------------------------------------------------
        alert_check = await session.execute(
            select(Alert).where(Alert.user_id == demo_user.id)
        )
        if not alert_check.scalars().first():
            # Seed Alert Rules
            r1 = AlertRule(
                user_id=demo_user.id,
                condition="PRICE_ABOVE",
                threshold=Decimal("460.00"),
                is_active=True,
            )
            r2 = AlertRule(
                user_id=demo_user.id,
                condition="PRICE_BELOW",
                threshold=Decimal("290.00"),
                is_active=True,
            )
            session.add_all([r1, r2])
            await session.flush()

            # Seed Inbox Notifications
            notifications = [
                (
                    "🤖 AI Predictive Signal: Systems Ltd (SYS)",
                    "Hybrid Attention-BiGRU + XGBoost model signals a 5-day Bullish trend with 65.2% confidence (Rank IC: +0.093). Immediate upside target: PKR 465.00.",
                    False,
                ),
                (
                    "💰 Dividend Notice: Engro Corporation (ENGRO)",
                    "Engro Corp board announced an interim cash dividend of PKR 11.00 per share. Book closure starts next week.",
                    False,
                ),
                (
                    "📈 PSX Market Pulse: KSE-100 Up +420 Points",
                    "KSE-100 index gained +420.15 points (+0.54%) in today's morning trading session backed by heavy institutional buying in commercial banks.",
                    True,
                ),
                (
                    "🛡️ Shariah Compliance Screening Update",
                    "KMI-30 semi-annual rebalancing confirmed 100% Shariah compliance for all portfolio holdings (MEBL, ENGRO, OGDC, HUBC, LUCK).",
                    True,
                ),
                (
                    "💬 Community Interaction: Post Comment",
                    "Ali Raza (@trader_two) commented on your analysis: 'Great technical breakdown on $SYS! Supporting volume looks strong.'",
                    True,
                ),
            ]
            for title, msg, is_read in notifications:
                session.add(
                    Alert(
                        user_id=demo_user.id,
                        rule_id=r1.id if not is_read else None,
                        title=title,
                        message=msg,
                        is_read=is_read,
                        created_at=datetime.utcnow() - timedelta(hours=len(notifications) * 2),
                    )
                )
            await session.commit()
            log.info("✓ Seeded alert rules and notification inbox for '%s'", demo_user.email)

        # -------------------------------------------------------------
        # 6. MULTI-TURN AI ASSISTANT CONVERSATION THREADS
        # -------------------------------------------------------------
        chat_check = await session.execute(
            select(AssistantConversation).where(AssistantConversation.user_id == demo_user.id)
        )
        if not chat_check.scalars().first():
            # Conversation 1: SYS Technical & ML Analysis
            c1 = AssistantConversation(
                user_id=demo_user.id,
                title="Systems Limited (SYS) 5-Day Forecast & Strategy",
            )
            session.add(c1)
            await session.flush()

            m1_user = AssistantMessage(
                conversation_id=c1.id,
                role="user",
                content="What is the latest ML directional forecast and technical outlook for Systems Limited (SYS)?",
            )
            m1_assistant = AssistantMessage(
                conversation_id=c1.id,
                role="assistant",
                content="""### 📈 Systems Limited (SYS) Investment Intelligence

**1. AI / ML Predictive Model Signal:**
- **Horizon**: 5-Day (1-Week) Directional Forecast
- **Ensemble Model**: Hybrid Temporal Attention-BiGRU (v2) + Multi-Horizon XGBoost (v3)
- **Signal**: **BULLISH / BUY** (Directional Probability: **65.38%**, Confidence Score: **78/100**)
- **Expected Return Range**: +2.4% to +4.8% over the 5-day trading window.

**2. Technical Indicator Matrix:**
- **Current Price**: PKR 442.50
- **RSI (14-Day)**: 58.4 (Neutral-Bullish momentum, ample room before overbought threshold)
- **MACD**: Positive histogram crossover above zero signal line.
- **Support / Resistance**: Immediate support at **PKR 430.00**; key overhead resistance at **PKR 465.00**.

**3. Actionable Quantitative Recommendation:**
- **Recommendation**: **BUY / ACCUMULATE**
- **Suggested Entry**: PKR 438.00 – PKR 444.00
- **Target Price**: PKR 465.00 (+5.1%)
- **Stop-Loss Bound**: PKR 422.00 (-4.6% risk limit)""",
            )
            session.add_all([m1_user, m1_assistant])

            # Conversation 2: Portfolio Risk & Shariah Review
            c2 = AssistantConversation(
                user_id=demo_user.id,
                title="Portfolio Risk (VaR) & Shariah Compliance Review",
            )
            session.add(c2)
            await session.flush()

            m2_user = AssistantMessage(
                conversation_id=c2.id,
                role="user",
                content="Can you review my portfolio's sector diversification and check if MEBL and ENGRO are Shariah-compliant under KMI-30 rules?",
            )
            m2_assistant = AssistantMessage(
                conversation_id=c2.id,
                role="assistant",
                content="""### 🛡️ Portfolio Health & Shariah Screening Summary

**1. Sector Diversification & Risk Profile:**
Your portfolio holds **6 liquid PSX equities** across 5 distinct economic sectors:
- **Technology (SYS)**: 24.5%
- **Fertilizer / Conglomerates (ENGRO)**: 22.8%
- **Islamic Commercial Banking (MEBL)**: 20.6%
- **Oil & Gas Exploration (OGDC)**: 18.2%
- **Power Generation (HUBC)**: 13.9%

**Portfolio Risk Metrics:**
- **1-Day 95% Value-at-Risk (VaR)**: **1.82%** (Low-to-Moderate tail risk)
- **Conditional VaR (CVaR / Expected Shortfall)**: **2.45%**
- **Sharpe Ratio (Annualized)**: **1.64** (Strong risk-adjusted excess returns over PKRV risk-free rate).

**2. Shariah Screening (KMI-30 Standards):**
- **Meezan Bank Limited (MEBL)**: **100% Shariah Compliant**. Operates entirely under Islamic banking principles (Riba-free assets, Mudarabah/Murabaha financing).
- **Engro Corporation (ENGRO)**: **100% Shariah Compliant**.
  - Total Interest-Bearing Debt to Total Assets: **21.4%** (Well below the 37% maximum ceiling).
  - Illiquid Assets to Total Assets: **68.2%** (Above the 25% minimum threshold).
  - Non-Compliant Income: **< 1.2%** (Purification amount calculated and deductible from dividends).""",
            )
            session.add_all([m2_user, m2_assistant])

            await session.commit()
            log.info("✓ Seeded 2 multi-turn AI Assistant conversations for '%s'", demo_user.email)

        # -------------------------------------------------------------
        # 7. COMMUNITY SOCIAL POSTS, COMMENTS, LIKES & FOLLOWS
        # -------------------------------------------------------------
        post_check = await session.execute(
            select(CommunityPost).where(CommunityPost.author_id == demo_user.id)
        )
        if not post_check.scalars().first():
            # Post 1 by demo_user (Stock Post)
            p1 = CommunityPost(
                author_id=demo_user.id,
                post_type=PostType.STOCK.value,
                stock_symbol="SYS",
                content="Technical analysis on $SYS: Forming a clean cup-and-handle pattern on the daily chart. Strong volume accumulation around 435-440 PKR. Watching closely for a breakout test of 465 PKR.",
                like_count=5,
                comment_count=2,
                status=PostStatus.PUBLISHED.value,
                created_at=datetime.utcnow() - timedelta(days=2),
            )
            # Post 2 by demo_user (Macro Post)
            p2 = CommunityPost(
                author_id=demo_user.id,
                post_type=PostType.GENERAL_MARKET.value,
                content="KSE-100 Macro View: Easing CPI inflation figures and expectations of policy rate cuts should provide major momentum to cyclical sectors (Cement & Tech). Maintain balanced exposure with strict stop-losses.",
                like_count=8,
                comment_count=1,
                status=PostStatus.PUBLISHED.value,
                created_at=datetime.utcnow() - timedelta(days=1),
            )
            # Post 3 by trader2
            p3 = CommunityPost(
                author_id=trader2.id,
                post_type=PostType.STOCK.value,
                stock_symbol="ENGRO",
                content="$ENGRO dividend payout confirmed at PKR 11/share. Consistently rewarding long-term value investors despite macroeconomic headwinds.",
                like_count=4,
                comment_count=1,
                status=PostStatus.PUBLISHED.value,
                created_at=datetime.utcnow() - timedelta(hours=12),
            )
            session.add_all([p1, p2, p3])
            await session.flush()

            # Add Comments
            c_p1_1 = CommunityComment(
                post_id=p1.id,
                author_id=trader2.id,
                content="Agreed! Foreign tech inflows are also supporting the IT index. Target 465 looks realistic.",
                status=CommentStatus.PUBLISHED.value,
                created_at=datetime.utcnow() - timedelta(days=1, hours=20),
            )
            c_p1_2 = CommunityComment(
                post_id=p1.id,
                author_id=admin.id,
                content="Solid technical breakdown. Keep monitoring volume on breakout confirmation.",
                status=CommentStatus.PUBLISHED.value,
                created_at=datetime.utcnow() - timedelta(days=1, hours=15),
            )
            c_p3_1 = CommunityComment(
                post_id=p3.id,
                author_id=demo_user.id,
                content="Great yield play. Holding ENGRO in core portfolio.",
                status=CommentStatus.PUBLISHED.value,
                created_at=datetime.utcnow() - timedelta(hours=6),
            )
            session.add_all([c_p1_1, c_p1_2, c_p3_1])

            # Add Likes
            l1 = CommunityPostLike(post_id=p1.id, user_id=trader2.id)
            l2 = CommunityPostLike(post_id=p1.id, user_id=admin.id)
            l3 = CommunityPostLike(post_id=p2.id, user_id=trader2.id)
            l4 = CommunityPostLike(post_id=p3.id, user_id=demo_user.id)
            session.add_all([l1, l2, l3, l4])

            # Add Follows
            f1 = CommunityFollow(follower_id=demo_user.id, following_id=trader2.id)
            f2 = CommunityFollow(follower_id=demo_user.id, following_id=admin.id)
            f3 = CommunityFollow(follower_id=trader2.id, following_id=demo_user.id)
            session.add_all([f1, f2, f3])

            await session.commit()
            log.info("✓ Seeded community posts, comments, likes, and follows for '%s'", demo_user.email)

        log.info("===================================================================================")
        log.info("🎯 COMPREHENSIVE DEMO SEEDING COMPLETE — ALL FEATURES FULLY POPULATED")
        log.info("===================================================================================")
        log.info("1. PRIMARY DEMO INVESTOR (Use for live presentations):")
        log.info("   • Email:      demo@basarat.pk")
        log.info("   • Username:   demo_investor")
        log.info("   • Password:   TestPassword12345!")
        log.info("   • Status:     Active, Verified (is_verified=True)")
        log.info("   • Features:   Diversified 5-sector portfolio (SYS, ENGRO, MEBL, OGDC, HUBC, LUCK)")
        log.info("                 Full Watchlist with targets & notes")
        log.info("                 Active Alert Rules & In-App Notification Inbox")
        log.info("                 Multi-Turn AI Assistant Chat Threads")
        log.info("                 Community Posts, Comments, Likes & Social Follows")
        log.info("-----------------------------------------------------------------------------------")
        log.info("2. SYSTEM ADMINISTRATOR (Full admin dashboard & audit rights):")
        log.info("   • Email:      admin@basarat.pk")
        log.info("   • Username:   admin_master")
        log.info("   • Password:   TestPassword12345!")
        log.info("   • Role:       Admin (is_admin=True, is_verified=True)")
        log.info("-----------------------------------------------------------------------------------")
        log.info("3. SECONDARY TRADER (Community & follower fixture):")
        log.info("   • Email:      trader2@basarat.pk")
        log.info("   • Username:   trader_two")
        log.info("   • Password:   TestPassword12345!")
        log.info("   • Status:     Active, Verified (is_verified=True)")
        log.info("===================================================================================")


if __name__ == "__main__":
    asyncio.run(seed_all_demo_data())
