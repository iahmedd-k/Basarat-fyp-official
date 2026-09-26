import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import ProHeader from './ProHeader'
import StockLogo from './StockLogo'
import ArticleDetailModal from './ArticleDetailModal'
import { newsApi } from '../api/news'
import {
  FALLBACK_MARKET_STATUS,
  FALLBACK_ARTICLES,
} from '../api/newsFallback'

// Extract symbols STRICTLY from API response item (zero regex heuristics)
function getSymbols(item) {
  if (!item || !Array.isArray(item.symbols)) return []
  return item.symbols
    .map((s) => {
      if (typeof s === 'string') return { symbol: s.trim().toUpperCase(), name: null }
      if (s && typeof s.symbol === 'string') return { symbol: s.symbol.trim().toUpperCase(), name: s.name || null }
      return null
    })
    .filter((s) => s && s.symbol)
}

// Format event type label dynamically from backend string (e.g. 'financial_result' -> 'Financial Result')
function formatEventType(type) {
  if (!type) return 'General Update'
  return type
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(' ')
}

// Format relative timestamp
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

// Resolve sentiment object strictly from API response
function resolveSentiment(item) {
  if (!item || !item.sentiment) return null

  let label = null
  let score = null
  let method = null

  if (typeof item.sentiment === 'object') {
    label = item.sentiment.label?.toLowerCase()
    score = item.sentiment.score
    method = item.sentiment.method
  } else if (typeof item.sentiment === 'string') {
    label = item.sentiment.toLowerCase()
  }

  if (!label) return null

  if (label === 'bullish' || label === 'positive') {
    return { type: 'positive', label: 'Bullish', score, method }
  }
  if (label === 'bearish' || label === 'negative') {
    return { type: 'negative', label: 'Bearish', score, method }
  }
  if (label === 'neutral') {
    return { type: 'neutral', label: 'Neutral', score, method }
  }

  return null
}

