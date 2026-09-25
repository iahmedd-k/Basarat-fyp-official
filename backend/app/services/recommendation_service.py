"""Recommendation Engine — combine the forecast, live technical, fundamental, and news signals.

Signal Synthesis Formula (over sources that are available):
    composite_score = sum(normalized_source_weight * source_signal)

Where:
    - ml_signal: the shared forecast ensemble's bullish minus bearish probability
    - technical_signal: daily OHLCV technical-indicators service
    - fundamental_signal: exploratory P/E and one-year price-change heuristic

Each signal is normalized to [-1, 1] range:
    +1 = strong bullish
     0 = neutral
    -1 = strong bearish

Final verdict:
    composite > 0.15  → BUY
    composite < -0.15 → SELL
    otherwise         → HOLD

ATR bands are volatility distances, not predicted prices or execution guarantees.

Where multipliers depend on risk tolerance:
    conservative: target_mult=2.0, stop_mult=1.5
    moderate:     target_mult=3.0, stop_mult=2.0
    aggressive:   target_mult=4.0, stop_mult=2.5
"""

import json
import logging
import hashlib
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

FEATURES_PATH = Path("data/features/features_daily.parquet")
RECOMMENDATIONS_CACHE = Path("data/reports/recommendations_cache.json")

# Default engine weights. The public/API key `gru` is retained for compatibility;
# it currently weights the XGBoost ML component.
DEFAULT_WEIGHTS = {
    "gru": 0.30,
    "technical": 0.25,
    "fundamental": 0.25,
    "sentiment": 0.20,
}

# Risk profile multipliers for target/stop-loss
RISK_MULTIPLIERS = {
    "conservative": {"target": 2.0, "stop": 1.5},
    "moderate": {"target": 3.0, "stop": 2.0},
    "aggressive": {"target": 4.0, "stop": 2.5},
}

# Verdict thresholds
BUY_THRESHOLD = 0.15
SELL_THRESHOLD = -0.15


