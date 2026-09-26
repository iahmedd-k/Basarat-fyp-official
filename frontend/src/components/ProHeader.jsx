import React, { useState, useEffect, useRef } from 'react'
import { getStoredUser } from '../api/auth'
import { dashboardApi } from '../api/dashboard'

export default function ProHeader({
  active = 'dashboard',
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
  onOpenSearch,
  onLogin,
  onRequireAuth,
}) {
  const user = getStoredUser()
  const name = user?.full_name || user?.username || 'Investor'
  const initials = name.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p.charAt(0).toUpperCase()).join('') || 'I'

  const [marketStatus, setMarketStatus] = useState(null)
  const [moreMenuOpen, setMoreMenuOpen] = useState(false)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const moreMenuRef = useRef(null)
  const userMenuRef = useRef(null)

  // Fetch market status
  useEffect(() => {
    let mounted = true
    dashboardApi.getMarketStatus()
      .then((res) => { if (mounted) setMarketStatus(res) })
      .catch(() => {})

    return () => { mounted = false }
  }, [user?.id, user?.email])

  // Close menus on outside click
  useEffect(() => {
    function handleClickOutside(e) {
      if (moreMenuRef.current && !moreMenuRef.current.contains(e.target)) {
        setMoreMenuOpen(false)
      }
      if (userMenuRef.current && !userMenuRef.current.contains(e.target)) {
        setUserMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const isMarketOpen = marketStatus?.status === 'market_hours' || marketStatus?.is_market_open || marketStatus?.market_open

  // Redirect or open auth modal if user is not authenticated
  const handleProtectedAction = (action) => {
    if (!user) {
      if (onRequireAuth) {
        onRequireAuth()
      } else if (onLogin) {
        onLogin()
      } else {
        window.dispatchEvent(new CustomEvent('open-auth-modal', { detail: { mode: 'login' } }))
      }
      return
    }
    action?.()
  }

  // 5 Main Directly Visible Pages
  // Main Directly Visible Pages
  const navLinks = [
    {
      id: 'dashboard',
      label: user ? 'Dashboard' : 'Home',
      icon: (
        <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
          <polyline points="9 22 9 12 15 12 15 22" />
        </svg>
      ),
      onClick: onDashboard,
    },
    {
      id: 'market',
      label: 'Stocks',
      icon: (
        <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <line x1="18" y1="20" x2="18" y2="10" />
          <line x1="12" y1="20" x2="12" y2="4" />
          <line x1="6" y1="20" x2="6" y2="14" />
        </svg>
      ),
      onClick: onMarket,
    },
    {
      id: 'news',
      label: 'Market Activity',
      icon: (
        <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
        </svg>
      ),
      onClick: onNews,
    },
    {
      id: 'recommendations',
      label: 'Recommendations',
      icon: (
        <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <circle cx="12" cy="12" r="10" />
          <circle cx="12" cy="12" r="6" />
          <circle cx="12" cy="12" r="2" />
        </svg>
      ),
      onClick: onRecommendations,
    },
  ]

  // Remaining Active Pages in More ▾ (100% Clean Vector SVGs, zero emojis)
  // Remaining Active Pages in More ▾ (including Sentiment)
  const moreLinks = [
    {
      id: 'sentiment',
      label: 'Sentiment',
      icon: (
        <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <circle cx="12" cy="12" r="10" />
          <path d="M8 14s1.5 2 4 2 4-2 4-2" />
          <line x1="9" y1="9" x2="9.01" y2="9" />
          <line x1="15" y1="9" x2="15.01" y2="9" />
        </svg>
      ),
      onClick: onSentiment,
    },
    {
      id: 'watchlist',
      label: 'Watchlist',
      icon: (
        <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
        </svg>
      ),
      onClick: () => handleProtectedAction(onWatchlist),
    },
    {
      id: 'portfolio',
      label: 'Portfolio',
      icon: (
        <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <rect x="2" y="7" width="20" height="14" rx="2" ry="2" />
          <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
        </svg>
      ),
      onClick: () => handleProtectedAction(onPortfolio),
    },
    {
      id: 'shariah',
      label: 'Shariah Screening',
      icon: (
        <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
        </svg>
      ),
      onClick: () => handleProtectedAction(onShariah),
    },
    {
      id: 'risk',
      label: 'Risk Analytics',
      icon: (
        <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <circle cx="12" cy="12" r="10" />
          <path d="m4.93 4.93 14.14 14.14" />
        </svg>
      ),
      onClick: onRisk,
    },
  ]

  const isMoreActive = ['sentiment', 'watchlist', 'portfolio', 'shariah', 'risk'].includes(active)

  return (
    <header className="pro-header sticky top-0 z-40 w-full bg-white/95 dark:bg-slate-900/95 backdrop-blur-md border-b border-slate-200/80 dark:border-slate-800/80 transition-colors">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between gap-3">
        
        {/* Left: Brand Identity */}
        <div className="flex items-center gap-4 shrink-0">
          <button
            type="button"
            onClick={onDashboard}
            className="flex items-center gap-2.5 text-left group cursor-pointer focus:outline-hidden"
            aria-label="Basarat Home"
          >
            {/* Custom Brand Mark */}
            <div className="flex items-end gap-0.5 h-6">
              <span className="w-1.5 h-3 rounded-full bg-emerald-500/70 group-hover:bg-emerald-500 transition-colors" />
              <span className="w-1.5 h-4.5 rounded-full bg-emerald-600 transition-colors" />
              <span className="w-1.5 h-6 rounded-full bg-emerald-400 group-hover:bg-emerald-300 transition-colors" />
            </div>
            <div className="flex flex-col">
              <div className="flex items-center gap-1.5">
                <span className="font-bold text-base tracking-tight text-slate-900 dark:text-slate-100 font-sans">
                  Basarat
                </span>
                <span className="inline-flex items-center px-1.5 py-0.2 rounded text-[10px] font-semibold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                  PSX
                </span>
              </div>
            </div>
          </button>
        </div>

        {/* Center: Search Trigger Button (TickerAnalysts style pill) */}
        <div className="flex-1 max-w-[220px] min-w-[140px] hidden md:block shrink">
          <button
            type="button"
            onClick={onOpenSearch}
            className="w-full h-8 flex items-center justify-between px-3 rounded-full bg-slate-100 hover:bg-slate-200/80 dark:bg-slate-800 dark:hover:bg-slate-750 border border-slate-200 dark:border-slate-700 text-slate-400 dark:text-slate-400 text-xs transition-all shadow-2xs group cursor-pointer overflow-hidden whitespace-nowrap"
            aria-label="Search stocks"
          >
            <div className="flex items-center gap-2 overflow-hidden min-w-0">
              <svg className="w-3.5 h-3.5 text-slate-400 group-hover:text-emerald-500 shrink-0 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <span className="truncate text-slate-500 dark:text-slate-400 group-hover:text-slate-700 dark:group-hover:text-slate-200 transition-colors">
                Search stocks...
              </span>
            </div>
            <kbd className="shrink-0 inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[10px] font-sans font-medium text-slate-400 dark:text-slate-500 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-sm ml-1.5">
              <span className="text-xs">⌘</span>K
            </kbd>
          </button>
        </div>

        {/* Right: Primary Navigation Links */}
        <nav className="flex items-center gap-1 shrink-0">
          {/* Mobile search button */}
          <button
            type="button"
            onClick={onOpenSearch}
            className="p-2 text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-100 md:hidden"
            aria-label="Search"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </button>

          {/* Desktop Nav Links (5 Direct Pages + More ▾) */}
          <div className="hidden md:flex items-center gap-1">
            {navLinks.map((link) => {
              const isActive = active === link.id
              return (
                <button
                  key={link.id}
                  type="button"
                  onClick={link.onClick}
                  className={`inline-flex items-center gap-1.5 whitespace-nowrap px-2.5 py-1.5 text-xs font-medium rounded-lg transition-colors cursor-pointer ${
                    isActive
                      ? 'bg-emerald-50 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-300 font-semibold'
                      : 'text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-white'
                  }`}
                >
                  {link.icon && <span className="shrink-0 text-slate-500 dark:text-slate-400">{link.icon}</span>}
                  <span>{link.label}</span>
                </button>
              )
            })}

            {/* "More" Dropdown Menu */}
            <div className="relative" ref={moreMenuRef}>
              <button
                type="button"
                onClick={() => setMoreMenuOpen(!moreMenuOpen)}
                className={`flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium rounded-lg transition-colors cursor-pointer ${
                  moreMenuOpen || isMoreActive
                    ? 'bg-emerald-50 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-300 font-semibold'
                    : 'text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'
                }`}
                aria-expanded={moreMenuOpen}
              >
                <span>More</span>
                <svg className="w-3.5 h-3.5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {moreMenuOpen && (
                <div className="absolute right-0 mt-2 w-56 bg-white dark:bg-slate-900 rounded-xl shadow-lg border border-slate-200 dark:border-slate-800 py-1.5 z-50 animate-in fade-in zoom-in-95 duration-100">
                  {moreLinks.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => {
                        setMoreMenuOpen(false)
                        item.onClick?.()
                      }}
                      className={`w-full flex items-center justify-between px-3.5 py-2 text-xs text-left cursor-pointer transition-colors ${
                        active === item.id
                          ? 'bg-emerald-50 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300 font-medium'
                          : 'text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800'
                      }`}
                    >
                      <div className="flex items-center gap-2.5">
                        <span className="w-4 flex items-center justify-center text-slate-400">{item.icon}</span>
                        <span>{item.label}</span>
                      </div>
                      {item.badge > 0 && (
                        <span className="px-1.5 py-0.2 bg-rose-500 text-white rounded-full text-[10px] font-bold">
                          {item.badge}
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* User Profile Pill & Dropdown OR Login button */}
          {user ? (
            <div className="relative ml-2" ref={userMenuRef}>
              <button
                type="button"
                onClick={() => setUserMenuOpen(!userMenuOpen)}
                className="flex items-center gap-2 p-1 rounded-full hover:ring-2 hover:ring-emerald-500/30 transition-all cursor-pointer"
                aria-label="User menu"
                title={name}
              >
                <div className="w-7 h-7 rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-900/60 dark:text-emerald-200 font-bold text-xs flex items-center justify-center border border-emerald-300 dark:border-emerald-700">
                  {initials}
                </div>
              </button>

              {userMenuOpen && (
                <div className="absolute right-0 mt-2 w-52 bg-white dark:bg-slate-900 rounded-xl shadow-lg border border-slate-200 dark:border-slate-800 py-2 z-50 animate-in fade-in zoom-in-95 duration-100">
                  <div className="px-3.5 py-2 border-b border-slate-100 dark:border-slate-800">
                    <p className="text-xs font-semibold text-slate-900 dark:text-slate-100 truncate">{name}</p>
                    <p className="text-[11px] text-slate-400 truncate">{user?.email || 'Investor'}</p>
                  </div>
                  <div className="py-1">
                    <button
                      type="button"
                      onClick={() => { setUserMenuOpen(false); onSettings?.() }}
                      className="w-full px-3.5 py-1.5 text-xs text-left text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 cursor-pointer"
                    >
                      Account Settings
                    </button>
                  </div>
                  <div className="pt-1 border-t border-slate-100 dark:border-slate-800">
                    <button
                      type="button"
                      onClick={() => { setUserMenuOpen(false); onLogout?.() }}
                      className="w-full px-3.5 py-1.5 text-xs text-left text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/30 cursor-pointer font-medium"
                    >
                      Sign out
                    </button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <button
              type="button"
              onClick={() => {
                if (onLogin) {
                  onLogin()
                } else {
                  window.dispatchEvent(new CustomEvent('open-auth-modal', { detail: { mode: 'login' } }))
                }
              }}
              className="ml-2 inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-[#0d0d0d] hover:bg-black text-white text-xs font-semibold shadow-xs transition-all cursor-pointer active:scale-95"
            >
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" />
                <polyline points="10 17 15 12 10 7" />
                <line x1="15" y1="12" x2="3" y2="12" />
              </svg>
              <span>Login</span>
            </button>
          )}
        </nav>
      </div>
    </header>
  )
}

