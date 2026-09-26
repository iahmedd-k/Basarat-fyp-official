import React from 'react'
import StockLogo from './StockLogo'
import ShariahBadge from './ShariahBadge'

// Format relative date / time
function formatRelativeTime(dateString) {
  if (!dateString) return 'Recent'
  try {
    const date = new Date(dateString)
    if (isNaN(date.getTime())) return 'Recent'
    const now = new Date()
    const diffMs = now - date
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMins / 60)
    const diffDays = Math.floor(diffHours / 24)

    if (diffMins < 2) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    if (diffDays === 1) return 'Yesterday'
    if (diffDays < 7) return `${diffDays}d ago`
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
  } catch {
    return 'Recent'
  }
}

// Format event type labels cleanly
function formatEventType(type) {
  if (!type) return null
  return type
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(' ')
}

/**
 * Reusable institutional-grade News Card component.
 * Features:
 * - Source metadata & official disclosure tag
 * - High-contrast headline with click navigation
 * - Clean excerpt clamping
 * - Stock association tags with official company logos & Mosque Shariah indicators
 * - Sentiment & impact score pills
 */
export default function NewsCard({
  article,
  onClick,
  onStockClick,
  className = '',
  kmiSymbolsSet = new Set(),
}) {
  if (!article) return null

  const {
    title = '',
    summary = '',
    source = {},
    is_official = false,
    symbols = [],
    event_type = '',
    sentiment = null,
    impact_score = null,
    published_at = '',
    external_url = '',
    url = '',
  } = article

  const sourceName = source?.name || 'Market Source'
  const timeLabel = formatRelativeTime(published_at)
  const eventLabel = formatEventType(event_type)

  const sentimentLabel = sentiment?.label?.toLowerCase()
  const sentimentScore = sentiment?.score != null ? Math.round(Math.abs(sentiment.score) * 100) : null

  const linkTarget = external_url || url

  const handleCardClick = (e) => {
    if (onClick) {
      onClick(article)
    } else if (linkTarget) {
      window.open(linkTarget, '_blank', 'noopener,noreferrer')
    }
  }

  const handleStockClick = (e, symbol) => {
    e.stopPropagation()
    if (onStockClick) {
      onStockClick(symbol)
    } else {
      window.history.pushState({}, '', `/stocks/${encodeURIComponent(symbol)}`)
      window.dispatchEvent(new PopStateEvent('popstate'))
    }
  }

  return (
    <article
      className={`pro-news-card group relative bg-white dark:bg-slate-900 border border-slate-200/90 dark:border-slate-800 rounded-2xl p-5 transition-all duration-200 hover:border-emerald-500/40 hover:shadow-md cursor-pointer flex flex-col justify-between gap-3 ${className}`}
      onClick={handleCardClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && handleCardClick(e)}
      aria-label={title}
    >
      {/* 1. Header Row: Source, Official Tag, Time, Impact */}
      <div className="flex items-center justify-between gap-3 text-xs flex-wrap">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-semibold text-slate-700 dark:text-slate-300 tracking-tight">
            {sourceName}
          </span>

          {is_official && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-200 dark:border-amber-800/80">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
              Official Filing
            </span>
          )}

          {eventLabel && (
            <span className="text-slate-500 dark:text-slate-400 font-medium px-2 py-0.5 rounded-md bg-slate-100 dark:bg-slate-800 text-[11px]">
              {eventLabel}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2 text-slate-400 text-xs shrink-0">
          <time dateTime={published_at}>{timeLabel}</time>
          {impact_score != null && impact_score > 0 && (
            <span
              className="text-[10px] font-mono font-semibold px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300"
              title={`Impact Score: ${impact_score}/100`}
            >
              Impact {impact_score}
            </span>
          )}
        </div>
      </div>

      {/* 2. Headline & Excerpt */}
      <div className="space-y-1.5">
        <h3 className="text-base sm:text-lg font-bold text-slate-900 dark:text-slate-100 tracking-tight leading-snug group-hover:text-emerald-600 dark:group-hover:text-emerald-400 transition-colors m-0">
          {title}
        </h3>
        {summary && (
          <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 line-clamp-2 leading-relaxed m-0">
            {summary}
          </p>
        )}
      </div>

      {/* 3. Footer Row: Associated Stocks with Official Logos & Sentiment */}
      <div className="flex items-center justify-between gap-3 pt-3 border-t border-slate-100 dark:border-slate-800/80 flex-wrap">
        {/* Left: Associated Stocks */}
        <div className="flex items-center gap-2 flex-wrap">
          {symbols && symbols.length > 0 ? (
            symbols.map((symObj) => {
              const sym = typeof symObj === 'string' ? symObj : symObj?.symbol
              if (!sym) return null
              const isCompliant = kmiSymbolsSet.has(sym.toUpperCase())
              return (
                <button
                  type="button"
                  key={sym}
                  className="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg bg-slate-50 dark:bg-slate-800 hover:bg-emerald-50 dark:hover:bg-emerald-950/50 border border-slate-200 dark:border-slate-700 hover:border-emerald-300 dark:hover:border-emerald-800 text-xs font-mono font-bold text-slate-800 dark:text-slate-200 transition-all"
                  onClick={(e) => handleStockClick(e, sym)}
                  title={`View ${sym} research & signals`}
                >
                  <StockLogo symbol={sym} size="xs" />
                  <span>{sym}</span>
                  {isCompliant && (
                    <ShariahBadge isCompliant={true} size="xs" showLabel={false} />
                  )}
                </button>
              )
            })
          ) : (
            <span className="text-[11px] text-slate-400">Broad Market</span>
          )}
        </div>

        {/* Right: Sentiment Pill & External Link Icon */}
        <div className="flex items-center gap-2 shrink-0">
          {sentimentLabel && (
            <span
              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold ${
                sentimentLabel === 'bullish'
                  ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800'
                  : sentimentLabel === 'bearish'
                  ? 'bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300 border border-rose-200 dark:border-rose-800'
                  : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300 border border-slate-200 dark:border-slate-700'
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  sentimentLabel === 'bullish'
                    ? 'bg-emerald-500'
                    : sentimentLabel === 'bearish'
                    ? 'bg-rose-500'
                    : 'bg-slate-400'
                }`}
              />
              <span className="capitalize">{sentimentLabel}</span>
              {sentimentScore != null && <span>{sentimentScore}%</span>}
            </span>
          )}

          {linkTarget && (
            <span
              className="text-slate-400 group-hover:text-emerald-500 transition-colors text-xs font-mono"
              aria-hidden="true"
              title="Open full document"
            >
              ↗
            </span>
          )}
        </div>
      </div>
    </article>
  )
}

