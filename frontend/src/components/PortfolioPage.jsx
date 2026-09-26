import React, { useState, useEffect, useCallback, useMemo } from 'react'
import ProHeader from './ProHeader'
import StockLogo from './StockLogo'
import { dashboardApi } from '../api/dashboard'

// Formatting helpers
function formatNumber(value, fractionDigits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '0'
  return Number(value).toLocaleString('en-PK', {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  })
}

function formatMoney(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return 'PKR 0'
  return `PKR ${formatNumber(value, 0)}`
}

export default function PortfolioPage({
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
  const [data, setData] = useState({
    portfolio: null,
    pnl: null,
    allocation: null,
    performance: null,
    transactions: null,
  })
  const [period, setPeriod] = useState('1M')
  const [activeTab, setActiveTab] = useState('holdings') // 'holdings' | 'transactions' | 'sectors' | 'performance'
  const [searchFilter, setSearchFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [form, setForm] = useState({
    symbol: '',
    transaction_type: 'BUY',
    quantity: '',
    price: '',
    fee: '0',
    transaction_date: new Date().toISOString().slice(0, 10),
  })
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [messageType, setMessageType] = useState('success') // 'success' | 'error'

  // Load all portfolio metrics from AWS backend
  const loadData = useCallback(async (isSilent = false) => {
    if (!isSilent) setLoading(true)
    else setRefreshing(true)

    try {
      const results = await Promise.allSettled([
        dashboardApi.getPortfolio(),
        dashboardApi.getPortfolioPnl(),
        dashboardApi.getPortfolioAllocation(),
        dashboardApi.getPortfolioPerformance(period),
        dashboardApi.getTransactions(),
      ])

      const [portfolio, pnl, allocation, performance, transactions] = results.map((r) =>
        r.status === 'fulfilled' ? r.value : null
      )

      setData((prev) => ({
        portfolio: portfolio ?? prev.portfolio,
        pnl: pnl ?? prev.pnl,
        allocation: allocation ?? prev.allocation,
        performance: performance ?? prev.performance,
        transactions: transactions ?? prev.transactions,
      }))
    } catch (err) {
      console.error('Failed to load portfolio data:', err)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [period])

  useEffect(() => {
    loadData()
  }, [loadData])

  // Save Transaction (Create or Update)
  async function handleSaveTransaction(e) {
    e.preventDefault()
    setSaving(true)
    setMessage('')

    try {
      const payload = {
        quantity: Number(form.quantity),
        price: Number(form.price),
        fee: Number(form.fee || 0),
        transaction_date: form.transaction_date,
      }

      if (editingId) {
        await dashboardApi.updateTransaction(editingId, payload)
        setMessage('Transaction successfully updated.')
        setMessageType('success')
      } else {
        await dashboardApi.createTransaction({
          ...form,
          symbol: form.symbol.trim().toUpperCase(),
          quantity: payload.quantity,
          price: payload.price,
          fee: payload.fee,
        })
        setMessage('Transaction successfully added.')
        setMessageType('success')
      }

      setTimeout(() => {
        setIsModalOpen(false)
        setEditingId(null)
        setForm({
          symbol: '',
          transaction_type: 'BUY',
          quantity: '',
          price: '',
          fee: '0',
          transaction_date: new Date().toISOString().slice(0, 10),
        })
        setMessage('')
      }, 700)

      await loadData(true)
    } catch (error) {
      setMessage(error.message || 'Failed to save transaction.')
      setMessageType('error')
    } finally {
      setSaving(false)
    }
  }

  // Open modal for new trade
  function openNewModal(symbol = '', type = 'BUY') {
    setEditingId(null)
    setForm({
      symbol: symbol || '',
      transaction_type: type,
      quantity: '',
      price: '',
      fee: '0',
      transaction_date: new Date().toISOString().slice(0, 10),
    })
    setMessage('')
    setIsModalOpen(true)
  }

  // Open modal for editing
  function openEditModal(tx) {
    setEditingId(tx.id)
    setForm({
      symbol: tx.symbol,
      transaction_type: tx.transaction_type,
      quantity: String(tx.quantity),
      price: String(tx.price),
      fee: String(tx.fee || 0),
      transaction_date: tx.transaction_date,
    })
    setMessage('')
    setIsModalOpen(true)
  }

  // Delete transaction
  async function handleDeleteTransaction(tx) {
    const confirmText = `Delete the ${tx.transaction_type} transaction for ${tx.symbol}?`
    if (!window.confirm(confirmText)) return

    try {
      await dashboardApi.deleteTransaction(tx.id)
      await loadData(true)
    } catch (error) {
      alert(`Delete failed: ${error.message}`)
    }
  }

  // Derived summaries & metrics
  const summary = data.portfolio?.summary || data.pnl || {}
  const holdings = data.portfolio?.holdings || []
  const transactions = data.transactions?.items || []
  const performanceData = data.performance?.data || []
  const allocation = data.allocation || { by_sector: [], by_stock: [] }

  const totalInvested = Number(summary.total_invested || 0)
  const currentValue = Number(summary.current_value || 0)
  const totalPnl = Number(summary.total_pnl ?? (currentValue - totalInvested))
  const totalPnlPercent = Number(summary.total_pnl_percent ?? (totalInvested > 0 ? (totalPnl / totalInvested) * 100 : 0))
  const todayPnl = Number(summary.today_pnl || 0)

  // Sector Allocation with fallback to holdings
  const sectorAllocationList = useMemo(() => {
    if (allocation.by_sector && allocation.by_sector.length > 0) {
      return allocation.by_sector
    }
    if (!holdings.length) return []
    const map = {}
    let total = 0
    for (const h of holdings) {
      const sec = h.sector || 'Other'
      const val = Number(h.market_value || 0)
      total += val
      map[sec] = (map[sec] || 0) + val
    }
    return Object.entries(map).map(([sec, val]) => ({
      sector: sec,
      market_value: val,
      percentage: total > 0 ? (val / total) * 100 : 0,
    }))
  }, [allocation.by_sector, holdings])

  // Stock Concentration with fallback to holdings
  const stockAllocationList = useMemo(() => {
    if (holdings.length > 0) {
      return holdings.map((h) => ({
        symbol: h.symbol,
        company_name: h.company_name || h.symbol,
        market_value: Number(h.market_value || 0),
        weight: Number(h.portfolio_weight ?? (currentValue > 0 ? (Number(h.market_value || 0) / currentValue) * 100 : 0)),
      }))
    }
    if (allocation.by_stock && allocation.by_stock.length > 0) {
      return allocation.by_stock.map((s) => ({
        symbol: s.symbol,
        company_name: s.symbol,
        market_value: Number(s.market_value || 0),
        weight: Number(s.percentage || 0),
      }))
    }
    return []
  }, [holdings, allocation.by_stock, currentValue])

  // Filtered holdings
  const filteredHoldings = useMemo(() => {
    const q = searchFilter.trim().toLowerCase()
    if (!q) return holdings
    return holdings.filter(
      (h) =>
        h.symbol?.toLowerCase().includes(q) ||
        h.company_name?.toLowerCase().includes(q) ||
        h.sector?.toLowerCase().includes(q)
    )
  }, [holdings, searchFilter])

  // Filtered transactions
  const filteredTransactions = useMemo(() => {
    const q = searchFilter.trim().toLowerCase()
    if (!q) return transactions
    return transactions.filter(
      (tx) =>
        tx.symbol?.toLowerCase().includes(q) ||
        tx.transaction_type?.toLowerCase().includes(q) ||
        tx.transaction_date?.toLowerCase().includes(q)
    )
  }, [transactions, searchFilter])

  // Estimated Outlay in trade modal
  const modalQuantity = Number(form.quantity || 0)
  const modalPrice = Number(form.price || 0)
  const modalFee = Number(form.fee || 0)
  const modalEstimatedOutlay = Math.max(0, modalQuantity * modalPrice + (form.transaction_type === 'BUY' ? modalFee : -modalFee))

  return (
    <main className="dashboard min-h-screen bg-[#f8fafc] dark:bg-slate-950 text-slate-900 dark:text-slate-100 transition-colors">
      <ProHeader
        active="portfolio"
        onDashboard={onDashboard || onBack}
        onMarket={onMarket || (() => {})}
        onPortfolio={onPortfolio || (() => {})}
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

      {/* TOP HERO SECTION (TickerAnalysts Style) */}
      <section className="bg-white dark:bg-slate-900 border-b border-slate-200/80 dark:border-slate-800 pt-8 pb-0">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 pb-6">
            <div>
              {/* Category eyebrow */}
              <p className="text-[11px] font-mono font-semibold tracking-[0.2em] text-slate-400 dark:text-slate-500 uppercase">
                LONG-TERM
              </p>

              {/* HUGE Main Value */}
              <h1
                data-testid="portfolio-hero-value"
                className="text-4xl sm:text-5xl font-black tracking-tight text-slate-900 dark:text-white mt-1.5 font-sans"
              >
                PKR {formatNumber(currentValue, 0)}
              </h1>

              {/* Unrealized & Today Pill Badges */}
              <div className="flex flex-wrap items-center gap-2.5 mt-3">
                {/* Unrealized Return Pill */}
                <div
                  className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-medium border ${
                    totalPnl >= 0
                      ? 'bg-emerald-50/80 text-emerald-700 border-emerald-200/80 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800'
                      : 'bg-rose-50/80 text-rose-700 border-rose-200/80 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800'
                  }`}
                >
                  <span className="text-[10px] font-sans font-bold tracking-wider uppercase text-slate-500 dark:text-slate-400">
                    UNREALIZED
                  </span>
                  <svg className="w-3 h-3 text-slate-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  {totalPnl >= 0 ? (
                    <svg className="w-3 h-3 text-emerald-600 dark:text-emerald-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M7 17L17 7m0 0H8m9 0v9" />
                    </svg>
                  ) : (
                    <svg className="w-3 h-3 text-rose-600 dark:text-rose-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M7 7l10 10m0 0H8m9 0V8" />
                    </svg>
                  )}
                  <span className="font-bold">
                    {totalPnl >= 0 ? '+' : '-'}PKR {formatNumber(Math.abs(totalPnl), 0)} (
                    {totalPnlPercent >= 0 ? '+' : ''}
                    {formatNumber(totalPnlPercent)}%)
                  </span>
                </div>

                {/* Today's Movement Pill */}
                <div
                  className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-medium border ${
                    todayPnl >= 0
                      ? 'bg-emerald-50/80 text-emerald-700 border-emerald-200/80 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800'
                      : 'bg-rose-50/80 text-rose-700 border-rose-200/80 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800'
                  }`}
                >
                  <span className="text-[10px] font-sans font-bold tracking-wider uppercase text-slate-500 dark:text-slate-400">
                    TODAY
                  </span>
                  <svg className="w-3 h-3 text-slate-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  {todayPnl >= 0 ? (
                    <svg className="w-3 h-3 text-emerald-600 dark:text-emerald-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M7 17L17 7m0 0H8m9 0v9" />
                    </svg>
                  ) : (
                    <svg className="w-3 h-3 text-rose-600 dark:text-rose-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M7 7l10 10m0 0H8m9 0V8" />
                    </svg>
                  )}
                  <span className="font-bold">
                    {todayPnl >= 0 ? '+' : '-'}PKR {formatNumber(Math.abs(todayPnl), 0)} (+0.00%)
                  </span>
                </div>
              </div>

              {/* Sub-line Stats */}
              <div className="flex items-center gap-3 mt-3 text-xs font-mono text-slate-500 dark:text-slate-400">
                <span>
                  <span className="font-sans font-semibold tracking-wider uppercase text-[11px] text-slate-400">
                    INVESTED
                  </span>{' '}
                  <strong className="text-slate-800 dark:text-slate-200">
                    PKR {formatNumber(totalInvested, 0)}
                  </strong>
                </span>
                <span>·</span>
                <span>
                  <span className="font-sans font-semibold tracking-wider uppercase text-[11px] text-slate-400">
                    POSITIONS
                  </span>{' '}
                  <strong className="text-slate-800 dark:text-slate-200">{holdings.length}</strong>
                </span>
              </div>
            </div>

            {/* Action Buttons (Right Aligned) */}
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => loadData(true)}
                disabled={refreshing}
                className="inline-flex items-center justify-center p-2.5 rounded-full border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-50 dark:hover:bg-slate-850 transition-colors shadow-2xs text-xs cursor-pointer"
                title="Refresh Portfolio"
                aria-label="Refresh Portfolio"
              >
                <svg
                  className={`w-4 h-4 ${refreshing ? 'animate-spin text-emerald-600' : ''}`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                  />
                </svg>
              </button>

              <button
                type="button"
                data-testid="portfolio-record-btn"
                onClick={() => openNewModal()}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs shadow-xs hover:shadow-sm transition-all cursor-pointer"
              >
                <span className="text-base leading-none font-bold">+</span>
                <span>Buy / Sell</span>
              </button>
            </div>
          </div>

          {/* Underlined Tab Row */}
          <div className="flex items-center gap-8 border-b border-slate-200 dark:border-slate-800">
            <button
              type="button"
              data-testid="portfolio-tab-holdings"
              onClick={() => setActiveTab('holdings')}
              className={`flex items-center gap-2 pb-3 text-xs font-semibold cursor-pointer transition-colors relative ${
                activeTab === 'holdings'
                  ? 'text-slate-900 dark:text-white font-bold'
                  : 'text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
              }`}
            >
              <span>Holdings</span>
              <span
                className={`px-1.5 py-0.2 rounded-full text-[10px] font-bold font-mono ${
                  activeTab === 'holdings'
                    ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-900'
                    : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300'
                }`}
              >
                {holdings.length}
              </span>
              {activeTab === 'holdings' && (
                <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-slate-900 dark:bg-white rounded-full" />
              )}
            </button>

            <button
              type="button"
              data-testid="portfolio-tab-transactions"
              onClick={() => setActiveTab('transactions')}
              className={`flex items-center gap-2 pb-3 text-xs font-semibold cursor-pointer transition-colors relative ${
                activeTab === 'transactions'
                  ? 'text-slate-900 dark:text-white font-bold'
                  : 'text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
              }`}
            >
              <span>Transactions</span>
              <span
                className={`px-1.5 py-0.2 rounded-full text-[10px] font-bold font-mono ${
                  activeTab === 'transactions'
                    ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-900'
                    : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300'
                }`}
              >
                {transactions.length}
              </span>
              {activeTab === 'transactions' && (
                <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-slate-900 dark:bg-white rounded-full" />
              )}
            </button>

            <button
              type="button"
              data-testid="portfolio-tab-sectors"
              onClick={() => setActiveTab('sectors')}
              className={`flex items-center gap-2 pb-3 text-xs font-semibold cursor-pointer transition-colors relative ${
                activeTab === 'sectors'
                  ? 'text-slate-900 dark:text-white font-bold'
                  : 'text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
              }`}
            >
              <span>Sectors</span>
              <span
                className={`px-1.5 py-0.2 rounded-full text-[10px] font-bold font-mono ${
                  activeTab === 'sectors'
                    ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-900'
                    : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300'
                }`}
              >
                {sectorAllocationList.length}
              </span>
              {activeTab === 'sectors' && (
                <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-slate-900 dark:bg-white rounded-full" />
              )}
            </button>

            <button
              type="button"
              data-testid="portfolio-tab-performance"
              onClick={() => setActiveTab('performance')}
              className={`flex items-center gap-2 pb-3 text-xs font-semibold cursor-pointer transition-colors relative ${
                activeTab === 'performance'
                  ? 'text-slate-900 dark:text-white font-bold'
                  : 'text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
              }`}
            >
              <span>Performance</span>
              <span
                className={`px-1.5 py-0.2 rounded-full text-[10px] font-bold font-mono ${
                  activeTab === 'performance'
                    ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-900'
                    : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300'
                }`}
              >
                Trend
              </span>
              {activeTab === 'performance' && (
                <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-slate-900 dark:bg-white rounded-full" />
              )}
            </button>
          </div>
        </div>
      </section>

      {/* LOWER CONTENT AREA */}
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-4">
        {/* Search bar & Positions Counter Row */}
        <div className="flex items-center justify-between gap-4">
          <div className="relative w-full max-w-xs">
            <svg
              className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              placeholder="Search by symbol or company..."
              className="w-full h-9 pl-9 pr-4 text-xs rounded-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-800 dark:text-slate-200 placeholder-slate-400 focus:outline-hidden focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 shadow-2xs transition-all"
            />
          </div>

          <div className="text-[11px] font-mono font-semibold uppercase tracking-wider text-slate-400 whitespace-nowrap">
            {filteredHoldings.length} {filteredHoldings.length === 1 ? 'POSITION' : 'POSITIONS'}
          </div>
        </div>

        {/* TAB 1: HOLDINGS */}
        {activeTab === 'holdings' && (
          <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/80 dark:border-slate-800 shadow-2xs overflow-hidden">
            {loading ? (
              <div className="py-16 text-center text-xs text-slate-400 animate-pulse">
                Loading live positions…
              </div>
            ) : filteredHoldings.length === 0 ? (
              /* EXACT EMPTY STATE MATCHING SCREENSHOT */
              <div className="py-16 px-4 text-center">
                <div className="w-12 h-12 mx-auto rounded-full bg-slate-50 dark:bg-slate-800/80 border border-slate-100 dark:border-slate-700/60 flex items-center justify-center text-slate-400 mb-3.5">
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="1.5"
                      d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"
                    />
                  </svg>
                </div>
                <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                  {searchFilter ? 'No matching holdings found' : 'No holdings yet'}
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 mb-5">
                  {searchFilter
                    ? `No positions match "${searchFilter}". Clear search to view all positions.`
                    : 'Add your first transaction to see holdings and P&L.'}
                </p>
                {!searchFilter && (
                  <button
                    type="button"
                    onClick={() => openNewModal()}
                    className="inline-flex items-center gap-1.5 text-[11px] font-mono font-bold tracking-widest text-slate-400 hover:text-emerald-600 dark:hover:text-emerald-400 uppercase transition-colors cursor-pointer"
                  >
                    <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M5 10l7-7m0 0l7 7m-7-7v18" />
                    </svg>
                    <span>USE BUY / SELL TO LOG YOUR FIRST TRANSACTION</span>
                  </button>
                )}
              </div>
            ) : (
              /* HOLDINGS TABLE */
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="bg-slate-50/60 dark:bg-slate-850/60 border-b border-slate-200/80 dark:border-slate-800 text-slate-400 font-semibold uppercase tracking-wider text-[10px]">
                      <th className="py-3 px-5">Asset / Symbol</th>
                      <th className="py-3 px-4 text-right">Shares</th>
                      <th className="py-3 px-4 text-right">Avg Cost</th>
                      <th className="py-3 px-4 text-right">LTP (Price)</th>
                      <th className="py-3 px-4 text-right">Market Value</th>
                      <th className="py-3 px-4 text-right">Unrealized P&amp;L</th>
                      <th className="py-3 px-4 text-right">Weight</th>
                      <th className="py-3 px-5 text-center">Quick Trade</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {filteredHoldings.map((h) => {
                      const pnlVal = Number(h.unrealized_pnl ?? ((Number(h.current_price || 0) - Number(h.average_cost || 0)) * Number(h.quantity || 0)))
                      const pnlPct = Number(h.unrealized_pnl_percent ?? (Number(h.average_cost || 0) > 0 ? ((Number(h.current_price || 0) - Number(h.average_cost || 0)) / Number(h.average_cost || 0)) * 100 : 0))
                      const weight = Number(h.portfolio_weight ?? (currentValue > 0 ? (Number(h.market_value || 0) / currentValue) * 100 : 0))

                      return (
                        <tr
                          key={h.symbol}
                          className="hover:bg-slate-50/70 dark:hover:bg-slate-850/50 transition-colors group"
                        >
                          {/* Symbol & Company */}
                          <td className="py-3.5 px-5">
                            <button
                              type="button"
                              onClick={() => onStock?.(h.symbol)}
                              className="flex items-center gap-2.5 text-left group-hover:text-emerald-600 dark:group-hover:text-emerald-400 transition-colors cursor-pointer"
                            >
                              <StockLogo symbol={h.symbol} name={h.company_name} size="sm" />
                              <div>
                                <div className="flex items-center gap-1.5">
                                  <strong className="font-mono text-xs font-bold text-slate-900 dark:text-white">
                                    {h.symbol}
                                  </strong>
                                  {h.sector && (
                                    <span className="hidden md:inline-block px-1.5 py-0.2 rounded text-[10px] bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400">
                                      {h.sector}
                                    </span>
                                  )}
                                </div>
                                <span className="block text-[11px] text-slate-500 dark:text-slate-400 truncate max-w-[160px]">
                                  {h.company_name || 'PSX Listed'}
                                </span>
                              </div>
                            </button>
                          </td>

                          {/* Shares */}
                          <td className="py-3.5 px-4 text-right font-mono font-medium text-slate-800 dark:text-slate-200">
                            {formatNumber(h.quantity, 0)}
                          </td>

                          {/* Avg Cost */}
                          <td className="py-3.5 px-4 text-right font-mono text-slate-600 dark:text-slate-400">
                            {formatNumber(h.average_cost)}
                          </td>

                          {/* LTP */}
                          <td className="py-3.5 px-4 text-right font-mono font-semibold text-slate-900 dark:text-white">
                            {formatNumber(h.current_price)}
                          </td>

                          {/* Market Value */}
                          <td className="py-3.5 px-4 text-right font-mono font-bold text-slate-900 dark:text-white">
                            {formatMoney(h.market_value)}
                          </td>

                          {/* Unrealized P&L */}
                          <td className="py-3.5 px-4 text-right font-mono">
                            <span
                              className={`font-semibold block ${
                                pnlVal >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'
                              }`}
                            >
                              {pnlVal >= 0 ? '+' : ''}
                              {formatMoney(pnlVal)}
                            </span>
                            <span
                              className={`text-[10px] font-bold block ${
                                pnlPct >= 0 ? 'text-emerald-700 dark:text-emerald-400' : 'text-rose-700 dark:text-rose-400'
                              }`}
                            >
                              {pnlPct >= 0 ? '+' : ''}
                              {formatNumber(pnlPct)}%
                            </span>
                          </td>

                          {/* Weight */}
                          <td className="py-3.5 px-4 text-right">
                            <div className="flex items-center justify-end gap-2">
                              <div className="w-14 h-1.5 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
                                <div
                                  className="h-full bg-emerald-500 rounded-full"
                                  style={{ width: `${Math.min(weight, 100)}%` }}
                                />
                              </div>
                              <span className="font-mono text-xs text-slate-600 dark:text-slate-400">
                                {formatNumber(weight, 1)}%
                              </span>
                            </div>
                          </td>

                          {/* Actions */}
                          <td className="py-3.5 px-5 text-center">
                            <div className="inline-flex items-center gap-1">
                              <button
                                type="button"
                                onClick={() => openNewModal(h.symbol, 'BUY')}
                                className="px-2 py-1 rounded bg-emerald-50 hover:bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:hover:bg-emerald-900/60 dark:text-emerald-300 text-[10px] font-bold cursor-pointer transition-colors"
                                title={`Buy more ${h.symbol}`}
                              >
                                + Buy
                              </button>
                              <button
                                type="button"
                                onClick={() => openNewModal(h.symbol, 'SELL')}
                                className="px-2 py-1 rounded bg-rose-50 hover:bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:hover:bg-rose-900/60 dark:text-rose-300 text-[10px] font-bold cursor-pointer transition-colors"
                                title={`Sell ${h.symbol}`}
                              >
                                - Sell
                              </button>
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: TRANSACTIONS */}
        {activeTab === 'transactions' && (
          <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/80 dark:border-slate-800 shadow-2xs overflow-hidden">
            {filteredTransactions.length === 0 ? (
              <div className="py-16 px-4 text-center">
                <div className="w-12 h-12 mx-auto rounded-full bg-slate-50 dark:bg-slate-800/80 border border-slate-100 dark:border-slate-700/60 flex items-center justify-center text-slate-400 mb-3.5">
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="1.5"
                      d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
                    />
                  </svg>
                </div>
                <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                  {searchFilter ? 'No matching transactions' : 'No transactions recorded yet'}
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 mb-5">
                  {searchFilter
                    ? `No transactions match "${searchFilter}". Clear search to view all.`
                    : 'Execute your first BUY or SELL order to establish an audit log.'}
                </p>
                {!searchFilter && (
                  <button
                    type="button"
                    onClick={() => openNewModal()}
                    className="inline-flex items-center gap-1.5 text-[11px] font-mono font-bold tracking-widest text-slate-400 hover:text-emerald-600 dark:hover:text-emerald-400 uppercase transition-colors cursor-pointer"
                  >
                    <svg className="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M5 10l7-7m0 0l7 7m-7-7v18" />
                    </svg>
                    <span>USE BUY / SELL TO LOG YOUR FIRST TRANSACTION</span>
                  </button>
                )}
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="bg-slate-50/60 dark:bg-slate-850/60 border-b border-slate-200/80 dark:border-slate-800 text-slate-400 font-semibold uppercase tracking-wider text-[10px]">
                      <th className="py-3 px-5">Date</th>
                      <th className="py-3 px-4">Asset</th>
                      <th className="py-3 px-4">Type</th>
                      <th className="py-3 px-4 text-right">Quantity</th>
                      <th className="py-3 px-4 text-right">Price (PKR)</th>
                      <th className="py-3 px-4 text-right">Fee (PKR)</th>
                      <th className="py-3 px-4 text-right">Total Outlay</th>
                      <th className="py-3 px-5 text-center">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {filteredTransactions.map((tx) => {
                      const totalOutlay = Number(tx.quantity || 0) * Number(tx.price || 0) + Number(tx.fee || 0)
                      return (
                        <tr
                          key={tx.id}
                          className="hover:bg-slate-50/70 dark:hover:bg-slate-850/50 transition-colors"
                        >
                          <td className="py-3.5 px-5 font-mono text-slate-600 dark:text-slate-400">
                            {tx.transaction_date}
                          </td>
                          <td className="py-3.5 px-4">
                            <div className="flex items-center gap-2">
                              <StockLogo symbol={tx.symbol} size="xs" />
                              <strong className="font-mono font-bold text-slate-900 dark:text-white">
                                {tx.symbol}
                              </strong>
                            </div>
                          </td>
                          <td className="py-3.5 px-4">
                            <span
                              className={`inline-flex px-2 py-0.5 rounded text-[10px] font-bold font-mono uppercase ${
                                tx.transaction_type === 'BUY'
                                  ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300'
                                  : 'bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300'
                              }`}
                            >
                              {tx.transaction_type}
                            </span>
                          </td>
                          <td className="py-3.5 px-4 text-right font-mono font-medium text-slate-800 dark:text-slate-200">
                            {formatNumber(tx.quantity, 0)}
                          </td>
                          <td className="py-3.5 px-4 text-right font-mono text-slate-800 dark:text-slate-200">
                            {formatNumber(tx.price)}
                          </td>
                          <td className="py-3.5 px-4 text-right font-mono text-slate-500 dark:text-slate-400">
                            {formatNumber(tx.fee)}
                          </td>
                          <td className="py-3.5 px-4 text-right font-mono font-bold text-slate-900 dark:text-white">
                            {formatMoney(totalOutlay)}
                          </td>
                          <td className="py-3.5 px-5 text-center">
                            <div className="inline-flex items-center gap-2">
                              <button
                                type="button"
                                onClick={() => openEditModal(tx)}
                                className="text-slate-500 hover:text-slate-900 dark:hover:text-white font-medium text-xs cursor-pointer"
                              >
                                Edit
                              </button>
                              <button
                                type="button"
                                onClick={() => handleDeleteTransaction(tx)}
                                className="text-rose-500 hover:text-rose-700 font-medium text-xs cursor-pointer"
                              >
                                Delete
                              </button>
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* TAB 3: SECTORS */}
        {activeTab === 'sectors' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            {/* Sector Diversification */}
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/80 dark:border-slate-800 shadow-2xs p-6 space-y-4">
              <div className="border-b border-slate-100 dark:border-slate-800 pb-3">
                <h2 className="text-sm font-bold text-slate-900 dark:text-white">Sector Diversification</h2>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Allocation breakdown across PSX industry segments.
                </p>
              </div>

              {sectorAllocationList.length === 0 ? (
                <div className="py-12 text-center text-xs text-slate-400">
                  No sector allocation available. Add holdings to see your portfolio diversification.
                </div>
              ) : (
                <div className="space-y-3.5">
                  {sectorAllocationList.map((item, idx) => {
                    const pct = Number(item.percentage || 0)
                    return (
                      <div key={item.sector || idx} className="space-y-1.5">
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-medium text-slate-800 dark:text-slate-200">
                            {item.sector || 'Other'}
                          </span>
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-slate-500 dark:text-slate-400 text-[11px]">
                              {formatMoney(item.market_value)}
                            </span>
                            <span className="font-mono font-semibold text-emerald-700 dark:text-emerald-400">
                              {formatNumber(pct, 1)}%
                            </span>
                          </div>
                        </div>
                        <div className="w-full h-2 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
                          <div
                            className="h-full bg-emerald-500 rounded-full transition-all duration-500"
                            style={{ width: `${Math.min(pct, 100)}%` }}
                          />
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>

            {/* Stock Concentration */}
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/80 dark:border-slate-800 shadow-2xs p-6 space-y-4">
              <div className="border-b border-slate-100 dark:border-slate-800 pb-3">
                <h2 className="text-sm font-bold text-slate-900 dark:text-white">Stock Concentration</h2>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Weight of each individual stock in your total portfolio.
                </p>
              </div>

              {stockAllocationList.length === 0 ? (
                <div className="py-12 text-center text-xs text-slate-400">
                  No positions available to calculate stock concentration.
                </div>
              ) : (
                <div className="space-y-3">
                  {stockAllocationList.map((h) => {
                    const weight = Number(h.weight || 0)
                    return (
                      <div
                        key={h.symbol}
                        className="flex items-center justify-between text-xs p-2 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-850/60 transition-colors"
                      >
                        <div className="flex items-center gap-2.5">
                          <StockLogo symbol={h.symbol} name={h.company_name} size="xs" />
                          <div>
                            <strong className="font-mono font-bold text-slate-900 dark:text-white block">
                              {h.symbol}
                            </strong>
                            <span className="text-[10px] text-slate-400 truncate block max-w-[140px]">
                              {h.company_name || 'PSX'}
                            </span>
                          </div>
                        </div>

                        <div className="flex items-center gap-3">
                          <span className="font-mono text-slate-700 dark:text-slate-300 font-medium">
                            {formatMoney(h.market_value)}
                          </span>
                          <span className="w-12 text-right font-mono font-bold text-emerald-700 dark:text-emerald-400">
                            {formatNumber(weight, 1)}%
                          </span>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 4: PERFORMANCE */}
        {activeTab === 'performance' && (
          <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/80 dark:border-slate-800 shadow-2xs p-6 space-y-5">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 dark:border-slate-800 pb-4">
              <div>
                <h2 className="text-sm font-bold text-slate-900 dark:text-white">Portfolio Valuation Trend</h2>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Historical equity curve and returns over the selected time horizon.
                </p>
              </div>

              {/* Period Selectors */}
              <div className="inline-flex items-center p-0.5 rounded-lg bg-slate-100 dark:bg-slate-800 text-xs">
                {['1W', '1M', '3M', '1Y', 'ALL'].map((p) => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => setPeriod(p)}
                    className={`px-3 py-1 rounded-md font-semibold transition-all cursor-pointer ${
                      period === p
                        ? 'bg-white dark:bg-slate-900 text-emerald-700 dark:text-emerald-400 shadow-2xs'
                        : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                    }`}
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>

            {performanceData.length === 0 ? (
              <div className="py-12 px-4 text-center">
                <div className="w-10 h-10 mx-auto rounded-full bg-slate-50 dark:bg-slate-800 flex items-center justify-center text-slate-400 mb-3">
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="1.5"
                      d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z"
                    />
                  </svg>
                </div>
                <h3 className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                  Performance History Initializing
                </h3>
                <p className="text-[11px] text-slate-500 dark:text-slate-400 max-w-sm mx-auto mt-1">
                  Historical valuation curves accumulate across consecutive market sessions. Current live portfolio valuation is{' '}
                  <strong className="text-slate-700 dark:text-slate-300 font-mono">
                    {formatMoney(currentValue)}
                  </strong>
                  .
                </p>
              </div>
            ) : (
              <div>
                <div className="h-64 w-full relative">
                  <svg className="w-full h-full overflow-visible" preserveAspectRatio="none" viewBox="0 0 600 200">
                    <line x1="0" y1="50" x2="600" y2="50" stroke="currentColor" className="text-slate-100 dark:text-slate-800" strokeDasharray="3 3" />
                    <line x1="0" y1="100" x2="600" y2="100" stroke="currentColor" className="text-slate-100 dark:text-slate-800" strokeDasharray="3 3" />
                    <line x1="0" y1="150" x2="600" y2="150" stroke="currentColor" className="text-slate-100 dark:text-slate-800" strokeDasharray="3 3" />
                  </svg>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* TRADE MODAL (+ Buy / Sell) */}
      {isModalOpen && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs animate-in fade-in duration-200"
        >
          <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-xl border border-slate-200 dark:border-slate-800 w-full max-w-md overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 dark:border-slate-800">
              <div>
                <h2 className="text-base font-bold text-slate-900 dark:text-white">
                  {editingId ? 'Edit PSX Trade' : 'Record New PSX Trade'}
                </h2>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Log a buy or sell transaction to update your holdings.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
                aria-label="Close modal"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <form onSubmit={handleSaveTransaction} className="p-6 space-y-4">
              {/* Order Type Toggle */}
              <div>
                <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1.5">
                  Order Type
                </label>
                <div className="grid grid-cols-2 gap-2 p-1 rounded-xl bg-slate-100 dark:bg-slate-800">
                  <button
                    type="button"
                    disabled={Boolean(editingId)}
                    onClick={() => setForm({ ...form, transaction_type: 'BUY' })}
                    className={`py-2 text-xs font-bold rounded-lg transition-all cursor-pointer ${
                      form.transaction_type === 'BUY'
                        ? 'bg-emerald-600 text-white shadow-xs'
                        : 'text-slate-600 dark:text-slate-400 hover:text-slate-900'
                    }`}
                  >
                    BUY (Acquire)
                  </button>
                  <button
                    type="button"
                    disabled={Boolean(editingId)}
                    onClick={() => setForm({ ...form, transaction_type: 'SELL' })}
                    className={`py-2 text-xs font-bold rounded-lg transition-all cursor-pointer ${
                      form.transaction_type === 'SELL'
                        ? 'bg-rose-600 text-white shadow-xs'
                        : 'text-slate-600 dark:text-slate-400 hover:text-slate-900'
                    }`}
                  >
                    SELL (Liquidate)
                  </button>
                </div>
              </div>

              {/* Symbol Input */}
              <div>
                <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                  PSX Symbol
                </label>
                <input
                  required
                  disabled={Boolean(editingId)}
                  type="text"
                  value={form.symbol}
                  onChange={(e) => setForm({ ...form, symbol: e.target.value.toUpperCase() })}
                  placeholder="E.G. OGDC, HBL, SYS"
                  className="w-full h-10 px-3 font-mono font-bold text-xs uppercase rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white placeholder-slate-400 focus:outline-hidden focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
                />
              </div>

              {/* Execution Date */}
              <div>
                <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                  Execution Date
                </label>
                <input
                  required
                  type="date"
                  value={form.transaction_date}
                  onChange={(e) => setForm({ ...form, transaction_date: e.target.value })}
                  className="w-full h-10 px-3 text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-hidden focus:border-emerald-500"
                />
              </div>

              {/* Shares & Price per Share */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                    Shares (Quantity)
                  </label>
                  <input
                    required
                    min="0.0001"
                    step="any"
                    type="number"
                    value={form.quantity}
                    onChange={(e) => setForm({ ...form, quantity: e.target.value })}
                    placeholder="e.g. 500"
                    className="w-full h-10 px-3 font-mono text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-hidden focus:border-emerald-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                    Price per Share (PKR)
                  </label>
                  <input
                    required
                    min="0.0001"
                    step="any"
                    type="number"
                    value={form.price}
                    onChange={(e) => setForm({ ...form, price: e.target.value })}
                    placeholder="e.g. 124.50"
                    className="w-full h-10 px-3 font-mono text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-hidden focus:border-emerald-500"
                  />
                </div>
              </div>

              {/* Commission / Fee */}
              <div>
                <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                  Commission / Fee (PKR)
                </label>
                <input
                  min="0"
                  step="any"
                  type="number"
                  value={form.fee}
                  onChange={(e) => setForm({ ...form, fee: e.target.value })}
                  placeholder="0"
                  className="w-full h-10 px-3 font-mono text-xs rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-hidden focus:border-emerald-500"
                />
              </div>

              {/* Estimated Total Outlay Box */}
              <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200/60 dark:border-slate-700/60 flex items-center justify-between text-xs">
                <span className="text-slate-500 dark:text-slate-400">Estimated Total Outlay:</span>
                <span className="font-mono font-bold text-slate-900 dark:text-white">
                  {formatMoney(modalEstimatedOutlay)}
                </span>
              </div>

              {message && (
                <p
                  className={`text-xs p-2 rounded-lg ${
                    messageType === 'success'
                      ? 'bg-emerald-50 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300'
                      : 'bg-rose-50 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300'
                  }`}
                >
                  {message}
                </p>
              )}

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 text-xs font-semibold rounded-xl text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 cursor-pointer transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="px-5 py-2 text-xs font-bold rounded-xl text-white bg-emerald-600 hover:bg-emerald-500 shadow-xs cursor-pointer transition-colors disabled:opacity-50"
                >
                  {saving ? 'Saving…' : 'Confirm & Save'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </main>
  )
}
