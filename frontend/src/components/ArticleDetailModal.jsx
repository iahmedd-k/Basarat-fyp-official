import React, { useState, useEffect, useMemo } from 'react'
import StockLogo from './StockLogo'
import { dashboardApi } from '../api/dashboard'

// Format relative time (e.g. "12h ago")
function formatRelativeTime(dateString) {
  if (!dateString) return null
  try {
    const date = new Date(dateString)
    if (isNaN(date.getTime())) return null
    const now = new Date()
    const diffMs = now - date
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMins / 60)
    const diffDays = Math.floor(diffHours / 24)

    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    if (diffDays === 1) return 'Yesterday'
    if (diffDays < 7) return `${diffDays}d ago`
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  } catch {
    return null
  }
}

/**
 * ArticleDetailModal - Clones the TickerAnalysts announcement detail popup.
 * Displays:
 * - Stock logo & ticker with category tag and relative timestamp
 * - Share and close controls
 * - Full headline and summary description
 * - Sentiment indicator badge (strictly if present from API)
 * - KEY FINDINGS bulleted card (derived from announcement text)
 * - Financial Indicators & Key Metrics (strictly from backend /stocks/{symbol}/fundamentals)
 * - "View full report ↗" direct source filing link
 */
export default function ArticleDetailModal({ article, onClose, onStock }) {
  const [fundamentals, setFundamentals] = useState(null)
  const [loadingFundamentals, setLoadingFundamentals] = useState(false)
  const [copied, setCopied] = useState(false)

  if (!article) return null

  const symbol = article.symbol || (article.symbols?.[0]?.symbol || article.symbols?.[0]) || null
  const sourceName = article.source?.name || 'PSX'
  const timeLabel = formatRelativeTime(article.published_at)
  const categoryLabel = article.categoryLabel || 'Financial Announcement'
  const sourceUrl = article.url || article.external_url || ''
  const hasValidSource = Boolean(sourceUrl && sourceUrl.startsWith('http'))

  // Close on Escape key press and lock background scroll
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose?.()
    }
    window.addEventListener('keydown', handleKeyDown)
    const originalOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    return () => {
      window.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = originalOverflow
    }
  }, [onClose])

  // Fetch company fundamentals from backend API if symbol is available
  useEffect(() => {
    if (!symbol) return
    setLoadingFundamentals(true)
    dashboardApi
      .getFundamentals(symbol)
      .then((data) => setFundamentals(data))
      .catch(() => setFundamentals(null))
      .finally(() => setLoadingFundamentals(false))
  }, [symbol])

  // Extract Key Findings from summary or announcement text
  const keyFindings = useMemo(() => {
    if (!article.summary) return []
    // Split summary by sentences or bullet characters
    const sentences = article.summary
      .split(/(?<=[.?!])\s+/)
      .map((s) => s.trim())
      .filter((s) => s.length > 15 && !s.toLowerCase().startsWith('key financial announcement'))
    
    // If sentences found, return up to 4 clean bullet points
    if (sentences.length > 0) {
      return sentences.slice(0, 4)
    }
    return [article.summary.trim()]
  }, [article.summary])

  // Compile strictly backend-derived financial indicators
  const metricsList = useMemo(() => {
    const list = []
    const ratios = fundamentals?.ratios
    const equity = fundamentals?.equity_profile
    const limits = fundamentals?.trading_limits
    const text = `${article.title || ''} ${article.summary || ''}`

    // 1. Earnings Per Share
    if (ratios?.eps != null) {
      list.push({
        label: 'Earnings Per Share',
        value: `PKR ${Number(ratios.eps).toFixed(2)}`,
        change: ratios.eps_growth_pct != null ? `${ratios.eps_growth_pct >= 0 ? '+' : ''}${ratios.eps_growth_pct}%` : null,
        isPositive: ratios.eps_growth_pct != null ? ratios.eps_growth_pct >= 0 : true,
      })
    }

    // 2. Net Profit Margin
    if (ratios?.net_profit_margin_pct != null) {
      list.push({
        label: 'Net Profit Margin',
        value: `${Number(ratios.net_profit_margin_pct).toFixed(2)}%`,
        change: null,
      })
    }

    // 3. Gross Profit Margin
    if (ratios?.gross_profit_margin_pct != null) {
      list.push({
        label: 'Gross Profit Margin',
        value: `${Number(ratios.gross_profit_margin_pct).toFixed(2)}%`,
        change: null,
      })
    }

    // 4. Dividend Yield
    if (ratios?.dividend_yield_pct != null) {
      list.push({
        label: 'Dividend Yield',
        value: `${Number(ratios.dividend_yield_pct).toFixed(2)}%`,
        change: null,
      })
    }

    // 5. Market Capitalization
    if (equity?.market_cap_pkr_m != null) {
      list.push({
        label: 'Market Capitalization',
        value: `PKR ${Number(equity.market_cap_pkr_m).toLocaleString()} Million`,
        change: null,
      })
    }

    // 6. 1-Year Stock Return
    if (limits?.year_change_pct != null) {
      const isPos = limits.year_change_pct >= 0
      list.push({
        label: '52-Week Stock Performance',
        value: `${isPos ? '+' : ''}${Number(limits.year_change_pct).toFixed(2)}%`,
        change: `${isPos ? '+' : ''}${Number(limits.year_change_pct).toFixed(2)}%`,
        isPositive: isPos,
        isNegative: !isPos,
      })
    }

    // Parse specific figures if found directly in article title or summary text (e.g. "PKR 9.18 billion")
    // Revenue match e.g. "revenue of PKR 9.18 billion"
    const revMatch = text.match(/revenue\s+(?:of\s+)?(PKR\s+[\d.]+\s*(?:billion|million)?)/i)
    if (revMatch && !list.some((m) => m.label.toLowerCase().includes('revenue'))) {
      list.unshift({
        label: 'Revenue',
        value: revMatch[1],
        change: null,
      })
    }

    // Net profit match e.g. "net profit of PKR 309 million"
    const profitMatch = text.match(/net\s+profit\s+(?:after\s+taxation\s+)?(?:of\s+)?(PKR\s+[\d.]+\s*(?:billion|million)?)/i)
    if (profitMatch && !list.some((m) => m.label.toLowerCase().includes('profit'))) {
      list.push({
        label: 'Net Profit After Taxation',
        value: profitMatch[1],
        change: null,
      })
    }

    // Cash dividend match e.g. "cash dividend of PKR 5"
    const divMatch = text.match(/(?:cash\s+)?dividend\s+(?:of\s+)?(PKR\s+[\d.]+)/i)
    if (divMatch && !list.some((m) => m.label.toLowerCase().includes('dividend'))) {
      list.push({
        label: 'Cash Dividend Per Share',
        value: divMatch[1],
        change: null,
      })
    }

    return list
  }, [fundamentals, article.title, article.summary, symbol])

  // Copy share URL
  const handleShare = () => {
    const url = article.url || article.external_url || `${window.location.origin}/news/${article.id}`
    if (navigator.clipboard) {
      navigator.clipboard.writeText(url)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const displaySummary = article.summary || ''

  const displaySentiment = useMemo(() => {
    if (!article.sentiment) return null
    let label = null
    if (typeof article.sentiment === 'object') {
      label = article.sentiment.label?.toLowerCase()
    } else if (typeof article.sentiment === 'string') {
      label = article.sentiment.toLowerCase()
    }
    if (!label) return null
    if (label === 'bullish' || label === 'positive') return { type: 'positive', label: 'Bullish' }
    if (label === 'bearish' || label === 'negative') return { type: 'negative', label: 'Bearish' }
    if (label === 'neutral') return { type: 'neutral', label: 'Neutral' }
    return null
  }, [article.sentiment])

  return (
    <div
      className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-3 sm:p-5 overflow-y-auto"
      onClick={onClose}
      aria-modal="true"
      role="dialog"
    >
      <div
        className="relative w-full max-w-lg sm:max-w-xl bg-white dark:bg-slate-900 rounded-2xl sm:rounded-3xl shadow-2xl border border-slate-200/90 dark:border-slate-800 overflow-hidden flex flex-col max-h-[88vh] my-auto animate-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Top Header */}
        <div className="px-5 sm:px-6 pt-5 pb-4 border-b border-slate-100 dark:border-slate-800/80 flex items-start justify-between gap-3 shrink-0">
          <div className="flex items-center gap-3">
            {symbol ? (
              <div
                onClick={() => {
                  onClose?.()
                  onStock?.(symbol)
                }}
                className="cursor-pointer group"
                title={`View ${symbol} stock detail`}
              >
                <StockLogo
                  symbol={symbol}
                  ticker={symbol}
                  size="md"
                  className="rounded-xl shadow-2xs group-hover:ring-2 group-hover:ring-emerald-500/40 transition-all"
                />
              </div>
            ) : (
              <div className="w-10 h-10 rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 font-bold text-xs flex items-center justify-center border border-slate-200 dark:border-slate-700">
                PSX
              </div>
            )}

            <div>
              <div className="flex items-center gap-2">
                {symbol ? (
                  <button
                    type="button"
                    onClick={() => {
                      onClose?.()
                      onStock?.(symbol)
                    }}
                    className="font-bold text-lg sm:text-xl text-slate-900 dark:text-white cursor-pointer"
                  >
                    {symbol}
                  </button>
                ) : (
                  <span className="font-bold text-base text-slate-800 dark:text-slate-200">
                    {sourceName}
                  </span>
                )}
              </div>

              <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                <span className="inline-flex items-center gap-1 font-semibold text-[11px] px-2 py-0.5 rounded-md bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-200/80 dark:border-amber-800">
                  <svg className="w-3 h-3 text-amber-600 dark:text-amber-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <polyline points="14 2 14 8 20 8" />
                    <line x1="16" y1="13" x2="8" y2="13" />
                    <line x1="16" y1="17" x2="8" y2="17" />
                  </svg>
                  {categoryLabel}
                </span>

                {timeLabel && (
                  <>
                    <span className="text-slate-300 dark:text-slate-700">·</span>
                    <span>{timeLabel}</span>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Action buttons (Share & Close in top right) */}
          <div className="flex flex-col items-center gap-1 shrink-0">
            <button
              type="button"
              onClick={onClose}
              className="p-1 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
              aria-label="Close"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>

            <button
              type="button"
              onClick={handleShare}
              className="p-1 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
              aria-label="Share"
              title="Share announcement"
            >
              {copied ? (
                <span className="text-[10px] font-bold text-emerald-600 dark:text-emerald-400 px-1">
                  Copied!
                </span>
              ) : (
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <circle cx="18" cy="5" r="3" />
                  <circle cx="6" cy="12" r="3" />
                  <circle cx="18" cy="19" r="3" />
                  <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
                  <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
                </svg>
              )}
            </button>
          </div>
        </div>

        {/* Modal Scrollable Body */}
        <div className="overflow-y-auto px-5 sm:px-6 py-5 space-y-5 flex-1">
          {/* Article Title */}
          {article.title && (
            <h2 className="text-base sm:text-lg font-bold text-slate-900 dark:text-white leading-snug">
              {article.title}
            </h2>
          )}

          {/* Main Summary Description */}
          {displaySummary && (
            <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
              {displaySummary}
            </p>
          )}

          {/* Sentiment Badge (strictly if present from API response, zero emojis) */}
          {displaySentiment && (
            <div>
              {displaySentiment.type === 'positive' && (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-50/80 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-200/80 dark:border-amber-800">
                  <svg className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <line x1="7" y1="17" x2="17" y2="7" />
                    <polyline points="7 7 17 7 17 17" />
                  </svg>
                  {displaySentiment.label || 'Cautiously Positive'}
                </span>
              )}

              {displaySentiment.type === 'negative' && (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300 border border-rose-200/80 dark:border-rose-800">
                  <svg className="w-3.5 h-3.5 text-rose-600 dark:text-rose-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <line x1="7" y1="7" x2="17" y2="17" />
                    <polyline points="17 7 17 17 7 17" />
                  </svg>
                  {displaySentiment.label || 'Negative'}
                </span>
              )}

              {displaySentiment.type === 'neutral' && (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
                  <span className="w-1.5 h-1.5 rounded-full bg-slate-400" aria-hidden="true" />
                  {displaySentiment.label || 'Neutral'}
                </span>
              )}

              {article.impact_score != null && article.impact_score > 0 && (
                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-mono font-bold bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border border-slate-200 dark:border-slate-700 ml-2">
                  Impact {article.impact_score}/100
                </span>
              )}
            </div>
          )}

          {/* Associated PSX Equities */}
          {Array.isArray(article.symbols) && article.symbols.length > 1 && (
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Tagged Equities:</span>
              {article.symbols.map((symObj, sIdx) => {
                const sym = typeof symObj === 'string' ? symObj : symObj?.symbol
                if (!sym) return null
                return (
                  <button
                    key={sIdx}
                    type="button"
                    onClick={() => {
                      onClose?.()
                      onStock?.(sym)
                    }}
                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-mono font-bold bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 hover:bg-emerald-50 hover:text-emerald-700 dark:hover:bg-emerald-950 dark:hover:text-emerald-300 transition-colors"
                  >
                    {sym}
                  </button>
                )
              })}
            </div>
          )}

          {/* KEY FINDINGS Card */}
          {keyFindings.length > 0 && (
            <div className="rounded-2xl bg-slate-50/80 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800 p-4 sm:p-4.5 space-y-2.5">
              <span className="text-[11px] font-bold tracking-wider text-slate-400 dark:text-slate-500 uppercase block">
                KEY FINDINGS
              </span>
              <ul className="space-y-2 text-xs sm:text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                {keyFindings.map((point, idx) => (
                  <li key={idx} className="flex items-start gap-2">
                    <span className="text-slate-400 dark:text-slate-500 select-none font-bold mt-0.5">•</span>
                    <span>{point}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Financial Indicators & Key Metrics (strictly from backend API) */}
          {loadingFundamentals ? (
            <div className="space-y-2.5 pt-2 animate-pulse">
              <div className="h-4 w-32 bg-slate-200 dark:bg-slate-800 rounded" />
              <div className="h-10 bg-slate-100 dark:bg-slate-800/60 rounded-xl" />
              <div className="h-10 bg-slate-100 dark:bg-slate-800/60 rounded-xl" />
            </div>
          ) : metricsList.length > 0 ? (
            <div className="space-y-4 pt-1">
              {metricsList.map((m, idx) => (
                <div
                  key={idx}
                  className="border-b border-slate-100 dark:border-slate-800/80 pb-3 last:border-b-0"
                >
                  <div className="flex items-center justify-between gap-2 text-xs">
                    <span className="text-slate-500 dark:text-slate-400 font-normal">
                      {m.label}
                    </span>
                    {m.change && (
                      <span
                        className={`inline-flex items-center gap-0.5 text-xs font-semibold ${
                          m.isPositive
                            ? 'text-emerald-600 dark:text-emerald-400'
                            : m.isNegative
                            ? 'text-rose-600 dark:text-rose-400'
                            : 'text-slate-500'
                        }`}
                      >
                        <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                          {m.isNegative ? (
                            <>
                              <line x1="7" y1="7" x2="17" y2="17" />
                              <polyline points="17 7 17 17 7 17" />
                            </>
                          ) : (
                            <>
                              <line x1="7" y1="17" x2="17" y2="7" />
                              <polyline points="7 7 17 7 17 17" />
                            </>
                          )}
                        </svg>
                        {m.change}
                      </span>
                    )}
                  </div>

                  <div className="mt-1 flex items-baseline gap-2 flex-wrap">
                    <span className="text-sm sm:text-base font-bold text-slate-900 dark:text-white">
                      {m.value}
                    </span>
                    {m.subtext && (
                      <span className="text-xs text-slate-400 dark:text-slate-500 font-normal">
                        {m.subtext}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : null}

          {/* View Full Report Link */}
          {hasValidSource && (
            <div className="pt-2">
              <a
                href={sourceUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-emerald-600 dark:text-emerald-400 font-semibold text-xs sm:text-sm hover:underline inline-flex items-center gap-1.5 transition-colors"
              >
                <span>View full report</span>
                <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                  <polyline points="15 3 21 3 21 9" />
                  <line x1="10" y1="14" x2="21" y2="3" />
                </svg>
              </a>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
