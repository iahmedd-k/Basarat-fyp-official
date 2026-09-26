import React, { useState, useEffect } from 'react'
import StockLogo from './StockLogo'
import ProHeader from './ProHeader'
import { formatNumber } from '../utils/formatters'
import { dashboardApi } from '../api/dashboard'
import { newsApi } from '../api/news'
import ArticleDetailModal from './ArticleDetailModal'

export default function LandingPage({
  onLogin,
  onSignup,
  onStock,
  onMarket,
  onNews,
  onRequireAuth,
  onOpenSearch,
}) {
  const [indices, setIndices] = useState([])
  const [gainers, setGainers] = useState([])
  const [losers, setLosers] = useState([])
  const [mostActive, setMostActive] = useState([])
  const [sentiment, setSentiment] = useState(null)
  const [recentNews, setRecentNews] = useState([])
  const [selectedArticle, setSelectedArticle] = useState(null)
  const [activeMoversTab, setActiveMoversTab] = useState('gainers')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let mounted = true
    const fetchData = async () => {
      try {
        const [indicesRes, gainersRes, losersRes, activeRes, newsRes, sentimentRes] = await Promise.allSettled([
          dashboardApi.getIndices(),
          dashboardApi.getGainers(10),
          dashboardApi.getLosers(10),
          dashboardApi.getMostActive(10),
          newsApi.getNews({ limit: 4 }),
          dashboardApi.getSentiment(),
        ])
        if (!mounted) return
        if (indicesRes.status === 'fulfilled' && indicesRes.value?.indices) setIndices(indicesRes.value.indices)
        if (gainersRes.status === 'fulfilled' && gainersRes.value?.gainers) setGainers(gainersRes.value.gainers)
        if (losersRes.status === 'fulfilled' && losersRes.value?.losers) setLosers(losersRes.value.losers)
        if (activeRes.status === 'fulfilled' && activeRes.value?.volume_spikes) setMostActive(activeRes.value.volume_spikes)
        if (newsRes.status === 'fulfilled') {
          const items = newsRes.value?.items || (Array.isArray(newsRes.value) ? newsRes.value : [])
          setRecentNews(items.slice(0, 3))
        }
        if (sentimentRes.status === 'fulfilled' && sentimentRes.value) setSentiment(sentimentRes.value)
      } catch (err) {
        console.warn('Landing page data load notice:', err)
      } finally {
        if (mounted) setLoading(false)
      }
    }
    fetchData()
    return () => { mounted = false }
  }, [])

  const currentMovers = activeMoversTab === 'gainers' ? gainers : activeMoversTab === 'losers' ? losers : mostActive

  const quickChips = gainers.length >= 5
    ? gainers.slice(0, 5).map((g) => g.symbol)
    : mostActive.length >= 5
      ? mostActive.slice(0, 5).map((m) => m.symbol)
      : ['SYS', 'OGDC', 'LUCK', 'HBL', 'ENGRO']

  const renderSparkline = (isPositive) => {
    const strokeColor = isPositive ? '#10b981' : '#f43f5e'
    const pathData = isPositive
      ? 'M0 24 Q25 18 50 20 T100 8 T140 14 T180 4'
      : 'M0 6 Q30 10 60 8 T110 22 T150 16 T180 26'
    return (
      <svg className="w-20 h-7 shrink-0 overflow-visible" viewBox="0 0 180 30" fill="none" aria-hidden="true">
        <path d={pathData} stroke={strokeColor} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    )
  }

  // Ticker symbols for scrolling bar
  const tickerSymbols = [...gainers.slice(0, 5), ...losers.slice(0, 5), ...mostActive.slice(0, 5)]

  return (
    <div className="min-h-screen bg-[#fafbfc] text-[#0d0d0d] font-sans antialiased flex flex-col selection:bg-emerald-100 selection:text-emerald-900">

      {/* ── Header ── */}
      <ProHeader
        active="dashboard"
        onDashboard={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
        onMarket={onMarket}
        onNews={onNews}
        onSentiment={onRequireAuth}
        onRecommendations={onRequireAuth}
        onPortfolio={onRequireAuth}
        onWatchlist={onRequireAuth}
        onShariah={onRequireAuth}
        onAssistant={onRequireAuth}
        onRisk={onRequireAuth}
        onSettings={onRequireAuth}
        onLogout={() => {}}
        onOpenSearch={onOpenSearch}
        onLogin={onLogin}
        onRequireAuth={onRequireAuth}
      />

      {/* ══════════════════════════════════════════
          HERO SECTION
      ══════════════════════════════════════════ */}
      <section className="relative overflow-hidden bg-white border-b border-black/5">
        {/* Background decoration */}
        <div className="absolute inset-0 pointer-events-none" aria-hidden="true">
          <div className="absolute inset-0 bg-gradient-to-br from-[#e8faf3]/60 via-white to-white" />
          <div
            className="absolute -top-40 -right-40 w-[600px] h-[600px] rounded-full opacity-30"
            style={{ background: 'radial-gradient(circle, #bbf7d0 0%, transparent 70%)', filter: 'blur(60px)' }}
          />
          <div
            className="absolute top-32 -left-24 w-[400px] h-[400px] rounded-full opacity-20"
            style={{ background: 'radial-gradient(circle, #6ee7b7 0%, transparent 70%)', filter: 'blur(80px)' }}
          />
          {/* Subtle dot grid */}
          <div
            className="absolute inset-0 opacity-[0.04]"
            style={{
              backgroundImage: 'radial-gradient(circle, #000 1px, transparent 1px)',
              backgroundSize: '28px 28px',
            }}
          />
        </div>

        <div className="relative max-w-4xl mx-auto px-6 lg:px-8 pt-20 pb-14 sm:pt-24 sm:pb-18 text-center">
          {/* Live badge */}
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full border border-emerald-200 bg-emerald-50 text-emerald-700 text-xs font-semibold mb-7">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            Live · Pakistan Stock Exchange Intelligence
          </div>

          {/* Main headline */}
          <h1 className="text-[42px] sm:text-[58px] lg:text-[70px] font-black leading-[1.0] tracking-[-2.5px] text-[#0d0d0d] text-balance mb-5 max-w-3xl mx-auto">
            Invest smarter{' '}
            <span
              style={{
                background: 'linear-gradient(135deg, #059669 0%, #10b981 50%, #0fa76e 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
              }}
            >
              in Pakistan
            </span>
          </h1>

          {/* Subtitle */}
          <p className="text-[16px] sm:text-[18px] text-slate-500 max-w-xl mx-auto leading-relaxed mb-10 text-pretty">
            Research every company on PSX. Live quotes, market activity,
            sector analysis, and quantitative intelligence — all in one place.
          </p>

          {/* Search pill */}
          <div className="w-full max-w-xl mx-auto mb-6">
            <button
              type="button"
              onClick={onOpenSearch}
              className="relative w-full flex items-center h-[54px] rounded-2xl border border-black/10 bg-white hover:border-emerald-400/60 hover:shadow-[0_0_0_4px_rgba(16,185,129,0.08)] transition-all cursor-pointer px-5 group shadow-[0_4px_24px_rgba(0,0,0,0.06)]"
            >
              <svg className="w-5 h-5 text-slate-400 mr-3 group-hover:text-emerald-600 transition-colors shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <span className="text-[15px] text-slate-400 text-left flex-1 group-hover:text-slate-600 transition-colors">
                Search stocks, companies, sectors…
              </span>
              <kbd className="hidden sm:inline-flex items-center gap-0.5 text-[11px] text-slate-400 border border-black/10 rounded-lg px-2 py-0.5 font-mono bg-slate-50">
                ⌘K
              </kbd>
            </button>
          </div>

          {/* Quick chips */}
          <div className="flex flex-wrap items-center justify-center gap-2 mb-9">
            <span className="text-[12px] text-slate-400">Try:</span>
            {quickChips.map((sym) => (
              <button
                key={sym}
                type="button"
                onClick={() => onStock(sym)}
                className="inline-flex items-center gap-1.5 text-[12px] font-semibold text-slate-600 hover:text-[#0d0d0d] border border-black/8 hover:border-emerald-400/50 rounded-full px-3 py-1 bg-white hover:bg-emerald-50 transition-all cursor-pointer shadow-2xs"
              >
                <StockLogo ticker={sym} size="xs" />
                <span>{sym}</span>
              </button>
            ))}
          </div>

          {/* CTA buttons */}
          <div className="flex items-center gap-3 flex-wrap justify-center">
            <button
              type="button"
              onClick={onSignup}
              className="inline-flex items-center gap-2 px-7 py-3 rounded-full font-bold text-[14px] text-white cursor-pointer transition-all active:scale-[0.97] shadow-[0_4px_20px_rgba(15,167,110,0.35)] hover:shadow-[0_6px_28px_rgba(15,167,110,0.5)]"
              style={{ background: 'linear-gradient(135deg, #059669 0%, #0fa76e 50%, #10b981 100%)' }}
            >
              Get started free
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="5" y1="12" x2="19" y2="12" />
                <polyline points="12 5 19 12 12 19" />
              </svg>
            </button>
            <button
              type="button"
              onClick={onMarket}
              className="inline-flex items-center gap-2 px-7 py-3 rounded-full font-bold text-[14px] text-slate-700 border border-black/12 bg-white hover:bg-slate-50 hover:border-black/20 cursor-pointer transition-all shadow-2xs"
            >
              Explore market
            </button>
          </div>
        </div>

        {/* Scrolling live ticker */}
        {tickerSymbols.length > 0 && (
          <div className="relative w-full border-t border-black/5 bg-slate-50/70 overflow-hidden py-3">
            <div
              className="flex items-center gap-8 whitespace-nowrap"
              style={{ width: 'max-content', animation: 'tickerScroll 40s linear infinite' }}
            >
              {[...tickerSymbols, ...tickerSymbols, ...tickerSymbols].map((stock, idx) => {
                const isPos = Number(stock.change_pct) >= 0
                return (
                  <button
                    key={`${stock.symbol}-${idx}`}
                    type="button"
                    onClick={() => onStock(stock.symbol)}
                    className="inline-flex items-center gap-2 text-xs cursor-pointer hover:opacity-70 transition-opacity shrink-0"
                  >
                    <StockLogo ticker={stock.symbol} size="xs" />
                    <span className="font-bold text-slate-700">{stock.symbol}</span>
                    <span className="font-mono font-semibold" style={{ color: isPos ? '#059669' : '#e11d48' }}>
                      {isPos ? '+' : ''}{formatNumber(stock.change_pct, 2)}%
                    </span>
                  </button>
                )
              })}
            </div>
            <div className="absolute inset-y-0 left-0 w-16 bg-gradient-to-r from-slate-50 to-transparent pointer-events-none" />
            <div className="absolute inset-y-0 right-0 w-16 bg-gradient-to-l from-slate-50 to-transparent pointer-events-none" />
          </div>
        )}
      </section>

      {/* ══════════════════════════════════════════
          MARKET PULSE — Live Indices
      ══════════════════════════════════════════ */}
      <section className="bg-white border-b border-black/5">
        <div className="max-w-6xl mx-auto px-5 sm:px-6 lg:px-8 py-12">
          <div className="flex items-baseline justify-between mb-7">
            <div>
              <h2 className="text-2xl sm:text-3xl font-black text-[#0d0d0d] tracking-tight">Market Pulse</h2>
              <p className="text-sm text-slate-500 mt-0.5">Live Pakistan Stock Exchange indices</p>
            </div>
            {sentiment && sentiment.advancing != null && (
              <div className="hidden sm:flex items-center gap-4 text-xs">
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-500" />
                  <span className="text-emerald-700 font-bold tabular-nums">{formatNumber(sentiment.advancing, 0)}</span>
                  <span className="text-slate-400">Advancing</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-rose-500" />
                  <span className="text-rose-600 font-bold tabular-nums">{formatNumber(sentiment.declining, 0)}</span>
                  <span className="text-slate-400">Declining</span>
                </div>
              </div>
            )}
          </div>

          <div className={`grid grid-cols-1 ${indices.length === 2 ? 'sm:grid-cols-2' : 'md:grid-cols-3'} gap-4`}>
            {indices.length === 0 ? (
              [1, 2, 3].map((i) => (
                <div key={i} className="rounded-2xl border border-black/8 bg-white p-6 animate-pulse h-32" />
              ))
            ) : (
              indices.map((item) => {
                const isPos = Number(item.change) >= 0
                const isShariah = item.index === 'KMI-30' || item.code === 'KMI30'
                const displayName = item.index ? item.index.replace('-', ' ') : item.code
                return (
                  <div
                    key={item.code || item.index}
                    className="rounded-2xl border border-black/8 bg-white hover:border-emerald-300 hover:shadow-[0_4px_20px_rgba(16,185,129,0.08)] transition-all p-6 flex justify-between items-start"
                  >
                    <div>
                      <div className="flex items-center gap-2 mb-1.5">
                        <span className="text-[11px] font-bold uppercase tracking-widest text-slate-400">
                          {displayName}
                        </span>
                        {isShariah && (
                          <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                            Shariah
                          </span>
                        )}
                      </div>
                      <p className="text-[28px] font-black font-mono tracking-tight text-[#0d0d0d]">
                        {formatNumber(item.current)}
                      </p>
                      <div className="mt-1.5">
                        <span
                          className="inline-flex items-center gap-1 text-xs font-bold font-mono px-2 py-0.5 rounded-md"
                          style={isPos
                            ? { background: '#f0fdf4', color: '#059669', border: '1px solid #bbf7d0' }
                            : { background: '#fff1f2', color: '#e11d48', border: '1px solid #fecdd3' }
                          }
                        >
                          {isPos ? '▲ +' : '▼ '}{formatNumber(Math.abs(item.change))} ({formatNumber(item.change_pct, 2)}%)
                        </span>
                      </div>
                      {item.high != null && item.low != null && (
                        <p className="text-[10px] text-slate-400 font-mono mt-2">
                          H: {formatNumber(item.high)} · L: {formatNumber(item.low)}
                        </p>
                      )}
                    </div>
                    {renderSparkline(isPos)}
                  </div>
                )
              })
            )}
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════════
          TODAY'S STOCKS
      ══════════════════════════════════════════ */}
      <section className="bg-[#fafbfc] border-b border-black/5">
        <div className="max-w-6xl mx-auto px-5 sm:px-6 lg:px-8 py-12">
          <div className="flex items-baseline justify-between mb-6">
            <div>
              <h2 className="text-2xl sm:text-3xl font-black text-[#0d0d0d] tracking-tight">Today's Stocks</h2>
              <p className="text-sm text-slate-500 mt-0.5">Live market movers from PSX</p>
            </div>
            <button
              type="button"
              onClick={onMarket}
              className="inline-flex items-center gap-1.5 text-xs font-bold text-emerald-600 hover:text-emerald-700 transition-colors cursor-pointer"
            >
              Browse all
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M5 12h14" /><path d="M12 5l7 7-7 7" />
              </svg>
            </button>
          </div>

          {/* Tab pills */}
          <div className="flex items-center gap-2 mb-5 overflow-x-auto scrollbar-none">
            {[
              {
                key: 'gainers', label: 'Gainers',
                icon: <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M16 7h6v6" /><path d="M22 7l-8.5 8.5-5-5L2 17" /></svg>
              },
              {
                key: 'losers', label: 'Losers',
                icon: <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M16 17h6v-6" /><path d="M22 17l-8.5-8.5-5 5L2 7" /></svg>
              },
              {
                key: 'active', label: 'Most Active',
                icon: <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12" /></svg>
              },
            ].map((tab) => (
              <button
                key={tab.key}
                type="button"
                onClick={() => setActiveMoversTab(tab.key)}
                className={`inline-flex items-center gap-1.5 px-4 py-2 text-xs font-bold rounded-full border transition-all cursor-pointer whitespace-nowrap ${
                  activeMoversTab === tab.key
                    ? 'bg-[#0fa76e] text-white border-[#0fa76e] shadow-[0_4px_14px_rgba(15,167,110,0.3)]'
                    : 'bg-white text-slate-500 border-black/10 hover:border-emerald-400/50 hover:text-slate-700'
                }`}
              >
                {tab.icon}
                {tab.label}
              </button>
            ))}
          </div>

          {/* Table */}
          <div className="rounded-2xl border border-black/8 bg-white overflow-hidden shadow-2xs">
            <div className="grid grid-cols-12 px-5 py-3 bg-slate-50/70 border-b border-black/5 text-[11px] font-bold text-slate-400 uppercase tracking-wider">
              <div className="col-span-7 sm:col-span-6">Stock</div>
              <div className="col-span-5 sm:col-span-2 text-right">Price</div>
              <div className="hidden sm:block sm:col-span-2 text-right">Change</div>
              <div className="hidden sm:block sm:col-span-2 text-right">Volume</div>
            </div>

            <div className="divide-y divide-black/5">
              {currentMovers.length === 0 ? (
                <div className="p-6 space-y-3">
                  {[1, 2, 3, 4, 5].map((i) => (
                    <div key={i} className="h-12 rounded-xl bg-slate-100 animate-pulse" />
                  ))}
                </div>
              ) : (
                currentMovers.slice(0, 10).map((stock, idx) => {
                  const isPositive = Number(stock.change) >= 0 || Number(stock.change_pct) >= 0
                  return (
                    <div
                      key={stock.symbol || idx}
                      onClick={() => onStock(stock.symbol)}
                      className="grid grid-cols-12 items-center px-5 py-3.5 hover:bg-slate-50/80 transition-colors cursor-pointer group"
                    >
                      <div className="col-span-7 sm:col-span-6 flex items-center gap-3 min-w-0">
                        <StockLogo ticker={stock.symbol} companyName={stock.name} size="md" />
                        <div className="min-w-0">
                          <p className="text-xs sm:text-sm font-bold text-slate-900 truncate">
                            {stock.name || stock.sector || stock.symbol}
                          </p>
                          <div className="flex items-center gap-1.5 text-[11px] text-slate-400 font-mono">
                            <span className="font-bold text-slate-600">{stock.symbol}</span>
                            {stock.sector && (
                              <>
                                <span>·</span>
                                <span className="truncate">{stock.sector}</span>
                              </>
                            )}
                          </div>
                        </div>
                      </div>

                      <div className="col-span-5 sm:col-span-2 text-right">
                        <p className="text-xs sm:text-sm font-black font-mono text-slate-900">
                          {formatNumber(stock.current, 2)}
                        </p>
                        <span className="sm:hidden text-[10px] font-mono font-bold" style={{ color: isPositive ? '#059669' : '#e11d48' }}>
                          {isPositive ? '+' : ''}{formatNumber(stock.change_pct, 2)}%
                        </span>
                      </div>

                      <div className="hidden sm:flex sm:col-span-2 justify-end">
                        <span
                          className="inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-bold font-mono"
                          style={isPositive
                            ? { background: '#f0fdf4', color: '#059669', border: '1px solid #bbf7d0' }
                            : { background: '#fff1f2', color: '#e11d48', border: '1px solid #fecdd3' }
                          }
                        >
                          {isPositive ? '▲ +' : '▼ '}{formatNumber(stock.change_pct, 2)}%
                        </span>
                      </div>

                      <div className="hidden sm:block sm:col-span-2 text-right font-mono text-xs text-slate-400">
                        {formatNumber(stock.volume, 0)}
                      </div>
                    </div>
                  )
                })
              )}
            </div>
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════════
          MARKET ACTIVITY (NEWS)
      ══════════════════════════════════════════ */}
      {recentNews.length > 0 && (
        <section className="bg-white border-b border-black/5">
          <div className="max-w-6xl mx-auto px-5 sm:px-6 lg:px-8 py-12">
            <div className="flex items-baseline justify-between mb-7">
              <div>
                <h2 className="text-2xl sm:text-3xl font-black text-[#0d0d0d] tracking-tight">Market Activity</h2>
                <p className="text-sm text-slate-500 mt-0.5">
                  Announcements, insider trades &amp; earnings from PSX
                </p>
              </div>
              <button
                type="button"
                onClick={onNews}
                className="inline-flex items-center gap-1.5 text-xs font-bold text-emerald-600 hover:text-emerald-700 transition-colors cursor-pointer"
              >
                Live feed
                <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M5 12h14" /><path d="M12 5l7 7-7 7" />
                </svg>
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
              {recentNews.map((item) => (
                <article
                  key={item.id}
                  onClick={() => setSelectedArticle(item)}
                  className="rounded-2xl border border-black/8 bg-white hover:border-emerald-300 hover:shadow-[0_4px_20px_rgba(16,185,129,0.08)] transition-all cursor-pointer flex flex-col justify-between overflow-hidden group shadow-2xs"
                >
                  <div className="h-0.5 w-full" style={{ background: 'linear-gradient(90deg, #10b981, #bbf7d0, transparent)' }} />
                  <div className="p-5 flex flex-col flex-1">
                    <div className="flex items-center justify-between gap-2 mb-3">
                      <span className="text-[11px] font-bold text-slate-700 bg-slate-100 px-2 py-0.5 rounded">
                        {item.symbols?.[0] || 'PSX'}
                      </span>
                      <span className="text-[10px] text-slate-400">
                        {item.published_at
                          ? new Date(item.published_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
                          : 'Recent'}
                      </span>
                    </div>
                    <h4 className="text-sm font-bold text-slate-900 line-clamp-2 mb-2 leading-snug">
                      {item.title}
                    </h4>
                    <p className="text-xs text-slate-500 line-clamp-2 leading-relaxed flex-1">
                      {item.summary || item.content}
                    </p>
                    <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] text-emerald-600 font-semibold">
                      <span>View details</span>
                      <svg className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                        <path d="M5 12h14" /><path d="M12 5l7 7-7 7" />
                      </svg>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* ══════════════════════════════════════════
          BENTO FEATURES (moved to end)
      ══════════════════════════════════════════ */}
      <section className="bg-[#fafbfc] border-b border-black/5">
        <div className="max-w-6xl mx-auto px-5 sm:px-6 lg:px-8 py-14">
          {/* Section header */}
          <div className="text-center mb-10">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-semibold mb-4">
              ✦ Platform Features
            </div>
            <h2 className="text-3xl sm:text-4xl font-black text-[#0d0d0d] tracking-tight mb-3">
              Everything you need to{' '}
              <span style={{ background: 'linear-gradient(135deg, #059669, #0fa76e)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text' }}>
                trade smarter
              </span>
            </h2>
            <p className="text-slate-500 max-w-lg mx-auto text-sm">
              From real-time quotes to AI-driven recommendations, everything that serious PSX investors need.
            </p>
          </div>

          {/* Feature grid — unified emerald theme */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-px bg-black/6 rounded-3xl overflow-hidden border border-black/8 shadow-sm">

            {/* Large — Stock Research */}
            <div
              className="md:col-span-2 bg-white p-8 relative overflow-hidden group hover:bg-emerald-50/40 transition-colors cursor-pointer"
              onClick={onOpenSearch}
            >
              <div className="relative">
                <div className="flex items-center gap-3 mb-5">
                  <div className="w-9 h-9 rounded-xl bg-emerald-100 flex items-center justify-center shrink-0">
                    <svg className="w-4.5 h-4.5 text-emerald-700" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                      <circle cx="11" cy="11" r="8" />
                      <line x1="21" y1="21" x2="16.65" y2="16.65" />
                    </svg>
                  </div>
                  <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-emerald-600">Research</span>
                </div>
                <h3 className="text-[19px] font-bold text-slate-900 mb-2 tracking-tight">Stock Research</h3>
                <p className="text-slate-500 text-sm leading-relaxed max-w-sm">
                  Deep-dive into any PSX listed company. Financials, dividends, sector comparisons, and insider trades — all instantly accessible.
                </p>
                <div className="mt-7 inline-flex items-center gap-1.5 text-emerald-700 text-xs font-bold border-b border-emerald-200 pb-0.5 group-hover:border-emerald-500 transition-colors">
                  Search stocks
                  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" /></svg>
                </div>
              </div>
            </div>

            {/* Small — Market Activity */}
            <div
              className="bg-white p-7 relative overflow-hidden group hover:bg-emerald-50/40 transition-colors cursor-pointer"
              onClick={onNews}
            >
              <div className="relative">
                <div className="flex items-center gap-3 mb-5">
                  <div className="w-9 h-9 rounded-xl bg-emerald-100 flex items-center justify-center shrink-0">
                    <svg className="w-4.5 h-4.5 text-emerald-700" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                      <path d="M4 22h16a2 2 0 002-2V7.5L14.5 2H6a2 2 0 00-2 2v4" />
                      <polyline points="14 2 14 8 20 8" />
                      <path d="M2 15h10M5 12l-3 3 3 3" />
                    </svg>
                  </div>
                  <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-emerald-600">Activity</span>
                </div>
                <h3 className="text-[19px] font-bold text-slate-900 mb-2 tracking-tight">Market Activity</h3>
                <p className="text-slate-500 text-sm leading-relaxed">
                  Announcements, AGMs, earnings, and corporate actions — live from PSX.
                </p>
                <div className="mt-6 inline-flex items-center gap-1.5 text-emerald-700 text-xs font-bold border-b border-emerald-200 pb-0.5 group-hover:border-emerald-500 transition-colors">
                  View feed
                  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" /></svg>
                </div>
              </div>
            </div>

            {/* Small — Sentiment */}
            <div
              className="bg-white p-7 relative overflow-hidden group hover:bg-emerald-50/40 transition-colors cursor-pointer"
              onClick={onRequireAuth}
            >
              <div className="relative">
                <div className="flex items-center gap-3 mb-5">
                  <div className="w-9 h-9 rounded-xl bg-emerald-100 flex items-center justify-center shrink-0">
                    <svg className="w-4.5 h-4.5 text-emerald-700" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
                    </svg>
                  </div>
                  <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-emerald-600">Sentiment</span>
                </div>
                <h3 className="text-[19px] font-bold text-slate-900 mb-2 tracking-tight">Sentiment Analysis</h3>
                <p className="text-slate-500 text-sm leading-relaxed">
                  Gauge market mood with advance/decline data, breadth indicators, and sector flows.
                </p>
                <div className="mt-6 inline-flex items-center gap-1.5 text-emerald-700 text-xs font-bold border-b border-emerald-200 pb-0.5 group-hover:border-emerald-500 transition-colors">
                  View sentiment
                  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" /></svg>
                </div>
              </div>
            </div>

            {/* Large — Portfolio */}
            <div
              className="md:col-span-2 bg-white p-8 relative overflow-hidden group hover:bg-emerald-50/40 transition-colors cursor-pointer"
              onClick={onRequireAuth}
            >
              <div className="relative">
                <div className="flex items-center gap-3 mb-5">
                  <div className="w-9 h-9 rounded-xl bg-emerald-100 flex items-center justify-center shrink-0">
                    <svg className="w-4.5 h-4.5 text-emerald-700" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                      <path d="M3 3h18v4H3z" />
                      <path d="M3 10h18v11H3z" />
                      <path d="M9 21V10M15 21V10" />
                    </svg>
                  </div>
                  <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-emerald-600">Portfolio</span>
                </div>
                <h3 className="text-[19px] font-bold text-slate-900 mb-2 tracking-tight">Portfolio Tracker</h3>
                <p className="text-slate-500 text-sm leading-relaxed max-w-sm">
                  Track your PSX holdings with live P&amp;L, unrealized gains, sector allocation, and transaction history — sign in to access.
                </p>
                <div className="mt-7 inline-flex items-center gap-1.5 text-emerald-700 text-xs font-bold border-b border-emerald-200 pb-0.5 group-hover:border-emerald-500 transition-colors">
                  Open portfolio
                  <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" /></svg>
                </div>
              </div>
            </div>

          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════════
          CTA SECTION
      ══════════════════════════════════════════ */}
      <section className="bg-[#fafbfc] border-t border-black/5">
        <div className="max-w-4xl mx-auto px-5 sm:px-6 lg:px-8 py-20 text-center">
          {/* Eyebrow badge */}
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full border border-emerald-200 bg-emerald-50 text-emerald-700 text-xs font-semibold mb-7">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            Free to get started — no credit card required
          </div>

          <h2 className="text-3xl sm:text-[42px] font-black text-[#0d0d0d] tracking-[-1.5px] leading-tight mb-4 text-balance">
            Ready to invest smarter?
          </h2>
          <p className="text-slate-500 text-[15px] sm:text-[16px] leading-relaxed max-w-lg mx-auto mb-10">
            Join Basarat and get live PSX data, portfolio tools, sentiment analysis, and AI-powered stock recommendations — all in one platform.
          </p>

          {/* CTA Buttons */}
          <div className="flex items-center justify-center gap-3 flex-wrap">
            <button
              type="button"
              onClick={onSignup}
              className="inline-flex items-center gap-2 px-7 py-3 rounded-full font-bold text-[14px] text-white cursor-pointer transition-all active:scale-[0.97] shadow-[0_4px_18px_rgba(15,167,110,0.3)] hover:shadow-[0_6px_26px_rgba(15,167,110,0.45)]"
              style={{ background: 'linear-gradient(135deg, #059669 0%, #0fa76e 100%)' }}
            >
              Create free account
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" />
              </svg>
            </button>
            <button
              type="button"
              onClick={onLogin}
              className="inline-flex items-center gap-2 px-7 py-3 rounded-full font-bold text-[14px] text-slate-700 border border-black/12 bg-white hover:bg-slate-50 hover:border-black/20 cursor-pointer transition-all shadow-2xs"
            >
              Sign in to account
            </button>
          </div>

          {/* Trust note */}
          <p className="mt-8 text-xs text-slate-400">
            Used by investors researching Pakistan Stock Exchange listed companies.
          </p>
        </div>
      </section>

      {/* ══════════════════════════════════════════
          FOOTER
      ══════════════════════════════════════════ */}
      <footer className="mt-auto border-t border-black/5 bg-white text-slate-700 pt-14 pb-8">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 space-y-10">

          {/* Logo & Description */}
          <div className="space-y-3">
            <div className="flex items-center gap-2.5">
              <div className="flex items-end gap-0.5 h-6">
                <span className="w-1.5 h-3 rounded-full bg-emerald-500/70" />
                <span className="w-1.5 h-4.5 rounded-full bg-emerald-600" />
                <span className="w-1.5 h-6 rounded-full bg-emerald-400" />
              </div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-lg tracking-tight text-slate-900 font-sans">Basarat</span>
                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                  PSX
                </span>
              </div>
            </div>
            <p className="text-sm text-slate-500 leading-relaxed max-w-3xl">
              Basarat is a Pakistan-focused financial intelligence platform designed to help users research stocks, understand market activity, analyze sentiment, explore recommendations, and make informed investment decisions.
            </p>
          </div>

          <hr className="border-slate-100" />

          {/* Platform Purpose & Disclaimer */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 text-xs leading-relaxed">
            <div className="space-y-2">
              <h3 className="font-bold text-slate-900 text-sm">Platform Purpose</h3>
              <p className="text-slate-500">
                Basarat provides financial market information, stock research, market activity, sentiment insights, portfolio tools, and analytical features for educational and research purposes. The platform is designed to help users explore and understand information related to the Pakistan Stock Exchange.
              </p>
            </div>
            <div className="space-y-2">
              <h3 className="font-bold text-slate-900 text-sm">Disclaimer</h3>
              <p className="text-slate-500">
                Basarat is intended for educational and research purposes only. Information provided on the platform should not be considered financial or investment advice. Users should conduct their own research before making investment decisions.
              </p>
            </div>
          </div>

          <hr className="border-slate-100" />

          {/* Developed By — professional clean style */}
          <div className="py-1">
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400 mb-5 text-center">
              Developed by
            </p>
            <div className="flex flex-wrap items-center justify-center gap-x-8 gap-y-4">
              {[
                { name: 'Talal Umar', role: 'Full Stack Developer' },
                { name: 'Ahmed Khan', role: 'Full Stack Developer' },
                { name: 'Abdul Rehman', role: 'Full Stack Developer' },
              ].map((dev, idx) => (
                <div key={dev.name} className="flex items-center gap-3 group">
                  {idx > 0 && (
                    <span className="hidden sm:block w-px h-8 bg-slate-200 -ml-4" />
                  )}
                  {/* Initials avatar */}
                  <div className="w-9 h-9 rounded-full bg-slate-100 border border-slate-200 flex items-center justify-center shrink-0">
                    <span className="text-[11px] font-black text-slate-600 tracking-tight">
                      {dev.name.split(' ').map(n => n[0]).join('')}
                    </span>
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-slate-800 leading-none">{dev.name}</p>
                    <p className="text-[11px] text-slate-400 mt-0.5">{dev.role}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <hr className="border-slate-100" />

          {/* Bottom copyright */}
          <div className="text-center text-[11px] text-slate-400">
            © {new Date().getFullYear()} Basarat Analytics. Real-time Pakistan Stock Exchange (PSX) market figures.
          </div>
        </div>
      </footer>

      {/* Ticker animation */}
      <style>{`
        @keyframes tickerScroll {
          0% { transform: translateX(0); }
          100% { transform: translateX(-33.333%); }
        }
      `}</style>

      {/* Article Detail Modal */}
      {selectedArticle && (
        <ArticleDetailModal
          article={selectedArticle}
          onClose={() => setSelectedArticle(null)}
          onStock={(sym) => {
            setSelectedArticle(null)
            onStock(sym)
          }}
        />
      )}
    </div>
  )
}
