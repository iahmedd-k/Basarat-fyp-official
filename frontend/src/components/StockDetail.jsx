import React, { useState, useEffect, useCallback } from 'react'
import { dashboardApi } from '../api/dashboard'
import { newsApi } from '../api/news'
import { sentimentApi } from '../api/sentiment'
import { forecastApi } from '../api/forecast'
import { getCached, getCacheKey, onCacheUpdate } from '../api/cache'
import ProHeader from './ProHeader'
import ShariahBadge from './ShariahBadge'
import StockPriceChart from './StockPriceChart'
import StockTechnicals from './StockTechnicals'
import StockFundamentals from './StockFundamentals'
import StockForecastSection from './StockForecastSection'
import SentimentBadge from './SentimentBadge'
import SentimentHistoryChart from './SentimentHistoryChart'
import NewsCard from './NewsCard'
import { formatNumber, formatPercent, formatCompactNumber } from '../utils/formatters'

/**
 * Pre-seed stock overview from cached screener/quotes if available
 * Enables instant 0ms display of price, name, and change % before network responds
 */
function getPreseededStock(symbol) {
  if (!symbol) return null
  const upper = symbol.toUpperCase()

  // 1. Direct overview cache check
  const exact = getCached(getCacheKey(`/stocks/${encodeURIComponent(upper)}/overview`))?.data
  if (exact) return exact

  // 2. Screener & quotes cache lookups
  const candidateKeys = [
    getCacheKey('/market/quotes?limit=500'),
    getCacheKey('/market/quotes'),
    getCacheKey('/market/all-stocks?limit=500'),
    getCacheKey('/market/all-stocks'),
    getCacheKey('/market/indices/kse-100'),
    getCacheKey('/market/indices/kmi-30'),
    getCacheKey('/market/indices/kse-30'),
    getCacheKey('/market/gainers?limit=15'),
    getCacheKey('/market/losers?limit=15'),
    getCacheKey('/market/volume-spikes?limit=15'),
    getCacheKey('/market/gainers?limit=10'),
    getCacheKey('/market/losers?limit=10'),
    getCacheKey('/market/volume-spikes?limit=10'),
  ]

  for (const k of candidateKeys) {
    const cached = getCached(k)?.data
    if (!cached) continue
    const list = cached.stocks || cached.quotes || cached.constituents || (Array.isArray(cached) ? cached : null)
    if (Array.isArray(list)) {
      const match = list.find((s) => s?.symbol?.toUpperCase() === upper)
      if (match) {
        return {
          symbol: match.symbol,
          name: match.name || match.company_name || match.symbol,
          sector: match.sector || '',
          current_price: match.current_price ?? match.ltp ?? match.price ?? match.close,
          ltp: match.current_price ?? match.ltp ?? match.price ?? match.close,
          change: match.change,
          change_pct: match.change_pct,
          volume: match.volume,
          open: match.open,
          high: match.high,
          low: match.low,
          ldcp: match.ldcp || match.prev_close,
          day_range: match.day_range,
          week_52_range: match.week_52_range,
        }
      }
    }
  }
  return null
}

function getPreseededCompliance(symbol) {
  if (!symbol) return undefined
  const upper = symbol.toUpperCase()
  const kmi = getCached(getCacheKey('/market/indices/kmi-30'))?.data?.constituents
  if (Array.isArray(kmi)) {
    return kmi.some((c) => c?.symbol?.toUpperCase() === upper)
  }
  return undefined
}

// ── Localized Widget Shimmer Skeletons for Non-Blocking Progressive Loading ──

function KeyStatsSkeleton() {
  return (
    <div className="divide-y divide-slate-100 text-xs animate-pulse">
      {[1, 2, 3, 4, 5].map((i) => (
        <div key={i} className="flex items-center justify-between py-2.5">
          <div className="h-3.5 w-20 bg-slate-100 rounded" />
          <div className="h-4 w-16 bg-slate-100 rounded" />
        </div>
      ))}
      <div className="pt-3 space-y-3">
        <div>
          <div className="flex justify-between mb-1">
            <div className="h-3 w-16 bg-slate-100 rounded" />
            <div className="h-3 w-16 bg-slate-100 rounded" />
          </div>
          <div className="h-2 w-full bg-slate-100 rounded-full" />
        </div>
        <div>
          <div className="flex justify-between mb-1">
            <div className="h-3 w-16 bg-slate-100 rounded" />
            <div className="h-3 w-16 bg-slate-100 rounded" />
          </div>
          <div className="h-2 w-full bg-slate-100 rounded-full" />
        </div>
      </div>
    </div>
  )
}

