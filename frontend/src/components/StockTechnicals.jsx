import React from 'react'
import { formatNumber, formatDate, getSignalStyle } from '../utils/formatters'

// Helper component to render an interactive SVG sparkline
function MiniSparkline({
  series = [],
  height = 80,
  strokeColor = '#10b981',
  referenceLines = [],
  shadedBand = null,
}) {
  const valid = (series || []).filter((d) => d && Number.isFinite(Number(d.value)))
  if (valid.length < 2) {
    return (
      <div className="h-20 flex items-center justify-center text-[11px] text-slate-400 bg-slate-50/50 dark:bg-slate-800/30 rounded-lg">
        Not enough historical data for chart
      </div>
    )
  }

  const values = valid.map((d) => Number(d.value))
  let min = Math.min(...values)
  let max = Math.max(...values)

  // Expand min/max to include reference lines if any
  referenceLines.forEach((ref) => {
    if (ref.value < min) min = ref.value
    if (ref.value > max) max = ref.value
  })

  const span = Math.max(max - min, 0.001)
  const width = 300
  const padY = 8

  const points = valid.map((d, i) => {
    const x = (i / (valid.length - 1)) * width
    const y = padY + (height - padY * 2) - ((Number(d.value) - min) / span) * (height - padY * 2)
    return { x, y, value: d.value, date: d.date }
  })

  const pathStr = points.reduce((acc, p, i) => `${acc} ${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)},${p.y.toFixed(1)}`, '')

  return (
    <div className="relative w-full">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-20 overflow-visible">
        {/* Shaded Band if specified (e.g. RSI 30-70 normal band) */}
        {shadedBand && (
          <rect
            x={0}
            y={padY + (height - padY * 2) - ((shadedBand.max - min) / span) * (height - padY * 2)}
            width={width}
            height={Math.max(0, (((shadedBand.max - shadedBand.min) / span) * (height - padY * 2)))}
            fill={shadedBand.fill || 'rgba(148, 163, 184, 0.12)'}
          />
        )}

        {/* Reference horizontal lines */}
        {referenceLines.map((ref, idx) => {
          const refY = padY + (height - padY * 2) - ((ref.value - min) / span) * (height - padY * 2)
          return (
            <g key={idx}>
              <line
                x1={0}
                y1={refY}
                x2={width}
                y2={refY}
                stroke={ref.color || '#94a3b8'}
                strokeDasharray="2 2"
                strokeWidth="1"
              />
              <text
                x={width - 2}
                y={refY - 2}
                textAnchor="end"
                className="text-[9px] font-mono fill-slate-400 select-none"
              >
                {ref.label || ref.value}
              </text>
            </g>
          )
        })}

        {/* Primary line */}
        <path
          d={pathStr}
          fill="none"
          stroke={strokeColor}
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* Last point dot */}
        {points.length > 0 && (
          <circle
            cx={points[points.length - 1].x}
            cy={points[points.length - 1].y}
            r="3.5"
            fill={strokeColor}
            stroke="#ffffff"
            strokeWidth="1.5"
          />
        )}
      </svg>
    </div>
  )
}

