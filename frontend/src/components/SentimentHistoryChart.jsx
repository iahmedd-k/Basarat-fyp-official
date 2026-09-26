import React, { useState, useMemo } from 'react'
import SentimentBadge from './SentimentBadge'

const PERIOD_OPTIONS = ['1D', '1W', '1M', '3M', '6M', '1Y']

export default function SentimentHistoryChart({
  symbol,
  data = [],
  period = '1M',
  onPeriodChange,
  loading = false,
  className = '',
}) {
  const [hoveredIndex, setHoveredIndex] = useState(null)

  const points = useMemo(() => {
    if (!Array.isArray(data) || data.length === 0) return []
    // Ensure chronological order
    return [...data].sort((a, b) => new Date(a.date) - new Date(b.date))
  }, [data])

  // Dimensions
  const width = 700
  const height = 220
  const padLeft = 45
  const padRight = 20
  const padTop = 25
  const padBottom = 35

  const chartWidth = width - padLeft - padRight
  const chartHeight = height - padTop - padBottom

  // Coordinates mapping
  // Score range [-1.0, 1.0] -> y range [padTop + chartHeight, padTop]
  const zeroY = padTop + chartHeight / 2

  const getY = (score) => {
    const clamped = Math.max(-1, Math.min(1, Number(score) || 0))
    // -1 => padTop + chartHeight
    // 0 => zeroY
    // +1 => padTop
    return zeroY - (clamped * (chartHeight / 2))
  }

  const getX = (index, total) => {
    if (total <= 1) return padLeft + chartWidth / 2
    return padLeft + (index / (total - 1)) * chartWidth
  }

  // Generate SVG path for line
  const linePath = useMemo(() => {
    if (points.length === 0) return ''
    if (points.length === 1) {
      const y = getY(points[0].score)
      return `M ${padLeft} ${y} L ${padLeft + chartWidth} ${y}`
    }
    return points.reduce((acc, pt, i) => {
      const x = getX(i, points.length)
      const y = getY(pt.score)
      return i === 0 ? `M ${x.toFixed(1)} ${y.toFixed(1)}` : `${acc} L ${x.toFixed(1)} ${y.toFixed(1)}`
    }, '')
  }, [points, chartWidth])

  // Area path for gradient fill
  const areaPath = useMemo(() => {
    if (points.length === 0) return ''
    const firstX = getX(0, points.length)
    const lastX = getX(points.length - 1, points.length)
    return `${linePath} L ${lastX.toFixed(1)} ${zeroY.toFixed(1)} L ${firstX.toFixed(1)} ${zeroY.toFixed(1)} Z`
  }, [linePath, points, zeroY])

  const hoveredPoint = hoveredIndex !== null && points[hoveredIndex] ? points[hoveredIndex] : null

  return (
    <div className={`bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800/80 rounded-2xl p-5 shadow-xs transition-colors ${className}`}>
      {/* Header with Title & Period Selector */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold tracking-tight text-slate-900 dark:text-slate-100">
              Sentiment Trend History
            </h3>
            {points.length > 0 && (
              <span className="text-xs text-slate-500 dark:text-slate-400 font-mono">
                ({points.length} {points.length === 1 ? 'data point' : 'data points'})
              </span>
            )}
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            FinBERT score trajectory (-1.0 Bearish to +1.0 Bullish) over time
          </p>
        </div>

        {/* Period Selector Buttons */}
        <div className="flex items-center bg-slate-100 dark:bg-slate-800/70 p-1 rounded-xl shrink-0 self-start sm:self-auto border border-slate-200/50 dark:border-slate-700/50">
          {PERIOD_OPTIONS.map((opt) => {
            const isActive = period === opt
            return (
              <button
                key={opt}
                type="button"
                onClick={() => onPeriodChange && onPeriodChange(opt)}
                disabled={loading}
                className={`px-2.5 py-1 text-xs font-medium rounded-lg transition-all ${
                  isActive
                    ? 'bg-white dark:bg-slate-900 text-emerald-600 dark:text-emerald-400 shadow-xs font-semibold'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100'
                }`}
              >
                {opt}
              </button>
            )
          })}
        </div>
      </div>

      {/* Chart Canvas or Loading / Empty States */}
      {loading ? (
        <div className="h-56 flex flex-col items-center justify-center text-center p-6 space-y-3">
          <div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-xs text-slate-500 dark:text-slate-400 font-medium">
            Loading sentiment trajectory for {symbol}…
          </p>
        </div>
      ) : points.length === 0 ? (
        <div className="h-56 flex flex-col items-center justify-center text-center p-6 border border-dashed border-slate-200 dark:border-slate-800 rounded-xl bg-slate-50/50 dark:bg-slate-800/20">
          <div className="w-10 h-10 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-400 mb-2">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" />
            </svg>
          </div>
          <p className="text-xs font-semibold text-slate-700 dark:text-slate-300">
            No Historical Sentiment Points Recorded
          </p>
          <p className="text-[11px] text-slate-500 dark:text-slate-400 max-w-sm mt-1">
            Historical time-series points have not been logged for {symbol} in the {period} period. As new corporate disclosures and articles arrive, time-series metrics populate automatically.
          </p>
        </div>
      ) : (
        <div className="relative">
          <svg
            viewBox={`0 0 ${width} ${height}`}
            className="w-full h-auto overflow-visible select-none"
            onMouseLeave={() => setHoveredIndex(null)}
          >
            <defs>
              <linearGradient id="sentimentAreaGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#10b981" stopOpacity="0.25" />
                <stop offset="50%" stopColor="#10b981" stopOpacity="0.03" />
                <stop offset="50%" stopColor="#f43f5e" stopOpacity="0.03" />
                <stop offset="100%" stopColor="#f43f5e" stopOpacity="0.25" />
              </linearGradient>
            </defs>

            {/* Grid Lines & Labels */}
            {/* Bullish line (+1.0) */}
            <line
              x1={padLeft}
              y1={padTop}
              x2={width - padRight}
              y2={padTop}
              stroke="currentColor"
              strokeDasharray="2 4"
              className="text-slate-200 dark:text-slate-800"
            />
            <text
              x={padLeft - 6}
              y={padTop + 3}
              textAnchor="end"
              className="text-[10px] fill-emerald-600 dark:fill-emerald-400 font-mono"
            >
              +1.0
            </text>

            {/* Neutral line (0.0) */}
            <line
              x1={padLeft}
              y1={zeroY}
              x2={width - padRight}
              y2={zeroY}
              stroke="currentColor"
              strokeWidth="1.2"
              strokeDasharray="4 4"
              className="text-slate-300 dark:text-slate-700"
            />
            <text
              x={padLeft - 6}
              y={zeroY + 3}
              textAnchor="end"
              className="text-[10px] fill-slate-400 dark:fill-slate-500 font-mono"
            >
              0.0
            </text>

            {/* Bearish line (-1.0) */}
            <line
              x1={padLeft}
              y1={padTop + chartHeight}
              x2={width - padRight}
              y2={padTop + chartHeight}
              stroke="currentColor"
              strokeDasharray="2 4"
              className="text-slate-200 dark:text-slate-800"
            />
            <text
              x={padLeft - 6}
              y={padTop + chartHeight + 3}
              textAnchor="end"
              className="text-[10px] fill-rose-600 dark:fill-rose-400 font-mono"
            >
              -1.0
            </text>

            {/* Area Fill */}
            {points.length > 1 && (
              <path d={areaPath} fill="url(#sentimentAreaGradient)" />
            )}

            {/* Score Trajectory Line */}
            <path
              d={linePath}
              fill="none"
              stroke="#10b981"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="transition-all"
            />

            {/* Date labels on X-axis (First, Middle, Last) */}
            {points.length > 0 && (
              <>
                <text
                  x={padLeft}
                  y={height - 8}
                  textAnchor="start"
                  className="text-[10px] fill-slate-400 dark:fill-slate-500 font-mono"
                >
                  {points[0].date}
                </text>
                {points.length > 2 && (
                  <text
                    x={padLeft + chartWidth / 2}
                    y={height - 8}
                    textAnchor="middle"
                    className="text-[10px] fill-slate-400 dark:fill-slate-500 font-mono"
                  >
                    {points[Math.floor(points.length / 2)].date}
                  </text>
                )}
                <text
                  x={width - padRight}
                  y={height - 8}
                  textAnchor="end"
                  className="text-[10px] fill-slate-400 dark:fill-slate-500 font-mono"
                >
                  {points[points.length - 1].date}
                </text>
              </>
            )}

            {/* Interactive Data Points & Hover Targets */}
            {points.map((pt, idx) => {
              const cx = getX(idx, points.length)
              const cy = getY(pt.score)
              const isHovered = hoveredIndex === idx
              const ptScore = Number(pt.score) || 0
              const fillColor = ptScore > 0 ? '#10b981' : ptScore < 0 ? '#f43f5e' : '#64748b'

              return (
                <g key={pt.date || idx}>
                  {/* Invisible broad hover target */}
                  <circle
                    cx={cx}
                    cy={cy}
                    r="14"
                    fill="transparent"
                    className="cursor-pointer"
                    onMouseEnter={() => setHoveredIndex(idx)}
                  />
                  {/* Visible point circle */}
                  <circle
                    cx={cx}
                    cy={cy}
                    r={isHovered ? '6' : '3.5'}
                    fill={fillColor}
                    stroke="#ffffff"
                    strokeWidth={isHovered ? '2.5' : '1.5'}
                    className="transition-all pointer-events-none"
                  />
                </g>
              )
            })}
          </svg>

          {/* Floating Tooltip */}
          {hoveredPoint && (
            <div
              className="absolute pointer-events-none z-10 bg-slate-900/95 text-white dark:bg-slate-100/95 dark:text-slate-900 text-xs px-3 py-2 rounded-xl shadow-lg border border-slate-700/50 dark:border-slate-300/50 backdrop-blur-sm transition-transform -translate-x-1/2 -translate-y-full"
              style={{
                left: `${(getX(hoveredIndex, points.length) / width) * 100}%`,
                top: `${(getY(hoveredPoint.score) / height) * 100}%`,
                marginTop: '-12px',
              }}
            >
              <div className="font-semibold text-[11px] text-slate-300 dark:text-slate-600 font-mono">
                {hoveredPoint.date}
              </div>
              <div className="flex items-center gap-2 mt-1">
                <span className="font-mono font-bold text-sm">
                  {hoveredPoint.score > 0 ? `+${Number(hoveredPoint.score).toFixed(2)}` : Number(hoveredPoint.score).toFixed(2)}
                </span>
                <span className={`text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded ${
                  hoveredPoint.score > 0 ? 'bg-emerald-500/20 text-emerald-400 dark:text-emerald-700' :
                  hoveredPoint.score < 0 ? 'bg-rose-500/20 text-rose-400 dark:text-rose-700' :
                  'bg-slate-500/20 text-slate-300 dark:text-slate-700'
                }`}>
                  {hoveredPoint.label || 'Neutral'}
                </span>
              </div>
              {hoveredPoint.article_count != null && (
                <div className="text-[10px] text-slate-400 dark:text-slate-500 mt-1 font-medium">
                  {hoveredPoint.article_count} articles analyzed
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

