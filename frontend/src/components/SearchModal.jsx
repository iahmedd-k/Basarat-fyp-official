import React, { useState, useEffect, useRef, useCallback } from 'react'
import StockLogo from './StockLogo'
import ShariahBadge from './ShariahBadge'
import { dashboardApi } from '../api/dashboard'

const POPULAR_STOCKS = [
  { symbol: 'OGDC', name: 'Oil & Gas Development Co.', sector: 'OIL & GAS EXPLORATION COMPANIES' },
  { symbol: 'SYS', name: 'Systems Limited', sector: 'TECHNOLOGY & COMMUNICATION' },
  { symbol: 'LUCK', name: 'Lucky Cement Limited', sector: 'CEMENT' },
  { symbol: 'MEBL', name: 'Meezan Bank Limited', sector: 'COMMERCIAL BANKS' },
  { symbol: 'MCB', name: 'MCB Bank Limited', sector: 'COMMERCIAL BANKS' },
  { symbol: 'ENGRO', name: 'Engro Corporation', sector: 'FERTILIZER' },
  { symbol: 'HUBC', name: 'The Hub Power Company', sector: 'POWER GENERATION & DISTRIBUTION' },
  { symbol: 'FFC', name: 'Fauji Fertilizer Company', sector: 'FERTILIZER' },
]