// Dual-line chart for MACD vs Signal or Price vs SMA
function DualSparkline({
  series1 = [],
  series2 = [],
  series1Label = 'Series 1',
  series2Label = 'Series 2',
  series1Color = '#3b82f6',
  series2Color = '#f59e0b',
  height = 80,
}) {
  const valid1 = (series1 || []).filter((d) => d && Number.isFinite(Number(d.value)))
  const valid2 = (series2 || []).filter((d) => d && Number.isFinite(Number(d.value)))
  if (valid1.length < 2 && valid2.length < 2) {
    return (
      <div className="h-20 flex items-center justify-center text-[11px] text-slate-400 bg-slate-50/50 dark:bg-slate-800/30 rounded-lg">
        Not enough historical data for comparison
      </div>
    )
  }

  const allVals = [...valid1.map((d) => Number(d.value)), ...valid2.map((d) => Number(d.value))]
  const min = Math.min(...allVals)
  const max = Math.max(...allVals)
  const span = Math.max(max - min, 0.001)
  const width = 300
  const padY = 8

  const pts1 = valid1.map((d, i) => ({
    x: (i / Math.max(valid1.length - 1, 1)) * width,
    y: padY + (height - padY * 2) - ((Number(d.value) - min) / span) * (height - padY * 2),
  }))

  const pts2 = valid2.map((d, i) => ({
    x: (i / Math.max(valid2.length - 1, 1)) * width,
    y: padY + (height - padY * 2) - ((Number(d.value) - min) / span) * (height - padY * 2),
  }))

  const p1Str = pts1.reduce((acc, p, i) => `${acc} ${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)},${p.y.toFixed(1)}`, '')
  const p2Str = pts2.reduce((acc, p, i) => `${acc} ${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)},${p.y.toFixed(1)}`, '')

  // Zero-line if cross 0
  const zeroY = min < 0 && max > 0 ? padY + (height - padY * 2) - ((0 - min) / span) * (height - padY * 2) : null

  return (
    <div className="relative w-full">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-20 overflow-visible">
        {zeroY !== null && (
          <line
            x1={0}
            y1={zeroY}
            x2={width}
            y2={zeroY}
            stroke="#94a3b8"
            strokeDasharray="2 2"
            strokeWidth="0.8"
          />
        )}
        {p1Str && (
          <path
            d={p1Str}
            fill="none"
            stroke={series1Color}
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        )}
        {p2Str && (
          <path
            d={p2Str}
            fill="none"
            stroke={series2Color}
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeDasharray="3 2"
          />
        )}
      </svg>
      <div className="flex items-center justify-end gap-3 mt-1 text-[10px] font-mono">
        <span className="flex items-center gap-1 text-slate-600 dark:text-slate-300">
          <span className="w-2.5 h-0.5 rounded-full" style={{ backgroundColor: series1Color }} />
          {series1Label}
        </span>
        <span className="flex items-center gap-1 text-slate-500 dark:text-slate-400">
          <span className="w-2.5 h-0.5 rounded-full" style={{ backgroundColor: series2Color }} />
          {series2Label}
        </span>
      </div>
    </div>
  )
}

// Envelope chart for Bollinger Bands (Upper, Mid, Lower)
function BollingerEnvelopeChart({
  upper = [],
  mid = [],
  lower = [],
  height = 80,
}) {
  const validU = (upper || []).filter((d) => d && Number.isFinite(Number(d.value)))
  const validM = (mid || []).filter((d) => d && Number.isFinite(Number(d.value)))
  const validL = (lower || []).filter((d) => d && Number.isFinite(Number(d.value)))

  if (validU.length < 2 || validL.length < 2) {
    return (
      <div className="h-20 flex items-center justify-center text-[11px] text-slate-400 bg-slate-50/50 dark:bg-slate-800/30 rounded-lg">
        Not enough historical data for Bollinger Bands
      </div>
    )
  }

  const allVals = [
    ...validU.map((d) => Number(d.value)),
    ...validM.map((d) => Number(d.value)),
    ...validL.map((d) => Number(d.value)),
  ]
  const min = Math.min(...allVals)
  const max = Math.max(...allVals)
  const span = Math.max(max - min, 0.001)
  const width = 300
  const padY = 8

  const ptsU = validU.map((d, i) => ({
    x: (i / Math.max(validU.length - 1, 1)) * width,
    y: padY + (height - padY * 2) - ((Number(d.value) - min) / span) * (height - padY * 2),
  }))

  const ptsM = validM.map((d, i) => ({
    x: (i / Math.max(validM.length - 1, 1)) * width,
    y: padY + (height - padY * 2) - ((Number(d.value) - min) / span) * (height - padY * 2),
  }))

  const ptsL = validL.map((d, i) => ({
    x: (i / Math.max(validL.length - 1, 1)) * width,
    y: padY + (height - padY * 2) - ((Number(d.value) - min) / span) * (height - padY * 2),
  }))

  const pathU = ptsU.reduce((acc, p, i) => `${acc} ${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)},${p.y.toFixed(1)}`, '')
  const pathM = ptsM.reduce((acc, p, i) => `${acc} ${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)},${p.y.toFixed(1)}`, '')
  const pathL = ptsL.reduce((acc, p, i) => `${acc} ${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)},${p.y.toFixed(1)}`, '')

  // Create closed polygon for shaded band between Upper and Lower
  const revL = [...ptsL].reverse()
  const shadedPath = `${pathU} ${revL.reduce((acc, p) => `${acc} L ${p.x.toFixed(1)},${p.y.toFixed(1)}`, '')} Z`

  return (
    <div className="relative w-full">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-20 overflow-visible">
        {/* Shaded envelope */}
        <path d={shadedPath} fill="rgba(99, 102, 241, 0.12)" />
        {/* Upper Band */}
        <path d={pathU} fill="none" stroke="#6366f1" strokeWidth="1.5" strokeDasharray="2 2" />
        {/* Mid SMA */}
        <path d={pathM} fill="none" stroke="#818cf8" strokeWidth="1.5" />
        {/* Lower Band */}
        <path d={pathL} fill="none" stroke="#6366f1" strokeWidth="1.5" strokeDasharray="2 2" />
      </svg>
      <div className="flex items-center justify-between text-[10px] font-mono text-slate-500 mt-1">
        <span>L: {formatNumber(validL[validL.length - 1]?.value, 1)}</span>
        <span>Mid (SMA): {formatNumber(validM[validM.length - 1]?.value, 1)}</span>
        <span>U: {formatNumber(validU[validU.length - 1]?.value, 1)}</span>
      </div>
    </div>
  )
}

