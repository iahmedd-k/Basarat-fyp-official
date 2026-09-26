import React from 'react'

function formatPktTime(isoString) {
  if (!isoString) return ''
  try {
    const d = new Date(isoString)
    if (isNaN(d.getTime())) return ''
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: true }) + ' PKT'
  } catch {
    return ''
  }
}

/**
 * Compact, institutional market schedule and news ingestion status panel.
 * Driven strictly by GET /api/v1/news/market-status.
 */
export default function MarketStatusWidget({ marketStatus, className = '' }) {
  if (!marketStatus) return null

  const {
    status = 'closed',
    session_label = 'closed',
    current_time_pkt = '',
    ingestion_allowed = false,
    is_weekend = false,
    is_holiday = false,
  } = marketStatus

  const isOpen = status?.toLowerCase() === 'open'
  const timeStr = formatPktTime(current_time_pkt)
  const sessionTitle = session_label?.replaceAll('_', ' ')

  return (
    <div
      className={`market-status-panel flex flex-wrap items-center justify-between gap-3 p-3.5 bg-slate-50 dark:bg-slate-800/60 border border-slate-200/90 dark:border-slate-800 rounded-xl text-xs ${className}`}
      role="region"
      aria-label="Market and news ingestion status"
    >
      <div className="flex items-center gap-3 flex-wrap">
        {/* Market state pill */}
        <span
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full font-bold uppercase tracking-wider text-[11px] ${
            isOpen
              ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20'
              : 'bg-slate-200/70 dark:bg-slate-700/70 text-slate-600 dark:text-slate-300'
          }`}
        >
          <span
            className={`w-2 h-2 rounded-full ${
              isOpen ? 'bg-emerald-500 animate-pulse' : 'bg-slate-400'
            }`}
          />
          Market {isOpen ? 'Open' : 'Closed'}
        </span>

        {/* Session details */}
        <span className="text-slate-600 dark:text-slate-300 font-medium">
          Session: <strong className="capitalize text-slate-900 dark:text-slate-100">{sessionTitle || (isOpen ? 'Trading' : 'Closed')}</strong>
        </span>

        {is_weekend && (
          <span className="text-amber-700 dark:text-amber-400 font-semibold px-2 py-0.5 rounded bg-amber-50 dark:bg-amber-950/40 text-[10px]">
            Weekend
          </span>
        )}

        {is_holiday && (
          <span className="text-amber-700 dark:text-amber-400 font-semibold px-2 py-0.5 rounded bg-amber-50 dark:bg-amber-950/40 text-[10px]">
            Exchange Holiday
          </span>
        )}
      </div>

      <div className="flex items-center gap-4 text-slate-500 dark:text-slate-400">
        {/* Ingestion status */}
        <span className="flex items-center gap-1.5">
          <span className={`w-1.5 h-1.5 rounded-full ${ingestion_allowed ? 'bg-emerald-500' : 'bg-amber-400'}`} />
          News Ingestion: <b className="text-slate-700 dark:text-slate-200">{ingestion_allowed ? 'Active' : 'Scheduled'}</b>
        </span>

        {/* Current PKT time */}
        {timeStr && (
          <span className="font-mono text-slate-600 dark:text-slate-300 hidden sm:inline">
            {timeStr}
          </span>
        )}
      </div>
    </div>
  )
}