export default function SearchModal({ isOpen, onClose, onSelectStock }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const [recentSearches, setRecentSearches] = useState([])
  const [kmiSet, setKmiSet] = useState(new Set())
  const inputRef = useRef(null)
  const listRef = useRef(null)

  // Fetch KMI-30 Shariah constituents list once on mount
  useEffect(() => {
    dashboardApi.getKmi30Constituents()
      .then((res) => {
        if (res?.constituents && Array.isArray(res.constituents)) {
          setKmiSet(new Set(res.constituents.map((c) => c.symbol.toUpperCase())))
        }
      })
      .catch(() => {})
  }, [])

  // Load recent searches on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem('basarat_recent_searches')
      if (saved) {
        setRecentSearches(JSON.parse(saved).slice(0, 5))
      }
    } catch {
      // Ignore localStorage errors
    }
  }, [isOpen])

  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      setQuery('')
      setResults([])
      setActiveIndex(0)
      setTimeout(() => inputRef.current?.focus(), 50)
      // Prevent body scrolling while modal is open
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [isOpen])

  // Debounced search query
  useEffect(() => {
    const trimmed = query.trim()
    if (trimmed.length < 1) {
      setResults([])
      setLoading(false)
      setActiveIndex(0)
      return undefined
    }

    const timer = setTimeout(() => {
      setLoading(true)
      dashboardApi.searchStocks(trimmed)
        .then((res) => {
          const list = res?.results || []
          setResults(list)
          setActiveIndex(0)
        })
        .catch(() => {
          setResults([])
        })
        .finally(() => setLoading(false))
    }, 180)

    return () => clearTimeout(timer)
  }, [query])

  const handleSelect = useCallback((stock) => {
    if (!stock || !stock.symbol) return
    const sym = stock.symbol.toUpperCase()

    // Update recent searches
    try {
      const updated = [
        { symbol: sym, name: stock.name || sym, sector: stock.sector || '' },
        ...recentSearches.filter((item) => item.symbol !== sym),
      ].slice(0, 6)
      setRecentSearches(updated)
      localStorage.setItem('basarat_recent_searches', JSON.stringify(updated))
    } catch {
      // Ignore storage errors
    }

    onSelectStock?.(sym)
    onClose?.()
  }, [recentSearches, onSelectStock, onClose])

  const clearRecent = (e) => {
    e.stopPropagation()
    setRecentSearches([])
    localStorage.removeItem('basarat_recent_searches')
  }

  // Handle keyboard events (ArrowUp, ArrowDown, Enter, Escape)
  const handleKeyDown = (e) => {
    const activeList = query.trim().length > 0 ? results : (recentSearches.length > 0 ? recentSearches : POPULAR_STOCKS)

    if (e.key === 'Escape') {
      e.preventDefault()
      onClose?.()
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIndex((prev) => (prev < activeList.length - 1 ? prev + 1 : 0))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIndex((prev) => (prev > 0 ? prev - 1 : activeList.length - 1))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (activeList[activeIndex]) {
        handleSelect(activeList[activeIndex])
      }
    }
  }

  // Scroll active item into view
  useEffect(() => {
    if (listRef.current) {
      const activeEl = listRef.current.querySelector('[data-active="true"]')
      if (activeEl) {
        activeEl.scrollIntoView({ block: 'nearest' })
      }
    }
  }, [activeIndex])

  if (!isOpen) return null

  const isSearching = query.trim().length > 0
  const displayItems = isSearching ? results : (recentSearches.length > 0 ? recentSearches : POPULAR_STOCKS)
  const displayTitle = isSearching ? 'Search Results' : (recentSearches.length > 0 ? 'Recent Searches' : 'Popular Stocks')

  return (
    <div
      className="search-modal-backdrop fixed inset-0 z-50 flex items-start justify-center pt-16 sm:pt-24 px-4 bg-black/50 backdrop-blur-xs transition-opacity animate-in fade-in duration-150"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Stock Search Modal"
    >
      <div
        className="w-full max-w-2xl bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 overflow-hidden flex flex-col max-h-[80vh]"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleKeyDown}
      >
        {/* Search Input Bar */}
        <div className="flex items-center px-4 py-3.5 border-b border-slate-100 dark:border-slate-800 gap-3">
          <svg className="w-5 h-5 text-slate-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            ref={inputRef}
            type="text"
            className="search-modal-input w-full bg-transparent text-slate-900 dark:text-slate-100 placeholder-slate-400 text-base outline-hidden"
            placeholder="Search by ticker symbol or company name (e.g. OGDC, Systems)..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-autocomplete="list"
          />
          {query && (
            <button
              type="button"
              onClick={() => { setQuery(''); inputRef.current?.focus() }}
              className="text-xs text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 px-1.5 py-0.5 rounded-sm"
              aria-label="Clear input"
            >
              Clear
            </button>
          )}
          <kbd className="hidden sm:inline-flex items-center px-2 py-0.5 text-xs text-slate-400 bg-slate-100 dark:bg-slate-800 rounded border border-slate-200 dark:border-slate-700 font-sans">
            ESC
          </kbd>
        </div>

        {/* Quick Chips Bar when empty */}
        {!isSearching && (
          <div className="px-4 py-2.5 bg-slate-50 dark:bg-slate-900/50 border-b border-slate-100 dark:border-slate-800 flex items-center gap-2 overflow-x-auto no-scrollbar">
            <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider shrink-0">Trending:</span>
            {POPULAR_STOCKS.slice(0, 6).map((item) => (
              <button
                key={item.symbol}
                type="button"
                onClick={() => handleSelect(item)}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-slate-700 dark:text-slate-300 bg-white dark:bg-slate-800 rounded-full border border-slate-200 dark:border-slate-700 hover:border-emerald-500 hover:text-emerald-600 transition-colors shrink-0 cursor-pointer shadow-2xs"
              >
                <StockLogo ticker={item.symbol} size="xs" />
                <span>{item.symbol}</span>
              </button>
            ))}
          </div>
        )}

        {/* Results List */}
        <div ref={listRef} className="overflow-y-auto p-2 flex-1 divide-y divide-slate-50 dark:divide-slate-800/40">
          <div className="flex items-center justify-between px-3 py-1.5">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">{displayTitle}</span>
            {!isSearching && recentSearches.length > 0 && (
              <button
                type="button"
                onClick={clearRecent}
                className="text-xs text-slate-400 hover:text-rose-500 transition-colors"
              >
                Clear recent
              </button>
            )}
          </div>

          {loading && (
            <div className="p-8 text-center text-slate-400 text-sm animate-pulse">
              Searching PSX companies…
            </div>
          )}

          {!loading && isSearching && results.length === 0 && (
            <div className="p-8 text-center text-slate-500 text-sm">
              No matching stocks found for <strong className="text-slate-800 dark:text-slate-200">"{query}"</strong>.
            </div>
          )}

          {!loading && displayItems.map((item, idx) => {
            const isActive = idx === activeIndex
            const isCompliant = item.is_shariah_compliant === true || kmiSet.has((item.symbol || '').toUpperCase())

            return (
              <div
                key={item.symbol}
                data-active={isActive}
                onClick={() => handleSelect(item)}
                className={`search-result-item flex items-center justify-between p-3 rounded-xl cursor-pointer transition-colors ${
                  isActive
                    ? 'bg-emerald-50/80 dark:bg-emerald-950/30 text-emerald-950 dark:text-emerald-100'
                    : 'hover:bg-slate-50 dark:hover:bg-slate-800/60 text-slate-800 dark:text-slate-200'
                }`}
              >
                <div className="flex items-center gap-3 min-w-0">
                  <StockLogo ticker={item.symbol} companyName={item.name} size="md" />
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-bold text-sm font-mono tracking-tight">{item.symbol}</span>
                      <span className="text-[10px] text-slate-400 font-medium px-1.5 py-0.2 bg-slate-100 dark:bg-slate-800 rounded">PSX</span>
                      {isCompliant && (
                        <ShariahBadge isCompliant={true} size="xs" />
                      )}
                      {item.sector && (
                        <span className="text-[11px] text-slate-400 dark:text-slate-500 truncate max-w-[180px] hidden sm:inline">
                          {item.sector}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-slate-500 dark:text-slate-400 truncate mt-0.5">{item.name || item.symbol}</p>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {isActive && (
                    <span className="text-[11px] text-emerald-700 dark:text-emerald-400 font-medium px-2 py-0.5 rounded bg-emerald-100/60 dark:bg-emerald-900/40 hidden sm:inline-flex items-center gap-1">
                      <span>Jump</span> ↵
                    </span>
                  )}
                  <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
                  </svg>
                </div>
              </div>
            )
          })}
        </div>

        {/* Footer info */}
        <div className="px-4 py-2.5 bg-slate-50 dark:bg-slate-900 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs text-slate-400">
          <div className="flex items-center gap-3">
            <span><kbd className="px-1 py-0.5 bg-white dark:bg-slate-800 border rounded text-[10px]">↑</kbd> <kbd className="px-1 py-0.5 bg-white dark:bg-slate-800 border rounded text-[10px]">↓</kbd> navigate</span>
            <span><kbd className="px-1.5 py-0.5 bg-white dark:bg-slate-800 border rounded text-[10px]">↵</kbd> select</span>
            <span><kbd className="px-1.5 py-0.5 bg-white dark:bg-slate-800 border rounded text-[10px]">esc</kbd> close</span>
          </div>
          <span className="font-medium text-emerald-600 dark:text-emerald-400">Basarat Stock Intelligence</span>
        </div>
      </div>
    </div>
  )
}

