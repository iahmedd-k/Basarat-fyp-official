"""Initialize all database tables, seed stocks, and default admin user."""
import asyncio
import logging
import sys
from pathlib import Path
from uuid import uuid4

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
from app.db.base import Base, engine, async_session_factory
from app.models.user import EmailVerificationToken, PasswordResetToken, RefreshToken, Device
from app.models.stock import Stock, StockPrice
from app.models.alert import Alert, AlertRule
from app.models.prediction import Prediction
from app.models.news import NewsArticle, NewsArticleSymbol
from app.models.sentiment import SentimentResult, SentimentAggregate
from app.models.community import CommunityPost, CommunityComment, CommunityPostLike, CommunityFollow
from app.models.portfolio import PortfolioTransaction
from app.models.assistant import AssistantConversation, AssistantMessage

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("init_db")

async def main():
    log.info("Creating all missing database tables for all modules...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("All module tables created successfully.")

    async with async_session_factory() as session:
        # Seed Stocks from data/raw/ohlcv/*.parquet
        raw_dir = backend_dir / "data" / "raw" / "ohlcv"
        if raw_dir.exists():
            existing_stocks = set((await session.scalars(select(Stock.symbol))).all())
            new_stocks = []
            for f in raw_dir.glob("*.parquet"):
                sym = f.stem.upper()
                if sym != "ALL_SYMBOLS" and sym not in existing_stocks:
                    new_stocks.append(
                        Stock(
                            id=str(uuid4()),
                            symbol=sym,
                            name=f"{sym} Pakistan",
                            sector="General",
                            market="PSX",
                            is_active=True,
                        )
                    )
                    existing_stocks.add(sym)

            if new_stocks:
                session.add_all(new_stocks)
                await session.commit()
                log.info("Seeded %d stocks into 'stocks' table.", len(new_stocks))

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
