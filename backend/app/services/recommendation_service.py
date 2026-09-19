"""Recommendation Engine — signal synthesis combining ML forecast, technical, and fundamental analysis.

Signal Synthesis Formula:
    composite_score = (gru_weight * ml_signal) + (tech_weight * technical_signal) + (fund_weight * fundamental_signal)

Where:
    - ml_signal: from GRU/XGB ensemble forecast direction + confidence
    - technical_signal: from RSI, MACD, ADX, Bollinger position
    - fundamental_signal: from P/E, EPS, market cap, dividend yield

Each signal is normalized to [-1, 1] range:
    +1 = strong bullish
     0 = neutral
    -1 = strong bearish

Final verdict:
    composite > 0.15  → BUY
    composite < -0.15 → SELL
    otherwise         → HOLD

Target Price (ATR-based):
    target = current_price + (atr_14 * target_multiplier)
    stop_loss = current_price - (atr_14 * stop_multiplier)

Where multipliers depend on risk tolerance:
    conservative: target_mult=2.0, stop_mult=1.5
    moderate:     target_mult=3.0, stop_mult=2.0
    aggressive:   target_mult=4.0, stop_mult=2.5
"""

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

FEATURES_PATH = Path("data/features/features_daily.parquet")
RECOMMENDATIONS_CACHE = Path("data/reports/recommendations_cache.json")

