import React, { useMemo, useState } from 'react'

export default function MonteCarloChart({
  paths = [],
  percentiles = null,
  stats = null,
  horizonDays = 30,
}) {
  const [hoverIndex, setHoverIndex] = useState(null)

  const chartData = useMemo(() => {
    if (!paths || paths.length === 0) return null

    // Determine min and max across all paths
    let minVal = 1.0
    let maxVal = 1.0

    paths.forEach((path) => {
      path.forEach((val) => {
        if (val < minVal) minVal = val
        if (val > maxVal) maxVal = val
      })
    })

    // Add 8% padding to the bounds
    const range = maxVal - minVal || 0.2
    const yMin = Math.max(0.4, minVal - range * 0.08)
    const yMax = maxVal + range * 0.08

    const width = 860
    const height = 340
    const padding = { top: 25, right: 70, bottom: 40, left: 65 }
    const plotWidth = width - padding.left - padding.right
    const plotHeight = height - padding.top - padding.bottom

    const numPoints = paths[0]?.length || horizonDays + 1

    const getX = (stepIndex) => padding.left + (stepIndex / (numPoints - 1)) * plotWidth
    const getY = (val) => padding.top + plotHeight - ((val - yMin) / (yMax - yMin)) * plotHeight

    // Generate path SVG d strings
    const pathStrings = paths.map((path) => {
      const d = path.reduce((acc, val, i) => `${acc} ${i === 0 ? 'M' : 'L'} ${getX(i).toFixed(1)} ${getY(val).toFixed(1)}`, '')
      const finalReturn = path[path.length - 1] - 1
      return { d, isPositive: finalReturn >= 0 }
    })

    // Compute median path
    const medianPath = []
    for (let i = 0; i < numPoints; i++) {
      const stepValues = paths.map((p) => p[i]).sort((a, b) => a - b)
      const mid = Math.floor(stepValues.length / 2)
      const medianVal = stepValues.length % 2 !== 0 ? stepValues[mid] : (stepValues[mid - 1] + stepValues[mid]) / 2
      medianPath.push({ x: getX(i), y: getY(medianVal), val: medianVal })
    }
    const medianD = medianPath.reduce((acc, pt, i) => `${acc} ${i === 0 ? 'M' : 'L'} ${pt.x.toFixed(1)} ${pt.y.toFixed(1)}`, '')

    // Y ticks
    const yTicks = []
    const step = 0.05
    const tickStart = Math.ceil(yMin / step) * step
    for (let t = tickStart; t <= yMax; t += step) {
      yTicks.push({
        val: t,
        pct: `${((t - 1) * 100).toFixed(0)}%`,
        y: getY(t),
        isZero: Math.abs(t - 1.0) < 0.001,
      })
    }

    // X ticks (days)
    const xTicks = []
    const xStep = Math.max(5, Math.round(horizonDays / 6))
    for (let d = 0; d <= horizonDays; d += xStep) {
      xTicks.push({
        day: d,
        label: d === 0 ? 'Day 0' : `T+${d}d`,
        x: getX(Math.min(d, numPoints - 1)),
      })
    }

    return {
      width,
      height,
      padding,
      plotWidth,
      plotHeight,
      numPoints,
      yMin,
      yMax,
      yTicks,
      xTicks,
      pathStrings,
      medianD,
      medianPath,
      getX,
      getY,
    }
  }, [paths, horizonDays])

  if (!chartData) {
    return (
      <div className="flex items-center justify-center h-64 bg-slate-50 dark:bg-slate-900/30 rounded-xl border border-slate-200 dark:border-slate-800 text-slate-500 dark:text-slate-400 text-sm">
        No simulation paths available. Click &quot;Run Simulation&quot; to project portfolio price trajectories.
      </div>
    )
  }

  const { width, height, yTicks, xTicks, pathStrings, medianD, medianPath, padding, plotHeight, getX } = chartData

  return (
    <div className="relative w-full overflow-hidden bg-white dark:bg-slate-950/60 rounded-xl border border-slate-200/90 dark:border-slate-800/80 p-4 sm:p-5 shadow-xs">
      {/* Chart Header Meta */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-3 text-xs text-slate-600 dark:text-slate-400">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-1.5">
            <span className="w-3.5 h-1 bg-emerald-600 dark:bg-emerald-500 rounded-full" />
            <span className="font-semibold text-slate-900 dark:text-slate-200">Median Path (p50)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-0.5 bg-emerald-600/50 dark:bg-emerald-400/40" />
            <span>Simulated Upside</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-0.5 bg-rose-600/50 dark:bg-rose-400/40" />
            <span>Simulated Drawdowns</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2 border-b-2 border-dashed border-slate-400 dark:border-slate-500" />
            <span>Baseline (0.0%)</span>
          </div>
        </div>
        <div className="font-mono text-slate-500 dark:text-slate-400 text-[11px]">
          Sampled: {paths.length} Paths · Horizon: {horizonDays} Trading Days
        </div>
      </div>

      {/* SVG Trajectory Canvas */}
      <div className="relative w-full aspect-[860/340] max-h-[380px]">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="w-full h-full select-none"
          onMouseLeave={() => setHoverIndex(null)}
        >
          <defs>
            <linearGradient id="medianGlowLight" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#059669" />
              <stop offset="100%" stopColor="#10b981" />
            </linearGradient>
          </defs>

          {/* Grid lines */}
          {yTicks.map((t, idx) => (
            <g key={`ytick-${idx}`}>
              <line
                x1={padding.left}
                y1={t.y}
                x2={width - padding.right}
                y2={t.y}
                stroke={t.isZero ? '#64748b' : '#cbd5e1'}
                className="dark:stroke-slate-700"
                strokeWidth={t.isZero ? '1.5' : '1'}
                strokeDasharray={t.isZero ? '4 3' : '2 2'}
                strokeOpacity={t.isZero ? 0.9 : 0.6}
              />
              <text
                x={padding.left - 10}
                y={t.y + 3.5}
                textAnchor="end"
                className="text-[10px] font-mono fill-slate-500 dark:fill-slate-400"
                style={{ fontSize: '10px' }}
              >
                {t.pct}
              </text>
            </g>
          ))}

          {/* X Axis ticks */}
          {xTicks.map((t, idx) => (
            <g key={`xtick-${idx}`}>
              <line
                x1={t.x}
                y1={padding.top}
                x2={t.x}
                y2={padding.top + plotHeight}
                stroke="#cbd5e1"
                className="dark:stroke-slate-700"
                strokeWidth="1"
                strokeDasharray="2 3"
                strokeOpacity="0.5"
              />
              <text
                x={t.x}
                y={height - 12}
                textAnchor="middle"
                className="text-[10px] font-mono fill-slate-500 dark:fill-slate-400"
                style={{ fontSize: '10px' }}
              >
                {t.label}
              </text>
            </g>
          ))}

          {/* Individual Simulation Paths */}
          {pathStrings.map((p, idx) => (
            <path
              key={`path-${idx}`}
              d={p.d}
              fill="none"
              stroke={p.isPositive ? 'rgba(5, 150, 105, 0.22)' : 'rgba(225, 29, 72, 0.22)'}
              strokeWidth="1.2"
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          ))}

          {/* Highlighted Median Path */}
          <path
            d={medianD}
            fill="none"
            stroke="url(#medianGlowLight)"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* Hover tracker column */}
          {hoverIndex !== null && hoverIndex >= 0 && hoverIndex < medianPath.length && (
            <g>
              <line
                x1={medianPath[hoverIndex].x}
                y1={padding.top}
                x2={medianPath[hoverIndex].x}
                y2={padding.top + plotHeight}
                stroke="#0284c7"
                strokeWidth="1.5"
                strokeDasharray="3 3"
              />
              <circle
                cx={medianPath[hoverIndex].x}
                cy={medianPath[hoverIndex].y}
                r="4.5"
                fill="#0284c7"
                stroke="#ffffff"
                strokeWidth="2"
              />
            </g>
          )}

          {/* Transparent hit boxes for mouse tracking */}
          {medianPath.map((pt, i) => (
            <rect
              key={`hit-${i}`}
              x={getX(i) - (width / chartData.numPoints) / 2}
              y={padding.top}
              width={width / chartData.numPoints}
              height={plotHeight}
              fill="transparent"
              onMouseEnter={() => setHoverIndex(i)}
            />
          ))}
        </svg>

        {/* Hover Tooltip Overlay */}
        {hoverIndex !== null && hoverIndex >= 0 && hoverIndex < medianPath.length && (
          <div
            className="absolute pointer-events-none bg-white/95 dark:bg-slate-900/95 backdrop-blur-md border border-slate-200 dark:border-slate-700/80 rounded-lg px-3 py-2 text-xs shadow-xl transition-all font-mono z-10"
            style={{
              left: `${Math.min(Math.max(12, (medianPath[hoverIndex].x / width) * 100), 82)}%`,
              top: '14px',
            }}
          >
            <div className="text-slate-500 dark:text-slate-400 font-sans font-medium text-[11px] mb-1">
              Day {hoverIndex} Projection
            </div>
            <div className="flex items-center gap-2 text-emerald-700 dark:text-emerald-400 font-bold">
              <span>Median:</span>
              <span>{(((medianPath[hoverIndex].val - 1) * 100)).toFixed(2)}%</span>
            </div>
            <div className="text-[10px] text-slate-500 dark:text-slate-400 mt-0.5">
              Portfolio Multiple: {medianPath[hoverIndex].val.toFixed(3)}x
            </div>
          </div>
        )}
      </div>

      {/* Terminal Percentile Pill Ladder */}
      {percentiles && (
        <div className="mt-4 pt-3.5 border-t border-slate-200 dark:border-slate-800">
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-2.5 flex items-center justify-between">
            <span>Terminal Return Distribution Percentiles</span>
            <span className="font-normal text-[11px] text-slate-500 dark:text-slate-400">Day {horizonDays} outcome probabilities</span>
          </div>
          <div className="grid grid-cols-3 sm:grid-cols-5 md:grid-cols-9 gap-2 text-center text-xs font-mono">
            {[
              { label: 'p1 (Worst)', val: percentiles.p1, tone: 'rose' },
              { label: 'p5', val: percentiles.p5, tone: 'rose' },
              { label: 'p10', val: percentiles.p10, tone: 'amber' },
              { label: 'p25', val: percentiles.p25, tone: 'amber' },
              { label: 'p50 (Median)', val: percentiles.p50, tone: 'emerald' },
              { label: 'p75', val: percentiles.p75, tone: 'emerald' },
              { label: 'p90', val: percentiles.p90, tone: 'emerald' },
              { label: 'p95', val: percentiles.p95, tone: 'emerald' },
              { label: 'p99 (Best)', val: percentiles.p99, tone: 'emerald' },
            ].map((p, idx) => {
              const numVal = p.val != null ? (Number(p.val) * 100).toFixed(1) : '—'
              const isNeg = p.val != null && Number(p.val) < 0
              return (
                <div
                  key={`pctl-${idx}`}
                  className="bg-slate-50 dark:bg-slate-900/60 border border-slate-200/90 dark:border-slate-800 rounded-lg p-2 flex flex-col items-center justify-center shadow-2xs"
                >
                  <span className="text-[10px] text-slate-500 dark:text-slate-400 tracking-tight font-medium">{p.label}</span>
                  <span className={`text-xs font-bold mt-0.5 ${isNeg ? 'text-rose-600 dark:text-rose-400' : 'text-emerald-600 dark:text-emerald-400'}`}>
                    {p.val != null ? (isNeg ? `${numVal}%` : `+${numVal}%`) : '—'}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