export default function StockTechnicals({
  symbol,
  data,
  price,
}) {
  if (!data) {
    return (
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-8 text-center">
        <p className="text-slate-400 text-sm">Technical indicator signals are being calculated for {symbol}...</p>
      </div>
    )
  }

  const { overall_signal, summary_message, signals_breakdown, summary = {}, indicators = {} } = data
  const overallStyle = getSignalStyle(overall_signal)

  const buys = signals_breakdown?.buy || 0
  const neutrals = signals_breakdown?.neutral || 0
  const sells = signals_breakdown?.sell || 0
  const totalSignals = Math.max(buys + neutrals + sells, 1)

  // Robust value extraction supporting backend object schema: { value, signal, description, ... }
  const rsiObj = summary.rsi || {}
  const rsiVal = typeof rsiObj === 'object' && rsiObj.value != null
    ? Number(rsiObj.value)
    : (Number.isFinite(Number(rsiObj)) ? Number(rsiObj) : indicators.RSI?.[indicators.RSI.length - 1]?.value)
  const rsiSignal = rsiObj.signal || (rsiVal > 70 ? 'OVERBOUGHT' : rsiVal < 30 ? 'OVERSOLD' : 'NEUTRAL')
  const rsiDesc = rsiObj.description

  const macdObj = summary.macd || {}
  const macdVal = typeof macdObj === 'object' && macdObj.value != null
    ? Number(macdObj.value)
    : (Number.isFinite(Number(macdObj)) ? Number(macdObj) : indicators.MACD?.[indicators.MACD.length - 1]?.value)
  const macdSignalVal = macdObj.signal_line != null
    ? Number(macdObj.signal_line)
    : indicators.MACD_SIGNAL?.[indicators.MACD_SIGNAL.length - 1]?.value
  const macdSignal = macdObj.signal || (macdVal > (macdSignalVal || 0) ? 'BUY' : 'SELL')
  const macdDesc = macdObj.description

  const smaObj = summary.sma || {}
  const smaVal = typeof smaObj === 'object' && smaObj.value != null
    ? Number(smaObj.value)
    : (Number.isFinite(Number(smaObj)) ? Number(smaObj) : indicators.SMA?.[indicators.SMA.length - 1]?.value)
  const smaSignal = smaObj.signal || (price >= (smaVal || 0) ? 'BUY' : 'SELL')
  const smaDesc = smaObj.description

  // Bollinger Summary
  const bbObj = summary.bollinger || {}
  const bbUpper = indicators.BB_UPPER || []
  const bbMid = indicators.BB_MID || []
  const bbLower = indicators.BB_LOWER || []
  const currentUpper = bbObj.upper != null ? Number(bbObj.upper) : bbUpper[bbUpper.length - 1]?.value
  const currentMid = bbObj.mid != null ? Number(bbObj.mid) : bbMid[bbMid.length - 1]?.value
  const currentLower = bbObj.lower != null ? Number(bbObj.lower) : bbLower[bbLower.length - 1]?.value
  const bbSignal = bbObj.signal || 'NEUTRAL'
  const bbDesc = bbObj.description

  const adxObj = summary.adx || {}
  const adxVal = typeof adxObj === 'object' && adxObj.value != null
    ? Number(adxObj.value)
    : (Number.isFinite(Number(adxObj)) ? Number(adxObj) : indicators.ADX?.[indicators.ADX.length - 1]?.value)
  const adxTrend = adxObj.trend_strength || (adxVal >= 40 ? 'VERY STRONG' : adxVal >= 25 ? 'STRONG' : 'WEAK')
  const adxDesc = adxObj.description

  return (
    <div className="space-y-6">
      {/* 1. Overall Signal & Verdict Banner */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-xs">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                Institutional Momentum Verdict
              </span>
              <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs border ${overallStyle.badge}`}>
                <span className={`w-2 h-2 rounded-full ${overallStyle.dot} animate-pulse`} />
                {overallStyle.label}
              </span>
            </div>
            <p className="text-sm text-slate-700 dark:text-slate-300 max-w-2xl leading-relaxed m-0 font-medium">
              {summary_message || `Technical indicator confluence indicates a ${overallStyle.label} bias based on 14-period momentum, moving averages, and volatility.`}
            </p>
          </div>

          {/* Signals Breakdown Counters & Meter */}
          <div className="bg-slate-50 dark:bg-slate-800/60 p-4 rounded-xl border border-slate-100 dark:border-slate-800 shrink-0 min-w-[280px]">
            <div className="text-xs font-semibold text-slate-500 dark:text-slate-400 mb-2 flex items-center justify-between">
              <span>Signals Consensus</span>
              <span className="font-mono text-slate-700 dark:text-slate-200">{buys} Buy · {neutrals} Neutral · {sells} Sell</span>
            </div>
            {/* Visual stacked bar meter */}
            <div className="h-3 w-full bg-slate-200 dark:bg-slate-700 rounded-full flex overflow-hidden">
              <div
                style={{ width: `${(buys / totalSignals) * 100}%` }}
                className="bg-emerald-500 transition-all duration-500"
                title={`${buys} Buy Signals`}
              />
              <div
                style={{ width: `${(neutrals / totalSignals) * 100}%` }}
                className="bg-amber-400 transition-all duration-500"
                title={`${neutrals} Neutral Signals`}
              />
              <div
                style={{ width: `${(sells / totalSignals) * 100}%` }}
                className="bg-rose-500 transition-all duration-500"
                title={`${sells} Sell Signals`}
              />
            </div>
            <div className="flex justify-between text-[11px] font-mono text-slate-500 mt-2">
              <span className="text-emerald-600 dark:text-emerald-400 font-semibold">{buys} Buy</span>
              <span className="text-amber-600 dark:text-amber-400 font-semibold">{neutrals} Hold</span>
              <span className="text-rose-600 dark:text-rose-400 font-semibold">{sells} Sell</span>
            </div>
          </div>
        </div>
      </div>

      {/* 2. Grid of 5 Technical Indicators */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {/* Indicator 1: RSI */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                RSI (14)
              </span>
              <span
                className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                  rsiVal > 70
                    ? 'bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300'
                    : rsiVal < 30
                    ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300'
                    : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300'
                }`}
              >
                {rsiVal > 70 ? 'Overbought (>70)' : rsiVal < 30 ? 'Oversold (<30)' : 'Neutral (30-70)'}
              </span>
            </div>
            <div className="flex items-baseline gap-2 mb-2">
              <span className="text-2xl font-bold font-mono text-slate-900 dark:text-slate-100">
                {formatNumber(rsiVal, 1)}
              </span>
              <span className="text-xs text-slate-400 font-medium">Momentum Oscillator</span>
            </div>
            {rsiDesc && (
              <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-tight mb-3">
                {rsiDesc}
              </p>
            )}
          </div>

          <MiniSparkline
            series={indicators.RSI || []}
            strokeColor={rsiVal > 70 ? '#f43f5e' : rsiVal < 30 ? '#10b981' : '#3b82f6'}
            referenceLines={[
              { value: 70, label: '70', color: '#f43f5e' },
              { value: 30, label: '30', color: '#10b981' },
            ]}
            shadedBand={{ min: 30, max: 70 }}
          />
        </div>

        {/* Indicator 2: MACD */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                MACD (12, 26, 9)
              </span>
              <span
                className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                  macdSignal === 'BUY' || macdVal > (macdSignalVal || 0)
                    ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300'
                    : 'bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300'
                }`}
              >
                {macdSignal === 'BUY' || macdVal > (macdSignalVal || 0) ? 'Bullish Cross' : 'Bearish Cross'}
              </span>
            </div>
            <div className="flex items-baseline gap-3 mb-2">
              <span className="text-2xl font-bold font-mono text-slate-900 dark:text-slate-100">
                {formatNumber(macdVal, 2)}
              </span>
              <span className="text-xs text-slate-400 font-mono">
                Signal: <b>{formatNumber(macdSignalVal, 2)}</b>
              </span>
            </div>
            {macdDesc && (
              <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-tight mb-3">
                {macdDesc}
              </p>
            )}
          </div>

          <DualSparkline
            series1={indicators.MACD || []}
            series2={indicators.MACD_SIGNAL || []}
            series1Label="MACD"
            series2Label="Signal"
            series1Color="#3b82f6"
            series2Color="#f59e0b"
          />
        </div>

        {/* Indicator 3: SMA (14) */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                14-Bar Simple Moving Avg
              </span>
              <span
                className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                  smaSignal === 'BUY' || (price != null && price >= (smaVal || 0))
                    ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300'
                    : 'bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300'
                }`}
              >
                {smaSignal === 'BUY' || (price != null && price >= (smaVal || 0)) ? 'Above SMA (Bullish)' : 'Below SMA (Bearish)'}
              </span>
            </div>
            <div className="flex items-baseline gap-2 mb-2">
              <span className="text-2xl font-bold font-mono text-slate-900 dark:text-slate-100">
                PKR {formatNumber(smaVal, 2)}
              </span>
              {price && smaVal ? (
                <span className={`text-xs font-mono font-semibold ${price >= smaVal ? 'text-emerald-600' : 'text-rose-600'}`}>
                  {price >= smaVal ? '+' : ''}{formatNumber(((price - smaVal) / smaVal) * 100, 2)}%
                </span>
              ) : null}
            </div>
            {smaDesc && (
              <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-tight mb-3">
                {smaDesc}
              </p>
            )}
          </div>

          <MiniSparkline
            series={indicators.SMA || []}
            strokeColor="#8b5cf6"
          />
        </div>

        {/* Indicator 4: Bollinger Bands (20, 2) */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                Bollinger Bands (20, 2)
              </span>
              <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                {bbSignal || 'Volatility Envelope'}
              </span>
            </div>
            <div className="flex items-baseline gap-3 mb-2">
              <span className="text-sm font-bold font-mono text-slate-700 dark:text-slate-300">
                Band: {formatNumber(currentLower, 1)} — {formatNumber(currentUpper, 1)}
              </span>
              {currentMid != null && (
                <span className="text-xs text-slate-400 font-mono">
                  Mid: {formatNumber(currentMid, 1)}
                </span>
              )}
            </div>
            {bbDesc && (
              <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-tight mb-3">
                {bbDesc}
              </p>
            )}
          </div>

          <BollingerEnvelopeChart
            upper={bbUpper}
            mid={bbMid}
            lower={bbLower}
          />
        </div>

        {/* Indicator 5: ADX (Trend Strength) */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                ADX Trend Strength (14)
              </span>
              <span
                className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                  adxVal >= 25
                    ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300'
                    : 'bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300'
                }`}
              >
                {adxVal >= 40 ? 'Very Strong Trend' : adxVal >= 25 ? 'Strong Trend (>25)' : 'Weak / Ranging (<25)'}
              </span>
            </div>
            <div className="flex items-baseline gap-2 mb-2">
              <span className="text-2xl font-bold font-mono text-slate-900 dark:text-slate-100">
                {formatNumber(adxVal, 1)}
              </span>
              <span className="text-xs text-slate-400 font-medium">{adxTrend ? `Conviction: ${adxTrend}` : 'Trend Conviction Score'}</span>
            </div>
            {adxDesc && (
              <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-tight mb-3">
                {adxDesc}
              </p>
            )}
          </div>

          <MiniSparkline
            series={indicators.ADX || []}
            strokeColor={adxVal >= 25 ? '#10b981' : '#f59e0b'}
            referenceLines={[
              { value: 25, label: '25 Threshold', color: '#64748b' },
            ]}
          />
        </div>
      </div>
    </div>
  )
}

