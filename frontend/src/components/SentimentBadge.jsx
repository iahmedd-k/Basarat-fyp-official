import React from 'react'

export default function SentimentBadge({
  sentiment,
  score,
  size = 'md',
  showScore = true,
  className = '',
}) {
  const norm = (sentiment || '').toString().toLowerCase().trim()
  const isPositive = norm.includes('pos') || norm.includes('bull')
  const isNegative = norm.includes('neg') || norm.includes('bear')
  const isNeutral = !isPositive && !isNegative

  let label = 'Neutral'
  let colorClasses = 'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800/80 dark:text-slate-300 dark:border-slate-700'
  let dotColor = 'bg-slate-400 dark:bg-slate-500'

  if (isPositive) {
    label = 'Bullish'
    colorClasses = 'bg-emerald-50 text-emerald-700 border-emerald-200/80 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800/60'
    dotColor = 'bg-emerald-500'
  } else if (isNegative) {
    label = 'Bearish'
    colorClasses = 'bg-rose-50 text-rose-700 border-rose-200/80 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800/60'
    dotColor = 'bg-rose-500'
  }

  const sizeClasses = {
    sm: 'text-[11px] px-2 py-0.5 gap-1.5',
    md: 'text-xs px-2.5 py-1 gap-2',
    lg: 'text-sm px-3 py-1.5 gap-2.5',
  }[size] || 'text-xs px-2.5 py-1 gap-2'

  const formattedScore = score != null && !isNaN(score) ? (
    <span className="font-mono text-[0.9em] opacity-85 ml-0.5">
      {score > 0 ? `+${Number(score).toFixed(2)}` : Number(score).toFixed(2)}
    </span>
  ) : null

  return (
    <span
      className={`inline-flex items-center font-medium rounded-full border transition-colors ${sizeClasses} ${colorClasses} ${className}`}
      title={score != null ? `FinBERT score: ${score}` : `Sentiment: ${label}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${dotColor}`} aria-hidden="true" />
      <span>{label}</span>
      {showScore && formattedScore}
    </span>
  )
}

