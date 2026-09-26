import React, { useState, useEffect, useCallback } from 'react'
import { forecastApi } from '../api/forecast'
import { getCached, getCacheKey } from '../api/cache'
import {
  FALLBACK_STOCK_FORECASTS,
  generateFallbackHistory,
} from '../api/forecastFallback'

function formatNumber(value, fractionDigits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  return Number(value).toLocaleString('en-PK', {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  })
}

function formatPercent(value, decimals = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  const num = Number(value)
  return `${num >= 0 ? '+' : ''}${num.toFixed(decimals)}%`
}

function formatDate(dateStr) {
  if (!dateStr) return '—'
  try {
    const d = new Date(dateStr)
    return d.toLocaleDateString('en-PK', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    })
  } catch {
    return dateStr
  }
}

export default function StockForecastSection({ symbol = 'MEBL', onStock }) {
  const [horizon, setHorizon] = useState('1D')
  const sym = symbol.toUpperCase()

  const cachedForecast = getCached(getCacheKey(`/forecast/${encodeURIComponent(sym)}?horizon=${horizon}`))?.data
  const cachedHistory = getCached(getCacheKey(`/forecast/${encodeURIComponent(sym)}/history?limit=20`))?.data

  const [forecast, setForecast] = useState(() => cachedForecast || null)
  const [history, setHistory] = useState(() => cachedHistory || null)
  const [loading, setLoading] = useState(() => !cachedForecast)
  const [historyLoading, setHistoryLoading] = useState(() => !cachedHistory)

  // Load ML Forecast for symbol and horizon
  const loadForecast = useCallback(async (h) => {
    const cached = getCached(getCacheKey(`/forecast/${encodeURIComponent(sym)}?horizon=${encodeURIComponent(h)}`))?.data
    if (cached && cached.symbol) {
      setForecast(cached)
      setLoading(false)
    } else {
      setLoading(true)
    }
    try {
      const data = await forecastApi.getForecast(sym, h)
      if (data && data.symbol) {
        setForecast(data)
      } else {
        // Fallback
        const symMap = FALLBACK_STOCK_FORECASTS[sym] || FALLBACK_STOCK_FORECASTS.MEBL
        setForecast(symMap[h] || symMap['1D'])
      }
    } catch {
      const symMap = FALLBACK_STOCK_FORECASTS[sym] || FALLBACK_STOCK_FORECASTS.MEBL
      setForecast(symMap[h] || symMap['1D'])
    } finally {
      setLoading(false)
    }
  }, [sym])

  // Load Historical Accuracy
  const loadHistory = useCallback(async () => {
    const cached = getCached(getCacheKey(`/forecast/${encodeURIComponent(sym)}/history?limit=20`))?.data
    if (cached && Array.isArray(cached.history) && cached.history.length > 0) {
      setHistory(cached)
      setHistoryLoading(false)
    } else {
      setHistoryLoading(true)
    }
    try {
      const data = await forecastApi.getForecastHistory(sym, 20)
      if (data && Array.isArray(data.history) && data.history.length > 0) {
        setHistory(data)
      } else {
        setHistory(generateFallbackHistory(sym, 15))
      }
    } catch {
      setHistory(generateFallbackHistory(sym, 15))
    } finally {
      setHistoryLoading(false)
    }
  }, [sym])

  useEffect(() => {
    loadForecast(horizon)
  }, [loadForecast, horizon])

  useEffect(() => {
    loadHistory()
  }, [loadHistory])

  // Signal Rating Pill style
  const signalRating = forecast?.signal_rating || (forecast?.direction === 'bullish' ? 'Buy' : forecast?.direction === 'bearish' ? 'Sell' : 'Hold / Neutral')
  const signalRatingStyle =
    signalRating.includes('Buy')
      ? 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/50 dark:text-emerald-300 dark:border-emerald-800'
      : signalRating.includes('Sell')
      ? 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/50 dark:text-rose-300 dark:border-rose-800'
      : 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/50 dark:text-amber-300 dark:border-amber-800'

  // Probability breakdown
  const probs = forecast?.probabilities || { bullish: 50, bearish: 25, sideways: 25 }
  const bullPct = Math.round(probs.bullish || 0)
  const bearPct = Math.round(probs.bearish || 0)
  const sidePct = Math.round(probs.sideways || 0)

  // Confidence
  const confPct = Math.round((forecast?.confidence || 0) * 100)

  if (loading && !forecast) {
    return (
      <div className="space-y-6 animate-pulse" aria-busy="true">
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 h-64" />
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 h-48" />
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 h-64" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* ── TOP FORECAST CONTROLS & TIMEFRAME ── */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200/90 dark:border-slate-800 rounded-2xl p-5 sm:p-6 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-100 dark:border-slate-800">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300 border border-emerald-200/80 dark:border-emerald-800/60 font-mono">
                Model: {forecast?.model_version || 'ensemble'}
              </span>
              <span className="text-xs text-slate-500 dark:text-slate-400">
                As of {formatDate(forecast?.as_of_date)}
              </span>
            </div>
            <h2 className="text-lg sm:text-xl font-bold text-slate-900 dark:text-slate-100">
              AI Price Forecast &amp; Predictive Signals
            </h2>
          </div>

          {/* Horizon Selector */}
          <div className="flex items-center gap-1.5 bg-slate-100 dark:bg-slate-950/80 border border-slate-200 dark:border-slate-800 p-1 rounded-xl shrink-0 self-start sm:self-auto">
            <span className="text-slate-500 dark:text-slate-400 px-2 text-xs font-medium">Horizon:</span>
            {[
              { id: '1D', label: '1D (Daily)' },
              { id: '1W', label: '1W (Weekly)' },
              { id: '1M', label: '1M (Monthly)' },
            ].map((h) => (
              <button
                key={h.id}
                type="button"
                onClick={() => setHorizon(h.id)}
                className={`px-3 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                  horizon === h.id
                    ? 'bg-emerald-600 text-white shadow-xs'
                    : 'text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200'
                }`}
              >
                {h.label}
              </button>
            ))}
          </div>
        </div>

        {/* ── PRIMARY PREDICTION & TARGET CARDS GRID ── */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mt-5">
          {/* Card 1: Ensemble Direction & Signal Rating */}
          <div className="bg-slate-50/80 dark:bg-slate-950/70 border border-slate-200/90 dark:border-slate-800/80 rounded-xl p-5 flex flex-col justify-between shadow-2xs">
            <div>
              <div className="flex items-center justify-between pb-3 border-b border-slate-200/80 dark:border-slate-800/60 mb-4">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  Ensemble Quantitative Signal
                </span>
                <span className={`px-2.5 py-1 rounded-full text-xs font-extrabold border shadow-2xs ${signalRatingStyle}`}>
                  {signalRating}
                </span>
              </div>

              <div className="flex items-baseline justify-between mb-4">
                <div>
                  <span className="text-[11px] text-slate-500 dark:text-slate-400 block mb-0.5">Predicted Direction</span>
                  <span className={`text-2xl font-black capitalize ${
                    forecast?.direction === 'bullish'
                      ? 'text-emerald-700 dark:text-emerald-400'
                      : forecast?.direction === 'bearish'
                      ? 'text-rose-700 dark:text-rose-400'
                      : 'text-amber-700 dark:text-amber-400'
                  }`}>
                    {forecast?.direction || 'Neutral'}
                  </span>
                </div>
                <div className="text-right">
                  <span className="text-[11px] text-slate-500 dark:text-slate-400 block mb-0.5">Top Confidence</span>
                  <span className="text-2xl font-black font-mono text-slate-900 dark:text-slate-100">
                    {confPct}%
                  </span>
                </div>
              </div>

              {/* 3-Way Probability Distribution Bar */}
              <div className="space-y-1.5 pt-2">
                <div className="flex items-center justify-between text-[11px] font-mono text-slate-600 dark:text-slate-400">
                  <span className="text-emerald-700 dark:text-emerald-400 font-bold">Bullish: {bullPct}%</span>
                  <span className="text-amber-700 dark:text-amber-400 font-bold">Sideways: {sidePct}%</span>
                  <span className="text-rose-700 dark:text-rose-400 font-bold">Bearish: {bearPct}%</span>
                </div>
                <div className="w-full h-2.5 bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden flex">
                  <div style={{ width: `${bullPct}%` }} className="bg-emerald-500 h-full transition-all" title={`Bullish: ${bullPct}%`} />
                  <div style={{ width: `${sidePct}%` }} className="bg-amber-400 h-full transition-all" title={`Sideways: ${sidePct}%`} />
                  <div style={{ width: `${bearPct}%` }} className="bg-rose-500 h-full transition-all" title={`Bearish: ${bearPct}%`} />
                </div>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-200/80 dark:border-slate-800/60 flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
              <span>Target Trading Date:</span>
              <strong className="text-slate-800 dark:text-slate-200 font-mono">{formatDate(forecast?.target_date)}</strong>
            </div>
          </div>

          {/* Card 2: Price Targets & Prediction Intervals */}
          <div className="bg-slate-50/80 dark:bg-slate-950/70 border border-slate-200/90 dark:border-slate-800/80 rounded-xl p-5 flex flex-col justify-between shadow-2xs">
            <div>
              <div className="flex items-center justify-between pb-3 border-b border-slate-200/80 dark:border-slate-800/60 mb-4">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  ATR Price Boundaries &amp; Intervals
                </span>
                <span className="text-xs font-mono text-slate-500 dark:text-slate-400">
                  Current: <strong className="text-slate-900 dark:text-slate-100">PKR {formatNumber(forecast?.current_price)}</strong>
                </span>
              </div>

              {/* Target & Stop vs Range */}
              {forecast?.target_price ? (
                <div className="grid grid-cols-2 gap-3 mb-4">
                  <div className="bg-emerald-50/80 dark:bg-emerald-950/30 border border-emerald-200/80 dark:border-emerald-800/40 rounded-xl p-3.5">
                    <span className="text-[11px] text-emerald-800 dark:text-emerald-400 font-medium block mb-0.5">Target Price</span>
                    <strong className="text-xl font-bold font-mono text-emerald-800 dark:text-emerald-300">
                      PKR {formatNumber(forecast.target_price)}
                    </strong>
                    <span className="text-xs font-mono font-bold text-emerald-700 dark:text-emerald-400 block mt-0.5">
                      {formatPercent(forecast.upside_pct)} Upside
                    </span>
                  </div>
                  <div className="bg-rose-50/80 dark:bg-rose-950/30 border border-rose-200/80 dark:border-rose-800/40 rounded-xl p-3.5">
                    <span className="text-[11px] text-rose-800 dark:text-rose-400 font-medium block mb-0.5">Stop-Loss Level</span>
                    <strong className="text-xl font-bold font-mono text-rose-800 dark:text-rose-300">
                      PKR {formatNumber(forecast.stop_loss)}
                    </strong>
                    <span className="text-xs font-mono font-bold text-rose-700 dark:text-rose-400 block mt-0.5">
                      {formatPercent(forecast.downside_pct)} Downside
                    </span>
                  </div>
                </div>
              ) : forecast?.expected_range ? (
                <div className="bg-amber-50/80 dark:bg-amber-950/30 border border-amber-200/80 dark:border-amber-800/40 rounded-xl p-4 mb-4">
                  <span className="text-xs text-amber-800 dark:text-amber-400 font-semibold block mb-1">
                    Prediction Interval (ATR Range Band)
                  </span>
                  <div className="flex items-baseline gap-2 font-mono">
                    <strong className="text-xl font-bold text-slate-900 dark:text-slate-100">
                      PKR {formatNumber(forecast.expected_range.low)}
                    </strong>
                    <span className="text-slate-400">to</span>
                    <strong className="text-xl font-bold text-slate-900 dark:text-slate-100">
                      PKR {formatNumber(forecast.expected_range.high)}
                    </strong>
                  </div>
                  <span className="text-[11px] text-slate-500 dark:text-slate-400 block mt-1">
                    Derived using {forecast.expected_range.method || 'ATR volatility range'}
                  </span>
                </div>
              ) : null}

              {/* Risk / Reward & Rationale */}
              <div className="space-y-2 text-xs">
                {forecast?.risk_reward_ratio != null && (
                  <div className="flex items-center justify-between py-1.5 border-t border-slate-200/60 dark:border-slate-800/60">
                    <span className="text-slate-500 dark:text-slate-400">Risk / Reward Ratio:</span>
                    <strong className="font-mono text-slate-900 dark:text-slate-200 font-bold">
                      {formatNumber(forecast.risk_reward_ratio, 2)} : 1
                    </strong>
                  </div>
                )}
                {forecast?.price_target_rationale && (
                  <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed italic pt-1">
                    {forecast.price_target_rationale}
                  </p>
                )}
              </div>
            </div>

            <div className="mt-3 pt-3 border-t border-slate-200/80 dark:border-slate-800/60 flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
              <span>Gating Consensus:</span>
              <strong className="text-slate-800 dark:text-slate-200 font-mono text-[11px]">{forecast?.gate_reason || 'Consensus Confirmed'}</strong>
            </div>
          </div>
        </div>
      </div>

      {/* ── DEEP LEARNING ARCHITECTURE & COMPONENT MODEL BREAKDOWN ── */}
      {forecast?.models && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200/90 dark:border-slate-800 rounded-2xl p-5 sm:p-6 shadow-xs space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-slate-100 dark:border-slate-800">
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-emerald-700 dark:text-emerald-400">
                Multi-Model Quant Breakdown
              </span>
              <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 mt-0.5">
                Deep Learning (GRU) vs Gradient Boosted (XGBoost)
              </h3>
            </div>
            <span className="text-xs font-mono text-slate-500 dark:text-slate-400">
              Ensemble Gate: <strong className="text-slate-800 dark:text-slate-200">{forecast.gate_reason || 'Active'}</strong>
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* GRU (Deep Recurrent Neural Network) */}
            {forecast.models.gru && (
              <div className="bg-slate-50/80 dark:bg-slate-950/70 border border-slate-200/90 dark:border-slate-800/80 rounded-xl p-4 shadow-2xs space-y-3">
                <div className="flex items-center justify-between pb-2 border-b border-slate-200/80 dark:border-slate-800/60">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-blue-500" />
                    <span className="font-bold text-slate-900 dark:text-slate-100 text-xs">GRU Neural Network</span>
                  </div>
                  <span className={`px-2 py-0.5 rounded text-[11px] font-bold uppercase ${
                    forecast.models.gru.direction === 'bullish'
                      ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400'
                      : forecast.models.gru.direction === 'bearish'
                      ? 'bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-400'
                      : 'bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-400'
                  }`}>
                    {forecast.models.gru.direction}
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-2 text-center text-xs font-mono">
                  <div className="bg-white dark:bg-slate-900 p-2 rounded-lg border border-slate-200 dark:border-slate-800">
                    <span className="text-[10px] text-slate-400 block">Bullish</span>
                    <strong className="text-emerald-700 dark:text-emerald-400 font-bold">{forecast.models.gru.bullish_pct}%</strong>
                  </div>
                  <div className="bg-white dark:bg-slate-900 p-2 rounded-lg border border-slate-200 dark:border-slate-800">
                    <span className="text-[10px] text-slate-400 block">Sideways</span>
                    <strong className="text-amber-700 dark:text-amber-400 font-bold">{forecast.models.gru.sideways_pct}%</strong>
                  </div>
                  <div className="bg-white dark:bg-slate-900 p-2 rounded-lg border border-slate-200 dark:border-slate-800">
                    <span className="text-[10px] text-slate-400 block">Bearish</span>
                    <strong className="text-rose-700 dark:text-rose-400 font-bold">{forecast.models.gru.bearish_pct}%</strong>
                  </div>
                </div>

                <div className="text-[11px] text-slate-500 dark:text-slate-400 flex items-center justify-between pt-1">
                  <span>Class Probability Gap:</span>
                  <strong className="font-mono text-slate-800 dark:text-slate-200">{forecast.models.gru.gap_pp} pp</strong>
                </div>
              </div>
            )}

            {/* XGBoost (Decision Tree Ensemble) */}
            {forecast.models.xgb && (
              <div className="bg-slate-50/80 dark:bg-slate-950/70 border border-slate-200/90 dark:border-slate-800/80 rounded-xl p-4 shadow-2xs space-y-3">
                <div className="flex items-center justify-between pb-2 border-b border-slate-200/80 dark:border-slate-800/60">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-purple-500" />
                    <span className="font-bold text-slate-900 dark:text-slate-100 text-xs">XGBoost Ensemble</span>
                  </div>
                  <span className={`px-2 py-0.5 rounded text-[11px] font-bold uppercase ${
                    forecast.models.xgb.direction === 'bullish'
                      ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400'
                      : forecast.models.xgb.direction === 'bearish'
                      ? 'bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-400'
                      : 'bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-400'
                  }`}>
                    {forecast.models.xgb.direction}
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-2 text-center text-xs font-mono">
                  <div className="bg-white dark:bg-slate-900 p-2 rounded-lg border border-slate-200 dark:border-slate-800">
                    <span className="text-[10px] text-slate-400 block">Bullish</span>
                    <strong className="text-emerald-700 dark:text-emerald-400 font-bold">{forecast.models.xgb.bullish_pct}%</strong>
                  </div>
                  <div className="bg-white dark:bg-slate-900 p-2 rounded-lg border border-slate-200 dark:border-slate-800">
                    <span className="text-[10px] text-slate-400 block">Sideways</span>
                    <strong className="text-amber-700 dark:text-amber-400 font-bold">{forecast.models.xgb.sideways_pct}%</strong>
                  </div>
                  <div className="bg-white dark:bg-slate-900 p-2 rounded-lg border border-slate-200 dark:border-slate-800">
                    <span className="text-[10px] text-slate-400 block">Bearish</span>
                    <strong className="text-rose-700 dark:text-rose-400 font-bold">{forecast.models.xgb.bearish_pct}%</strong>
                  </div>
                </div>

                <div className="text-[11px] text-slate-500 dark:text-slate-400 flex items-center justify-between pt-1">
                  <span>Class Probability Gap:</span>
                  <strong className="font-mono text-slate-800 dark:text-slate-200">{forecast.models.xgb.gap_pp} pp</strong>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── MARKET CONTEXT & RELATIVE MOMENTUM ── */}
      {forecast?.market_context && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200/90 dark:border-slate-800 rounded-2xl p-5 sm:p-6 shadow-xs space-y-3">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                Macro &amp; Relative PSX Momentum
              </span>
              <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                Market Context Snapshot
              </h3>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="bg-slate-50/80 dark:bg-slate-950/70 p-3 rounded-xl border border-slate-200/90 dark:border-slate-800/80 text-center">
              <span className="text-[11px] text-slate-500 dark:text-slate-400 block mb-0.5">5D Market Return</span>
              <span className="font-mono font-bold text-xs text-slate-800 dark:text-slate-200">
                {formatPercent((forecast.market_context.market_return_5d || 0) * 100)}
              </span>
            </div>
            <div className="bg-slate-50/80 dark:bg-slate-950/70 p-3 rounded-xl border border-slate-200/90 dark:border-slate-800/80 text-center">
              <span className="text-[11px] text-slate-500 dark:text-slate-400 block mb-0.5">20D Market Return</span>
              <span className="font-mono font-bold text-xs text-slate-800 dark:text-slate-200">
                {formatPercent((forecast.market_context.market_return_20d || 0) * 100)}
              </span>
            </div>
            <div className="bg-slate-50/80 dark:bg-slate-950/70 p-3 rounded-xl border border-slate-200/90 dark:border-slate-800/80 text-center">
              <span className="text-[11px] text-slate-500 dark:text-slate-400 block mb-0.5">20D Stock Return</span>
              <span className="font-mono font-bold text-xs text-slate-800 dark:text-slate-200">
                {formatPercent((forecast.market_context.stock_return_20d || 0) * 100)}
              </span>
            </div>
            <div className="bg-slate-50/80 dark:bg-slate-950/70 p-3 rounded-xl border border-slate-200/90 dark:border-slate-800/80 text-center">
              <span className="text-[11px] text-slate-500 dark:text-slate-400 block mb-0.5">Alpha vs PSX</span>
              <span className={`font-mono font-bold text-xs ${
                Number(forecast.market_context.stock_relative_return_20d || 0) >= 0
                  ? 'text-emerald-700 dark:text-emerald-400'
                  : 'text-rose-700 dark:text-rose-400'
              }`}>
                {formatPercent((forecast.market_context.stock_relative_return_20d || 0) * 100)}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* ── HISTORICAL FORECAST ACCURACY & VALIDATION LOG ── */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200/90 dark:border-slate-800 rounded-2xl p-5 sm:p-6 shadow-xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100 dark:border-slate-800">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-emerald-700 dark:text-emerald-400">
                Model Validation Log
              </span>
              <span className="text-xs text-slate-400 font-mono">
                {history?.count || 0} Records
              </span>
            </div>
            <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 mt-0.5">
              Historical Forecast Accuracy &amp; Out-of-Sample Verification
            </h3>
          </div>

          <div className="flex items-center gap-3">
            <div className="bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800/60 px-3.5 py-1.5 rounded-xl text-center">
              <span className="text-[10px] text-emerald-800 dark:text-emerald-400 uppercase font-semibold block">Directional Accuracy</span>
              <span className="text-base font-black font-mono text-emerald-700 dark:text-emerald-300">
                {history?.accuracy != null ? `${(Number(history.accuracy) * 100).toFixed(1)}%` : 'Pending'}
              </span>
            </div>
          </div>
        </div>

        {history?.accuracy_summary && (
          <p className="text-xs text-slate-500 dark:text-slate-400 italic">
            {history.accuracy_summary}
          </p>
        )}

        {/* Validation Records Table */}
        <div className="overflow-x-auto w-full border border-slate-200/80 dark:border-slate-800/80 rounded-xl">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-200 dark:border-slate-800 text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider bg-slate-50/70 dark:bg-slate-950/40">
                <th className="py-2.5 px-3">Predicted At</th>
                <th className="py-2.5 px-3">Target Date</th>
                <th className="py-2.5 px-3">Predicted Direction</th>
                <th className="py-2.5 px-3 text-right">Confidence</th>
                <th className="py-2.5 px-3 text-right">Probabilities (B/S/B)</th>
                <th className="py-2.5 px-3 text-center">Outcome Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 font-mono">
              {(history?.history || []).map((row, idx) => {
                const wasCorrect = row.actual?.was_correct
                const isPending = wasCorrect === null || row.actual?.direction === 'pending' || row.actual?.status?.includes('pending')
                const statusTag = isPending
                  ? { label: 'Pending Evaluation', style: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400' }
                  : wasCorrect
                  ? { label: 'Correct Direction', style: 'bg-emerald-50 text-emerald-700 border border-emerald-200/80 dark:bg-emerald-950/40 dark:text-emerald-400' }
                  : { label: 'Incorrect', style: 'bg-rose-50 text-rose-700 border border-rose-200/80 dark:bg-rose-950/40 dark:text-rose-400' }

                return (
                  <tr key={`h-${idx}`} className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors">
                    <td className="py-2.5 px-3 font-sans text-slate-700 dark:text-slate-300">
                      {formatDate(row.predicted_at)}
                    </td>
                    <td className="py-2.5 px-3 text-slate-500 dark:text-slate-400">
                      {formatDate(row.target_date)}
                    </td>
                    <td className="py-2.5 px-3 font-sans font-bold capitalize">
                      <span className={
                        row.predicted_direction === 'bullish'
                          ? 'text-emerald-700 dark:text-emerald-400'
                          : row.predicted_direction === 'bearish'
                          ? 'text-rose-700 dark:text-rose-400'
                          : 'text-amber-700 dark:text-amber-400'
                      }>
                        {row.predicted_direction}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-right text-slate-800 dark:text-slate-200">
                      {Math.round((row.confidence || 0) * 100)}%
                    </td>
                    <td className="py-2.5 px-3 text-right text-slate-500 dark:text-slate-400 text-[11px]">
                      {Math.round(row.probabilities?.bullish || 0)}% / {Math.round(row.probabilities?.sideways || 0)}% / {Math.round(row.probabilities?.bearish || 0)}%
                    </td>
                    <td className="py-2.5 px-3 text-center">
                      <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold ${statusTag.style}`}>
                        {statusTag.label}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
