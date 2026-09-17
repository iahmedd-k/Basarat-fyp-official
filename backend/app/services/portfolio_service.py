import asyncio
import logging
from collections import defaultdict

import numpy as np
from sqlalchemy import select

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.portfolio import PortfolioHolding
from app.models.stock import Stock
from app.repository.portfolio_repository import PortfolioRepository
from app.schemas.portfolio import (
    AllocationItem,
    AllocationResponse,
    HoldingCreate,
    HoldingResponse,
    HoldingUpdate,
    PnLSummary,
    PortfolioResponse,
    RiskMetricsResponse,
)
from app.services.stock_service import StockService

logger = logging.getLogger(__name__)


class PortfolioService:
    def __init__(
        self,
        portfolio_repo: PortfolioRepository,
        stock_service: StockService,
    ):
        self.repo = portfolio_repo
        self.stocks = stock_service

    async def get_portfolio(self, user_id: str) -> PortfolioResponse:
        portfolio = await self.repo.get_or_create_portfolio(user_id)
        holdings = await self.repo.get_all_holdings(portfolio.id)
        enriched = await self._enrich_holdings(holdings)

        total_value = sum(h.current_value or 0 for h in enriched)
        total_invested = sum(h.avg_buy_price * h.quantity for h in enriched)
        total_pnl = total_value - total_invested
        total_pnl_pct = (total_pnl / total_invested * 100) if total_invested else 0.0

        return PortfolioResponse(
            id=portfolio.id,
            name=portfolio.name,
            holdings=enriched,
            total_value=round(total_value, 2),
            total_invested=round(total_invested, 2),
            total_pnl=round(total_pnl, 2),
            total_pnl_pct=round(total_pnl_pct, 2),
            created_at=portfolio.created_at,
            updated_at=portfolio.updated_at,
        )

    async def add_holding(self, user_id: str, data: HoldingCreate) -> HoldingResponse:
        portfolio = await self.repo.get_or_create_portfolio(user_id)
        stock = await self.repo.get_stock_by_symbol(data.symbol)
        if stock is None:
            raise NotFoundError("Stock not found. Please ensure the symbol is correct.")

        existing = await self.repo.get_holding_by_stock(portfolio.id, stock.id)
        if existing:
            new_qty = existing.quantity + data.quantity
            total_cost = float(existing.avg_buy_price) * existing.quantity + data.avg_buy_price * data.quantity
            new_avg = total_cost / new_qty
            holding = await self.repo.upsert_holding(
                portfolio.id, stock.id, quantity=new_qty,
                avg_buy_price=new_avg, purchase_date=data.purchase_date,
            )
        else:
            holding = await self.repo.upsert_holding(
                portfolio.id, stock.id, quantity=data.quantity,
                avg_buy_price=data.avg_buy_price, purchase_date=data.purchase_date,
            )

        quote = await asyncio.to_thread(self.stocks.get_quote, stock.symbol)
        return self._build_response(holding, stock.symbol, quote)

    async def update_holding(self, user_id: str, holding_id: str, data: HoldingUpdate) -> HoldingResponse:
        if not data.symbol and not data.quantity and not data.avg_buy_price and not data.purchase_date:
            raise BadRequestError("At least one field must be provided.")

        portfolio = await self.repo.get_or_create_portfolio(user_id)
        holding = await self.repo.get_holding(holding_id, portfolio.id)
        if holding is None:
            raise NotFoundError("Holding not found.")

        stock = await self.repo.get_stock_by_symbol(data.symbol) if data.symbol else None

        await self.repo.update_holding(
            holding,
            quantity=data.quantity,
            avg_buy_price=data.avg_buy_price,
            purchase_date=data.purchase_date,
        )

        if stock:
            symbol = stock.symbol
        else:
            stock = await self._get_stock_for_holding(holding)
            symbol = stock.symbol if stock else "UNKNOWN"

        quote = await asyncio.to_thread(self.stocks.get_quote, symbol)
        return self._build_response(holding, symbol, quote)

    async def delete_holding(self, user_id: str, holding_id: str) -> None:
        portfolio = await self.repo.get_or_create_portfolio(user_id)
        holding = await self.repo.get_holding(holding_id, portfolio.id)
        if holding is None:
            raise NotFoundError("Holding not found.")
        await self.repo.delete_holding(holding)

    async def get_pnl(self, user_id: str) -> PnLSummary:
        portfolio = await self.repo.get_or_create_portfolio(user_id)
        holdings = await self.repo.get_all_holdings(portfolio.id)
        enriched = await self._enrich_holdings(holdings)

        total_invested = sum(h.avg_buy_price * h.quantity for h in enriched)
        total_current = sum(h.current_value or 0 for h in enriched)
        total_pnl = total_current - total_invested
        total_pnl_pct = (total_pnl / total_invested * 100) if total_invested else 0.0

        return PnLSummary(
            total_invested=round(total_invested, 2),
            total_current_value=round(total_current, 2),
            total_pnl=round(total_pnl, 2),
            total_pnl_pct=round(total_pnl_pct, 2),
            holdings=enriched,
        )

    async def get_allocation(self, user_id: str) -> AllocationResponse:
        portfolio = await self.repo.get_or_create_portfolio(user_id)
        holdings = await self.repo.get_all_holdings(portfolio.id)
        enriched = await self._enrich_holdings(holdings)

        stock_map = await self._batch_load_stocks(h.stock_id for h in holdings)

        sector_map: dict[str, dict] = defaultdict(lambda: {"value": 0.0, "count": 0})
        for h in enriched:
            stock = stock_map.get(h.stock_id)
            sector = stock.sector if stock and stock.sector else "Unknown"
            sector_map[sector]["value"] += h.current_value or 0
            sector_map[sector]["count"] += 1

        total_value = sum(s["value"] for s in sector_map.values())

        allocations = sorted(
            [
                AllocationItem(
                    sector=sector,
                    value=round(stats["value"], 2),
                    weight_pct=round((stats["value"] / total_value * 100) if total_value else 0, 2),
                    holding_count=stats["count"],
                )
                for sector, stats in sector_map.items()
            ],
            key=lambda a: a.weight_pct,
            reverse=True,
        )

        return AllocationResponse(allocations=allocations, total_value=round(total_value, 2))

    async def get_risk_metrics(self, user_id: str) -> RiskMetricsResponse:
        portfolio = await self.repo.get_or_create_portfolio(user_id)
        holdings = await self.repo.get_all_holdings(portfolio.id)

        if not holdings:
            return RiskMetricsResponse()

        stock_map = await self._batch_load_stocks(h.stock_id for h in holdings)

        symbols = []
        weights = []
        total_value = 0.0

        for h in holdings:
            stock = stock_map.get(h.stock_id)
            if stock is None:
                continue
            quote = await asyncio.to_thread(self.stocks.get_quote, stock.symbol)
            current_price = quote["current"] if quote else float(h.avg_buy_price)
            value = current_price * h.quantity
            symbols.append(stock.symbol)
            weights.append(value)
            total_value += value

        if total_value == 0:
            return RiskMetricsResponse()

        weights = [w / total_value for w in weights]

        async def _fetch_history(sym: str):
            return await asyncio.to_thread(self.stocks.get_price_history, sym, "1Y")

        history_results = await asyncio.gather(*[_fetch_history(sym) for sym in symbols])

        returns_data = []
        active_symbols = []
        active_weights = []
        for sym, bars, w in zip(symbols, history_results, weights):
            if bars and bars.get("bars"):
                prices = [b["close"] for b in bars["bars"]]
                if len(prices) > 1:
                    daily_returns = [
                        (prices[i] - prices[i - 1]) / prices[i - 1]
                        for i in range(1, len(prices))
                    ]
                    returns_data.append(daily_returns)
                    active_symbols.append(sym)
                    active_weights.append(w)

        if not returns_data:
            return RiskMetricsResponse()

        min_len = min(len(r) for r in returns_data)
        returns_matrix = [r[-min_len:] for r in returns_data]

        returns_arr = np.array(returns_matrix)
        weights_arr = np.array(active_weights[: len(returns_matrix)])
        portfolio_returns = returns_arr.T @ weights_arr

        mean_return = float(np.mean(portfolio_returns))
        std_return = float(np.std(portfolio_returns, ddof=1))

        annualized_return = mean_return * 252
        annualized_vol = std_return * (252 ** 0.5)
        sharpe = (annualized_return / annualized_vol) if annualized_vol else None

        sorted_returns = np.sort(portfolio_returns)
        var_95_idx = int(len(sorted_returns) * 0.05)
        var_99_idx = int(len(sorted_returns) * 0.01)
        var_95 = float(-sorted_returns[var_95_idx]) if var_95_idx < len(sorted_returns) else None
        var_99 = float(-sorted_returns[var_99_idx]) if var_99_idx < len(sorted_returns) else None

        cumulative = np.cumprod(1 + portfolio_returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = (cumulative - running_max) / running_max
        max_drawdown = float(np.min(drawdowns))

        return RiskMetricsResponse(
            var_95=round(var_95, 4) if var_95 is not None else None,
            var_99=round(var_99, 4) if var_99 is not None else None,
            sharpe_ratio=round(sharpe, 4) if sharpe is not None else None,
            max_drawdown=round(max_drawdown, 4),
            volatility=round(annualized_vol, 4),
        )

    async def _batch_load_stocks(self, stock_ids) -> dict[str, Stock]:
        unique_ids = list(set(stock_ids))
        if not unique_ids:
            return {}
        result = await self.repo.db.execute(
            select(Stock).where(Stock.id.in_(unique_ids))
        )
        return {s.id: s for s in result.scalars().all()}

    async def _enrich_holdings(self, holdings: list[PortfolioHolding]) -> list[HoldingResponse]:
        if not holdings:
            return []

        stock_map = await self._batch_load_stocks(h.stock_id for h in holdings)

        symbols = []
        for h in holdings:
            stock = stock_map.get(h.stock_id)
            symbols.append(stock.symbol if stock else "UNKNOWN")

        quotes = await asyncio.to_thread(self.stocks.get_quote_batch, symbols)
        quote_map = {sym: q for sym, q in zip(symbols, quotes)}

        return [
            self._build_response(h, sym, quote_map.get(sym))
            for h, sym in zip(holdings, symbols)
        ]

    async def _get_stock_for_holding(self, holding: PortfolioHolding):
        result = await self.repo.db.execute(
            select(Stock).where(Stock.id == holding.stock_id)
        )
        return result.scalars().first()

    @staticmethod
    def _build_response(holding: PortfolioHolding, symbol: str, quote: dict | None) -> HoldingResponse:
        current_price = quote["current"] if quote and quote.get("current") else None
        current_value = (current_price * holding.quantity) if current_price else None
        invested = float(holding.avg_buy_price) * holding.quantity
        pnl = (current_value - invested) if current_value is not None else None
        pnl_pct = (pnl / invested * 100) if invested and pnl is not None else None

        return HoldingResponse(
            id=holding.id,
            portfolio_id=holding.portfolio_id,
            stock_id=holding.stock_id,
            symbol=symbol,
            quantity=holding.quantity,
            avg_buy_price=float(holding.avg_buy_price),
            purchase_date=holding.purchase_date,
            current_price=round(current_price, 2) if current_price else None,
            current_value=round(current_value, 2) if current_value is not None else None,
            pnl=round(pnl, 2) if pnl is not None else None,
            pnl_pct=round(pnl_pct, 2) if pnl_pct is not None else None,
            created_at=holding.created_at,
        )