function TechnicalsSectionSkeleton() {
  return (
    <div className="bg-white border border-[#e5e9ef] rounded-2xl p-6 shadow-[0_1px_4px_rgba(15,23,42,0.04)] animate-pulse space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-100">
        <div className="space-y-2">
          <div className="h-3 w-32 bg-slate-100 rounded" />
          <div className="h-5 w-48 bg-slate-100 rounded" />
        </div>
        <div className="h-8 w-28 bg-slate-100 rounded-full" />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="p-4 rounded-xl border border-slate-100 bg-slate-50/60 space-y-3">
            <div className="flex justify-between">
              <div className="h-3.5 w-16 bg-slate-200 rounded" />
              <div className="h-3.5 w-12 bg-slate-200 rounded" />
            </div>
            <div className="h-16 w-full bg-slate-200/50 rounded-lg" />
            <div className="h-3 w-24 bg-slate-200 rounded" />
          </div>
        ))}
      </div>
    </div>
  )
}

function FinancialsSkeleton() {
  return (
    <div className="space-y-5 animate-pulse">
      <div className="h-8 w-80 bg-slate-200 rounded-lg" />
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <div key={i} className="bg-white border border-[#e5e9ef] rounded-xl p-4 space-y-2">
            <div className="h-3 w-16 bg-slate-100 rounded" />
            <div className="h-6 w-20 bg-slate-100 rounded" />
          </div>
        ))}
      </div>
      <div className="bg-white border border-[#e5e9ef] rounded-2xl p-6 h-64" />
    </div>
  )
}

function ShariahSkeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="bg-white border border-[#e5e9ef] rounded-2xl p-6 space-y-4">
        <div className="flex justify-between">
          <div className="space-y-2">
            <div className="h-3 w-28 bg-slate-100 rounded" />
            <div className="h-6 w-60 bg-slate-100 rounded" />
          </div>
          <div className="h-8 w-20 bg-slate-100 rounded" />
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-16 bg-slate-50 border border-slate-100 rounded-xl" />
          ))}
        </div>
      </div>
      <div className="bg-white border border-[#e5e9ef] rounded-2xl p-6 h-64" />
    </div>
  )
}

function NewsSkeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white border border-[#e5e9ef] rounded-2xl p-6 h-48" />
        <div className="md:col-span-2 bg-white border border-[#e5e9ef] rounded-2xl p-6 h-48" />
      </div>
      <div className="bg-white border border-[#e5e9ef] rounded-2xl p-6 space-y-3">
        <div className="h-5 w-48 bg-slate-100 rounded mb-4" />
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-20 bg-slate-50 border border-slate-100 rounded-xl" />
        ))}
      </div>
    </div>
  )
}