class RecommendationEngine:
    """Compute stock recommendations by synthesizing multiple signal sources."""

    def __init__(self, weights: dict | None = None):
        self.weights = weights or DEFAULT_WEIGHTS.copy()

    # ───────────────────────────────────────────────────────────────────
    # ML Signal (shared forecast ensemble)
    # ───────────────────────────────────────────────────────────────────

    def _ml_signal(self, sym_df: pd.DataFrame, symbol: str | None = None) -> tuple[float, dict]:
        """Use the same forecast inference that backs GET /forecast/{symbol}."""
        if sym_df.empty:
            return 0.0, {"status": "unavailable", "reason": "no data"}
        try:
            from app.ml.serving.inference import get_forecast

            forecast = get_forecast(symbol or str(sym_df.iloc[-1].get("symbol", "")), horizon="1W", sym_df=sym_df)
            p_bull = float(forecast["bullish_pct"]) / 100.0
            p_bear = float(forecast["bearish_pct"]) / 100.0
            score = float(np.clip(p_bull - p_bear, -1.0, 1.0))
            return score, {
                "status": "available",
                "model": "forecast ensemble",
                "model_version": forecast.get("model_version"),
                "direction": forecast.get("direction"),
                "gate_reason": forecast.get("gate_reason"),
                "as_of_date": str(forecast.get("as_of_date")),
                "signal_bias": "Bullish" if score > 0.1 else "Bearish" if score < -0.1 else "Neutral",
                "prob_bullish": round(p_bull, 4),
                "prob_bearish": round(p_bear, 4),
                "prob_sideways": round(float(forecast.get("sideways_pct", 0.0)) / 100.0, 4),
                "probabilities_calibrated": False,
            }
        except Exception as exc:
            log.warning("Forecast recommendation unavailable for %s: %s", symbol, exc)
            return 0.0, {"status": "unavailable", "reason": f"forecast inference failed: {exc}"}

    # ───────────────────────────────────────────────────────────────────
    # Technical Signal (from indicators)
    # ───────────────────────────────────────────────────────────────────

    def _technical_signal(self, sym_df: pd.DataFrame, symbol: str | None = None) -> tuple[float, dict]:
        """Compute a composite technical signal from multiple indicators.

        Combines:
        - RSI momentum
        - MACD crossover direction
        - Bollinger Band position
        - ADX trend strength
        - Volume confirmation

        Returns (signal in [-1, 1], reasoning dict).
        """
        if sym_df.empty:
            return 0.0, {"reason": "no data"}

        # Use the same daily OHLCV-backed indicator service exposed by the
        # stock technical-indicators route. It refreshes stale history from the
        # PSX provider and reports the observation date alongside its result.
        if symbol:
            try:
                from app.services.stock_service import StockService
                live = StockService().technical_indicators(symbol)
                counts = live.get("signals_breakdown") or {}
                total = sum(int(counts.get(key, 0) or 0) for key in ("buy", "neutral", "sell"))
                if total:
                    score = float(np.clip((counts.get("buy", 0) - counts.get("sell", 0)) / total, -1.0, 1.0))
                    return score, {
                        "status": "available",
                        "source": "daily OHLCV technical-indicators service",
                        "overall_signal": live.get("overall_signal"),
                        "signals_breakdown": counts,
                        "as_of_date": live.get("as_of_date"),
                        "is_stale": bool(live.get("is_stale", True)),
                        "summary": live.get("summary", {}),
                    }
                return 0.0, {
                    "status": "unavailable",
                    "reason": live.get("summary_message") or "daily OHLCV indicators returned no usable signals",
                    "as_of_date": live.get("as_of_date"),
                }
            except Exception as exc:
                log.warning("Live technical indicators unavailable for %s: %s", symbol, exc)
                return 0.0, {"status": "unavailable", "reason": f"daily OHLCV indicator lookup failed: {exc}"}

        latest = sym_df.iloc[-1]
        prev = sym_df.iloc[-2] if len(sym_df) > 1 else latest
        signals = []

        # 1. RSI momentum
        rsi = latest.get("rsi_14", 50)
        if "rsi_14" in latest.index and pd.notna(rsi):
            rsi_score = 0.0
            if rsi < 30:
                rsi_score = 0.8  # oversold = bullish
            elif rsi < 40:
                rsi_score = 0.3
            elif rsi > 70:
                rsi_score = -0.8  # overbought = bearish
            elif rsi > 60:
                rsi_score = -0.3
            signals.append(("rsi", rsi_score, f"RSI={rsi:.1f}"))

        # 2. MACD crossover
        macd_now = latest.get("macd_hist", 0)
        macd_prev = prev.get("macd_hist", 0)
        if "macd_hist" in latest.index and "macd_hist" in prev.index and pd.notna(macd_now) and pd.notna(macd_prev):
            if macd_now > 0 and macd_prev <= 0:
                macd_score = 0.7  # bullish crossover
            elif macd_now < 0 and macd_prev >= 0:
                macd_score = -0.7  # bearish crossover
            elif macd_now > 0:
                macd_score = 0.3
            elif macd_now < 0:
                macd_score = -0.3
            else:
                macd_score = 0.0
            signals.append(("macd", macd_score, f"MACD_cross={macd_now:.4f}"))

        # 3. Bollinger Band position
        close = latest.get("close", 0)
        bb_upper = latest.get("bb_upper", close)
        bb_lower = latest.get("bb_lower", close)
        bb_mid = latest.get("bb_mid", close)
        if all(name in latest.index for name in ("bb_upper", "bb_lower", "close")) and pd.notna(bb_upper) and pd.notna(bb_lower) and bb_upper != bb_lower:
            bb_pos = (close - bb_lower) / (bb_upper - bb_lower)  # 0 to 1
            # Near lower band = bullish, near upper = bearish
            bb_score = float(np.clip((0.5 - bb_pos) * 2, -1, 1))  # map [0,1] to [1,-1]
            signals.append(("bb", float(bb_score), f"BB_pos={bb_pos:.2f}"))

        # 4. ADX trend confirmation
        adx = latest.get("adx_14", latest.get("adx", 20))
        trend_mult = 1.0
        if pd.notna(adx):
            if adx > 25:
                trend_mult = 1.3
            elif adx < 15:
                trend_mult = 0.6

        # 5. Volume confirmation
        vol_zscore = latest.get("volume_zscore_20", 0)
        if pd.notna(vol_zscore) and abs(vol_zscore) > 1.5:
            vol_mult = 1.2
        else:
            vol_mult = 1.0

        if not signals:
            return 0.0, {"status": "unavailable", "reason": "no technical indicators available"}

        raw = sum(s[1] for s in signals) / len(signals)
        final = np.clip(raw * trend_mult * vol_mult, -1, 1)

        reasoning = {s[0]: s[2] for s in signals}
        reasoning["status"] = "available"
        reasoning["trend_mult"] = f"{trend_mult:.2f}"
        reasoning["vol_mult"] = f"{vol_mult:.2f}"

        return float(final), reasoning

    # ───────────────────────────────────────────────────────────────────
    # Fundamental Signal (from live market data)
    # ───────────────────────────────────────────────────────────────────

    def _fundamental_signal(self, symbol: str, overview_data: dict | None = None) -> tuple[float, dict]:
        """Compute a fundamental signal from live market data or cached data.

        Uses P/E ratio, dividend yield, and market cap to assess
        whether the stock is fundamentally attractive.

        Returns (signal in [-1, 1], reasoning dict).
        """
        try:
            if overview_data is not None:
                overview = overview_data
            else:
                from app.services.stock_service import StockService
                stock_svc = StockService()
                overview = stock_svc.get_overview(symbol)

            pe_ratio = overview.get("pe_ratio")
            year_change = overview.get("year_change_pct")

            # The overview/quote feed often has prices but no valuation fields.
            # Pull the canonical fundamentals service response before declaring
            # this component unavailable.
            if pe_ratio is None or year_change is None:
                from app.services.stock_service import StockService

                fundamentals = StockService().get_fundamentals(symbol)
                extras = fundamentals.get("extras") or {}
                if year_change is None:
                    year_change = extras.get("year_change_pct")
                if pe_ratio is None:
                    for metric in fundamentals.get("metrics") or []:
                        if str(metric.get("key", metric.get("name", ""))).strip().casefold() in {"p/e ratio", "pe ratio", "price to earnings"}:
                            pe_ratio = metric.get("value")
                            break

            signals = []

            # P/E ratio signal
            if pe_ratio is not None and pe_ratio > 0:
                if pe_ratio < 10:
                    pe_score = 0.6  # cheap
                elif pe_ratio < 15:
                    pe_score = 0.3
                elif pe_ratio > 25:
                    pe_score = -0.5  # expensive
                elif pe_ratio > 20:
                    pe_score = -0.2
                else:
                    pe_score = 0.0
                signals.append(("pe", pe_score, f"P/E={pe_ratio:.1f}"))

            # Year change momentum (mean reversion)
            if year_change is not None:
                if year_change > 50:
                    yc_score = -0.4  # extended, reversion risk
                elif year_change > 20:
                    yc_score = -0.2
                elif year_change < -30:
                    yc_score = 0.5  # beaten down, potential recovery
                elif year_change < -10:
                    yc_score = 0.3
                else:
                    yc_score = 0.0
                signals.append(("year_momentum", yc_score, f"1Y_change={year_change:.1f}%"))

            if not signals:
                reason = "PSX fundamentals feed has no usable P/E or one-year change for this symbol."
                return 0.0, {"status": "unavailable", "reason": reason}

            raw = sum(s[1] for s in signals) / len(signals)
            final = np.clip(raw, -1, 1)

            reasoning = {s[0]: s[2] for s in signals}
            reasoning["status"] = "available"
            reasoning["method"] = "unvalidated_pe_and_one_year_momentum_heuristic"
            return float(final), reasoning

        except Exception as e:
            log.warning("Fundamental signal failed for %s: %s", symbol, e)
            return 0.0, {"status": "unavailable", "reason": f"PSX fundamental data lookup failed: {e}"}

    def _sentiment_signal(self, symbol: str, sentiment_data: dict | None = None) -> tuple[float, dict]:
        """Use the asynchronously aggregated per-stock FinBERT sentiment cache."""
        try:
            from app.services.sentiment_service import get_cached_sentiment

            sentiment = sentiment_data or get_cached_sentiment(symbol)
            if sentiment and sentiment.get("status") == "unavailable":
                return 0.0, {
                    "status": "unavailable",
                    "reason": sentiment.get("reason") or "FinBERT sentiment could not be computed",
                }
            if not sentiment or int(sentiment.get("article_count", 0) or 0) <= 0:
                reason = (sentiment or {}).get("reason") or "no scored news articles available for this symbol in the 7-day window"
                return 0.0, {"status": "unavailable", "reason": reason}
            raw_score = sentiment.get("score")
            if raw_score is None or not np.isfinite(float(raw_score)):
                return 0.0, {"status": "unavailable", "reason": "sentiment score missing or invalid"}

            updated_at = sentiment.get("updated_at")
            if updated_at:
                timestamp = pd.Timestamp(updated_at)
                if timestamp.tzinfo is None:
                    timestamp = timestamp.tz_localize("UTC")
                age = datetime.now(timezone.utc) - timestamp.to_pydatetime()
                if age > timedelta(days=7) or age < timedelta(minutes=-5):
                    return 0.0, {"status": "unavailable", "reason": "sentiment cache is stale or dated in the future", "updated_at": updated_at}

            score = float(np.clip(float(raw_score), -1.0, 1.0))
            return score, {
                "status": "available", "model": "FinBERT news aggregate",
                "label": sentiment.get("label"), "article_count": int(sentiment.get("article_count", 0)),
                "trend": sentiment.get("trend"), "updated_at": updated_at,
            }
        except Exception as exc:
            log.warning("Sentiment recommendation unavailable for %s: %s", symbol, exc)
            return 0.0, {"status": "unavailable", "reason": "sentiment lookup failed"}

    # ───────────────────────────────────────────────────────────────────
    # Composite Signal
    # ───────────────────────────────────────────────────────────────────

    def compute_composite(
        self,
        symbol: str,
        sym_df: pd.DataFrame,
        weights: dict | None = None,
        overview_data: dict | None = None,
        sentiment_data: dict | None = None,
    ) -> dict:
        """Compute the full composite recommendation for a single symbol."""
        w = weights or self.weights

        ml_score, ml_reasoning = self._ml_signal(sym_df, symbol=symbol)
        tech_score, tech_reasoning = self._technical_signal(sym_df, symbol=symbol)
        fund_score, fund_reasoning = self._fundamental_signal(symbol, overview_data=overview_data)
        sentiment_score, sentiment_reasoning = self._sentiment_signal(symbol, sentiment_data=sentiment_data)

        components = [
            ("gru", ml_score, ml_reasoning),
            ("technical", tech_score, tech_reasoning),
            ("fundamental", fund_score, fund_reasoning),
            ("sentiment", sentiment_score, sentiment_reasoning),
        ]
        available = [(key, score, reason) for key, score, reason in components if reason.get("status") != "unavailable"]
        active_weight_total = sum(float(w.get(key, 0.0)) for key, _, _ in available)
        effective_weights = {
            key: (float(w.get(key, 0.0)) / active_weight_total if active_weight_total else 0.0)
            for key, _, _ in available
        }
        composite = sum(effective_weights[key] * score for key, score, _ in available) if active_weight_total else 0.0

        # Determine verdict
        if composite > BUY_THRESHOLD:
            verdict = "buy"
            decision_reason = f"Composite score {composite:.3f} crossed the BUY threshold ({BUY_THRESHOLD:.2f})."
        elif composite < SELL_THRESHOLD:
            verdict = "sell"
            decision_reason = f"Composite score {composite:.3f} crossed the SELL threshold ({SELL_THRESHOLD:.2f})."
        else:
            verdict = "hold"
            decision_reason = (
                f"Composite score {composite:.3f} is between the BUY threshold ({BUY_THRESHOLD:.2f}) "
                f"and SELL threshold ({SELL_THRESHOLD:.2f})."
            )

        # Confidence = how far from neutral
        confidence = min(abs(composite) / 0.5, 1.0)

        return {
            "symbol": symbol,
            "composite_score": round(composite, 4),
            "verdict": verdict,
            "decision_reason": decision_reason,
            "confidence": round(confidence, 4),
            "ml_signal": round(ml_score, 4),
            "technical_signal": round(tech_score, 4),
            "fundamental_signal": round(fund_score, 4),
            "sentiment_signal": round(sentiment_score, 4),
            "weights_used": w,
            "effective_weights": effective_weights,
            "status": "available" if len(available) == len(components) else "partial" if available else "insufficient_data",
            "reasoning": {
                "ml": ml_reasoning,
                "technical": tech_reasoning,
                "fundamental": fund_reasoning,
                "sentiment": sentiment_reasoning,
            },
        }

    # ───────────────────────────────────────────────────────────────────
    # Target Price + Stop Loss (ATR-based)
    # ───────────────────────────────────────────────────────────────────

    def compute_target_stop(
        self,
        symbol: str,
        sym_df: pd.DataFrame,
        risk_tolerance: str = "moderate",
        ml_direction: str | None = None,
        horizon: str = "1W",
        current_price_override: float | None = None,
    ) -> dict:
        """Compute target price and stop-loss using ATR-based method scaled for horizon."""
        if sym_df.empty:
            return {
                "symbol": symbol,
                "target_price": None,
                "stop_loss": None,
                "method": "atr_band",
                "error": "no data",
            }

        latest = sym_df.iloc[-1]
        current_price = float(current_price_override or latest.get("close", 0))
        atr = float(latest.get("atr_14", 0))

        if not np.isfinite(current_price) or not np.isfinite(atr) or current_price <= 0 or atr <= 0:
            return {
                "symbol": symbol,
                "target_price": None,
                "stop_loss": None,
                "method": "atr_band",
                "error": "invalid price or atr",
            }

        multipliers = RISK_MULTIPLIERS.get(risk_tolerance, RISK_MULTIPLIERS["moderate"])
        target_mult = multipliers["target"]
        stop_mult = multipliers["stop"]

        # Scale multipliers based on forecast horizon
        horizon_scales = {"1D": 0.60, "1W": 1.00, "1M": 1.60}
        scale = horizon_scales.get(horizon, 1.00)
        target_mult *= scale
        stop_mult *= scale

        direction = (ml_direction or "sideways").lower()
        if direction in ("bullish", "buy"):
            target_price = round(current_price + (atr * target_mult), 2)
            stop_loss = round(current_price - (atr * stop_mult), 2)
            expected_range = None
            upside_pct = round((target_price - current_price) / current_price * 100, 2)
            downside_pct = round((stop_loss - current_price) / current_price * 100, 2)
        elif direction in ("bearish", "sell"):
            target_price = round(current_price - (atr * target_mult), 2)
            stop_loss = round(current_price + (atr * stop_mult), 2)
            expected_range = None
            upside_pct = round((target_price - current_price) / current_price * 100, 2)
            downside_pct = round((stop_loss - current_price) / current_price * 100, 2)
        else:  # sideways or uncertain
            target_price = None
            # A neutral volatility envelope is not a directional stop-loss.
            stop_loss = None
            range_half = round(atr * target_mult, 2)
            expected_range = {
                "low": round(current_price - range_half, 2),
                "high": round(current_price + range_half, 2),
                "method": "atr_range",
            }
            upside_pct = None
            downside_pct = None

        stop_risk = abs(current_price - stop_loss) if stop_loss else 0
        target_reward = abs(target_price - current_price) if target_price else 0
        rr_ratio = round(target_reward / stop_risk, 2) if stop_risk > 0 and target_reward > 0 else None

        return {
            "symbol": symbol,
            "current_price": round(current_price, 2),
            "target_price": target_price,
            "stop_loss": stop_loss,
            "expected_range": expected_range,
            "upside_pct": upside_pct,
            "downside_pct": downside_pct,
            "risk_reward_ratio": rr_ratio,
            "method": "atr_band",
            "atr_14": round(atr, 4),
            "target_multiplier": round(target_mult, 2),
            "stop_multiplier": round(stop_mult, 2),
            "risk_tolerance": risk_tolerance,
            "horizon": horizon,
            "ml_direction_used": direction,
        }

    # ───────────────────────────────────────────────────────────────────
    # Full Recommendation (combines all)
    # ───────────────────────────────────────────────────────────────────

    def get_recommendation(
        self,
        symbol: str,
        risk_tolerance: str = "moderate",
        weights: dict | None = None,
        sym_df: pd.DataFrame | None = None,
        overview_data: dict | None = None,
        sentiment_data: dict | None = None,
    ) -> dict:
        """Get the full recommendation for a single symbol."""
        symbol = symbol.upper()
        if sym_df is None:
            if not FEATURES_PATH.exists():
                return {
                    "symbol": symbol,
                    "signal": "hold",
                    "confidence": 0.0,
                    "composite_score": 0.0,
                    "signals": {"ml": 0.0, "technical": 0.0, "fundamental": 0.0, "sentiment": 0.0},
                    "weights": (weights or self.weights).copy(),
                    "effective_weights": {},
                    "status": "insufficient_data",
                    "data_as_of": None,
                    "target_price": None,
                    "stop_loss": None,
                    "current_price": None,
                    "expected_range": None,
                    "upside_pct": None,
                    "downside_pct": None,
                    "risk_reward_ratio": None,
                    "target_stop_method": "atr_band",
                    "reasoning": {"error": "features not available"},
                    "technical_score": 0.0,
                    "fundamental_score": 0.0,
                }

            try:
                df = pd.read_parquet(
                    FEATURES_PATH,
                    filters=[[("symbol", "==", symbol)]],
                )
            except Exception:
                try:
                    df = pd.read_parquet(FEATURES_PATH)
                    df = df[df["symbol"] == symbol]
                except Exception:
                    df = pd.DataFrame()

            if df.empty:
                return {
                    "symbol": symbol,
                    "signal": "hold",
                    "confidence": 0.0,
                    "composite_score": 0.0,
                    "signals": {"ml": 0.0, "technical": 0.0, "fundamental": 0.0, "sentiment": 0.0},
                    "weights": (weights or self.weights).copy(),
                    "effective_weights": {},
                    "status": "insufficient_data",
                    "data_as_of": None,
                    "target_price": None,
                    "stop_loss": None,
                    "current_price": None,
                    "expected_range": None,
                    "upside_pct": None,
                    "downside_pct": None,
                    "risk_reward_ratio": None,
                    "target_stop_method": "atr_band",
                    "reasoning": {"error": f"no data for {symbol}"},
                    "technical_score": 0.0,
                    "fundamental_score": 0.0,
                }

            df["date"] = pd.to_datetime(df["date"])
            sym_df = df.copy().sort_values("date").reset_index(drop=True)

        if sym_df.empty:
            return {
                "symbol": symbol,
                "signal": "hold",
                "confidence": 0.0,
                "composite_score": 0.0,
                "signals": {"ml": 0.0, "technical": 0.0, "fundamental": 0.0, "sentiment": 0.0},
                "weights": (weights or self.weights).copy(),
                "effective_weights": {},
                "status": "insufficient_data",
                "data_as_of": None,
                "target_price": None,
                "stop_loss": None,
                "current_price": None,
                "expected_range": None,
                "upside_pct": None,
                "downside_pct": None,
                "risk_reward_ratio": None,
                "target_stop_method": "atr_band",
                "reasoning": {"error": f"no data for {symbol}"},
                "technical_score": 0.0,
                "fundamental_score": 0.0,
            }

        if overview_data is None:
            try:
                from app.services.stock_service import StockService
                overview_data = StockService().get_overview(symbol)
            except Exception as exc:
                log.info("Live quote lookup unavailable for %s: %s", symbol, exc)
                overview_data = {}

        # Compute composite signal
        composite = self.compute_composite(symbol, sym_df, weights, overview_data=overview_data, sentiment_data=sentiment_data)

        quoted_price = None
        for key in ("current", "current_price", "ltp"):
            try:
                candidate = float((overview_data or {}).get(key))
                if np.isfinite(candidate) and candidate > 0:
                    quoted_price = candidate
                    break
            except (TypeError, ValueError):
                continue

        # Compute target/stop — pass composite verdict so target aligns with signal direction
        target_stop = self.compute_target_stop(symbol, sym_df, risk_tolerance,
                                               ml_direction=composite["verdict"], horizon="1W",
                                               current_price_override=quoted_price)
        quote_as_of = None
        try:
            from app.services.market_service import MarketService
            quote_as_of = MarketService.quote_freshness().get("as_of")
        except Exception:
            pass

        return {
            "symbol": symbol,
            "name": (overview_data or {}).get("name") or symbol,
            "sector": (overview_data or {}).get("sector"),
            "signal": composite["verdict"],
            "decision_reason": composite["decision_reason"],
            "confidence": composite["confidence"],
            "composite_score": composite["composite_score"],
            "signals": {
                "ml": composite["ml_signal"],
                "technical": composite["technical_signal"],
                "fundamental": composite["fundamental_signal"],
                "sentiment": composite["sentiment_signal"],
            },
            "weights": composite["weights_used"],
            "effective_weights": composite["effective_weights"],
            "status": composite["status"],
            "data_as_of": str(sym_df.iloc[-1].get("date"))[:10] if sym_df.iloc[-1].get("date") is not None else None,
            "quote_as_of": quote_as_of,
            "quote_is_stale": bool((overview_data or {}).get("quote_is_stale", False)),
            "target_price": target_stop.get("target_price"),
            "stop_loss": target_stop.get("stop_loss"),
            "expected_range": target_stop.get("expected_range"),
            "upside_pct": target_stop.get("upside_pct"),
            "downside_pct": target_stop.get("downside_pct"),
            "risk_reward_ratio": target_stop.get("risk_reward_ratio"),
            "target_stop_method": target_stop.get("method"),
            "target_stop_reason": (
                "HOLD has no directional target or stop; the expected range is an ATR volatility envelope."
                if composite["verdict"] == "hold" and target_stop.get("expected_range")
                else "Directional target and stop are ATR-based volatility levels, not price forecasts or execution guarantees."
                if target_stop.get("target_price") is not None or target_stop.get("stop_loss") is not None
                else target_stop.get("error", "Directional ATR levels are unavailable for this data.")
            ),
            "reasoning": composite["reasoning"],
            "current_price": target_stop.get("current_price"),
            "atr_14": target_stop.get("atr_14"),
        }

    def get_all_recommendations(
        self,
        risk_tolerance: str = "moderate",
        sector_filter: str | None = None,
        weights: dict | None = None,
    ) -> list[dict]:
        """Get recommendations for all active symbols with Redis caching."""
        if not FEATURES_PATH.exists():
            return []

        # Check Redis cache first
        from app.core.redis import cache_get_sync, cache_set_sync
        requested_weights = weights or self.weights
        weight_key = hashlib.sha256(
            json.dumps(requested_weights, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:12]
        sector_key = (sector_filter or "all").strip().lower()
        cache_key = f"rec:all:v4:{risk_tolerance}:{sector_key}:{weight_key}"
        cached = cache_get_sync(cache_key)
        if cached:
            return cached

        from app.data.scraper.symbol_universe import get_active_symbols
        from app.services.stock_service import StockService

        active = get_active_symbols()
        symbols = [e["symbol"] for e in active]

        # Load features once
        try:
            df = pd.read_parquet(FEATURES_PATH)
            df["date"] = pd.to_datetime(df["date"])
        except Exception as exc:
            log.warning("Failed to read features parquet in bulk: %s", exc)
            df = pd.DataFrame()

        # Batch load quotes for fundamental signals
        stock_svc = StockService()
        quotes = stock_svc.get_quote_batch(symbols)
        quote_map = {q.get("symbol", "").upper(): q for q in quotes if isinstance(q, dict)}

        results = []
        for sym in symbols:
            try:
                overview_data = quote_map.get(sym, {})
                if not df.empty:
                    sym_df = df[df["symbol"] == sym].copy().sort_values("date").reset_index(drop=True)
                    if sym_df.empty or len(sym_df) < 10:
                        continue
                    rec = self.get_recommendation(sym, risk_tolerance, requested_weights, sym_df=sym_df, overview_data=overview_data)
                else:
                    rec = self.get_recommendation(sym, risk_tolerance, requested_weights, overview_data=overview_data)
                # The market watch quote is refreshed independently of the
                # daily feature parquet. Present the latest quote while retaining
                # the historical analysis date used for indicator/model scores.
                if overview_data.get("current"):
                    rec["current_price"] = overview_data["current"]
                try:
                    from app.services.market_service import MarketService
                    rec["quote_as_of"] = MarketService.quote_freshness().get("as_of")
                    rec["quote_is_stale"] = MarketService.quote_freshness().get("is_stale", True)
                except Exception:
                    pass
                if sector_filter and str(rec.get("sector") or "").casefold() != sector_filter.casefold():
                    continue
                results.append(rec)

            except Exception as e:
                log.warning("Recommendation failed for %s: %s", sym, e)
                continue

        # Sort by composite score (best first)
        results.sort(key=lambda r: r.get("composite_score", 0), reverse=True)
        cache_set_sync(cache_key, results, ttl_seconds=300)

        return results


# ───────────────────────────────────────────────────────────────────────
# Cache management
# ───────────────────────────────────────────────────────────────────────

def get_cached_recommendations() -> list[dict] | None:
    """Load the shared default-profile recommendation snapshot from Redis."""
    try:
        from app.core.redis import cache_get_sync
        data = cache_get_sync("recommendations:default:v5")
        if not isinstance(data, dict):
            return None
        cached_at = datetime.fromisoformat(data.get("timestamp", "2000-01-01"))
        if cached_at.tzinfo is not None:
            cached_at = cached_at.astimezone(timezone.utc).replace(tzinfo=None)
        # The Celery schedule refreshes this shared default-profile cache every 4h.
        cache_age = (datetime.utcnow() - cached_at).total_seconds()
        if cache_age < 0 or cache_age > 4 * 3600:
            return None
        recommendations = data.get("recommendations", [])
        # Reject older cache files created before the API had real component
        # scores and composite scores; otherwise clients would see misleading zeros.
        if data.get("cache_version") != 5:
            return None
        if any(
            not isinstance(item, dict)
            or not {"composite_score", "signals", "weights"}.issubset(item)
            for item in recommendations
        ):
            return None
        return recommendations
    except Exception:
        return None


def save_recommendations_cache(recommendations: list[dict]) -> None:
    """Publish recommendations for API containers through shared Redis."""
    data = {
        "timestamp": datetime.utcnow().isoformat(),
        "cache_version": 5,
        "count": len(recommendations),
        "recommendations": recommendations,
    }
    from app.core.redis import cache_set_sync
    cache_set_sync("recommendations:default:v5", data, 4 * 3600)
    log.info("Saved %d recommendations to cache", len(recommendations))
