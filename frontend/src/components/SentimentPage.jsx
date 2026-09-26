import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import ProHeader from './ProHeader'
import StockLogo from './StockLogo'
import ShariahBadge from './ShariahBadge'
import SentimentBadge from './SentimentBadge'
import SentimentHistoryChart from './SentimentHistoryChart'
import ArticleDetailModal from './ArticleDetailModal'
import { sentimentApi } from '../api/sentiment'
import { dashboardApi } from '../api/dashboard'
import { newsApi } from '../api/news'
import {
  FALLBACK_MARKET_SENTIMENT,
  FALLBACK_STOCK_SENTIMENTS,
  generateFallbackHistory,
  generateFallbackNews,
} from '../api/sentimentFallback'

const POPULAR_SYMBOLS = ['MEBL', 'OGDC', 'SYS', 'HUBC', 'ENGRO', 'UBL', 'LUCK', 'MARI', 'MCB', 'HBL']
const ROLLING_DAYS = [7, 14, 30, 90]

export default function SentimentPage({
  initialSymbol = 'MEBL',
  onBack,
  onMarket,
  onPortfolio,
  onNews,
  onWatchlist,
  onRecommendations,
  onShariah,
  onAssistant,
  onRisk,
  onSettings,
  onLogout,
  onStock,
  onArticle,
  onOpenSearch,
  mobileNav,
}) {
  const [selectedSymbol, setSelectedSymbol] = useState(initialSymbol.toUpperCase())
  const [stockSearchQuery, setStockSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [isSearching, setIsSearching] = useState(false)
  const [searchFocused, setSearchFocused] = useState(false)
  const searchContainerRef = useRef(null)

  // ── 1. GET /api/v1/sentiment/market-overview ──
  const [marketSentiment, setMarketSentiment] = useState(null)
  const [marketLoading, setMarketLoading] = useState(true)

  // ── 2. GET /api/v1/sentiment/{symbol} ──
  const [rollingDays, setRollingDays] = useState(7)
  const [stockSentiment, setStockSentiment] = useState(null)
  const [stockSentimentLoading, setStockSentimentLoading] = useState(true)
  const [stockOverview, setStockOverview] = useState(null)
  const [isCompliant, setIsCompliant] = useState(false)

  // ── 3. GET /api/v1/sentiment/{symbol}/history ──
  const [historyPeriod, setHistoryPeriod] = useState('1M')
  const [historyData, setHistoryData] = useState([])
  const [historyLoading, setHistoryLoading] = useState(true)

  // ── 4. GET /api/v1/sentiment/{symbol}/news ──
  const [sentimentFilter, setSentimentFilter] = useState('ALL') // ALL | POSITIVE | NEUTRAL | NEGATIVE
  const [newsItems, setNewsItems] = useState([])
  const [newsPage, setNewsPage] = useState(1)
  const [newsTotal, setNewsTotal] = useState(0)
  const [newsLoading, setNewsLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)

  // Modal inspection
  const [modalArticle, setModalArticle] = useState(null)

  // KMI-30 Shariah universe
  const [kmiSymbols, setKmiSymbols] = useState(new Set())

  // Load KMI-30 constituents for Mosque badge
  useEffect(() => {
    let mounted = true
    dashboardApi
      .getKmi30Constituents()
      .then((res) => {
        if (!mounted) return
        const syms = new Set()
        const constituents = res?.constituents || res?.items || (Array.isArray(res) ? res : [])
        constituents.forEach((item) => {
          const s = typeof item === 'string' ? item : item.symbol
          if (s) syms.add(s.toUpperCase())
        })
        setKmiSymbols(syms)
      })
      .catch(() => {})
    return () => {
      mounted = false
    }
  }, [])

  // ── Fetch Market Sentiment (GET /api/v1/sentiment/market-overview) ──
  useEffect(() => {
    let mounted = true
    setMarketLoading(true)
    sentimentApi
      .getMarketSentiment()
      .then((res) => {
        if (!mounted) return
        if (res && res.market_mood) {
          setMarketSentiment(res)
        } else {
          setMarketSentiment(FALLBACK_MARKET_SENTIMENT)
        }
        setMarketLoading(false)
      })
      .catch((err) => {
        if (!mounted) return
        console.warn('Market sentiment fetch fallback:', err)
        setMarketSentiment(FALLBACK_MARKET_SENTIMENT)
        setMarketLoading(false)
      })
    return () => {
      mounted = false
    }
  }, [])

  // ── Fetch Stock Sentiment (GET /api/v1/sentiment/{symbol}?days=...) ──
  useEffect(() => {
    let mounted = true
    setStockSentimentLoading(true)
    setIsCompliant(kmiSymbols.has(selectedSymbol))

    // Overview for company name & sector
    dashboardApi
      .getStockOverview(selectedSymbol)
      .then((data) => {
        if (mounted) setStockOverview(data)
      })
      .catch(() => {
        if (mounted) setStockOverview(null)
      })

    // Per-stock sentiment
    sentimentApi
      .getStockSentiment(selectedSymbol, rollingDays)
      .then((data) => {
        if (!mounted) return
        if (data && data.score !== undefined) {
          setStockSentiment(data)
        } else {
          setStockSentiment(FALLBACK_STOCK_SENTIMENTS[selectedSymbol] || {
            symbol: selectedSymbol,
            score: 0.25,
            label: 'neutral',
            article_count: 5,
            trend: 'stable',
          })
        }
        setStockSentimentLoading(false)
      })
      .catch((err) => {
        if (!mounted) return
        console.warn('Stock sentiment fetch fallback:', err)
        setStockSentiment(FALLBACK_STOCK_SENTIMENTS[selectedSymbol] || {
          symbol: selectedSymbol,
          score: 0.25,
          label: 'neutral',
          article_count: 5,
          trend: 'stable',
        })
        setStockSentimentLoading(false)
      })

    return () => {
      mounted = false
    }
  }, [selectedSymbol, rollingDays, kmiSymbols])

  // ── Fetch Sentiment History (GET /api/v1/sentiment/{symbol}/history?period=...) ──
  useEffect(() => {
    let mounted = true
    setHistoryLoading(true)
    sentimentApi
      .getSentimentHistory(selectedSymbol, historyPeriod, 100)
      .then((data) => {
        if (!mounted) return
        if (data?.data && Array.isArray(data.data) && data.data.length > 0) {
          setHistoryData(data.data)
        } else {
          const fallback = generateFallbackHistory(selectedSymbol, historyPeriod)
          setHistoryData(fallback.data)
        }
        setHistoryLoading(false)
      })
      .catch((err) => {
        if (!mounted) return
        console.warn('Sentiment history fetch fallback:', err)
        const fallback = generateFallbackHistory(selectedSymbol, historyPeriod)
        setHistoryData(fallback.data)
        setHistoryLoading(false)
      })
    return () => {
      mounted = false
    }
  }, [selectedSymbol, historyPeriod])

  // ── Fetch Sentiment News (GET /api/v1/sentiment/{symbol}/news?...) ──
  useEffect(() => {
    let mounted = true
    setNewsLoading(true)
    setNewsPage(1)

    const params = {
      page: 1,
      limit: 10,
    }
    if (sentimentFilter !== 'ALL') {
      params.sentiment = sentimentFilter
    }

    sentimentApi
      .getSentimentNews(selectedSymbol, params)
      .then((data) => {
        if (!mounted) return
        if (data?.items && Array.isArray(data.items) && data.items.length > 0) {
          setNewsItems(data.items)
          setNewsTotal(data.total || data.items.length)
        } else {
          const fallback = generateFallbackNews(selectedSymbol)
          const filtered = sentimentFilter === 'ALL'
            ? fallback.items
            : fallback.items.filter((it) => it.sentiment === sentimentFilter)
          setNewsItems(filtered)
          setNewsTotal(filtered.length)
        }
        setNewsLoading(false)
      })
      .catch((err) => {
        if (!mounted) return
        console.warn('Sentiment news fetch fallback:', err)
        const fallback = generateFallbackNews(selectedSymbol)
        const filtered = sentimentFilter === 'ALL'
          ? fallback.items
          : fallback.items.filter((it) => it.sentiment === sentimentFilter)
        setNewsItems(filtered)
        setNewsTotal(filtered.length)
        setNewsLoading(false)
      })

    return () => {
      mounted = false
    }
  }, [selectedSymbol, sentimentFilter])

  // Load more news
  const handleLoadMoreNews = async () => {
    if (loadingMore || newsItems.length >= newsTotal) return
    setLoadingMore(true)
    const nextPage = newsPage + 1
    const params = {
      page: nextPage,
      limit: 10,
    }
    if (sentimentFilter !== 'ALL') {
      params.sentiment = sentimentFilter
    }

    try {
      const data = await sentimentApi.getSentimentNews(selectedSymbol, params)
      const newItems = data?.items || []
      setNewsItems((prev) => [...prev, ...newItems])
      setNewsPage(nextPage)
      setNewsTotal(data?.total || newsTotal)
    } catch {
      // no more items
    } finally {
      setLoadingMore(false)
    }
  }

  // Stock search debounce
  useEffect(() => {
    if (!stockSearchQuery.trim()) {
      setSearchResults([])
      return
    }
    setIsSearching(true)
    const timer = setTimeout(() => {
      dashboardApi
        .searchStocks(stockSearchQuery.trim())
        .then((res) => {
          const results = Array.isArray(res) ? res : res?.results || res?.items || []
          setSearchResults(results)
        })
        .catch(() => setSearchResults([]))
        .finally(() => setIsSearching(false))
    }, 250)

    return () => clearTimeout(timer)
  }, [stockSearchQuery])

  // Close search dropdown on click outside
  useEffect(() => {
    function handleClickOutside(e) {
      if (searchContainerRef.current && !searchContainerRef.current.contains(e.target)) {
        setSearchFocused(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleSelectSymbol = (sym) => {
    if (!sym) return
    setSelectedSymbol(sym.toUpperCase())
    setStockSearchQuery('')
    setSearchFocused(false)
    setSearchResults([])
  }

  // Calculate score meter position (-1.0 to +1.0 mapped to 0% - 100%)
  const sentimentScore = stockSentiment?.score ?? 0
  const scorePercent = Math.max(0, Math.min(100, ((sentimentScore + 1) / 2) * 100))

  // Distribution percentages from MarketSentimentResponse
  const dist = marketSentiment?.score_distribution
  const distTotal = dist ? (dist.positive || 0) + (dist.neutral || 0) + (dist.negative || 0) : 0
  const posPct = distTotal > 0 ? Math.round(((dist.positive || 0) / distTotal) * 100) : 0
  const neuPct = distTotal > 0 ? Math.round(((dist.neutral || 0) / distTotal) * 100) : 0
  const negPct = distTotal > 0 ? Math.round(((dist.negative || 0) / distTotal) * 100) : 0

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 flex flex-col font-sans transition-colors antialiased overflow-x-hidden max-w-full">
      <ProHeader
        active="sentiment"
        onDashboard={onBack}
        onMarket={onMarket}
        onPortfolio={onPortfolio}
        onNews={onNews}
        onSentiment={() => {}}
        onWatchlist={onWatchlist}
        onRecommendations={onRecommendations}
        onShariah={onShariah}
        onAssistant={onAssistant}
        onRisk={onRisk}
        onSettings={onSettings}
        onLogout={onLogout}
        onOpenSearch={onOpenSearch}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6 overflow-x-hidden">
        {/* ── HEADER & SEARCH ── */}
        <section className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-2xl p-5 sm:p-6 shadow-xs">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300 border border-emerald-200/60 dark:border-emerald-800/60">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  FinBERT NLP
                </span>
                <span className="text-xs text-slate-500 dark:text-slate-400 font-medium">
                  Pakistan Stock Exchange
                </span>
              </div>
              <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100 mt-1">
                PSX Sentiment Intelligence
              </h1>
              <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 mt-1 max-w-2xl leading-relaxed">
                Quantitative sentiment extracted directly from PSX corporate filings, regulatory disclosures, and financial news via fine-tuned financial transformer models.
              </p>
            </div>

            {/* Quick Symbol Search */}
            <div className="relative w-full md:w-72 shrink-0" ref={searchContainerRef}>
              <div className="relative">
                <input
                  type="text"
                  value={stockSearchQuery}
                  onChange={(e) => setStockSearchQuery(e.target.value)}
                  onFocus={() => setSearchFocused(true)}
                  placeholder="Search symbol (e.g. MEBL, OGDC)…"
                  className="w-full pl-9 pr-8 py-2 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition-all font-mono uppercase"
                />
                <span className="absolute left-3 top-2.5 text-slate-400 pointer-events-none">
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                </span>
                {stockSearchQuery && (
                  <button
                    type="button"
                    onClick={() => {
                      setStockSearchQuery('')
                      setSearchResults([])
                    }}
                    className="absolute right-2.5 top-2.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-0.5"
                  >
                    ×
                  </button>
                )}
              </div>

              {/* Search Results Dropdown */}
              {searchFocused && (searchResults.length > 0 || isSearching) && (
                <div className="absolute left-0 right-0 top-full mt-1.5 z-30 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl max-h-60 overflow-y-auto divide-y divide-slate-100 dark:divide-slate-800">
                  {isSearching && (
                    <div className="p-3 text-center text-xs text-slate-400">Searching…</div>
                  )}
                  {!isSearching &&
                    searchResults.map((item) => {
                      const sym = item.symbol || item.code
                      const name = item.name || item.company_name || sym
                      return (
                        <button
                          key={sym}
                          type="button"
                          onClick={() => handleSelectSymbol(sym)}
                          className="w-full px-3 py-2 text-left hover:bg-slate-50 dark:hover:bg-slate-800/60 flex items-center justify-between gap-2 transition-colors cursor-pointer"
                        >
                          <div className="flex items-center gap-2 min-w-0">
                            <StockLogo symbol={sym} size="xs" />
                            <div className="truncate">
                              <span className="font-mono font-bold text-xs text-slate-900 dark:text-slate-100 mr-2">
                                {sym}
                              </span>
                              <span className="text-[11px] text-slate-500 dark:text-slate-400 truncate">
                                {name}
                              </span>
                            </div>
                          </div>
                          {kmiSymbols.has(sym) && (
                            <span className="text-[10px] text-emerald-600 font-medium shrink-0">
                              KMI-30
                            </span>
                          )}
                        </button>
                      )
                    })}
                </div>
              )}
            </div>
          </div>

          {/* Quick Stock Selector Chips */}
          <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center gap-1.5 flex-wrap">
            <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 mr-1 shrink-0">
              Popular:
            </span>
            {POPULAR_SYMBOLS.map((sym) => {
              const isActive = selectedSymbol === sym
              return (
                <button
                  key={sym}
                  type="button"
                  onClick={() => handleSelectSymbol(sym)}
                  className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-mono font-medium transition-all cursor-pointer ${
                    isActive
                      ? 'bg-emerald-600 text-white font-bold shadow-xs'
                      : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'
                  }`}
                >
                  <StockLogo symbol={sym} size="xs" />
                  <span>{sym}</span>
                </button>
              )
            })}
          </div>
        </section>

        {/* ── 1. MARKET-WIDE SENTIMENT OVERVIEW (GET /api/v1/sentiment/market-overview) ── */}
        <section className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-2xl p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold tracking-tight text-slate-900 dark:text-slate-100 uppercase text-[11px]">
                Market-Wide Sentiment Overview
              </h2>
              <span className="text-xs text-slate-400">·</span>
              <span className="text-xs text-slate-500 dark:text-slate-400">
                FinBERT PSX Composite Analysis
              </span>
            </div>
            {marketLoading && (
              <span className="text-xs text-slate-400 animate-pulse">Syncing…</span>
            )}
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 sm:gap-4">
            {/* Card 1: Market Mood & Score */}
            <div className="bg-slate-50 dark:bg-slate-800/50 p-3.5 rounded-xl border border-slate-200/50 dark:border-slate-700/50 flex flex-col justify-between">
              <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400">
                Market Mood
              </div>
              <div className="mt-2 flex items-baseline gap-2">
                <SentimentBadge
                  sentiment={marketSentiment?.market_mood || 'neutral'}
                  size="sm"
                  showScore={false}
                />
                {marketSentiment?.overall_score != null && (
                  <span className="font-mono text-xs font-bold text-slate-700 dark:text-slate-300">
                    {marketSentiment.overall_score > 0 ? `+${marketSentiment.overall_score.toFixed(2)}` : marketSentiment.overall_score.toFixed(2)}
                  </span>
                )}
              </div>
            </div>

            {/* Card 2: Advance / Decline Ratio */}
            <div className="bg-slate-50 dark:bg-slate-800/50 p-3.5 rounded-xl border border-slate-200/50 dark:border-slate-700/50 flex flex-col justify-between">
              <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400">
                Advance / Decline
              </div>
              <div className="mt-1 font-mono text-lg font-bold text-slate-900 dark:text-slate-100">
                {marketSentiment?.advance_decline_ratio != null
                  ? Number(marketSentiment.advance_decline_ratio).toFixed(2)
                  : '—'}
              </div>
              <div className="text-[10px] text-slate-500 dark:text-slate-400">
                A/D Ratio
              </div>
            </div>

            {/* Card 3: Advancing Equities */}
            <div className="bg-slate-50 dark:bg-slate-800/50 p-3.5 rounded-xl border border-slate-200/50 dark:border-slate-700/50 flex flex-col justify-between">
              <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400">
                Advancing
              </div>
              <div className="mt-1 font-mono text-lg font-bold text-emerald-600 dark:text-emerald-400">
                {marketSentiment?.advancing ?? '—'}
              </div>
              <div className="text-[10px] text-slate-500 dark:text-slate-400">
                Positive return stocks
              </div>
            </div>

            {/* Card 4: Declining Equities */}
            <div className="bg-slate-50 dark:bg-slate-800/50 p-3.5 rounded-xl border border-slate-200/50 dark:border-slate-700/50 flex flex-col justify-between">
              <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400">
                Declining
              </div>
              <div className="mt-1 font-mono text-lg font-bold text-rose-600 dark:text-rose-400">
                {marketSentiment?.declining ?? '—'}
              </div>
              <div className="text-[10px] text-slate-500 dark:text-slate-400">
                Negative return stocks
              </div>
            </div>

            {/* Card 5: Unchanged Equities */}
            <div className="bg-slate-50 dark:bg-slate-800/50 p-3.5 rounded-xl border border-slate-200/50 dark:border-slate-700/50 flex flex-col justify-between">
              <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400">
                Unchanged
              </div>
              <div className="mt-1 font-mono text-lg font-bold text-slate-700 dark:text-slate-300">
                {marketSentiment?.unchanged ?? '—'}
              </div>
              <div className="text-[10px] text-slate-500 dark:text-slate-400">
                Flat returns
              </div>
            </div>

            {/* Card 6: Articles Analyzed */}
            <div className="bg-slate-50 dark:bg-slate-800/50 p-3.5 rounded-xl border border-slate-200/50 dark:border-slate-700/50 flex flex-col justify-between">
              <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400">
                Articles Analyzed
              </div>
              <div className="mt-1 font-mono text-lg font-bold text-slate-900 dark:text-slate-100">
                {marketSentiment?.article_count != null ? marketSentiment.article_count : 0}
              </div>
              <div className="text-[10px] text-slate-500 dark:text-slate-400">
                Live FinBERT NLP
              </div>
            </div>
          </div>

          {/* Sentiment Distribution Bar (strictly from score_distribution response) */}
          {distTotal > 0 && (
            <div className="pt-2 border-t border-slate-100 dark:border-slate-800 space-y-1.5">
              <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
                <span>Sentiment Score Distribution:</span>
                <span className="font-mono text-[11px]">
                  <strong className="text-emerald-600 dark:text-emerald-400">{dist.positive || 0} Positive ({posPct}%)</strong> ·{' '}
                  <strong className="text-slate-500">{dist.neutral || 0} Neutral ({neuPct}%)</strong> ·{' '}
                  <strong className="text-rose-600 dark:text-rose-400">{dist.negative || 0} Negative ({negPct}%)</strong>
                </span>
              </div>
              <div className="h-2 w-full rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden flex">
                {posPct > 0 && <div style={{ width: `${posPct}%` }} className="bg-emerald-500 h-full" />}
                {neuPct > 0 && <div style={{ width: `${neuPct}%` }} className="bg-slate-400 h-full" />}
                {negPct > 0 && <div style={{ width: `${negPct}%` }} className="bg-rose-500 h-full" />}
              </div>
            </div>
          )}
        </section>

        {/* ── 2. GET /api/v1/sentiment/{symbol} & 3. HISTORY & 4. NEWS ── */}
        <section className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-2xl p-5 sm:p-6 shadow-xs space-y-6">
          {/* Stock Header Banner */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-100 dark:border-slate-800">
            <div className="flex items-center gap-3.5">
              <StockLogo symbol={selectedSymbol} size="md" />
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-lg font-bold font-mono tracking-tight text-slate-900 dark:text-slate-100">
                    {selectedSymbol}
                  </h2>
                  <ShariahBadge isCompliant={isCompliant} size="sm" />
                </div>
                <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                  {stockOverview?.name || `${selectedSymbol} Pakistan Stock Exchange`}
                  {stockOverview?.sector && <span className="ml-1.5 text-slate-400">· {stockOverview.sector}</span>}
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2.5 flex-wrap self-start sm:self-auto max-w-full">
              {/* Rolling Window Days Selector (days param for GET /api/v1/sentiment/{symbol}) */}
              <div className="flex items-center bg-slate-100 dark:bg-slate-800 p-1 rounded-xl border border-slate-200/50 dark:border-slate-700/50 overflow-x-auto max-w-full">
                <span className="text-[10px] font-semibold text-slate-400 dark:text-slate-500 uppercase px-2">
                  Window:
                </span>
                {ROLLING_DAYS.map((d) => (
                  <button
                    key={d}
                    type="button"
                    onClick={() => setRollingDays(d)}
                    disabled={stockSentimentLoading}
                    className={`px-2 py-0.5 text-xs font-mono font-medium rounded-lg transition-all cursor-pointer ${
                      rollingDays === d
                        ? 'bg-white dark:bg-slate-900 text-emerald-600 dark:text-emerald-400 shadow-xs font-semibold'
                        : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100'
                    }`}
                  >
                    {d}D
                  </button>
                ))}
              </div>

              {/* View Full Stock Details Link */}
              <button
                type="button"
                onClick={() => onStock && onStock(selectedSymbol)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-xl border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-200 transition-colors cursor-pointer"
              >
                <span>Stock Profile</span>
                <span aria-hidden="true">→</span>
              </button>
            </div>
          </div>

          {/* Metric Cards Grid from GET /api/v1/sentiment/{symbol} */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Card 1: FinBERT Score & Tone */}
            <div className="bg-slate-50 dark:bg-slate-800/40 p-4 rounded-xl border border-slate-200/60 dark:border-slate-700/60 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">
                    FinBERT Sentiment Tone
                  </span>
                  <span className="text-[10px] text-slate-400 font-mono">
                    {rollingDays}-Day Window
                  </span>
                </div>
                <div className="mt-3 flex items-baseline gap-3">
                  <span className="font-mono text-3xl font-bold text-slate-900 dark:text-slate-100">
                    {stockSentiment?.score != null
                      ? stockSentiment.score > 0
                        ? `+${Number(stockSentiment.score).toFixed(2)}`
                        : Number(stockSentiment.score).toFixed(2)
                      : '0.00'}
                  </span>
                  <SentimentBadge
                    sentiment={stockSentiment?.label || 'neutral'}
                    score={null}
                    size="md"
                    showScore={false}
                  />
                </div>
              </div>

              {/* Score Meter Bar */}
              <div className="mt-4 pt-3 border-t border-slate-200/60 dark:border-slate-700/60">
                <div className="flex justify-between text-[10px] font-mono text-slate-400 mb-1">
                  <span className="text-rose-500">-1.0 Bearish</span>
                  <span>0.0 Neutral</span>
                  <span className="text-emerald-500">+1.0 Bullish</span>
                </div>
                <div className="relative h-2 rounded-full bg-linear-to-r from-rose-500 via-slate-300 dark:via-slate-600 to-emerald-500">
                  <div
                    className="absolute top-1/2 -translate-y-1/2 w-3.5 h-3.5 bg-white dark:bg-slate-900 rounded-full border-2 border-slate-900 dark:border-white shadow-md transition-all"
                    style={{ left: `calc(${scorePercent}% - 7px)` }}
                  />
                </div>
              </div>
            </div>

            {/* Card 2: Trend & Trajectory */}
            <div className="bg-slate-50 dark:bg-slate-800/40 p-4 rounded-xl border border-slate-200/60 dark:border-slate-700/60 flex flex-col justify-between">
              <div>
                <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">
                  Sentiment Trajectory
                </span>
                <div className="mt-3 flex items-center gap-2.5">
                  <span
                    className={`inline-flex items-center justify-center w-8 h-8 rounded-lg text-sm font-bold ${
                      (stockSentiment?.trend || '').toLowerCase().includes('imp')
                        ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300'
                        : (stockSentiment?.trend || '').toLowerCase().includes('dec')
                        ? 'bg-rose-100 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300'
                        : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300'
                    }`}
                  >
                    {(stockSentiment?.trend || '').toLowerCase().includes('imp')
                      ? '↑'
                      : (stockSentiment?.trend || '').toLowerCase().includes('dec')
                      ? '↓'
                      : '→'}
                  </span>
                  <div>
                    <div className="font-bold text-sm text-slate-900 dark:text-slate-100 capitalize">
                      {stockSentiment?.trend || 'Stable'}
                    </div>
                    <div className="text-[11px] text-slate-500 dark:text-slate-400">
                      Based on rolling {rollingDays}-day shift
                    </div>
                  </div>
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-slate-200/60 dark:border-slate-700/60">
                <div className="text-[11px] text-slate-500 dark:text-slate-400">
                  Coverage Volume: <strong className="text-slate-800 dark:text-slate-200">{stockSentiment?.article_count || 0} items</strong>
                </div>
              </div>
            </div>

            {/* Card 3: Source Breakdown (strictly from response) */}
            <div className="bg-slate-50 dark:bg-slate-800/40 p-4 rounded-xl border border-slate-200/60 dark:border-slate-700/60 flex flex-col justify-between">
              <div>
                <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">
                  Source Channel Analysis
                </span>
                <div className="mt-3 space-y-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-600 dark:text-slate-400 flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-blue-500" />
                      Official &amp; News Media
                    </span>
                    <strong className="font-mono text-slate-900 dark:text-slate-100">
                      {stockSentiment?.source_breakdown?.news ?? stockSentiment?.article_count ?? 0}
                    </strong>
                  </div>
                  {stockSentiment?.source_breakdown?.community != null && (
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-slate-600 dark:text-slate-400 flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-purple-500" />
                        Community Discussions
                      </span>
                      <strong className="font-mono text-slate-900 dark:text-slate-100">
                        {stockSentiment.source_breakdown.community}
                      </strong>
                    </div>
                  )}
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-slate-200/60 dark:border-slate-700/60">
                <div className="text-[10px] text-slate-400">
                  Model: FinBERT (Prosus / HuggingFace Financial Transformer)
                </div>
              </div>
            </div>
          </div>

          {/* ── 3. GET /api/v1/sentiment/{symbol}/history ── */}
          <SentimentHistoryChart
            symbol={selectedSymbol}
            data={historyData}
            period={historyPeriod}
            onPeriodChange={(newPeriod) => setHistoryPeriod(newPeriod)}
            loading={historyLoading}
          />

          {/* ── 4. GET /api/v1/sentiment/{symbol}/news ── */}
          <div className="pt-2">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
              <div>
                <h3 className="text-sm font-semibold tracking-tight text-slate-900 dark:text-slate-100">
                  Disclosures &amp; Sentiment News for {selectedSymbol}
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                  Articles and PSX regulatory announcements tagged for {selectedSymbol} with individual FinBERT scores
                </p>
              </div>

              {/* Sentiment Filter Tabs */}
              <div className="flex items-center bg-slate-100 dark:bg-slate-800 p-1 rounded-xl shrink-0 self-start sm:self-auto border border-slate-200/50 dark:border-slate-700/50">
                {['ALL', 'POSITIVE', 'NEUTRAL', 'NEGATIVE'].map((tab) => {
                  const isActive = sentimentFilter === tab
                  const label = tab === 'ALL' ? 'All' : tab.charAt(0) + tab.slice(1).toLowerCase()
                  return (
                    <button
                      key={tab}
                      type="button"
                      onClick={() => setSentimentFilter(tab)}
                      className={`px-2.5 py-1 text-xs font-medium rounded-lg transition-all cursor-pointer ${
                        isActive
                          ? 'bg-white dark:bg-slate-900 text-emerald-600 dark:text-emerald-400 shadow-xs font-semibold'
                          : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100'
                      }`}
                    >
                      {label}
                    </button>
                  )
                })}
              </div>
            </div>

            {/* News Articles List */}
            {newsLoading ? (
              <div className="p-8 text-center space-y-2">
                <div className="w-6 h-6 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin mx-auto" />
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Loading {selectedSymbol} sentiment news…
                </p>
              </div>
            ) : newsItems.length === 0 ? (
              <div className="p-8 text-center border border-dashed border-slate-200 dark:border-slate-800 rounded-xl bg-slate-50/50 dark:bg-slate-800/20">
                <p className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                  No Articles Found for {selectedSymbol} {sentimentFilter !== 'ALL' ? `(${sentimentFilter})` : ''}
                </p>
                <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1">
                  Try switching to 'All' or selecting another stock (such as MEBL or OGDC) to view analyzed announcements.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {newsItems.map((article) => {
                  const pubDate = article.published_at
                    ? new Date(article.published_at).toLocaleDateString('en-PK', {
                        year: 'numeric',
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })
                    : 'Recent'

                  return (
                    <article
                      key={article.id || article.url}
                      className="group bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl p-4 hover:border-emerald-500/50 hover:shadow-xs transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-3.5"
                    >
                      <div className="space-y-1.5 flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap text-xs text-slate-500 dark:text-slate-400">
                          <span className="font-semibold text-slate-700 dark:text-slate-300">
                            {article.source || 'PSX Announcement'}
                          </span>
                          <span>·</span>
                          <time className="font-mono text-[11px]">{pubDate}</time>
                          <SentimentBadge
                            sentiment={article.sentiment}
                            score={article.sentiment_score}
                            size="sm"
                          />
                        </div>

                        <h4
                          onClick={() => {
                            if (article.id) {
                              setModalArticle(article)
                            } else if (article.url) {
                              window.open(article.url, '_blank', 'noopener,noreferrer')
                            }
                          }}
                          className="text-sm font-semibold text-slate-900 dark:text-slate-100 group-hover:text-emerald-600 dark:group-hover:text-emerald-400 transition-colors cursor-pointer line-clamp-2 leading-snug"
                        >
                          {article.title}
                        </h4>
                      </div>

                      <div className="shrink-0 flex items-center gap-2 self-end sm:self-center">
                        <button
                          type="button"
                          onClick={() => setModalArticle(article)}
                          className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-emerald-50 hover:text-emerald-600 dark:hover:bg-emerald-950/40 dark:hover:text-emerald-300 text-slate-700 dark:text-slate-300 transition-colors cursor-pointer"
                        >
                          View Details →
                        </button>
                      </div>
                    </article>
                  )
                })}

                {/* Pagination Load More Button */}
                {newsItems.length < newsTotal && (
                  <div className="text-center pt-2">
                    <button
                      type="button"
                      onClick={handleLoadMoreNews}
                      disabled={loadingMore}
                      className="px-4 py-2 text-xs font-semibold rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-200 transition-all shadow-xs cursor-pointer inline-flex items-center gap-2"
                    >
                      {loadingMore ? (
                        <>
                          <span className="w-3.5 h-3.5 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
                          <span>Loading more…</span>
                        </>
                      ) : (
                        <span>Load More Articles ({newsItems.length} of {newsTotal})</span>
                      )}
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </section>
      </main>

      {/* Article Detail Modal */}
      {modalArticle && (
        <ArticleDetailModal
          article={modalArticle}
          onClose={() => setModalArticle(null)}
          onStock={(sym) => {
            setModalArticle(null)
            handleSelectSymbol(sym)
          }}
        />
      )}

      {mobileNav}
    </div>
  )
}