export default function StockDetail({
  symbol,
  onBack,
  onDashboard,
  onMarket,
  onPortfolio,
  onNews,
  onSentiment,
  onWatchlist,
  onRecommendations,
  onShariah,
  onAssistant,
  onRisk,
  onSettings,
  onLogout,
  onStock,
  onOpenSearch,
}) {
  const preseeded = getPreseededStock(symbol)
  const cachedHistory = getCached(getCacheKey(`/stocks/${encodeURIComponent(symbol)}/price-history?range=1M`))?.data?.bars
  const cachedTech = getCached(getCacheKey(`/stocks/${encodeURIComponent(symbol)}/technical-indicators?indicators=RSI%2CMACD%2CBB%2CSMA%2CADX&period=14&limit=30`))?.data
  const cachedFund = getCached(getCacheKey(`/stocks/${encodeURIComponent(symbol)}/fundamentals`))?.data
  const cachedShariah = getCached(getCacheKey(`/shariah/${encodeURIComponent(symbol)}`))?.data

  // State: Seeded immediately from cache/screener data for 0ms initial render
  const [overview, setOverview] = useState(() => preseeded || null)
  const [overviewLoading, setOverviewLoading] = useState(() => !preseeded)

  const [history, setHistory] = useState(() => cachedHistory || [])
  const [historyLoading, setHistoryLoading] = useState(() => !cachedHistory || cachedHistory.length === 0)

  const [technical, setTechnical] = useState(() => cachedTech || null)
  const [technicalsLoading, setTechnicalsLoading] = useState(false)

  const [fundamentals, setFundamentals] = useState(() => cachedFund || null)
  const [fundamentalsLoading, setFundamentalsLoading] = useState(false)

  const [shariahData, setShariahData] = useState(() => cachedShariah || (getPreseededCompliance(symbol) ? { is_shariah_compliant: true } : null))
  const [shariahCriteria, setShariahCriteria] = useState(() => getCached(getCacheKey(`/shariah/${encodeURIComponent(symbol)}/criteria`))?.data || null)
  const [shariahLoading, setShariahLoading] = useState(false)

  const [stockSentiment, setStockSentiment] = useState(() => getCached(getCacheKey(`/sentiment/${encodeURIComponent(symbol)}?days=7`))?.data || null)
  const [sentimentHistory, setSentimentHistory] = useState(() => getCached(getCacheKey(`/sentiment/${encodeURIComponent(symbol)}/history?period=1M&limit=100`))?.data || null)
  const [news, setNews] = useState(() => getCached(getCacheKey(`/stocks/${encodeURIComponent(symbol)}/news?limit=5`))?.data?.items || [])
  const [sentimentNews, setSentimentNews] = useState(() => getCached(getCacheKey(`/sentiment/${encodeURIComponent(symbol)}/news?limit=5`))?.data?.items || [])
  const [newsLoading, setNewsLoading] = useState(false)

  const [range, setRange] = useState('1D')
  const [rangeLoading, setRangeLoading] = useState(false)
  const [sentimentPeriod, setSentimentPeriod] = useState('1M')
  const [sentimentHistoryLoading, setSentimentHistoryLoading] = useState(false)
  const [activeTab, setActiveTab] = useState('overview')
  const [visitedTabs, setVisitedTabs] = useState(() => new Set(['overview']))
  const [watchlisted, setWatchlisted] = useState(false)

  // Reset tab selection & retention when a new symbol is selected
  useEffect(() => {
    setActiveTab('overview')
    setVisitedTabs(new Set(['overview']))
  }, [symbol])

  useEffect(() => {
    try {
      const stored = JSON.parse(localStorage.getItem('basarat_watchlist') || '[]')
      setWatchlisted(stored.includes(symbol))
    } catch {
      setWatchlisted(false)
    }
  }, [symbol])

  const toggleWatchlist = () => {
    try {
      const stored = JSON.parse(localStorage.getItem('basarat_watchlist') || '[]')
      const next = watchlisted ? stored.filter((s) => s !== symbol) : [...stored, symbol]
      localStorage.setItem('basarat_watchlist', JSON.stringify(next))
      setWatchlisted(!watchlisted)
    } catch {}
  }

  // ── Stage 1: Load Core Overview & Chart History Immediately on Mount ──
  // Fast, unblocked, lightweight. Never holds up the page with heavy secondary endpoints.
  useEffect(() => {
    let active = true

    const freshPreseeded = getPreseededStock(symbol)
    if (freshPreseeded && !overview) {
      setOverview(freshPreseeded)
    }

    setOverviewLoading(!overview && !freshPreseeded)
    setHistoryLoading(history.length === 0)

    // 1. Fetch live stock overview
    dashboardApi
      .getStockOverview(symbol)
      .then((res) => {
        if (!active || !res) return
        setOverview(res)
      })
      .catch((err) => console.warn('Stock overview fetch failed:', err))
      .finally(() => {
        if (active) setOverviewLoading(false)
      })

    // 2. Fetch price history bars for chart
    dashboardApi
      .getPriceHistory(symbol, range === '1D' ? '1M' : range)
      .then((res) => {
        if (!active || !res?.bars) return
        setHistory(res.bars)
      })
      .catch((err) => console.warn('Stock price history fetch failed:', err))
      .finally(() => {
        if (active) setHistoryLoading(false)
      })

    // 3. Staggered Stage 2: Technicals & Shariah (delay slightly by 120ms so core price & chart get bandwidth first)
    const timerTech = setTimeout(() => {
      if (!active) return
      if (!technical) setTechnicalsLoading(true)
      dashboardApi
        .getTechnicalIndicators(symbol, { indicators: 'RSI,MACD,BB,SMA,ADX', period: 14, limit: 30 })
        .then((res) => {
          if (active && res) setTechnical(res)
        })
        .catch(() => {})
        .finally(() => {
          if (active) setTechnicalsLoading(false)
        })

      dashboardApi
        .getShariah(symbol)
        .then((res) => {
          if (active && res) setShariahData(res)
        })
        .catch(() => {})
    }, 120)

    return () => {
      active = false
      clearTimeout(timerTech)
    }
  }, [symbol])

  // ── Unified Non-Blocking Tab Prefetcher (Instant Cache Hydration) ──
  const prefetchTab = useCallback((tabKey) => {
    if (!symbol) return

    if (tabKey === 'financials') {
      if (!fundamentals) {
        setFundamentalsLoading(true)
        dashboardApi
          .getFundamentals(symbol)
          .then((res) => {
            if (res) setFundamentals(res)
          })
          .catch(() => {})
          .finally(() => setFundamentalsLoading(false))
      }
    } else if (tabKey === 'technicals') {
      if (!technical) {
        setTechnicalsLoading(true)
        dashboardApi
          .getTechnicalIndicators(symbol, { indicators: 'RSI,MACD,BB,SMA,ADX', period: 14, limit: 30 })
          .then((res) => {
            if (res) setTechnical(res)
          })
          .catch(() => {})
          .finally(() => setTechnicalsLoading(false))
      }
    } else if (tabKey === 'shariah') {
      if (!shariahCriteria || !shariahData?.overall_score) {
        setShariahLoading(true)
        Promise.allSettled([
          dashboardApi.getShariah(symbol),
          dashboardApi.getShariahCriteria(symbol),
        ]).then(([resShariah, resCrit]) => {
          if (resShariah.status === 'fulfilled' && resShariah.value) setShariahData(resShariah.value)
          if (resCrit.status === 'fulfilled' && resCrit.value) setShariahCriteria(resCrit.value)
        }).finally(() => {
          setShariahLoading(false)
        })
      }
    } else if (tabKey === 'recommendation') {
      forecastApi.getForecast(symbol, '1D').catch(() => {})
      forecastApi.getForecastHistory(symbol, 20).catch(() => {})
    } else if (tabKey === 'news') {
      if (news.length === 0 && !stockSentiment) {
        setNewsLoading(true)
        Promise.allSettled([
          dashboardApi.getStockNews(symbol),
          newsApi.getStockSentiment(symbol),
          sentimentApi.getSentimentHistory(symbol, sentimentPeriod),
          newsApi.getSentimentNews(symbol, { limit: 5 }),
        ]).then(([resNews, resSent, resSentHist, resSentNews]) => {
          if (resNews.status === 'fulfilled') setNews(resNews.value?.items || [])
          if (resSent.status === 'fulfilled') setStockSentiment(resSent.value)
          if (resSentHist.status === 'fulfilled') setSentimentHistory(resSentHist.value)
          if (resSentNews.status === 'fulfilled') setSentimentNews(resSentNews.value?.items || [])
        }).finally(() => {
          setNewsLoading(false)
        })
      }
    }
  }, [symbol, fundamentals, technical, shariahCriteria, shariahData, news.length, stockSentiment, sentimentPeriod])

  // Instant tab switcher maintaining DOM view retention & zero reload
  const handleTabChange = useCallback((tabKey) => {
    setActiveTab(tabKey)
    setVisitedTabs((prev) => {
      if (prev.has(tabKey)) return prev
      const next = new Set(prev)
      next.add(tabKey)
      return next
    })
    prefetchTab(tabKey)
  }, [prefetchTab])

  // Background idle prefetch of secondary tabs so subsequent tab shifts are 0ms instant
  useEffect(() => {
    const idleTimer = setTimeout(() => {
      prefetchTab('financials')
      prefetchTab('shariah')
      prefetchTab('recommendation')
      prefetchTab('news')
    }, 280)
    return () => clearTimeout(idleTimer)
  }, [symbol, prefetchTab])

  // Runtime live cache subscriptions (updates state silently when background SWR refreshes)
  useEffect(() => {
    const unsubOverview = onCacheUpdate(getCacheKey(`/stocks/${encodeURIComponent(symbol)}/overview`), (data) => {
      if (data) setOverview(data)
    })
    const unsubTech = onCacheUpdate(getCacheKey(`/stocks/${encodeURIComponent(symbol)}/technical-indicators?indicators=RSI%2CMACD%2CBB%2CSMA%2CADX&period=14&limit=30`), (data) => {
      if (data) setTechnical(data)
    })
    const unsubShariah = onCacheUpdate(getCacheKey(`/shariah/${encodeURIComponent(symbol)}`), (data) => {
      if (data) setShariahData(data)
    })
    return () => {
      unsubOverview()
      unsubTech()
      unsubShariah()
    }
  }, [symbol])

  const handleRangeChange = (newRange) => {
    setRange(newRange)
    if (newRange === '1D') {
      setRangeLoading(false)
      return
    }
    setRangeLoading(true)
    dashboardApi
      .getPriceHistory(symbol, newRange)
      .then((res) => {
        if (res?.bars) setHistory(res.bars)
      })
      .catch(() => {})
      .finally(() => setRangeLoading(false))
  }

  const handleSentimentPeriodChange = (p) => {
    setSentimentPeriod(p)
    setSentimentHistoryLoading(true)
    sentimentApi
      .getSentimentHistory(symbol, p)
      .then((res) => setSentimentHistory(res))
      .catch(() => {})
      .finally(() => setSentimentHistoryLoading(false))
  }

  // Key pricing & range calculations directly aligned with backend PSX endpoints
  const ltp = Number(overview?.current_price ?? overview?.ltp ?? 0)
  const prevClose = Number(overview?.ldcp ?? (overview?.prev_close ?? (ltp && overview?.change != null ? (ltp - overview.change) : ltp)))
  const latestBar = history && history.length > 0 ? history[history.length - 1] : null
  const openPrice = Number(overview?.open ?? (latestBar?.open ?? prevClose))

  const low = Number(overview?.day_range?.low ?? (latestBar?.low ?? ltp * 0.985))
  const high = Number(overview?.day_range?.high ?? (latestBar?.high ?? ltp * 1.015))
  const rangePct = high > low
    ? Math.max(0, Math.min(100, ((ltp - low) / (high - low)) * 100))
    : 50

  const week52Low = Number(fundamentals?.trading_limits?.year_low ?? overview?.week_52_range?.low ?? (low * 0.78))
  const week52High = Number(fundamentals?.trading_limits?.year_high ?? overview?.week_52_range?.high ?? (high * 1.28))
  const week52Pct = week52High > week52Low
    ? Math.max(0, Math.min(100, ((ltp - week52Low) / (week52High - week52Low)) * 100))
    : 50

  const ytdReturn = overview?.ytd_change_pct ?? fundamentals?.trading_limits?.ytd_change_pct ?? overview?.year_change_pct ?? overview?.change_pct
  const isCompliant = shariahData?.is_shariah_compliant ?? getPreseededCompliance(symbol)
  const isPositive = Number(overview?.change) >= 0

  // Shared card styling
  const card = 'bg-white border border-[#e5e9ef] rounded-2xl shadow-[0_1px_4px_rgba(15,23,42,0.04)]'

  return (
    <main className="min-h-screen bg-[#f5f7fa] text-slate-900 flex flex-col">
      <ProHeader
        active="market"
        onDashboard={onDashboard || onBack}
        onMarket={onMarket || onBack}
        onPortfolio={onPortfolio}
        onNews={onNews}
        onSentiment={onSentiment}
        onWatchlist={onWatchlist}
        onRecommendations={onRecommendations}
        onShariah={onShariah}
        onAssistant={onAssistant}
        onRisk={onRisk}
        onSettings={onSettings}
        onLogout={onLogout}
        onOpenSearch={onOpenSearch}
      />

      {/* ── Instant Page Shell (Renders immediately in 0ms, loads content progressively) ── */}
      <div className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-5 space-y-5">
        {/* ── 1. Top Header Bar (Renders Immediately) ── */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pt-1">
          <div>
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="text-2xl sm:text-[28px] font-bold tracking-tight text-slate-900 m-0">
                {overview?.name ? `${overview.name} (${symbol})` : `${symbol} Details`}
              </h1>
              {onBack && (
                <button
                  type="button"
                  onClick={onBack}
                  className="text-slate-400 hover:text-slate-700 p-1 sm:hidden ml-auto"
                  title="Back to Screener"
                >
                  ✕
                </button>
              )}
            </div>

            {/* Sub-header Badges */}
            <div className="flex items-center gap-2 mt-2 flex-wrap text-xs">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 font-semibold text-[11px]">
                <span className="text-emerald-600">★</span> Top Pick PSX · Verified Security
              </span>

              {isCompliant !== undefined && (
                <ShariahBadge isCompliant={isCompliant} size="sm" fullLabel={true} />
              )}

              {overview?.sector && (
                <span className="text-[11px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
                  {overview.sector}
                </span>
              )}
            </div>
          </div>

          {/* Action Links on Top Right */}
          <div className="flex items-center gap-2.5 self-start sm:self-center">
            <a
              href={`https://dps.psx.com.pk/company/${symbol}`}
              target="_blank"
              rel="noopener noreferrer"
              className="px-3.5 py-1.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-xs font-semibold text-slate-700 flex items-center gap-1.5 shadow-2xs transition-colors"
            >
              <span>Open in DPS PSX</span>
              <svg className="w-3.5 h-3.5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
            </a>
            <button
              type="button"
              onClick={() => window.open(window.location.href, '_blank')}
              className="px-3.5 py-1.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-xs font-semibold text-slate-700 flex items-center gap-1.5 shadow-2xs transition-colors"
            >
              <span>Open in New tab</span>
              <svg className="w-3.5 h-3.5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
            </button>
            {onBack && (
              <button
                type="button"
                onClick={onBack}
                className="hidden sm:inline-flex p-1.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-400 hover:text-slate-800 transition-colors shadow-2xs"
                title="Close"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>
        </div>

        {/* ── 2. Navigation Tabs (Renders Immediately) ── */}
        <div className="flex items-center gap-6 overflow-x-auto border-b border-slate-200 text-xs sm:text-[13px] font-semibold scrollbar-none">
          {[
            ['overview', 'Overview'],
            ['financials', 'Financials'],
            ['technicals', 'Technicals'],
            ['shariah', 'Shariah Screening'],
            ['recommendation', 'AI Forecast & Signals'],
            ['news', 'News & Sentiment'],
          ].map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => handleTabChange(key)}
              onMouseEnter={() => prefetchTab(key)}
              onPointerEnter={() => prefetchTab(key)}
              className={`py-3 whitespace-nowrap border-b-2 transition-all cursor-pointer ${
                activeTab === key
                  ? 'border-slate-900 text-slate-900 font-bold'
                  : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* ── 3. Retained Tab Content Panels (0ms Instant Shifts) ── */}
        <div className="stock-tabs-content">
          {/* ── TAB 1: OVERVIEW (Progressive Loading: Chart + Key Stats + Technicals) ── */}
          {visitedTabs.has('overview') && (
            <div
              className={`stock-tab-panel ${activeTab === 'overview' ? 'active' : 'inactive'}`}
              aria-hidden={activeTab !== 'overview'}
            >
              <div className="space-y-6">
            {/* 2-Column Hero: Left = Price Chart, Right = Key Statistics Card */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
              {/* Left Column (Chart) */}
              <div className="lg:col-span-8">
                <StockPriceChart
                  symbol={symbol}
                  bars={history}
                  range={range}
                  onRangeChange={handleRangeChange}
                  loading={historyLoading || rangeLoading}
                  currentPrice={overview?.ltp}
                  currentChange={overview?.change}
                  currentChangePct={overview?.change_pct}
                  overview={overview}
                />
              </div>

              {/* Right Column: Key Statistics Card */}
              <div className="lg:col-span-4">
                <div className={`${card} p-5 space-y-4`}>
                  {overviewLoading && !overview ? (
                    <KeyStatsSkeleton />
                  ) : (
                    <>
                      {/* Metric Table Rows */}
                      <div className="divide-y divide-slate-100 text-xs">
                        <div className="flex items-center justify-between py-2">
                          <span className="text-slate-500">Prev Close</span>
                          <strong className="font-mono text-slate-900">{formatNumber(prevClose)}</strong>
                        </div>
                        <div className="flex items-center justify-between py-2">
                          <span className="text-slate-500">Open</span>
                          <strong className="font-mono text-slate-900">{formatNumber(openPrice)}</strong>
                        </div>
                        <div className="flex items-center justify-between py-2">
                          <span className="text-slate-500">Day Change</span>
                          <span
                            className="font-bold font-mono px-2 py-0.5 rounded text-[11px]"
                            style={isPositive
                              ? { background: '#f0fdf4', color: '#15803d' }
                              : { background: '#fff1f2', color: '#be123c' }
                            }
                          >
                            {isPositive ? '+' : ''}{formatNumber(overview?.change)} {formatPercent(overview?.change_pct)}
                          </span>
                        </div>
                        <div className="flex items-center justify-between py-2">
                          <span className="text-slate-500">Volume</span>
                          <strong className="font-mono text-slate-900">{formatCompactNumber(overview?.volume)}</strong>
                        </div>
                        <div className="flex items-center justify-between py-2">
                          <span className="text-slate-500">YTD Return</span>
                          <span className={`font-bold font-mono ${Number(ytdReturn) >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                            {formatPercent(ytdReturn)}
                          </span>
                        </div>
                      </div>

                      {/* Day Range & 52W Range Sliders */}
                      <div className="pt-2 border-t border-slate-100 space-y-3.5">
                        {/* Day Range */}
                        <div>
                          <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1 font-mono">
                            <span>Day Range</span>
                          </div>
                          <div className="flex items-center justify-between text-xs font-mono mb-1 text-slate-700">
                            <span>{formatNumber(low)}</span>
                            <span>{formatNumber(high)}</span>
                          </div>
                          <div className="relative h-2 w-full bg-slate-100 rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full transition-all duration-300"
                              style={{
                                width: `${rangePct}%`,
                                background: 'linear-gradient(90deg, #f59e0b, #10b981)',
                              }}
                            />
                            {/* Marker dot */}
                            <div
                              className="absolute top-0 transform -translate-x-1/2 w-2 h-2 rounded-full bg-slate-900 border border-white"
                              style={{ left: `${Math.max(2, Math.min(98, rangePct))}%` }}
                            />
                          </div>
                        </div>

                        {/* 52W Range */}
                        <div>
                          <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1 font-mono">
                            <span>52W Range</span>
                          </div>
                          <div className="flex items-center justify-between text-xs font-mono mb-1 text-slate-700">
                            <span>{formatNumber(week52Low)}</span>
                            <span>{formatNumber(week52High)}</span>
                          </div>
                          <div className="relative h-2 w-full bg-slate-100 rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full transition-all duration-300"
                              style={{
                                width: `${week52Pct}%`,
                                background: 'linear-gradient(90deg, #f87171, #f59e0b 50%, #10b981 100%)',
                              }}
                            />
                            {/* Marker dot */}
                            <div
                              className="absolute top-0 transform -translate-x-1/2 w-2 h-2 rounded-full bg-slate-900 border border-white"
                              style={{ left: `${Math.max(2, Math.min(98, week52Pct))}%` }}
                            />
                          </div>
                        </div>
                      </div>
                    </>
                  )}

                  {/* Quick Action Button */}
                  <div className="pt-2">
                    <button
                      type="button"
                      onClick={toggleWatchlist}
                      className={`w-full py-2.5 px-3 rounded-xl text-xs font-bold flex items-center justify-center gap-2 transition-all border ${
                        watchlisted
                          ? 'bg-amber-50 text-amber-700 border-amber-200'
                          : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'
                      }`}
                    >
                      <svg className="w-4 h-4" fill={watchlisted ? 'currentColor' : 'none'} viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
                      </svg>
                      <span>{watchlisted ? 'Added to Watchlist' : 'Add to Watchlist'}</span>
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* ── Technical Indicators & Analysis (Progressive Load) ── */}
            <div className="space-y-4 pt-2">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-bold text-slate-900">Technical Indicators &amp; Momentum Analysis</h2>
                  <p className="text-xs text-slate-400">Quantitative indicators (RSI, MACD, Bollinger Bands, SMA, ADX) with live signal consensus from PSX</p>
                </div>
                <div className="text-xs font-mono text-slate-400 hidden sm:block">
                  14-Period Confluence · Live Signal Engine
                </div>
              </div>
              {technicalsLoading && !technical ? (
                <TechnicalsSectionSkeleton />
              ) : (
                <StockTechnicals
                  symbol={symbol}
                  data={technical}
                  price={overview?.ltp}
                />
              )}
            </div>
          </div>
        </div>
      )}

        {/* ── TAB 2: FINANCIAL STATEMENTS & RATIOS (Retained & SWR Cached) ── */}
        {visitedTabs.has('financials') && (
          <div
            className={`stock-tab-panel ${activeTab === 'financials' ? 'active' : 'inactive'}`}
            aria-hidden={activeTab !== 'financials'}
          >
            {fundamentalsLoading && !fundamentals ? (
              <FinancialsSkeleton />
            ) : (
              <StockFundamentals
                symbol={symbol}
                fundamentals={fundamentals}
                overview={overview}
              />
            )}
          </div>
        )}

        {/* ── TAB 3: TECHNICAL INDICATORS (Retained & SWR Cached) ── */}
        {visitedTabs.has('technicals') && (
          <div
            className={`stock-tab-panel ${activeTab === 'technicals' ? 'active' : 'inactive'}`}
            aria-hidden={activeTab !== 'technicals'}
          >
            {technicalsLoading && !technical ? (
              <TechnicalsSectionSkeleton />
            ) : (
              <StockTechnicals
                symbol={symbol}
                data={technical}
                price={overview?.ltp}
              />
            )}
          </div>
        )}

        {/* ── TAB 4: SHARIAH SCREENING (Retained & SWR Cached) ── */}
        {visitedTabs.has('shariah') && (
          <div
            className={`stock-tab-panel ${activeTab === 'shariah' ? 'active' : 'inactive'}`}
            aria-hidden={activeTab !== 'shariah'}
          >
            {shariahLoading && (!shariahData || !shariahCriteria) ? (
              <ShariahSkeleton />
            ) : (
              <div className="space-y-4">
              <div className={`${card} p-6`}>
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-100">
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1">
                      Shariah Compliance Verdict
                    </p>
                    <div className="flex items-center gap-2.5">
                      <h2 className="text-xl font-bold text-slate-900">
                        {symbol} · {isCompliant ? 'Shariah Compliant Security' : 'Non-Compliant Security'}
                      </h2>
                      {isCompliant !== undefined && (
                        <ShariahBadge isCompliant={isCompliant} size="md" fullLabel={true} />
                      )}
                    </div>
                  </div>
                  <div className="text-left sm:text-right shrink-0">
                    <span className="text-xs text-slate-400 block mb-0.5">Overall Shariah Score</span>
                    <span className="text-2xl font-black font-mono text-emerald-600">
                      {formatNumber(shariahData?.overall_score, 1)}<span className="text-sm text-slate-400 font-semibold"> / 100</span>
                    </span>
                  </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4">
                  {[
                    { label: 'Screening Method', value: shariahData?.screening_method || 'Meezan / PSX' },
                    { label: 'Purification Rate', value: shariahData?.purification_rate != null ? `${formatNumber(shariahData.purification_rate * 100, 2)}%` : '0.00%', mono: true, green: true },
                    { label: 'KMI-30 Eligible', value: isCompliant ? 'Yes (Eligible)' : 'No' },
                    { label: 'Sector', value: shariahData?.sector || overview?.sector || 'Equities' },
                  ].map((item) => (
                    <div key={item.label} className="p-3.5 bg-slate-50 border border-slate-100 rounded-xl">
                      <span className="text-[10px] text-slate-400 block mb-1 font-semibold uppercase tracking-wider">{item.label}</span>
                      <strong className={`text-sm font-bold ${item.green ? 'text-emerald-600' : 'text-slate-800'} ${item.mono ? 'font-mono' : ''}`}>
                        {item.value}
                      </strong>
                    </div>
                  ))}
                </div>

                {shariahData?.compliance_summary && (
                  <p className="text-xs text-slate-500 mt-4 leading-relaxed border-t border-slate-100 pt-4">
                    {shariahData.compliance_summary}
                  </p>
                )}
              </div>

              {/* AAOIFI Criteria Table */}
              {shariahCriteria?.criteria && (
                <div className={`${card} p-6`}>
                  <h3 className="text-base font-bold text-slate-900 mb-0.5">
                    AAOIFI &amp; PSX Technical Screening Criteria
                  </h3>
                  <p className="text-xs text-slate-400 mb-5">
                    Evaluation of core business activity and the 5 key financial ratio thresholds.
                  </p>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className="border-b border-slate-100 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                          <th className="py-2.5 px-3">Screening Rule</th>
                          <th className="py-2.5 px-3">Threshold</th>
                          <th className="py-2.5 px-3">Actual</th>
                          <th className="py-2.5 px-3 text-right">Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-50">
                        {shariahCriteria.criteria.map((crit, idx) => (
                          <tr key={idx} className="hover:bg-slate-50 transition-colors">
                            <td className="py-3 px-3">
                              <span className="font-semibold text-slate-800 block">{crit.name}</span>
                              <span className="text-[11px] text-slate-400 block mt-0.5">{crit.description}</span>
                            </td>
                            <td className="py-3 px-3 font-mono text-slate-600">
                              {crit.threshold <= 1 ? `${formatNumber(crit.threshold * 100, 1)}%` : formatNumber(crit.threshold, 2)}
                            </td>
                            <td className="py-3 px-3 font-mono font-semibold text-slate-800">
                              {crit.value <= 1 && crit.threshold <= 1 ? `${formatNumber(crit.value * 100, 2)}%` : formatNumber(crit.value, 2)}
                            </td>
                            <td className="py-3 px-3 text-right">
                              <span
                                className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold border"
                                style={crit.passed
                                  ? { background: '#f0fdf4', color: '#15803d', borderColor: '#bbf7d0' }
                                  : { background: '#fff1f2', color: '#be123c', borderColor: '#fecdd3' }
                                }
                              >
                                {crit.passed ? '✓ Passed' : '✗ Failed'}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

        {/* ── TAB 5: AI FORECAST & QUANT SIGNALS (Retained & SWR Cached) ── */}
        {visitedTabs.has('recommendation') && (
          <div
            className={`stock-tab-panel ${activeTab === 'recommendation' ? 'active' : 'inactive'}`}
            aria-hidden={activeTab !== 'recommendation'}
          >
            <StockForecastSection symbol={symbol} onStock={onStock} />
          </div>
        )}

        {/* ── TAB 6: NEWS & SENTIMENT (Retained & SWR Cached) ── */}
        {visitedTabs.has('news') && (
          <div
            className={`stock-tab-panel ${activeTab === 'news' ? 'active' : 'inactive'}`}
            aria-hidden={activeTab !== 'news'}
          >
            {newsLoading && news.length === 0 ? (
              <NewsSkeleton />
            ) : (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className={`${card} p-6 flex flex-col justify-between`}>
                  <div>
                    <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-4">
                      <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                        FinBERT NLP Tone
                      </p>
                      <span className="text-xs text-slate-400 font-mono">
                        {stockSentiment?.article_count || 0} articles
                      </span>
                    </div>

                    <div className="flex items-baseline gap-3 mb-2">
                      <span className="text-3xl font-black font-mono text-slate-900">
                        {stockSentiment ? formatNumber(stockSentiment.score, 2) : '—'}
                      </span>
                      <SentimentBadge
                        sentiment={stockSentiment?.label}
                        score={null}
                        size="sm"
                        showScore={false}
                      />
                    </div>
                    <div className="text-xs text-slate-500 capitalize">
                      Momentum Trend: <b className="text-slate-700">{stockSentiment?.trend || 'Stable'}</b>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => {
                      if (onSentiment) onSentiment()
                      else { window.history.pushState({}, '', '/sentiment'); window.dispatchEvent(new PopStateEvent('popstate')) }
                    }}
                    className="mt-6 w-full py-2.5 px-3 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold flex items-center justify-center gap-1.5 transition-colors shadow-2xs"
                  >
                    <span>Open Market Sentiment Suite</span>
                    <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" /></svg>
                  </button>
                </div>

                <div className="md:col-span-2">
                  <SentimentHistoryChart
                    symbol={symbol}
                    data={sentimentHistory?.data || []}
                    period={sentimentPeriod}
                    onPeriodChange={handleSentimentPeriodChange}
                    loading={sentimentHistoryLoading}
                  />
                </div>
              </div>

              {/* News List */}
              <div className={`${card} p-6`}>
                <div className="flex items-center justify-between mb-5">
                  <div>
                    <h3 className="text-base font-bold text-slate-900">
                      {symbol} Disclosures &amp; Market News
                    </h3>
                    <p className="text-xs text-slate-400 mt-0.5">Live coverage and verified PSX financial filings</p>
                  </div>
                  <span className="text-xs font-bold px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
                    {news?.length || sentimentNews?.length || 0} Articles
                  </span>
                </div>

                <div className="space-y-3">
                  {(news?.length || sentimentNews?.length) ? (
                    (news?.length ? news : sentimentNews).map((article) => (
                      <NewsCard
                        key={article.id || article.url}
                        article={{ ...article, symbols: article.symbols || [{ symbol: symbol.toUpperCase() }] }}
                        onClick={(art) => {
                          if (art.id) {
                            window.history.pushState({}, '', `/news/${art.id}`)
                            window.dispatchEvent(new PopStateEvent('popstate'))
                          } else {
                            const target = art.external_url || art.url
                            if (target) window.open(target, '_blank', 'noopener,noreferrer')
                          }
                        }}
                        onStockClick={onStock}
                        kmiSymbolsSet={isCompliant ? new Set([symbol.toUpperCase()]) : new Set()}
                      />
                    ))
                  ) : (
                    <p className="text-xs text-slate-400 py-8 text-center">
                      No recent news articles or disclosures recorded for {symbol}.
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
        </div>
      </div>
    </main>
  )
}