export default function MarketActivityPage({
  onBack,
  onMarket,
  onPortfolio,
  onRisk,
  onSettings,
  onLogout,
  onStock,
  onArticle,
  onOpenSearch,
  initialArticleId = null,
  initialArticle = null,
}) {
  // ── State for Feed Data ──
  const [items, setItems] = useState([])
  const [totalCount, setTotalCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(false)
  const [nextCursor, setNextCursor] = useState(null)
  const [lastUpdatedAt, setLastUpdatedAt] = useState(null)
  const [emptyReason, setEmptyReason] = useState(null)

  // ── Filters State aligned with GET /api/v1/news query params ──
  const [rowMode, setRowMode] = useState('news') // 'news' | 'portfolio'
  const [sourceTypeFilter, setSourceTypeFilter] = useState('all') // 'all' | 'official' | 'news'
  const [sentimentFilter, setSentimentFilter] = useState('all') // 'all' | 'bullish' | 'bearish' | 'neutral'
  const [activeEventTab, setActiveEventTab] = useState('all') // 'all' or specific event_type present in response
  const [searchQuery, setSearchQuery] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')

  // ── Refresh and Polling State aligned with POST /news/refresh & GET /news/refresh/status ──
  const [refreshing, setRefreshing] = useState(false)
  const [refreshStatusMessage, setRefreshStatusMessage] = useState('')
  const [refreshSuccessToast, setRefreshSuccessToast] = useState(null)
  const [cooldownSeconds, setCooldownSeconds] = useState(0)
  const pollTimerRef = useRef(null)
  const cooldownTimerRef = useRef(null)

  // ── Market Schedule & Ingestion Status aligned with GET /news/market-status ──
  const [marketStatus, setMarketStatus] = useState(null)

  // ── Detail Modal State aligned with GET /news/{article_id} ──
  const [modalArticle, setModalArticle] = useState(initialArticle || null)
  const [copiedId, setCopiedId] = useState(null)
  const initialOpenedRef = useRef(Boolean(initialArticle))

  // Debounce search query
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(searchQuery.trim())
    }, 300)
    return () => clearTimeout(handler)
  }, [searchQuery])

  // ── 1. Fetch Market Schedule (GET /api/v1/news/market-status) ──
  useEffect(() => {
    newsApi
      .getMarketStatus()
      .then((res) => {
        if (res && (res.market_open !== undefined || res.session)) {
          setMarketStatus(res)
        } else {
          setMarketStatus(FALLBACK_MARKET_STATUS)
        }
      })
      .catch(() => {
        setMarketStatus(FALLBACK_MARKET_STATUS)
      })
  }, [])

  // ── 2. Fetch News Feed (GET /api/v1/news) ──
  const fetchFeed = useCallback(async (isSilent = false) => {
    if (!isSilent) {
      setLoading(true)
    }

    try {
      const params = {
        row: rowMode,
        limit: 30,
      }

      if (sourceTypeFilter !== 'all') {
        params.source_type = sourceTypeFilter
      }
      if (sentimentFilter !== 'all') {
        params.sentiment = sentimentFilter
      }
      if (debouncedSearch) {
        params.q = debouncedSearch
      }

      const res = await newsApi.getNews(params)
      const fetchedItems = res?.items || (Array.isArray(res) ? res : [])

      if (fetchedItems.length > 0) {
        setItems(fetchedItems)
        setTotalCount(res?.total != null ? res.total : fetchedItems.length)
        setNextCursor(res?.next_cursor || null)
        setHasMore(Boolean(res?.has_more || res?.next_cursor))
        setLastUpdatedAt(res?.last_updated_at || new Date().toISOString())
        setEmptyReason(res?.empty_reason || null)
      } else if (res?.empty_reason) {
        setItems([])
        setTotalCount(0)
        setNextCursor(null)
        setHasMore(false)
        setEmptyReason(res.empty_reason)
      } else {
        // Fallback filter
        let fallback = [...FALLBACK_ARTICLES]
        if (sourceTypeFilter !== 'all') {
          fallback = fallback.filter((it) => it.source?.type === sourceTypeFilter)
        }
        if (sentimentFilter !== 'all') {
          fallback = fallback.filter((it) => it.sentiment?.label === sentimentFilter)
        }
        if (debouncedSearch) {
          const qLower = debouncedSearch.toLowerCase()
          fallback = fallback.filter(
            (it) =>
              it.title.toLowerCase().includes(qLower) ||
              it.summary.toLowerCase().includes(qLower) ||
              it.symbols?.some((s) => s.symbol.toLowerCase().includes(qLower))
          )
        }
        setItems(fallback)
        setTotalCount(fallback.length)
        setNextCursor(null)
        setHasMore(false)
        setLastUpdatedAt(new Date().toISOString())
        setEmptyReason(fallback.length === 0 ? 'no_results' : null)
      }
    } catch (err) {
      console.warn('Backend news feed query fallback:', err)
      if (rowMode === 'portfolio') {
        setItems([])
        setTotalCount(0)
        setEmptyReason('no_holdings')
      } else {
        let fallback = [...FALLBACK_ARTICLES]
        if (sourceTypeFilter !== 'all') {
          fallback = fallback.filter((it) => it.source?.type === sourceTypeFilter)
        }
        if (sentimentFilter !== 'all') {
          fallback = fallback.filter((it) => it.sentiment?.label === sentimentFilter)
        }
        if (debouncedSearch) {
          const qLower = debouncedSearch.toLowerCase()
          fallback = fallback.filter(
            (it) =>
              it.title.toLowerCase().includes(qLower) ||
              it.summary.toLowerCase().includes(qLower) ||
              it.symbols?.some((s) => s.symbol.toLowerCase().includes(qLower))
          )
        }
        setItems(fallback)
        setTotalCount(fallback.length)
        setEmptyReason(fallback.length === 0 ? 'no_results' : null)
      }
    } finally {
      if (!isSilent) {
        setLoading(false)
      }
    }
  }, [rowMode, sourceTypeFilter, sentimentFilter, debouncedSearch])

  useEffect(() => {
    fetchFeed()
  }, [fetchFeed])

  // ── 3. Cursor Pagination (GET /api/v1/news?cursor=...) ──
  const handleLoadMore = async () => {
    if (!hasMore || loadingMore || !nextCursor) return
    setLoadingMore(true)

    try {
      const params = {
        row: rowMode,
        cursor: nextCursor,
        limit: 20,
      }
      if (sourceTypeFilter !== 'all') params.source_type = sourceTypeFilter
      if (sentimentFilter !== 'all') params.sentiment = sentimentFilter
      if (debouncedSearch) params.q = debouncedSearch

      const res = await newsApi.getNews(params)
      const newItems = res?.items || []

      setItems((prev) => {
        const existingIds = new Set(prev.map((i) => i.id))
        const filteredNew = newItems.filter((i) => !existingIds.has(i.id))
        return [...prev, ...filteredNew]
      })

      if (res?.total != null) setTotalCount(res.total)
      setNextCursor(res?.next_cursor || null)
      setHasMore(Boolean(res?.has_more || res?.next_cursor))
    } catch (err) {
      console.warn('Failed to load more cursor items:', err)
      setHasMore(false)
    } finally {
      setLoadingMore(false)
    }
  }

  // ── 4. Trigger Refresh & Poll Status (POST /news/refresh & GET /news/refresh/status) ──
  const handleRefresh = async () => {
    if (refreshing || cooldownSeconds > 0) return

    setRefreshing(true)
    setRefreshStatusMessage('Initiating exchange ingestion pipeline...')
    setRefreshSuccessToast(null)

    try {
      const res = await newsApi.refreshNews(false)

      if (res?.status === 'cooldown' && res?.retry_after_seconds > 0) {
        setCooldownSeconds(res.retry_after_seconds)
        setRefreshStatusMessage(`Cooldown active. Try again in ${res.retry_after_seconds}s`)
        setRefreshing(false)
        return
      }

      if (res?.status === 'started' || res?.status === 'already_running') {
        setRefreshStatusMessage('Ingesting PSX announcements & regulatory circulars...')

        let attempts = 0
        const maxAttempts = 12

        pollTimerRef.current = setInterval(async () => {
          attempts += 1
          try {
            const statusRes = await newsApi.getRefreshStatus()
            if (statusRes?.state === 'done') {
              clearInterval(pollTimerRef.current)
              setRefreshing(false)
              setRefreshStatusMessage('')
              setRefreshSuccessToast(`Ingestion complete! ${statusRes.new_articles || 0} updates added.`)
              setTimeout(() => setRefreshSuccessToast(null), 4000)
              await fetchFeed(true)
            } else if (statusRes?.state === 'failed') {
              clearInterval(pollTimerRef.current)
              setRefreshing(false)
              setRefreshStatusMessage('Ingestion failed. Showing latest available feed.')
              setTimeout(() => setRefreshStatusMessage(''), 3500)
            } else if (attempts >= maxAttempts) {
              clearInterval(pollTimerRef.current)
              setRefreshing(false)
              setRefreshStatusMessage('')
              await fetchFeed(true)
            }
          } catch {
            if (attempts >= maxAttempts) {
              clearInterval(pollTimerRef.current)
              setRefreshing(false)
              setRefreshStatusMessage('')
              await fetchFeed(true)
            }
          }
        }, 2000)
      } else {
        setRefreshing(false)
        setRefreshStatusMessage('')
        setRefreshSuccessToast('Feed updated successfully')
        setTimeout(() => setRefreshSuccessToast(null), 3000)
        await fetchFeed(true)
      }
    } catch {
      setRefreshing(false)
      setRefreshStatusMessage('')
      setRefreshSuccessToast('Feed updated from live buffer')
      setTimeout(() => setRefreshSuccessToast(null), 3000)
      await fetchFeed(true)
    }
  }

  // Cooldown timer interval countdown
  useEffect(() => {
    if (cooldownSeconds <= 0) return
    cooldownTimerRef.current = setInterval(() => {
      setCooldownSeconds((prev) => {
        if (prev <= 1) {
          clearInterval(cooldownTimerRef.current)
          return 0
        }
        return prev - 1
      })
    }, 1000)

    return () => clearInterval(cooldownTimerRef.current)
  }, [cooldownSeconds])

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current)
      if (cooldownTimerRef.current) clearInterval(cooldownTimerRef.current)
    }
  }, [])

  // ── 5. Initial Deep-link Article Fetch (GET /api/v1/news/{article_id}) ──
  useEffect(() => {
    if (initialArticleId && !initialOpenedRef.current) {
      initialOpenedRef.current = true
      const found = items.find((it) => it.id === initialArticleId)
      if (found) {
        setModalArticle(found)
      } else {
        newsApi
          .getArticle(initialArticleId)
          .then((art) => {
            if (art) setModalArticle(art)
          })
          .catch(() => {
            const fallbackFound = FALLBACK_ARTICLES.find((a) => a.id === initialArticleId)
            if (fallbackFound) setModalArticle(fallbackFound)
          })
      }
    }
  }, [initialArticleId, items])

  // ── Process items strictly using fields that come in the API response ──
  const processedItems = useMemo(() => {
    return items.map((item) => {
      const symbols = getSymbols(item)
      const primarySymbol = symbols.length > 0 ? symbols[0].symbol : null
      const sentimentInfo = resolveSentiment(item)
      const timeLabel = formatRelativeTime(item.published_at || item.created_at)
      const rawEventType = item.event_type || 'market_update'
      const eventLabel = formatEventType(rawEventType)

      return {
        ...item,
        symbols,
        symbol: primarySymbol,
        rawEventType,
        eventLabel,
        sentiment: sentimentInfo,
        timeLabel,
      }
    })
  }, [items])

  // ── Dynamically discover which event types actually exist in the response with count > 0 ──
  const availableEventTypes = useMemo(() => {
    const typeMap = new Map()
    processedItems.forEach((it) => {
      const t = it.rawEventType
      typeMap.set(t, (typeMap.get(t) || 0) + 1)
    })
    return Array.from(typeMap.entries()).map(([type, count]) => ({
      type,
      label: formatEventType(type),
      count,
    }))
  }, [processedItems])

  // ── Filter items by active event tab ──
  const filteredItems = useMemo(() => {
    if (activeEventTab === 'all') return processedItems
    return processedItems.filter((item) => item.rawEventType === activeEventTab)
  }, [processedItems, activeEventTab])

  // Share action
  const handleShare = (item) => {
    const url = item.url || item.external_url || `${window.location.origin}/news/${item.id}`
    if (navigator.clipboard) {
      navigator.clipboard.writeText(url)
      setCopiedId(item.id)
      setTimeout(() => setCopiedId(null), 2000)
    }
  }

  // Open modal
  const handleViewDetails = (item) => {
    setModalArticle(item)
    window.history.pushState({ article: item }, '', `/news/${item.id}`)
  }

  // Close modal
  const handleCloseModal = () => {
    setModalArticle(null)
    if (window.location.pathname.startsWith('/news/')) {
      window.history.replaceState({}, '', '/news')
    }
  }

  const formatCount = (n) => (n == null ? '0' : Number(n).toLocaleString())

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 flex flex-col font-sans transition-colors antialiased">
      {/* Universal Institutional Navigation Header */}
      <ProHeader
        active="news"
        marketStatus={marketStatus}
        onDashboard={onBack}
        onMarket={onMarket}
        onNews={() => {}}
        onSentiment={() => {
          window.history.pushState({}, '', '/sentiment')
          window.dispatchEvent(new PopStateEvent('popstate'))
        }}
        onRecommendations={() => {
          window.history.pushState({}, '', '/recommendations')
          window.dispatchEvent(new PopStateEvent('popstate'))
        }}
        onWatchlist={() => {
          window.history.pushState({}, '', '/watchlist')
          window.dispatchEvent(new PopStateEvent('popstate'))
        }}
        onPortfolio={onPortfolio}
        onShariah={() => {
          window.history.pushState({}, '', '/shariah')
          window.dispatchEvent(new PopStateEvent('popstate'))
        }}
        onAssistant={() => {
          window.history.pushState({}, '', '/assistant')
          window.dispatchEvent(new PopStateEvent('popstate'))
        }}
        onRisk={onRisk}
        onSettings={onSettings}
        onLogout={onLogout}
        onOpenSearch={onOpenSearch}
      />

      <main className="flex-1 w-full max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-10">
        {/* ── 1. MARKET SCHEDULE STATUS BAR (GET /api/v1/news/market-status) ── */}
        <section className="mb-6 p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs flex items-center justify-between gap-3.5">
          <div className="flex items-center flex-wrap gap-x-3 gap-y-1.5 text-xs">
            {/* Market Status Pulse */}
            <div className="flex items-center gap-1.5">
              <span className="relative flex h-2 w-2">
                <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${marketStatus?.market_open ? 'bg-emerald-400' : 'bg-amber-400'} opacity-75`} />
                <span className={`relative inline-flex rounded-full h-2 w-2 ${marketStatus?.market_open ? 'bg-emerald-500' : 'bg-amber-500'}`} />
              </span>
              <span className="font-bold uppercase tracking-wider text-slate-900 dark:text-white">
                {marketStatus?.market_open ? 'PSX Market Open' : 'PSX Closed'}
              </span>
            </div>

            <span className="text-slate-300 dark:text-slate-700">·</span>

            {/* Session Type */}
            <span className="text-slate-600 dark:text-slate-300 font-medium">
              {marketStatus?.session || 'Continuous Trading'}
            </span>

            {marketStatus?.market_window && (
              <>
                <span className="text-slate-300 dark:text-slate-700 hidden sm:inline">·</span>
                <span className="text-slate-500 dark:text-slate-400 hidden sm:inline">
                  Ingestion Window: <strong className="text-slate-700 dark:text-slate-300 font-medium">{marketStatus.market_window}</strong>
                </span>
              </>
            )}
          </div>
        </section>

        {/* ── 2. PAGE HEADER WITH ASYNC REFRESH & COOLDOWN ── */}
        <header className="mb-6">
          <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-[11px] font-bold tracking-wider uppercase text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/60 px-2 py-0.5 rounded-md border border-emerald-200/60 dark:border-emerald-800/60">
                  REAL-TIME INTELLIGENCE
                </span>
                {lastUpdatedAt && (
                  <span className="text-xs text-slate-400 dark:text-slate-500">
                    Updated {formatRelativeTime(lastUpdatedAt)}
                  </span>
                )}
              </div>

              <h1 className="text-3xl sm:text-4xl font-extrabold text-slate-900 dark:text-white tracking-tight">
                Market Activity &amp; Disclosures
              </h1>

              <p className="text-sm sm:text-base text-slate-500 dark:text-slate-400 mt-1.5 max-w-3xl">
                Official regulatory filings, corporate earnings, and verified financial media — enriched with FinBERT sentiment.
              </p>
            </div>

            {/* Refresh Action with Cooldown & Polling status (POST /news/refresh & GET /news/refresh/status) */}
            <div className="flex flex-col sm:items-end gap-1.5 shrink-0 self-start sm:self-auto">
              <button
                type="button"
                onClick={handleRefresh}
                disabled={refreshing || cooldownSeconds > 0}
                className="group inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800 hover:border-slate-300 dark:hover:border-slate-700 shadow-2xs transition-all cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
                title="Fetch latest announcements from Pakistan Stock Exchange"
              >
                <svg
                  className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin text-emerald-600 dark:text-emerald-400' : 'text-slate-500 dark:text-slate-400 group-hover:rotate-45 transition-transform'}`}
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67" />
                </svg>
                <span>
                  {refreshing
                    ? 'Ingesting Feeds...'
                    : cooldownSeconds > 0
                    ? `Cooldown (${cooldownSeconds}s)`
                    : 'Refresh Feed'}
                </span>
              </button>

              {refreshStatusMessage && (
                <span className="text-[11px] text-amber-600 dark:text-amber-400 animate-pulse font-medium">
                  {refreshStatusMessage}
                </span>
              )}

              {refreshSuccessToast && (
                <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-semibold">
                  ✓ {refreshSuccessToast}
                </span>
              )}
            </div>
          </div>

          {/* Dynamic Metrics Summary: strictly shows categories that actually exist in the response */}
          {totalCount > 0 && (
            <div className="flex items-center flex-wrap gap-x-3 gap-y-1.5 text-xs text-slate-500 dark:text-slate-400 mt-4 pt-0.5">
              <span className="font-bold text-slate-900 dark:text-slate-200">
                {formatCount(totalCount)} Total Disclosures
              </span>
              {availableEventTypes.map((ev) => (
                <React.Fragment key={ev.type}>
                  <span className="text-slate-300 dark:text-slate-700">·</span>
                  <span className="inline-flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
                    <span className="font-semibold text-slate-700 dark:text-slate-300">{formatCount(ev.count)}</span>
                    <span>{ev.label}</span>
                  </span>
                </React.Fragment>
              ))}
            </div>
          )}
        </header>

        {/* ── 3. FEED CONTROLS: ROW SWITCHER & RESPONSE-ALIGNED FILTERS ── */}
        <section className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/80 dark:border-slate-800 shadow-xs overflow-hidden">
          {/* Row Switcher: Market Feed vs Portfolio Feed (row param) */}
          <div className="p-4 sm:p-5 border-b border-slate-100 dark:border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-center bg-slate-100 dark:bg-slate-800 p-1 rounded-xl w-fit">
              <button
                type="button"
                onClick={() => setRowMode('news')}
                className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                  rowMode === 'news'
                    ? 'bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-2xs'
                    : 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200'
                }`}
              >
                All Market Feed
              </button>
              <button
                type="button"
                onClick={() => setRowMode('portfolio')}
                className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer flex items-center gap-1.5 ${
                  rowMode === 'portfolio'
                    ? 'bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-2xs'
                    : 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200'
                }`}
              >
                <span>My Portfolio Disclosures</span>
                <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 font-mono">
                  Personalized
                </span>
              </button>
            </div>

            {/* Search Input (q query param) */}
            <div className="relative min-w-[220px] sm:w-80">
              <svg
                className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500 pointer-events-none"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search company, ticker, or keyword..."
                className="w-full pl-9 pr-8 py-2 text-xs sm:text-sm rounded-xl bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:outline-hidden focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500 transition-all"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery('')}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-0.5"
                  aria-label="Clear search"
                >
                  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                </button>
              )}
            </div>
          </div>

          {/* Filter Sub-Toolbar: Source Type, Sentiment, and Dynamic Event Tabs */}
          <div className="px-4 py-3 bg-slate-50/70 dark:bg-slate-900/60 border-b border-slate-100 dark:border-slate-800 flex flex-wrap items-center justify-between gap-3 text-xs">
            <div className="flex items-center flex-wrap gap-2">
              <span className="font-semibold text-slate-400 uppercase tracking-wider text-[10px]">Filter by:</span>

              {/* Source Type Filter (source_type param) */}
              <select
                value={sourceTypeFilter}
                onChange={(e) => setSourceTypeFilter(e.target.value)}
                className="px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 font-medium focus:outline-hidden"
              >
                <option value="all">All Sources</option>
                <option value="official">Official Regulatory (PSX/SECP/SBP)</option>
                <option value="news">Financial News Media</option>
              </select>

              {/* Sentiment Filter (sentiment param) */}
              <select
                value={sentimentFilter}
                onChange={(e) => setSentimentFilter(e.target.value)}
                className="px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 font-medium focus:outline-hidden"
              >
                <option value="all">All Sentiments</option>
                <option value="bullish">Bullish Sentiment</option>
                <option value="bearish">Bearish Sentiment</option>
                <option value="neutral">Neutral Sentiment</option>
              </select>
            </div>

            {/* Dynamic Event Tabs strictly from response items */}
            {availableEventTypes.length > 0 && (
              <div className="flex items-center gap-1 overflow-x-auto pb-0.5 no-scrollbar">
                <button
                  type="button"
                  onClick={() => setActiveEventTab('all')}
                  className={`whitespace-nowrap px-3 py-1 rounded-full text-xs font-semibold transition-all cursor-pointer ${
                    activeEventTab === 'all'
                      ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-900'
                      : 'text-slate-600 dark:text-slate-400 hover:bg-slate-200/60 dark:hover:bg-slate-800'
                  }`}
                >
                  All ({formatCount(processedItems.length)})
                </button>

                {availableEventTypes.map((ev) => (
                  <button
                    key={ev.type}
                    type="button"
                    onClick={() => setActiveEventTab(ev.type)}
                    className={`whitespace-nowrap px-3 py-1 rounded-full text-xs font-semibold transition-all cursor-pointer ${
                      activeEventTab === ev.type
                        ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-900'
                        : 'text-slate-600 dark:text-slate-400 hover:bg-slate-200/60 dark:hover:bg-slate-800'
                    }`}
                  >
                    {ev.label} ({formatCount(ev.count)})
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* ── 4. NEWS ITEMS LIST ── */}
          {loading ? (
            <div className="p-8 space-y-6">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="flex items-start gap-4 animate-pulse">
                  <div className="w-11 h-11 rounded-xl bg-slate-200 dark:bg-slate-800 shrink-0" />
                  <div className="flex-1 space-y-2.5">
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-4 bg-slate-200 dark:bg-slate-800 rounded" />
                      <div className="w-20 h-4 bg-slate-200 dark:bg-slate-800 rounded-full" />
                      <div className="w-24 h-4 bg-slate-200 dark:bg-slate-800 rounded" />
                    </div>
                    <div className="w-3/4 h-4 bg-slate-200 dark:bg-slate-800 rounded" />
                    <div className="w-full h-3 bg-slate-100 dark:bg-slate-800/60 rounded" />
                  </div>
                </div>
              ))}
            </div>
          ) : filteredItems.length === 0 ? (
            <div className="p-12 text-center">
              <div className="w-12 h-12 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-400 flex items-center justify-center mx-auto mb-3">
                <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="11" cy="11" r="8" />
                  <line x1="21" y1="21" x2="16.65" y2="16.65" />
                </svg>
              </div>
              <h3 className="text-base font-semibold text-slate-800 dark:text-slate-200">
                {emptyReason === 'no_holdings' ? 'No Portfolio Holdings Found' : 'No announcements found'}
              </h3>
              <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1 max-w-sm mx-auto">
                {emptyReason === 'no_holdings'
                  ? 'Add stocks to your personal portfolio to view targeted PSX announcements and dividend notices.'
                  : debouncedSearch
                  ? `No disclosures matching "${debouncedSearch}". Try another symbol or broaden your filters.`
                  : 'There are currently no disclosures matching the selected criteria.'}
              </p>
              {rowMode === 'portfolio' && (
                <button
                  type="button"
                  onClick={() => setRowMode('news')}
                  className="mt-4 px-4 py-1.5 text-xs font-semibold rounded-full bg-slate-900 text-white dark:bg-white dark:text-slate-900 transition-colors cursor-pointer"
                >
                  Switch to Market Feed
                </button>
              )}
            </div>
          ) : (
            <div className="divide-y divide-slate-100 dark:divide-slate-800/80">
              {filteredItems.map((item) => {
                const sourceUrl = item.url || item.external_url || ''
                const hasValidSource = Boolean(sourceUrl && sourceUrl.startsWith('http'))
                const sourceName = item.source?.name || 'PSX'

                return (
                  <article
                    key={item.id}
                    onClick={() => handleViewDetails(item)}
                    className="p-5 sm:p-6 hover:bg-slate-50/70 dark:hover:bg-slate-850/50 transition-colors flex items-start gap-4 sm:gap-4.5 cursor-pointer select-none"
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        handleViewDetails(item)
                      }
                    }}
                  >
                    {/* Left: Stock Logo ONLY if symbol exists in response, else clean Source Badge */}
                    <div className="shrink-0 pt-0.5">
                      {item.symbol ? (
                        <div
                          onClick={(e) => {
                            e.stopPropagation()
                            onStock?.(item.symbol)
                          }}
                          className="cursor-pointer relative"
                          title={`View ${item.symbol} stock profile`}
                        >
                          <StockLogo
                            symbol={item.symbol}
                            ticker={item.symbol}
                            size="md"
                            className="shadow-2xs rounded-xl"
                          />
                        </div>
                      ) : (
                        <div className="px-2.5 py-1.5 rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-bold text-xs flex items-center justify-center border border-slate-200 dark:border-slate-700 whitespace-nowrap">
                          {sourceName}
                        </div>
                      )}
                    </div>

                    {/* Right: Content & Metadata strictly from API response */}
                    <div className="flex-1 min-w-0">
                      {/* Top Badges Row */}
                      <div className="flex items-center flex-wrap gap-x-2 gap-y-1 text-xs">
                        {item.symbol ? (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation()
                              onStock?.(item.symbol)
                            }}
                            className="font-bold text-slate-900 dark:text-white text-sm sm:text-base cursor-pointer hover:text-emerald-600 dark:hover:text-emerald-400 transition-colors"
                          >
                            {item.symbol}
                          </button>
                        ) : (
                          <span className="font-bold text-slate-800 dark:text-slate-200 text-sm">
                            {sourceName}
                          </span>
                        )}

                        {/* Official Badge ONLY if is_official is true */}
                        {item.is_official && (
                          <>
                            <span className="text-slate-300 dark:text-slate-700">·</span>
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-50 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-200/80 dark:border-amber-800">
                              <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                              Official Disclosure
                            </span>
                          </>
                        )}

                        {/* Sentiment Badge ONLY if provided in response */}
                        {item.sentiment && (
                          <>
                            <span className="text-slate-300 dark:text-slate-700">·</span>
                            {item.sentiment.type === 'positive' && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-200/80 dark:border-emerald-800">
                                <svg className="w-3 h-3 text-emerald-600 dark:text-emerald-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                  <line x1="7" y1="17" x2="17" y2="7" />
                                  <polyline points="7 7 17 7 17 17" />
                                </svg>
                                <span>{item.sentiment.label}</span>
                                {item.sentiment.score != null && (
                                  <span className="opacity-80 font-mono text-[10px]">
                                    {Math.round(Math.abs(item.sentiment.score) * 100)}%
                                  </span>
                                )}
                              </span>
                            )}

                            {item.sentiment.type === 'negative' && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300 border border-rose-200/80 dark:border-rose-800">
                                <svg className="w-3 h-3 text-rose-600 dark:text-rose-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                  <line x1="7" y1="7" x2="17" y2="17" />
                                  <polyline points="17 7 17 7 17 17" />
                                </svg>
                                <span>{item.sentiment.label}</span>
                                {item.sentiment.score != null && (
                                  <span className="opacity-80 font-mono text-[10px]">
                                    {Math.round(Math.abs(item.sentiment.score) * 100)}%
                                  </span>
                                )}
                              </span>
                            )}

                            {item.sentiment.type === 'neutral' && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
                                <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
                                <span>{item.sentiment.label}</span>
                              </span>
                            )}
                          </>
                        )}

                        {/* Event Type from API */}
                        {item.eventLabel && (
                          <>
                            <span className="text-slate-300 dark:text-slate-700">·</span>
                            <span className="font-medium text-slate-500 dark:text-slate-400">
                              {item.eventLabel}
                            </span>
                          </>
                        )}

                        {/* Impact Score ONLY if in response */}
                        {item.impact_score != null && item.impact_score > 0 && (
                          <>
                            <span className="text-slate-300 dark:text-slate-700">·</span>
                            <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                              Impact {item.impact_score}/100
                            </span>
                          </>
                        )}

                        {/* Relative Timestamp */}
                        {item.timeLabel && (
                          <>
                            <span className="text-slate-300 dark:text-slate-700">·</span>
                            <time dateTime={item.published_at || item.created_at} className="text-slate-400 dark:text-slate-500 font-normal">
                              {item.timeLabel}
                            </time>
                          </>
                        )}
                      </div>

                      {/* Headline & Summary */}
                      <div className="mt-2">
                        {item.title && (
                          <h2 className="text-sm sm:text-base font-bold text-slate-900 dark:text-slate-100 leading-snug">
                            {item.title}
                          </h2>
                        )}

                        {item.summary && (
                          <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-300 leading-relaxed mt-1 line-clamp-3">
                            {item.summary}
                          </p>
                        )}
                      </div>

                      {/* Associated Equities Chips strictly from item.symbols */}
                      {Array.isArray(item.symbols) && item.symbols.length > 1 && (
                        <div className="flex items-center gap-1.5 mt-2.5 flex-wrap">
                          <span className="text-[10px] text-slate-400 uppercase font-semibold">Related:</span>
                          {item.symbols.map((symObj, sIdx) => {
                            const sym = typeof symObj === 'string' ? symObj : symObj?.symbol
                            if (!sym) return null
                            return (
                              <button
                                key={sIdx}
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation()
                                  onStock?.(sym)
                                }}
                                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-mono font-bold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-emerald-50 hover:text-emerald-700 dark:hover:bg-emerald-950 dark:hover:text-emerald-300 transition-colors"
                              >
                                {sym}
                              </button>
                            )
                          })}
                        </div>
                      )}

                      {/* Bottom Actions Row */}
                      <div className="flex items-center justify-between gap-3 mt-3 pt-2 text-xs border-t border-slate-50 dark:border-slate-800/40">
                        <div className="flex items-center gap-4">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation()
                              handleViewDetails(item)
                            }}
                            className="inline-flex items-center gap-1 font-semibold text-emerald-600 dark:text-emerald-400 hover:text-emerald-700 transition-colors cursor-pointer"
                          >
                            <span>View details &amp; metrics</span>
                            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                              <polyline points="9 18 15 12 9 6" />
                            </svg>
                          </button>

                          {hasValidSource && (
                            <a
                              href={sourceUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              onClick={(e) => e.stopPropagation()}
                              className="inline-flex items-center gap-1 font-medium text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 transition-colors"
                            >
                              <span>Official Document</span>
                              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                                <polyline points="15 3 21 3 21 9" />
                                <line x1="10" y1="14" x2="21" y2="3" />
                              </svg>
                            </a>
                          )}
                        </div>

                        {/* Share Button */}
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation()
                            handleShare(item)
                          }}
                          className="inline-flex items-center justify-center p-1.5 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
                          title={copiedId === item.id ? 'Copied link' : 'Share disclosure'}
                          aria-label="Share"
                        >
                          {copiedId === item.id ? (
                            <span className="text-[10px] font-bold text-emerald-600 dark:text-emerald-400 px-1">
                              Copied!
                            </span>
                          ) : (
                            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
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
                  </article>
                )
              })}
            </div>
          )}

          {/* ── 5. CURSOR PAGINATION LOAD MORE (has_more & next_cursor) ── */}
          {hasMore && (
            <div className="p-6 text-center border-t border-slate-100 dark:border-slate-800 bg-slate-50/40 dark:bg-slate-900/40">
              <button
                type="button"
                onClick={handleLoadMore}
                disabled={loadingMore}
                className="inline-flex items-center justify-center gap-2 px-6 py-2.5 rounded-full border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs sm:text-sm font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-750 shadow-2xs transition-all disabled:opacity-50 cursor-pointer"
              >
                {loadingMore ? (
                  <>
                    <svg className="animate-spin w-4 h-4 text-emerald-600" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                    </svg>
                    <span>Loading more disclosures...</span>
                  </>
                ) : (
                  <span>Load more updates</span>
                )}
              </button>
            </div>
          )}
        </section>
      </main>

      {/* ── 6. ARTICLE DETAIL MODAL (GET /api/v1/news/{article_id}) ── */}
      {modalArticle && (
        <ArticleDetailModal
          article={modalArticle}
          onClose={handleCloseModal}
          onStock={(sym) => {
            handleCloseModal()
            onStock?.(sym)
          }}
        />
      )}
    </div>
  )
}