# Default engine weights
DEFAULT_WEIGHTS = {
    "gru": 0.40,
    "technical": 0.35,
    "fundamental": 0.25,
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


PROD_MODEL_PATH = Path("models/final/final_v3/xgb_model.ubj")
PROD_FEATURES_PATH = Path("models/final/final_v3/xgb_features.json")

_cached_xgb_model = None
_cached_xgb_features = None


def _get_production_model():
    global _cached_xgb_model, _cached_xgb_features
    if _cached_xgb_model is None and PROD_MODEL_PATH.exists():
        try:
            import xgboost as xgb
            model = xgb.XGBClassifier()
            model.load_model(str(PROD_MODEL_PATH))
            _cached_xgb_model = model
            if PROD_FEATURES_PATH.exists():
                _cached_xgb_features = json.loads(PROD_FEATURES_PATH.read_text(encoding="utf-8"))
            log.info("Loaded Production XGBoost v3 model successfully")
        except Exception as e:
            log.warning("Could not load XGBoost production model: %s", e)
    return _cached_xgb_model, _cached_xgb_features


class RecommendationEngine:
    """Compute stock recommendations by synthesizing multiple signal sources."""

    def __init__(self, weights: dict | None = None):
        self.weights = weights or DEFAULT_WEIGHTS.copy()

    # ───────────────────────────────────────────────────────────────────
    # ML Signal (Production XGBoost v3 Alpha Model)
    # ───────────────────────────────────────────────────────────────────

    def _ml_signal(self, sym_df: pd.DataFrame) -> tuple[float, dict]:
        """Derive a directional signal using the Production XGBoost v3 model.

        Evaluates the 30 clean normalized cross-sectional technical features.
        Returns (signal in [-1, 1], reasoning dict).
        """
        if sym_df.empty:
            return 0.0, {"reason": "no data"}

        latest = sym_df.iloc[-1]
        model, feat_names = _get_production_model()

        if model is not None and feat_names:
            try:
                # Build feature vector in exact training order
                feat_dict = {}
                for fn in feat_names:
                    # Match column name directly or fallback
                    raw_fn = fn.replace("_csrank", "")
                    val = latest.get(fn, latest.get(raw_fn, 0.50))
                    feat_dict[fn] = float(val) if pd.notna(val) else 0.50

                X_input = np.array([[feat_dict[fn] for fn in feat_names]])
                probs = model.predict_proba(X_input)[0]
                p_buy = float(probs[0]) # Class 0 = Buy
                
                # Scale [0, 1] to [-1, 1]
                ml_signal = np.clip(2.0 * (p_buy - 0.50), -1.0, 1.0)
                score_pct = round(p_buy * 100, 1)

                reasoning = {
                    "model": "XGBoost v3 Alpha Engine",
                    "ai_score": f"{score_pct}/100",
                    "signal_bias": "Bullish" if ml_signal > 0.1 else "Bearish" if ml_signal < -0.1 else "Neutral",
                    "prob_buy": f"{p_buy:.3f}",
                }
                return float(ml_signal), reasoning
            except Exception as e:
                log.warning("XGBoost prediction error: %s, falling back to heuristic", e)

        # Fallback heuristic if model file is not present
        signals = []
        rsi = latest.get("rsi_14", 50)
        if pd.notna(rsi):
            rsi_signal = 0.0
            if rsi < 30:
                rsi_signal = (30 - rsi) / 30
            elif rsi > 70:
                rsi_signal = -(rsi - 70) / 30
            signals.append(("rsi", rsi_signal, f"RSI={rsi:.1f}"))

        # MACD histogram signal
        macd_hist = latest.get("macd_hist", 0)
        if pd.notna(macd_hist):
            # Normalize by recent volatility of macd_hist
            macd_std = sym_df["macd_hist"].tail(20).std()
            if macd_std and macd_std > 0:
                macd_signal = np.clip(macd_hist / (2 * macd_std), -1, 1)
            else:
                macd_signal = 0.0
            signals.append(("macd", float(macd_signal), f"MACD_hist={macd_hist:.4f}"))

        # Price position relative to SMAs
        close = latest.get("close", 0)
        sma_20 = latest.get("sma_20", close)
        sma_50 = latest.get("sma_50", close)
        if pd.notna(sma_20) and pd.notna(sma_50) and sma_20 > 0 and sma_50 > 0:
            # Above both SMAs = bullish, below both = bearish
            above_20 = 1.0 if close > sma_20 else -1.0
            above_50 = 1.0 if close > sma_50 else -1.0
            sma_signal = (above_20 + above_50) / 2
            # Dampen if close is far from SMAs (mean reversion risk)
            dist_20 = (close - sma_20) / sma_20
            if abs(dist_20) > 0.1:
                sma_signal *= 0.5
            signals.append(("sma", float(sma_signal), f"close_vs_sma20={dist_20:.3f}"))

        # ADX trend strength (doesn't indicate direction, but amplifies signal)
        adx = latest.get("adx_14", latest.get("adx", 20))
        trend_strength = 1.0
        if pd.notna(adx) and adx > 25:
            trend_strength = min(adx / 50, 1.5)

        if not signals:
            return 0.0, {"reason": "no signals available"}

        # Weighted average of sub-signals
        raw_signal = sum(s[1] for s in signals) / len(signals)
        # Amplify by trend strength but cap at [-1, 1]
        final_signal = np.clip(raw_signal * trend_strength, -1, 1)

        reasoning = {s[0]: s[2] for s in signals}
        reasoning["adx_trend_strength"] = f"{trend_strength:.2f}"

        return float(final_signal), reasoning

    # ───────────────────────────────────────────────────────────────────
    # Technical Signal (from indicators)
    # ───────────────────────────────────────────────────────────────────

    def _technical_signal(self, sym_df: pd.DataFrame) -> tuple[float, dict]:
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

        latest = sym_df.iloc[-1]
        prev = sym_df.iloc[-2] if len(sym_df) > 1 else latest
        signals = []

        # 1. RSI momentum
        rsi = latest.get("rsi_14", 50)
        if pd.notna(rsi):
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
        if pd.notna(macd_now) and pd.notna(macd_prev):
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
        if pd.notna(bb_upper) and pd.notna(bb_lower) and bb_upper != bb_lower:
            bb_pos = (close - bb_lower) / (bb_upper - bb_lower)  # 0 to 1
            # Near lower band = bullish, near upper = bearish
            bb_score = (0.5 - bb_pos) * 2  # map [0,1] to [1,-1]
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
            return 0.0, {"reason": "no signals"}

        raw = sum(s[1] for s in signals) / len(signals)
        final = np.clip(raw * trend_mult * vol_mult, -1, 1)

        reasoning = {s[0]: s[2] for s in signals}
        reasoning["trend_mult"] = f"{trend_mult:.2f}"
        reasoning["vol_mult"] = f"{vol_mult:.2f}"

        return float(final), reasoning

    # ───────────────────────────────────────────────────────────────────
    # Fundamental Signal (from live market data)
    # ───────────────────────────────────────────────────────────────────

    def _fundamental_signal(self, symbol: str) -> tuple[float, dict]:
        """Compute a fundamental signal from live market data.

        Uses P/E ratio, dividend yield, and market cap to assess
        whether the stock is fundamentally attractive.

        Returns (signal in [-1, 1], reasoning dict).
        """
        try:
            from app.services.stock_service import StockService
            from app.services.market_service import MarketService

            stock_svc = StockService(market_service=MarketService())

            overview = stock_svc.get_overview(symbol)
            pe_ratio = overview.get("pe_ratio")
            year_change = overview.get("year_change_pct")
            current = overview.get("ltp", 0)

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
                return 0.0, {"reason": "no fundamental data available"}

            raw = sum(s[1] for s in signals) / len(signals)
            final = np.clip(raw, -1, 1)

            reasoning = {s[0]: s[2] for s in signals}
            return float(final), reasoning

        except Exception as e:
            log.warning("Fundamental signal failed for %s: %s", symbol, e)
            return 0.0, {"reason": f"error: {e}"}

    # ───────────────────────────────────────────────────────────────────
    # Composite Signal
    # ───────────────────────────────────────────────────────────────────

    def compute_composite(
        self,
        symbol: str,
        sym_df: pd.DataFrame,
        weights: dict | None = None,
    ) -> dict:
        """Compute the full composite recommendation for a single symbol.

        Returns dict with: composite_score, verdict, ml_signal, technical_signal,
        fundamental_signal, reasoning, confidence.
        """
        w = weights or self.weights

        ml_score, ml_reasoning = self._ml_signal(sym_df)
        tech_score, tech_reasoning = self._technical_signal(sym_df)
        fund_score, fund_reasoning = self._fundamental_signal(symbol)

        composite = (
            w["gru"] * ml_score
            + w["technical"] * tech_score
            + w["fundamental"] * fund_score
        )

        # Determine verdict
        if composite > BUY_THRESHOLD:
            verdict = "buy"
        elif composite < SELL_THRESHOLD:
            verdict = "sell"
        else:
            verdict = "hold"

        # Confidence = how far from neutral
        confidence = min(abs(composite) / 0.5, 1.0)

        return {
            "symbol": symbol,
            "composite_score": round(composite, 4),
            "verdict": verdict,
            "confidence": round(confidence, 4),
            "ml_signal": round(ml_score, 4),
            "technical_signal": round(tech_score, 4),
            "fundamental_signal": round(fund_score, 4),
            "weights_used": w,
            "reasoning": {
                "ml": ml_reasoning,
                "technical": tech_reasoning,
                "fundamental": fund_reasoning,
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
        horizon: str = "1D",
    ) -> dict:
        """Compute target price and stop-loss using ATR-based method scaled for horizon.

        Method: ATR Band (direction-aware and horizon-scaled)
            bullish:  target = current_price + (atr_14 * target_multiplier * horizon_scale)
                      stop  = current_price - (atr_14 * stop_multiplier * horizon_scale)
            bearish:  target = current_price - (atr_14 * target_multiplier * horizon_scale)
                      stop  = current_price + (atr_14 * stop_multiplier * horizon_scale)
            sideways: target = None (no directional target)
                      stop  = current_price - (atr_14 * stop_multiplier * horizon_scale)
                      expected_range = [current_price - atr*mult*scale, current_price + atr*mult*scale]

        Horizon scale:
            1D: 0.60x (intraday / 1-day move bounds)
            1W: 1.00x (standard 5-day move bounds)
            1M: 1.60x (monthly position bounds)
        """
        if sym_df.empty:
            return {
                "symbol": symbol,
                "target_price": None,
                "stop_loss": None,
                "method": "atr_band",
                "error": "no data",
            }

        latest = sym_df.iloc[-1]
        current_price = float(latest.get("close", 0))
        atr = float(latest.get("atr_14", 0))

        if current_price <= 0 or atr <= 0 or pd.isna(atr):
            return {
                "symbol": symbol,
                "target_price": None,
                "stop_loss": None,
                "method": "atr_band",
                "error": "insufficient data (no ATR or price)",
            }

        mult = RISK_MULTIPLIERS.get(risk_tolerance, RISK_MULTIPLIERS["moderate"]).copy()
        
        # Scale multipliers based on horizon
        HORIZON_SCALES = {"1D": 0.60, "1W": 1.00, "1M": 1.60}
        h_scale = HORIZON_SCALES.get(horizon, 1.00)
        
        target_mult = mult["target"] * h_scale
        stop_mult = mult["stop"] * h_scale

        # Normalize direction (default to bullish for backward compatibility)
        direction = (ml_direction or "bullish").lower()

        if direction == "bearish":
            # Bearish: target is BELOW current price, stop is above
            target_price = round(current_price - (atr * target_mult), 2)
            stop_loss = round(current_price + (atr * stop_mult), 2)
            expected_range = None
            upside_pct = round(((target_price - current_price) / current_price) * 100, 2)
            downside_pct = round(((stop_loss - current_price) / current_price) * 100, 2)
            rr_ratio = round(abs(target_price - current_price) / (abs(stop_loss - current_price) + 1e-6), 2)
        elif direction == "sideways":
            target_price = None
            stop_loss = round(current_price - (atr * stop_mult), 2)
            range_width = atr * target_mult
            expected_range = {
                "low": round(current_price - range_width, 2),
                "high": round(current_price + range_width, 2),
                "method": "atr_range",
            }
            upside_pct = None
            downside_pct = round(((stop_loss - current_price) / current_price) * 100, 2)
            rr_ratio = None
        else:
            # Bullish (or unknown): target above, stop below
            target_price = round(current_price + (atr * target_mult), 2)
            stop_loss = round(current_price - (atr * stop_mult), 2)
            expected_range = None
            upside_pct = round(((target_price - current_price) / current_price) * 100, 2)
            downside_pct = round(((stop_loss - current_price) / current_price) * 100, 2)
            rr_ratio = round(abs(target_price - current_price) / (abs(current_price - stop_loss) + 1e-6), 2)

        # Ensure stop_loss is positive (max 20% loss floor)
        stop_loss = max(stop_loss, round(current_price * 0.80, 2))

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
    ) -> dict:
        """Get the full recommendation for a single symbol.

        Combines composite signal + target/stop-loss + reasoning.
        """
        # Load features
        if not FEATURES_PATH.exists():
            return {
                "symbol": symbol,
                "signal": "hold",
                "confidence": 0.0,
                "target_price": None,
                "stop_loss": None,
                "reasoning": {"error": "features not available"},
                "technical_score": 0.0,
                "fundamental_score": 0.0,
            }

        df = pd.read_parquet(FEATURES_PATH)
        df["date"] = pd.to_datetime(df["date"])
        sym_df = df[df["symbol"] == symbol].copy().sort_values("date").reset_index(drop=True)

        if sym_df.empty:
            return {
                "symbol": symbol,
                "signal": "hold",
                "confidence": 0.0,
                "target_price": None,
                "stop_loss": None,
                "reasoning": {"error": f"no data for {symbol}"},
                "technical_score": 0.0,
                "fundamental_score": 0.0,
            }

        # Compute composite signal
        composite = self.compute_composite(symbol, sym_df, weights)

        # Compute target/stop — pass composite verdict so target aligns with signal direction
        target_stop = self.compute_target_stop(symbol, sym_df, risk_tolerance,
                                               ml_direction=composite["verdict"])

        return {
            "symbol": symbol,
            "name": symbol,
            "signal": composite["verdict"],
            "confidence": composite["confidence"],
            "target_price": target_stop.get("target_price"),
            "stop_loss": target_stop.get("stop_loss"),
            "expected_range": target_stop.get("expected_range"),
            "reasoning": composite["reasoning"],
            "technical_score": composite["technical_signal"],
            "fundamental_score": composite["fundamental_signal"],
            "ml_score": composite["ml_signal"],
            "composite_score": composite["composite_score"],
            "target_stop_method": target_stop.get("method"),
        }

    def get_all_recommendations(
        self,
        risk_tolerance: str = "moderate",
        sector_filter: str | None = None,
        weights: dict | None = None,
    ) -> list[dict]:
        """Get recommendations for all active symbols.

        Optionally filter by sector.
        """
        if not FEATURES_PATH.exists():
            return []

        from app.data.scraper.symbol_universe import get_active_symbols

        active = get_active_symbols()
        symbols = [e["symbol"] for e in active]

        # Load features once
        df = pd.read_parquet(FEATURES_PATH)
        df["date"] = pd.to_datetime(df["date"])

        results = []
        for sym in symbols:
            try:
                sym_df = df[df["symbol"] == sym].copy().sort_values("date").reset_index(drop=True)
                if sym_df.empty or len(sym_df) < 10:
                    continue

                rec = self.get_recommendation(sym, risk_tolerance, weights)
                results.append(rec)

            except Exception as e:
                log.warning("Recommendation failed for %s: %s", sym, e)
                continue

        # Sort by composite score (best first)
        results.sort(key=lambda r: r.get("composite_score", 0), reverse=True)

        return results


# ───────────────────────────────────────────────────────────────────────
# Cache management
# ───────────────────────────────────────────────────────────────────────

def get_cached_recommendations() -> list[dict] | None:
    """Load cached recommendations from disk."""
    if not RECOMMENDATIONS_CACHE.exists():
        return None
    try:
        data = json.loads(RECOMMENDATIONS_CACHE.read_text(encoding="utf-8"))
        cached_at = datetime.fromisoformat(data.get("timestamp", "2000-01-01"))
        # Cache valid for 1 hour
        if (datetime.utcnow() - cached_at).total_seconds() > 3600:
            return None
        return data.get("recommendations", [])
    except Exception:
        return None


def save_recommendations_cache(recommendations: list[dict]) -> None:
    """Save recommendations to disk cache."""
    RECOMMENDATIONS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "timestamp": datetime.utcnow().isoformat(),
        "count": len(recommendations),
        "recommendations": recommendations,
    }
    RECOMMENDATIONS_CACHE.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    log.info("Saved %d recommendations to cache", len(recommendations))
