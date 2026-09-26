/**
 * Formatting utilities for financial numbers, currencies, percentages, and signals.
 */

export function formatNumber(value, fractionDigits = 2) {
  if (value === null || value === undefined || value === '' || Number.isNaN(Number(value))) {
    return '—'
  }
  return Number(value).toLocaleString('en-PK', {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  })
}

export function formatMoney(value, fractionDigits = 2) {
  if (value === null || value === undefined || value === '' || Number.isNaN(Number(value))) {
    return '—'
  }
  return `PKR ${formatNumber(value, fractionDigits)}`
}

export function formatCompactNumber(value) {
  if (value === null || value === undefined || value === '' || Number.isNaN(Number(value))) {
    return '—'
  }
  const num = Number(value)
  const abs = Math.abs(num)
  if (abs >= 1e12) return `${(num / 1e12).toFixed(2)}T`
  if (abs >= 1e9) return `${(num / 1e9).toFixed(2)}B`
  if (abs >= 1e6) return `${(num / 1e6).toFixed(2)}M`
  if (abs >= 1e3) return `${(num / 1e3).toFixed(1)}K`
  return num.toLocaleString('en-PK')
}

export function formatPercent(value, fractionDigits = 2) {
  if (value === null || value === undefined || value === '' || Number.isNaN(Number(value))) {
    return '—'
  }
  const num = Number(value)
  const sign = num > 0 ? '+' : ''
  return `${sign}${num.toFixed(fractionDigits)}%`
}

export function formatDate(dateString) {
  if (!dateString) return '—'
  try {
    const d = new Date(dateString)
    if (isNaN(d.getTime())) return String(dateString)
    return d.toLocaleDateString('en-PK', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  } catch {
    return String(dateString)
  }
}

export function getSignalStyle(signal) {
  const norm = (signal || '').toString().toUpperCase().trim()
  if (norm.includes('STRONGLY_BULLISH') || norm.includes('STRONG_BUY')) {
    return {
      label: 'Strong Buy',
      badge: 'bg-emerald-600 text-white border-emerald-600 font-bold',
      text: 'text-emerald-600 dark:text-emerald-400 font-bold',
      dot: 'bg-emerald-400',
    }
  }
  if (norm.includes('BULLISH') || norm.includes('BUY')) {
    return {
      label: 'Bullish',
      badge: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800',
      text: 'text-emerald-600 dark:text-emerald-400 font-semibold',
      dot: 'bg-emerald-500',
    }
  }
  if (norm.includes('STRONGLY_BEARISH') || norm.includes('STRONG_SELL')) {
    return {
      label: 'Strong Sell',
      badge: 'bg-rose-600 text-white border-rose-600 font-bold',
      text: 'text-rose-600 dark:text-rose-400 font-bold',
      dot: 'bg-rose-300',
    }
  }
  if (norm.includes('BEARISH') || norm.includes('SELL')) {
    return {
      label: 'Bearish',
      badge: 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800',
      text: 'text-rose-600 dark:text-rose-400 font-semibold',
      dot: 'bg-rose-500',
    }
  }
  return {
    label: norm ? norm.replace('_', ' ') : 'Neutral',
    badge: 'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700',
    text: 'text-slate-600 dark:text-slate-400 font-medium',
    dot: 'bg-slate-400',
  }
}

