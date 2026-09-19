from fastapi import APIRouter

from app.api.v1.portfolio_routes.transactions import router as transactions_router
from app.api.v1.portfolio_routes.prices import router as prices_router
from app.api.v1.portfolio_routes.summary import router as summary_router

router = APIRouter()

router.include_router(transactions_router)
router.include_router(prices_router)
router.include_router(summary_router)