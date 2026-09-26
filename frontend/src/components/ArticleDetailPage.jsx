import React, { useState, useEffect, useCallback } from 'react'
import ProHeader from './ProHeader'
import StockLogo from './StockLogo'
import ShariahBadge from './ShariahBadge'
import { newsApi } from '../api/news'
import { dashboardApi } from '../api/dashboard'
import { FALLBACK_ARTICLES } from '../api/newsFallback'

function formatFullDate(dateString) {
  if (!dateString) return 'Date unavailable'
  try {
    const d = new Date(dateString)
    if (isNaN(d.getTime())) return 'Date unavailable'
    return d.toLocaleDateString(undefined, {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true,
    })
  } catch {
    return 'Date unavailable'
  }
}

/**
 * Dedicated, institutional-grade Article Detail View.
 * Displays the complete article content, source metadata, external filing link,
 * and associated stocks with official logos and Mosque Shariah badges.
 */
export default function ArticleDetailPage({
  articleId,
  initialArticle,
  onBack,
  onMarket,
  onPortfolio,
  onNews,
  onStock,
  onWatchlist,
  onRisk,
  onSettings,
  onLogout,
}) {
  const [article, setArticle] = useState(() => {
    return initialArticle || window.history?.state?.article || null
  })
  const [loading, setLoading] = useState(() => {
    return !(initialArticle || window.history?.state?.article)
  })
  const [error, setError] = useState('')
  const [kmiSymbolsSet, setKmiSymbolsSet] = useState(new Set())

  // Load KMI-30 Shariah universe
  useEffect(() => {
    dashboardApi
      .getKmi30Constituents()
      .then((res) => {
        if (res?.constituents && Array.isArray(res.constituents)) {
          setKmiSymbolsSet(new Set(res.constituents.map((c) => c.symbol.toUpperCase())))
        }
      })
      .catch(() => {})
  }, [])

  const loadArticle = useCallback(async () => {
    if (!articleId) return
    console.log('[ArticleDetailPage] loadArticle starting for:', articleId)
    if (!article) {
      setLoading(true)
    }
    setError('')
    try {
      if (articleId.startsWith('psx_')) {
        const parts = articleId.split('_')
        const sym = parts[1]
        if (sym) {
          console.log('[ArticleDetailPage] Fetching stock news for:', sym)
          const res = await newsApi.getStockNews(sym)
          const found = res?.items?.find((item) => item.id === articleId)
          if (found) {
            console.log('[ArticleDetailPage] Found PSX disclosure:', found.title)
            setArticle(found)
            return
          }
        }
      }
      console.log('[ArticleDetailPage] Calling newsApi.getArticle for:', articleId)
      const data = await newsApi.getArticle(articleId)
      console.log('[ArticleDetailPage] getArticle received:', data?.title)
      setArticle(data)
    } catch (err) {
      console.warn('[ArticleDetailPage] loadArticle remote error, checking fallback:', err)
      const fallbackFound = FALLBACK_ARTICLES.find((a) => a.id === articleId)
      if (fallbackFound) {
        setArticle(fallbackFound)
      } else if (!article) {
        setError(err.message || 'Article could not be loaded.')
      }
    } finally {
      console.log('[ArticleDetailPage] finished loading')
      setLoading(false)
    }
  }, [articleId, article])

  useEffect(() => {
    loadArticle()
  }, [loadArticle])

  const sourceName = article?.source?.name || 'Pakistan Market Source'
  const linkTarget = article?.external_url || article?.url
  const eventLabel = article?.event_type?.replaceAll('_', ' ')
  const sentimentLabel = article?.sentiment?.label?.toLowerCase()
  const sentimentScore = article?.sentiment?.score != null ? Math.round(Math.abs(article.sentiment.score) * 100) : null

  return (
    <main className="dashboard min-h-screen bg-slate-50/50 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
      <ProHeader
        active="news"
        onDashboard={onBack}
        onMarket={onMarket}
        onPortfolio={onPortfolio}
        onNews={onNews || onBack}
        onWatchlist={onWatchlist}
        onRisk={onRisk}
        onSettings={onSettings}
        onLogout={onLogout}
      />

      <section className="dashboard-content max-w-4xl mx-auto px-4 py-8">
        {/* Back navigation */}
        <button
          type="button"
          className="back-button inline-flex items-center gap-2 text-xs font-semibold text-slate-500 hover:text-emerald-600 dark:text-slate-400 dark:hover:text-emerald-400 mb-6 transition-colors"
          onClick={onBack}
        >
          ← Back to Market News
        </button>

        {loading && (
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-8 space-y-4 animate-pulse">
            <div className="h-4 bg-slate-200 dark:bg-slate-800 rounded w-1/4" />
            <div className="h-8 bg-slate-200 dark:bg-slate-800 rounded w-3/4" />
            <div className="h-4 bg-slate-200 dark:bg-slate-800 rounded w-1/3" />
            <div className="h-32 bg-slate-100 dark:bg-slate-800/60 rounded mt-6" />
          </div>
        )}

        {!loading && error && (
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-8 text-center space-y-4">
            <div className="w-12 h-12 rounded-full bg-rose-50 dark:bg-rose-950/40 text-rose-500 flex items-center justify-center mx-auto text-xl font-bold">
              !
            </div>
            <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100">
              Unable to load article
            </h2>
            <p className="text-sm text-slate-500 dark:text-slate-400 max-w-md mx-auto">
              {error}
            </p>
            <div className="flex items-center justify-center gap-3 pt-2">
              <button
                type="button"
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-emerald-600 text-white hover:bg-emerald-700 transition"
                onClick={loadArticle}
              >
                Retry
              </button>
              <button
                type="button"
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 transition"
                onClick={onBack}
              >
                Return to News Feed
              </button>
            </div>
          </div>
        )}

        {!loading && !error && article && (
          <article className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 sm:p-10 shadow-xs space-y-8">
            {/* Header Metadata */}
            <div className="space-y-4 border-b border-slate-100 dark:border-slate-800 pb-6">
              <div className="flex items-center gap-2.5 flex-wrap">
                <span className="font-bold text-sm text-slate-800 dark:text-slate-200 tracking-tight">
                  {sourceName}
                </span>

                {article.is_official && (
                  <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-50 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                    Official Regulatory Disclosure
                  </span>
                )}

                {eventLabel && (
                  <span className="text-xs font-semibold px-2.5 py-0.5 rounded-md bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 capitalize">
                    {eventLabel}
                  </span>
                )}
              </div>

              {/* Main Headline */}
              <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 dark:text-slate-100 tracking-tight leading-tight m-0">
                {article.title}
              </h1>

              {/* Publication Timestamp & Sentiment */}
              <div className="flex items-center justify-between gap-4 text-xs text-slate-500 dark:text-slate-400 flex-wrap">
                <time dateTime={article.published_at}>
                  Published: {formatFullDate(article.published_at || article.created_at)}
                </time>

                {sentimentLabel && (
                  <span
                    className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold ${
                      sentimentLabel === 'bullish'
                        ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800'
                        : sentimentLabel === 'bearish'
                        ? 'bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300 border border-rose-200 dark:border-rose-800'
                        : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300 border border-slate-200 dark:border-slate-700'
                    }`}
                  >
                    <span
                      className={`w-2 h-2 rounded-full ${
                        sentimentLabel === 'bullish'
                          ? 'bg-emerald-500'
                          : sentimentLabel === 'bearish'
                          ? 'bg-rose-500'
                          : 'bg-slate-400'
                      }`}
                    />
                    <span className="capitalize">{sentimentLabel} Sentiment</span>
                    {sentimentScore != null && <span>({sentimentScore}%)</span>}
                  </span>
                )}
              </div>
            </div>

            {/* Article Content / Summary */}
            <div className="article-body prose dark:prose-invert max-w-none text-slate-700 dark:text-slate-300 text-base leading-relaxed space-y-4">
              {article.summary ? (
                <p className="m-0 whitespace-pre-line text-slate-800 dark:text-slate-200 text-lg leading-relaxed font-normal">
                  {article.summary}
                </p>
              ) : (
                <p className="text-slate-500 italic">
                  No article excerpt provided by the source. Please refer to the official document link below.
                </p>
              )}
            </div>

            {/* Related Stocks Section with Official Logos & Mosque Shariah Indicator */}
            {article.symbols && article.symbols.length > 0 && (
              <div className="border-t border-slate-100 dark:border-slate-800 pt-6 space-y-3">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  Related Equities
                </h3>
                <div className="flex items-center gap-3 flex-wrap">
                  {article.symbols.map((symObj) => {
                    const sym = typeof symObj === 'string' ? symObj : symObj?.symbol
                    const compName = typeof symObj === 'object' ? symObj?.name : ''
                    if (!sym) return null
                    const isCompliant = kmiSymbolsSet.has(sym.toUpperCase())
                    return (
                      <div
                        key={sym}
                        className="flex items-center gap-3 p-2.5 pr-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-800/50 hover:border-emerald-500/50 transition cursor-pointer"
                        onClick={() => onStock?.(sym)}
                      >
                        <StockLogo symbol={sym} name={compName} size="md" />
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-mono font-bold text-sm text-slate-900 dark:text-slate-100">
                              {sym}
                            </span>
                            {isCompliant && (
                              <ShariahBadge isCompliant={true} size="xs" fullLabel={false} />
                            )}
                          </div>
                          {compName && (
                            <span className="text-xs text-slate-500 block truncate max-w-[200px]">
                              {compName}
                            </span>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {/* Actions: Read Original Document & Back */}
            <div className="border-t border-slate-100 dark:border-slate-800 pt-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              {linkTarget ? (
                <a
                  href={linkTarget}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl font-semibold text-sm bg-emerald-600 hover:bg-emerald-700 text-white shadow-xs transition"
                >
                  Read Full Filing / Source Article
                  <span aria-hidden="true">↗</span>
                </a>
              ) : (
                <div />
              )}

              <button
                type="button"
                className="inline-flex items-center justify-center px-4 py-2.5 rounded-xl text-sm font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition"
                onClick={onBack}
              >
                ← Back to Feed
              </button>
            </div>
          </article>
        )}
      </section>
    </main>
  )
}
