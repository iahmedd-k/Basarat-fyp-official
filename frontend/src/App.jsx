import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  authApi,
  clearSession,
  getStoredUser,
  refreshSession,
  saveSession,
  getTokenExpiry,
  isTokenExpiringSoon,
} from './api/auth'
import { dashboardApi } from './api/dashboard'
import { newsApi } from './api/news'
import { sentimentApi } from './api/sentiment'
import { assistantApi } from './api/assistant'
import { recommendationsApi } from './api/recommendations'
import StockLogo from './components/StockLogo'
import ShariahBadge from './components/ShariahBadge'
import SearchModal from './components/SearchModal'
import ProHeader from './components/ProHeader'
import NewsCard from './components/NewsCard'
import MarketStatusWidget from './components/MarketStatusWidget'
import ArticleDetailPage from './components/ArticleDetailPage'
import ArticleDetailModal from './components/ArticleDetailModal'
import MarketActivityPage from './components/MarketActivityPage'
import SentimentPage from './components/SentimentPage'
import RiskPage from './components/RiskPage'
import SentimentHistoryChart from './components/SentimentHistoryChart'
import SentimentBadge from './components/SentimentBadge'
import StockDetail from './components/StockDetail'
import PortfolioPage from './components/PortfolioPage'
import VerifyEmailPage from './components/VerifyEmailPage'
import ForgotPasswordFlow from './components/ForgotPasswordFlow'
import LandingPage from './components/LandingPage'
import AuthModal from './components/AuthModal'
import FloatingCopilotButton from './components/FloatingCopilotButton'
import './App.css'

const initialLogin = { email: '', password: '' }
const initialSignup = { full_name: '', email: '', password: '', confirmPassword: '' }

function BrandMark() {
  return <div className="brand-mark" aria-hidden="true"><span /><span /><span /></div>
}

function MenuIcon() {
  return <span className="menu-icon" aria-hidden="true"><i /><i /><i /></span>
}

function Field({ label, name, type = 'text', value, onChange, placeholder, autoComplete, required = true }) {
  return (
    <label className="field">
      <span>{label}</span>
      <input required={required} name={name} type={type} value={value} onChange={onChange}
        placeholder={placeholder} autoComplete={autoComplete} />
    </label>
  )
}

function AuthShell({ children }) {
  return (
    <main className="auth-layout">
      <section className="auth-intro">
        <div className="brand"><BrandMark /><span>Basarat</span></div>
        <div className="intro-copy">
          <p className="eyebrow">Pakistan market intelligence</p>
          <h1>Make your next move with a clearer view.</h1>
          <p className="intro-description">One calm, focused workspace for market signals, stock research, and decisions that keep you ahead.</p>
        </div>
        <div className="market-note"><span className="status-dot" /><span>Markets open <strong>·</strong> Live insights ready</span></div>
      </section>
      <section className="auth-panel">{children}</section>
    </main>
  )
}

function AuthPage({ mode, onModeChange, onAuthenticated, onRequireVerification, onForgot }) {
  const isSignup = mode === 'signup'
  const [login, setLogin] = useState(initialLogin)
  const [signup, setSignup] = useState(initialSignup)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [unverifiedEmail, setUnverifiedEmail] = useState('')

  const update = (setter) => (event) => {
    const { name, value } = event.target
    setter((current) => ({ ...current, [name]: value }))
    setError('')
    setUnverifiedEmail('')
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setUnverifiedEmail('')

    if (isSignup) {
      if (!signup.email || !signup.email.includes('@')) {
        setError('Please enter a valid email address.')
        return
      }
      if (!signup.password) {
        setError('Password is required.')
        return
      }
      if (signup.password.length < 8) {
        setError('Password must be at least 8 characters with 1 uppercase letter, 1 number, and 1 special character.')
        return
      }
      if (signup.password !== signup.confirmPassword) {
        setError('Passwords do not match.')
        return
      }
    } else {
      if (!login.email || !login.email.includes('@')) {
        setError('Please enter your email address.')
        return
      }
      if (!login.password) {
        setError('Please enter your password.')
        return
      }
    }

    setIsSubmitting(true)
    try {
      if (isSignup) {
        await authApi.signup({
          email: signup.email.trim(),
          password: signup.password,
          full_name: signup.full_name?.trim() || null,
        })
        localStorage.setItem('basarat_pending_verify_email', signup.email.trim())
        if (onRequireVerification) {
          onRequireVerification(signup.email.trim())
        }
      } else {
        const response = await authApi.login({
          email: login.email.trim(),
          password: login.password,
        })
        saveSession(response)
        onAuthenticated(response.user, false)
      }
    } catch (requestError) {
      if (requestError.status === 403 || requestError.message?.toLowerCase().includes('not verified')) {
        setUnverifiedEmail(login.email.trim())
        setError('Your account is not verified yet. Please enter the verification code sent to your email.')
      } else {
        setError(requestError.message || 'An error occurred during authentication.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthShell>
      <div className="auth-card">
        <div className="auth-heading">
          <p className="eyebrow">{isSignup ? 'Create your account' : 'Welcome back'}</p>
          <h2>{isSignup ? 'Start investing with intention.' : 'Good to see you again.'}</h2>
          <p>{isSignup ? 'Set up your free workspace in less than a minute.' : 'Sign in to pick up where you left off.'}</p>
        </div>
        <div className="auth-tabs" role="tablist" aria-label="Authentication">
          <button
            type="button"
            role="tab"
            aria-selected={!isSignup}
            className={!isSignup ? 'active' : ''}
            onClick={() => {
              onModeChange('login')
              setError('')
              setUnverifiedEmail('')
            }}
          >
            Sign in
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={isSignup}
            className={isSignup ? 'active' : ''}
            onClick={() => {
              onModeChange('signup')
              setError('')
              setUnverifiedEmail('')
            }}
          >
            Create account
          </button>
        </div>
        <form onSubmit={handleSubmit} noValidate>
          {isSignup && <Field label="Full name" name="full_name" value={signup.full_name} onChange={update(setSignup)} placeholder="Your name" autoComplete="name" required={false} />}
          <Field label="Email address" name="email" type="email" value={isSignup ? signup.email : login.email} onChange={update(isSignup ? setSignup : setLogin)} placeholder="you@example.com" autoComplete="email" />
          <Field label="Password" name="password" type="password" value={isSignup ? signup.password : login.password} onChange={update(isSignup ? setSignup : setLogin)} placeholder="Enter your password" autoComplete={isSignup ? 'new-password' : 'current-password'} />
          {isSignup && <Field label="Confirm password" name="confirmPassword" type="password" value={signup.confirmPassword} onChange={update(setSignup)} placeholder="Repeat your password" autoComplete="new-password" />}
          {!isSignup && <button type="button" className="text-button" onClick={onForgot}>Forgot password?</button>}
          {isSignup && <p className="password-hint">Use 8+ characters with one uppercase letter, number, and special character.</p>}
          {error && <p className="form-error" role="alert">{error}</p>}
          {unverifiedEmail && (
            <button
              type="button"
              className="text-button"
              style={{ fontWeight: 600, color: '#216b57', marginBottom: '14px', textAlign: 'left' }}
              onClick={() => onRequireVerification && onRequireVerification(unverifiedEmail)}
            >
              Verify Your Email Now →
            </button>
          )}
          <button className="submit-button" type="submit" disabled={isSubmitting}>
            {isSubmitting ? (isSignup ? 'Creating account…' : 'Signing in…') : (isSignup ? 'Create account' : 'Sign in')}
            {!isSubmitting && <span aria-hidden="true">→</span>}
          </button>
        </form>
        <p className="terms">By continuing, you agree to our <a href="#terms">Terms</a> and <a href="#privacy">Privacy Policy</a>.</p>
      </div>
    </AuthShell>
  )
}

function ProfileSetup({ user, onComplete }) {
  const [form, setForm] = useState({ full_name: user?.full_name || '', risk_tolerance: '', investment_horizon: '', sector_preferences: [] })
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const sectors = ['Commercial Banks', 'Oil & Gas', 'Technology', 'Pharmaceuticals', 'Cement', 'All Sectors']
  const update = (name, value) => setForm((current) => ({ ...current, [name]: value }))
  const toggleSector = (sector) => update('sector_preferences', form.sector_preferences.includes(sector) ? form.sector_preferences.filter((item) => item !== sector) : [...form.sector_preferences.filter((item) => item !== 'All Sectors'), sector])

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setIsSubmitting(true)
    try {
      const profile = await authApi.updateProfile({ ...form, sector_preferences: form.sector_preferences.length ? form.sector_preferences : ['All Sectors'] })
      localStorage.setItem('basarat_user', JSON.stringify(profile))
      onComplete(profile)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthShell>
      <div className="auth-card setup-card">
        <div className="auth-heading"><p className="eyebrow">A quick first step</p><h2>Make Basarat yours.</h2><p>Tell us how you invest so your workspace feels relevant from day one.</p></div>
        <form onSubmit={handleSubmit}>
          <Field label="Full name" name="full_name" value={form.full_name} onChange={(event) => update('full_name', event.target.value)} placeholder="Your name" autoComplete="name" required={false} />
          <label className="field"><span>Risk comfort</span><select value={form.risk_tolerance} onChange={(event) => update('risk_tolerance', event.target.value)} required><option value="">Choose one</option><option value="conservative">Conservative</option><option value="moderate">Moderate</option><option value="aggressive">Aggressive</option></select></label>
          <label className="field"><span>Investment horizon</span><select value={form.investment_horizon} onChange={(event) => update('investment_horizon', event.target.value)} required><option value="">Choose one</option><option value="short_term">Short term</option><option value="medium_term">Medium term</option><option value="long_term">Long term</option></select></label>
          <div className="field"><span>Sectors you follow</span><div className="choice-grid">{sectors.map((sector) => <button type="button" key={sector} className={form.sector_preferences.includes(sector) ? 'choice selected' : 'choice'} onClick={() => toggleSector(sector)}>{sector}</button>)}</div></div>
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="submit-button" type="submit" disabled={isSubmitting}>{isSubmitting ? 'Saving…' : 'Save preferences'}<span aria-hidden="true">→</span></button>
        </form>
        <button type="button" className="skip-button" onClick={() => onComplete(user)}>I’ll do this later</button>
      </div>
    </AuthShell>
  )
}

function formatNumber(value, fractionDigits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  return Number(value).toLocaleString('en-PK', { minimumFractionDigits: fractionDigits, maximumFractionDigits: fractionDigits })
}

function formatMoney(value) {
  return `Rs. ${formatNumber(value, 0)}`
}

function Change({ value }) {
  const number = Number(value)
  return <span className={number >= 0 ? 'positive' : 'negative'}>{number >= 0 ? '+' : ''}{formatNumber(number)}%</span>
}

function getWatchlist() {
  try { return JSON.parse(localStorage.getItem('basarat_watchlist') || '[]') } catch { return [] }
}

function saveWatchlist(symbols) {
  localStorage.setItem('basarat_watchlist', JSON.stringify([...new Set(symbols.map((item) => item.toUpperCase()))]))
}

function DataState({ loading, error, children, empty = 'No data available yet.' }) {
  if (loading) return <p className="data-state">Loading live data…</p>
  if (error) return <p className="data-state">This section is temporarily unavailable.</p>
  return children || <p className="data-state">{empty}</p>
}

function StockSearch({ onSelect, placeholder = 'Search 500+ PSX stocks, indices, or sectors...' }) {
  return (
    <div
      className="pro-hero-search-btn"
      onClick={() => window.dispatchEvent(new CustomEvent('open-stock-search'))}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          window.dispatchEvent(new CustomEvent('open-stock-search'))
        }
      }}
      aria-label="Search PSX Stocks"
    >
      <div className="flex items-center gap-2.5">
        <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <span className="text-slate-400 text-sm">{placeholder}</span>
      </div>
      <kbd className="inline-flex items-center gap-0.5 px-2 py-0.5 text-xs text-slate-400 bg-slate-100 rounded border border-slate-200 font-sans">
        ⌘K
      </kbd>
    </div>
  )
}

function NavIcon({ name, className = 'nav-icon' }) {
  const props = {
    className,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: '2',
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    'aria-hidden': 'true',
    width: '18',
    height: '18',
  }
  switch (name) {
    case 'dashboard':
      return <svg {...props}><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /><polyline points="9 22 9 12 15 12 15 22" /></svg>
    case 'market':
      return <svg {...props}><polyline points="23 6 13.5 15.5 8.5 10.5 1 18" /><polyline points="17 6 23 6 23 12" /></svg>
    case 'portfolio':
      return <svg {...props}><rect x="2" y="7" width="20" height="14" rx="2" ry="2" /><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" /></svg>
    case 'watchlist':
      return <svg {...props}><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" /></svg>
    case 'recommendations':
      return <svg {...props}><polygon points="12 2 19 12 12 22 5 12 12 2" /></svg>
    case 'shariah':
      return <svg {...props}><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" /></svg>
    case 'news':
      return <svg {...props}><path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2Zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2" /><path d="M18 14h-8" /><path d="M15 18h-5" /><path d="M10 6h8v4h-8V6Z" /></svg>
    case 'sentiment':
      return <svg {...props}><path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm0 14a4 4 0 0 1-4-4h8a4 4 0 0 1-4 4z" /><circle cx="9" cy="9" r="1" fill="currentColor" /><circle cx="15" cy="9" r="1" fill="currentColor" /></svg>
    case 'assistant':
      return <svg {...props}><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z" /></svg>
    case 'risk':
      return <svg {...props}><circle cx="12" cy="12" r="10" /><path d="m4.93 4.93 14.14 14.14" /></svg>
    case 'settings':
      return <svg {...props}><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" /></svg>
    case 'more':
      return <svg {...props}><circle cx="12" cy="12" r="1.5" /><circle cx="19" cy="12" r="1.5" /><circle cx="5" cy="12" r="1.5" /></svg>
    case 'close':
      return <svg {...props}><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
    default:
      return null
  }
}

function defaultAssistantNavigation() {
  window.history.pushState({}, '', '/assistant')
  window.dispatchEvent(new PopStateEvent('popstate'))
}
function defaultWatchlistNavigation() {
  window.history.pushState({}, '', '/watchlist')
  window.dispatchEvent(new PopStateEvent('popstate'))
}
function defaultRecommendationsNavigation() {
  window.history.pushState({}, '', '/recommendations')
  window.dispatchEvent(new PopStateEvent('popstate'))
}
function defaultShariahNavigation() {
  window.history.pushState({}, '', '/shariah')
  window.dispatchEvent(new PopStateEvent('popstate'))
}
function defaultSentimentNavigation() {
  window.history.pushState({}, '', '/sentiment')
  window.dispatchEvent(new PopStateEvent('popstate'))
}

function MobileNav({
  active,
  onDashboard,
  onMarket,
  onPortfolio,
  onNews,
  onSentiment = defaultSentimentNavigation,
  onAssistant = defaultAssistantNavigation,
  onWatchlist = defaultWatchlistNavigation,
  onRecommendations = defaultRecommendationsNavigation,
  onShariah = defaultShariahNavigation,
  onRisk,
  onSettings,
}) {
  const [showMore, setShowMore] = useState(false)
  const isMoreActive = ['watchlist', 'recommendations', 'shariah', 'sentiment', 'risk', 'settings'].includes(active)

  const handleSelect = (callback) => {
    setShowMore(false)
    callback?.()
  }

  return (
    <>
      {showMore && (
        <div className="mobile-more-overlay" onClick={() => setShowMore(false)}>
          <div className="mobile-more-sheet" onClick={(e) => e.stopPropagation()}>
            <div className="mobile-more-header">
              <h3>More features</h3>
              <button type="button" className="close-more-btn" aria-label="Close menu" onClick={() => setShowMore(false)}>
                <NavIcon name="close" />
              </button>
            </div>
            <div className="mobile-more-grid">
              <button type="button" className={active === 'sentiment' ? 'active' : ''} onClick={() => handleSelect(onSentiment)}>
                <NavIcon name="sentiment" />
                <span>Sentiment</span>
              </button>
              <button type="button" className={active === 'watchlist' ? 'active' : ''} onClick={() => handleSelect(onWatchlist)}>
                <NavIcon name="watchlist" />
                <span>Watchlist</span>
              </button>
              <button type="button" className={active === 'recommendations' ? 'active' : ''} onClick={() => handleSelect(onRecommendations)}>
                <NavIcon name="recommendations" />
                <span>Recommendations</span>
              </button>
              <button type="button" className={active === 'shariah' ? 'active' : ''} onClick={() => handleSelect(onShariah)}>
                <NavIcon name="shariah" />
                <span>Shariah</span>
              </button>
              <button type="button" className={active === 'risk' ? 'active' : ''} onClick={() => handleSelect(onRisk)}>
                <NavIcon name="risk" />
                <span>Risk</span>
              </button>
              <button type="button" className={active === 'settings' ? 'active' : ''} onClick={() => handleSelect(onSettings)}>
                <NavIcon name="settings" />
                <span>Settings</span>
              </button>
            </div>
          </div>
        </div>
      )}
      <nav className="mobile-nav">
        <button type="button" className={active === 'dashboard' ? 'active' : ''} onClick={onDashboard}>
          <NavIcon name="dashboard" />
          <span>Home</span>
        </button>
        <button type="button" className={active === 'market' ? 'active' : ''} onClick={onMarket}>
          <NavIcon name="market" />
          <span>Market</span>
        </button>
        <button type="button" className={active === 'portfolio' ? 'active' : ''} onClick={onPortfolio}>
          <NavIcon name="portfolio" />
          <span>Portfolio</span>
        </button>
        <button type="button" className={active === 'news' ? 'active' : ''} onClick={onNews}>
          <NavIcon name="news" />
          <span>Activity</span>
        </button>
        <button type="button" className={isMoreActive || showMore ? 'active' : ''} onClick={() => setShowMore((v) => !v)}>
          <NavIcon name="more" />
          <span>More</span>
        </button>
      </nav>
    </>
  )
}

function Header({
  active,
  onDashboard,
  onMarket,
  onPortfolio,
  onNews = () => {},
  onSentiment = defaultSentimentNavigation,
  onAssistant = defaultAssistantNavigation,
  onWatchlist = defaultWatchlistNavigation,
  onRecommendations = defaultRecommendationsNavigation,
  onShariah = defaultShariahNavigation,
  onRisk,
  onSettings,
  onLogout,
  onOpenSearch,
}) {
  return (
    <ProHeader
      active={active}
      onDashboard={onDashboard}
      onMarket={onMarket}
      onPortfolio={onPortfolio}
      onNews={onNews}
      onSentiment={onSentiment}
      onAssistant={onAssistant}
      onWatchlist={onWatchlist}
      onRecommendations={onRecommendations}
      onShariah={onShariah}
      onRisk={onRisk}
      onSettings={onSettings}
      onLogout={onLogout}
      onOpenSearch={onOpenSearch || (() => window.dispatchEvent(new CustomEvent('open-stock-search')))}
    />
  )
}


function Dashboard({ user, onLogout, onMarket, onStock, onPortfolio, onNews, onRisk, onSettings }) {
  const firstName = user?.full_name?.split(' ')[0] || user?.username || 'Investor'
  const [data, setData] = useState({})
  const [loading, setLoading] = useState(true)
  const [moversTab, setMoversTab] = useState('gainers')
  const [selectedArticle, setSelectedArticle] = useState(null)

  useEffect(() => {
    let active = true
    const sources = {
      indices: dashboardApi.getIndices(),
      marketStatus: dashboardApi.getMarketStatus(),
      gainers: dashboardApi.getGainers(10),
      losers: dashboardApi.getLosers(10),
      mostActive: dashboardApi.getMostActive(10),
      portfolio: dashboardApi.getPortfolio(),
      news: dashboardApi.getNews(),
      recommendations: dashboardApi.getRecommendations(),
      kmi30: dashboardApi.getKmi30Constituents(),
    }
    Promise.allSettled(Object.entries(sources).map(async ([key, promise]) => [key, await promise]))
      .then((results) => {
        if (!active) return
        const next = {}
        results.forEach((result, idx) => {
          if (result.status === 'fulfilled') next[result.value[0]] = { value: result.value[1] }
          else next[Object.keys(sources)[idx]] = { error: result.reason }
        })
        setData(next)
      })
      .finally(() => active && setLoading(false))
    return () => { active = false }
  }, [])

  const indices = data.indices?.value?.indices || []
  const marketStatus = data.marketStatus?.value
  const portfolio = data.portfolio?.value
  const news = data.news?.value?.items || []
  const recommendations = data.recommendations?.value?.recommendations || []
  const kmi30List = data.kmi30?.value?.constituents || []
  const statusOpen = marketStatus?.status === 'market_hours' || marketStatus?.is_market_open || marketStatus?.market_open

  const gainers = data.gainers?.value?.gainers || []
  const losers = data.losers?.value?.losers || []
  const mostActive = data.mostActive?.value?.volume_spikes || []
  const activeMovers = moversTab === 'gainers' ? gainers : moversTab === 'losers' ? losers : mostActive

  return (
    <main className="dashboard">
      <Header
        active="dashboard"
        onDashboard={() => {}}
        onMarket={onMarket}
        onPortfolio={onPortfolio}
        onNews={onNews}
        onRisk={onRisk}
        onSettings={onSettings}
        onLogout={onLogout}
      />
      <section className="dashboard-content">
        {/* Pro Hero Banner (TickerAnalysts UX) */}
        <div className="pro-hero-banner">
          <div className="pro-hero-badge">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            Pakistan Stock Exchange Intelligence
          </div>
          <h1 className="pro-hero-title">Empowering informed investments in Pakistan.</h1>
          <p className="pro-hero-sub">
            Real-time PSX quotes, KMI-30 Shariah screening, AI forecasts, and automated quantitative signals.
          </p>

          {/* Central Search Pill */}
          <button
            type="button"
            className="pro-hero-search-btn"
            onClick={() => window.dispatchEvent(new CustomEvent('open-stock-search'))}
          >
            <div className="flex items-center gap-2.5">
              <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <span>Search 500+ PSX stocks, indices, or sectors...</span>
            </div>
            <kbd className="inline-flex items-center gap-0.5 px-2 py-0.5 text-xs text-slate-400 bg-slate-100 rounded border border-slate-200 font-sans">
              ⌘K
            </kbd>
          </button>

          {/* Trending Ticker Chips */}
          <div className="pro-hero-trending">
            <span className="label">Trending:</span>
            {['OGDC', 'SYS', 'LUCK', 'MEBL', 'MCB', 'ENGRO', 'HUBC', 'FFC'].map((sym) => (
              <button
                key={sym}
                type="button"
                className="pro-hero-chip flex items-center gap-1.5"
                onClick={() => onStock(sym)}
              >
                <StockLogo ticker={sym} size="xs" />
                <span>{sym}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Market Pulse Index Cards */}
        <div className="index-grid">
          {['KSE-100', 'KSE-30', 'KMI-30'].map((name) => {
            const item = indices.find((idx) => idx.index === name)
            return (
              <article className="index-card" key={name}>
                <div className="flex items-center justify-between mb-1">
                  <span className="card-label">{name}</span>
                  {name === 'KMI-30' && (
                    <ShariahBadge isCompliant={true} size="xs" />
                  )}
                </div>
                <strong>{formatNumber(item?.current)}</strong>
                <div>
                  <span className={Number(item?.change) >= 0 ? 'positive' : 'negative'}>
                    {Number(item?.change) >= 0 ? '+' : ''}{formatNumber(item?.change)}
                  </span>
                  <span className="index-percent"><Change value={item?.change_pct} /></span>
                </div>
                <small className="range">H {formatNumber(item?.high)} · L {formatNumber(item?.low)}</small>
              </article>
            )
          })}
        </div>

        {/* Tabbed Market Movers */}
        <div className="pro-movers-card">
          <div className="pro-movers-header">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
              <h2 className="text-base font-bold text-slate-900 tracking-tight">Market Movers</h2>
            </div>
            <div className="pro-tabs">
              <button
                type="button"
                className={`pro-tab-btn ${moversTab === 'gainers' ? 'active' : ''}`}
                onClick={() => setMoversTab('gainers')}
              >
                Top Gainers ({gainers.length})
              </button>
              <button
                type="button"
                className={`pro-tab-btn ${moversTab === 'losers' ? 'active' : ''}`}
                onClick={() => setMoversTab('losers')}
              >
                Top Losers ({losers.length})
              </button>
              <button
                type="button"
                className={`pro-tab-btn ${moversTab === 'active' ? 'active' : ''}`}
                onClick={() => setMoversTab('active')}
              >
                Most Active ({mostActive.length})
              </button>
            </div>
          </div>

          <div className="pro-movers-list">
            <DataState loading={loading} error={data[moversTab === 'gainers' ? 'gainers' : moversTab === 'losers' ? 'losers' : 'mostActive']?.error}>
              {activeMovers.slice(0, 10).map((item, idx) => {
                const isCompliant = kmi30List.some((k) => k.symbol === item.symbol)
                return (
                  <div
                    key={item.symbol}
                    className="pro-stock-item"
                    onClick={() => onStock(item.symbol)}
                    role="button"
                    tabIndex={0}
                  >
                    <div className="pro-stock-info">
                      <span className="text-xs font-semibold text-slate-400 dark:text-slate-500 w-5 text-center font-mono shrink-0">
                        {idx + 1}
                      </span>
                      <StockLogo ticker={item.symbol} companyName={item.name} size="md" />
                      <div className="pro-stock-names">
                        <div className="pro-stock-symbol-row">
                          <span className="pro-stock-symbol">{item.symbol}</span>
                          {isCompliant && <ShariahBadge isCompliant={true} size="xs" />}
                          {item.sector && (
                            <span className="text-[10px] text-slate-400 uppercase tracking-wider hidden sm:inline">
                              {item.sector.split(' ')[0]}
                            </span>
                          )}
                        </div>
                        <span className="pro-stock-name">{item.name || item.sector || item.symbol}</span>
                      </div>
                    </div>

                    <div className="pro-stock-metrics">
                      <div>
                        <div className="pro-stock-price">PKR {formatNumber(item.current)}</div>
                        <div className="pro-stock-volume">{formatNumber(item.volume, 0)} vol</div>
                      </div>
                      <Change value={item.change_pct} />
                    </div>
                  </div>
                )
              })}
            </DataState>
          </div>
        </div>

        {/* Curated Research Grid */}
        <div className="dashboard-main-grid">
          {/* Shariah Spotlight (KMI-30) */}
          <section className="dashboard-section">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Ethical Universe</p>
                <h2>KMI-30 Shariah Spotlight</h2>
              </div>
              <button
                type="button"
                onClick={() => { window.history.pushState({}, '', '/shariah'); window.dispatchEvent(new PopStateEvent('popstate')) }}
                className="text-xs text-emerald-600 hover:text-emerald-700 font-semibold"
              >
                View all 30 →
              </button>
            </div>
            <DataState loading={loading} error={data.kmi30?.error}>
              <div className="compact-list">
                {kmi30List.slice(0, 5).map((item) => (
                  <div
                    className="compact-row cursor-pointer hover:bg-slate-50 transition-colors"
                    key={item.symbol}
                    onClick={() => onStock(item.symbol)}
                  >
                    <div className="flex items-center gap-2.5">
                      <StockLogo ticker={item.symbol} companyName={item.name} size="sm" />
                      <span className="stock-symbol">{item.symbol}<small>{item.sector?.split(' ')[0]}</small></span>
                    </div>
                    <div className="flex items-center gap-2">
                      <ShariahBadge isCompliant={true} size="xs" />
                      <Change value={item.change_pct} />
                    </div>
                  </div>
                ))}
              </div>
            </DataState>
          </section>

          {/* Quantitative Strategy Recommendations */}
          <section className="dashboard-section">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Quant Rankings</p>
                <h2>Top Stock Signals</h2>
              </div>
              <button
                type="button"
                onClick={() => { window.history.pushState({}, '', '/recommendations'); window.dispatchEvent(new PopStateEvent('popstate')) }}
                className="text-xs text-emerald-600 hover:text-emerald-700 font-semibold"
              >
                Tune weights →
              </button>
            </div>
            <DataState loading={loading} error={data.recommendations?.error}>
              <div className="compact-list">
                {recommendations.slice(0, 5).map((item) => (
                  <div
                    className="recommendation-row cursor-pointer hover:bg-slate-50 transition-colors"
                    key={item.symbol}
                    onClick={() => onStock(item.symbol)}
                  >
                    <div className="flex items-center gap-2.5">
                      <StockLogo symbol={item.symbol} size="xs" />
                      <span><strong>{item.symbol}</strong><small>{item.summary || 'Market signal'}</small></span>
                    </div>
                    <span className={`signal ${item.signal?.toLowerCase()}`}>{item.signal}</span>
                  </div>
                ))}
              </div>
            </DataState>
          </section>

          {/* Portfolio Summary */}
          <section className="dashboard-section">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Your Holdings</p>
                <h2>Portfolio Summary</h2>
              </div>
              <span className="section-meta">Live</span>
            </div>
            <DataState loading={loading} error={data.portfolio?.error}>
              {portfolio && (
                <>
                  <div className="portfolio-total">
                    <span>Total value</span>
                    <strong>{formatMoney(portfolio.summary?.current_value)}</strong>
                    <Change value={portfolio.summary?.total_pnl_percent} />
                  </div>
                  <div className="portfolio-stats">
                    <div><span>Invested</span><strong>{formatMoney(portfolio.summary?.total_invested)}</strong></div>
                    <div>
                      <span>Today's P&amp;L</span>
                      <strong className={Number(portfolio.summary?.today_pnl) >= 0 ? 'positive' : 'negative'}>
                        {formatMoney(portfolio.summary?.today_pnl)}
                      </strong>
                    </div>
                  </div>
                </>
              )}
            </DataState>
          </section>
        </div>

        {/* Financial News Section */}
        <section className="dashboard-section news-section">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Market Coverage</p>
              <h2>Latest Market News</h2>
            </div>
            <button
              type="button"
              onClick={onNews}
              className="text-xs text-emerald-600 hover:text-emerald-700 font-semibold cursor-pointer"
            >
              Browse all news →
            </button>
          </div>
          <DataState loading={loading} error={data.news?.error}>
            <div className="news-list">
              {news.slice(0, 4).map((article) => (
                <div
                  className="news-row cursor-pointer select-none"
                  key={article.id}
                  onClick={() => setSelectedArticle(article)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      setSelectedArticle(article)
                    }
                  }}
                >
                  <span>
                    <strong>{article.title}</strong>
                    <small>{article.source?.name || 'Market update'} · {article.published_at ? new Date(article.published_at).toLocaleDateString() : 'Latest'}</small>
                  </span>
                  <span aria-hidden="true">↗</span>
                </div>
              ))}
            </div>
          </DataState>
        </section>
      </section>
      <MobileNav active="dashboard" onDashboard={() => {}} onMarket={onMarket} onPortfolio={onPortfolio} onNews={onNews} onRisk={onRisk} onSettings={onSettings} />

      {/* Direct in-place Article Detail Modal on Dashboard (no page change / no hang) */}
      {selectedArticle && (
        <ArticleDetailModal
          article={selectedArticle}
          onClose={() => setSelectedArticle(null)}
          onStock={(sym) => {
            setSelectedArticle(null)
            onStock?.(sym)
          }}
        />
      )}
    </main>
  )
}

function MarketOverview({
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
  onOpenSearch,
}) {
  const [data, setData] = useState({})
  const [selectedIndex, setSelectedIndex] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedSector, setSelectedSector] = useState('ALL')
  const [shariahOnly, setShariahOnly] = useState(false)
  const [sortKey, setSortKey] = useState('volume')
  const [sortAsc, setSortAsc] = useState(false)
  const [loading, setLoading] = useState(true)
  const [moversTab, setMoversTab] = useState('volume') // 'volume' | 'gainers' | 'losers'
  const [visibleCount, setVisibleCount] = useState(50)
  const [showAllSectors, setShowAllSectors] = useState(false)
  const [sectorSearch, setSectorSearch] = useState('')

  useEffect(() => {
    let active = true
    const sources = {
      indices: dashboardApi.getIndices(),
      status: dashboardApi.getMarketStatus(),
      gainers: dashboardApi.getGainers(15),
      losers: dashboardApi.getLosers(15),
      volume: dashboardApi.getMostActive(15),
      sentiment: dashboardApi.getSentiment(),
      marketSentiment: newsApi.getMarketSentiment(),
      sectorsPerformance: dashboardApi.getSectorPerformance(),
      allStocks: dashboardApi.getQuotes({ limit: 500 }),
      kse100: dashboardApi.getConstituents('kse-100'),
      kse30: dashboardApi.getConstituents('kse-30'),
      kmi30: dashboardApi.getConstituents('kmi-30'),
    }

    Promise.allSettled(Object.entries(sources).map(async ([key, promise]) => [key, await promise]))
      .then((results) => {
        if (!active) return
        const next = {}
        results.forEach((result, index) => {
          next[Object.keys(sources)[index]] = result.status === 'fulfilled'
            ? { value: result.value[1] }
            : { error: result.reason }
        })
        setData(next)
      })
      .finally(() => active && setLoading(false))
    return () => { active = false }
  }, [])

  const indices = data.indices?.value?.indices || []
  const sentiment = data.sentiment?.value
  const marketSentiment = data.marketSentiment?.value
  const sectorsPerformance = data.sectorsPerformance?.value?.sectors || []
  const allStocksList = data.allStocks?.value?.stocks || []
  const kse100List = data.kse100?.value?.constituents || []
  const kse30List = data.kse30?.value?.constituents || []
  const kmi30List = data.kmi30?.value?.constituents || []
  const kmiSymbolsSet = useMemo(() => new Set(kmi30List.map((c) => c.symbol)), [kmi30List])
  const marketOpen = data.status?.value?.status === 'market_hours' || data.status?.value?.is_market_open

  // Stock metadata map (symbol -> sector & name) to enrich constituent data
  const stockMetaMap = useMemo(() => {
    const map = new Map()
    allStocksList.forEach((s) => {
      if (s.symbol) {
        map.set(s.symbol, { sector: s.sector, name: s.name, market_cap_m: s.market_cap_m })
      }
    })
    return map
  }, [allStocksList])

  // Active raw list based on selected index/filter
  const activeRawList = useMemo(() => {
    if (selectedIndex === 'kse-100') return kse100List
    if (selectedIndex === 'kse-30') return kse30List
    if (selectedIndex === 'kmi-30') return kmi30List
    return allStocksList
  }, [selectedIndex, allStocksList, kse100List, kse30List, kmi30List])

  // Normalized stocks with standardized fields
  const normalizedStocks = useMemo(() => {
    return activeRawList.map((item) => {
      const meta = stockMetaMap.get(item.symbol) || {}
      return {
        ...item,
        name: item.name || meta.name || item.symbol,
        sector: item.sector || meta.sector || 'General',
        current: Number(item.current ?? item.ldcp ?? 0),
        change_pct: Number(item.change_pct ?? 0),
        change: Number(item.change ?? 0),
        volume: Number(item.volume ?? 0),
        market_cap_m: Number(item.market_cap_m ?? meta.market_cap_m ?? 0),
        weight_pct: item.weight_pct != null ? Number(item.weight_pct) : null,
      }
    })
  }, [activeRawList, stockMetaMap])

  // Sector list for filter dropdown and quick chips
  const allSectorsList = useMemo(() => {
    const fromPerf = sectorsPerformance.map((s) => s.sector).filter(Boolean)
    if (fromPerf.length > 0) return ['ALL', ...fromPerf]
    return ['ALL', ...new Set(allStocksList.map((s) => s.sector).filter(Boolean))]
  }, [sectorsPerformance, allStocksList])

  // Filter and sort stocks
  const filteredStocks = useMemo(() => {
    const q = searchQuery.trim().toLowerCase()
    return normalizedStocks.filter((item) => {
      const sym = item.symbol?.toLowerCase() || ''
      const name = item.name?.toLowerCase() || ''
      const sec = item.sector?.toLowerCase() || ''
      const matchesSearch = !q || sym.includes(q) || name.includes(q) || sec.includes(q)

      const matchesSector = selectedSector === 'ALL' || item.sector.toUpperCase() === selectedSector.toUpperCase()
      const isShariah = selectedIndex === 'kmi-30' || kmiSymbolsSet.has(item.symbol)
      const matchesShariah = !shariahOnly || isShariah

      return matchesSearch && matchesSector && matchesShariah
    }).sort((a, b) => {
      let valA = a[sortKey] ?? 0
      let valB = b[sortKey] ?? 0
      if (typeof valA === 'string') {
        return sortAsc ? valA.localeCompare(valB) : valB.localeCompare(valA)
      }
      return sortAsc ? Number(valA) - Number(valB) : Number(valB) - Number(valA)
    })
  }, [normalizedStocks, searchQuery, selectedSector, shariahOnly, sortKey, sortAsc, kmiSymbolsSet, selectedIndex])

  const displayedStocks = useMemo(() => {
    return filteredStocks.slice(0, visibleCount)
  }, [filteredStocks, visibleCount])

  // Sector performance filtering
  const filteredSectors = useMemo(() => {
    const q = sectorSearch.trim().toLowerCase()
    const sorted = [...sectorsPerformance].sort((a, b) => (Number(b.avg_change_pct) || 0) - (Number(a.avg_change_pct) || 0))
    if (!q) return sorted
    return sorted.filter((s) => s.sector?.toLowerCase().includes(q))
  }, [sectorsPerformance, sectorSearch])

  const displayedSectors = useMemo(() => {
    return showAllSectors ? filteredSectors : filteredSectors.slice(0, 8)
  }, [filteredSectors, showAllSectors])

  // Market Breadth metrics & circular chart geometry
  const advancing = Number(sentiment?.advancing) || 0
  const declining = Number(sentiment?.declining) || 0
  const unchanged = Number(sentiment?.unchanged) || 0
  const breadthTotal = advancing + declining + unchanged || 1
  const advPct = ((advancing / breadthTotal) * 100).toFixed(1)
  const decPct = ((declining / breadthTotal) * 100).toFixed(1)
  const uncPct = ((unchanged / breadthTotal) * 100).toFixed(1)

  const radius = 46
  const circ = 2 * Math.PI * radius
  const advStroke = (advancing / breadthTotal) * circ
  const decStroke = (declining / breadthTotal) * circ
  const uncStroke = (unchanged / breadthTotal) * circ
  const decOffset = -advStroke
  const uncOffset = -(advStroke + decStroke)

  const rawMood = sentiment?.market_mood || 'neutral'
  const formattedMood = rawMood
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(' ')
  const isBullish = rawMood.toLowerCase().includes('bullish')
  const isBearish = rawMood.toLowerCase().includes('bearish')
  const moodBadgeClasses = isBullish
    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
    : isBearish
    ? 'bg-rose-50 text-rose-700 border-rose-200'
    : 'bg-slate-100 text-slate-700 border-slate-200'
  const moodDotClasses = isBullish
    ? 'bg-emerald-500'
    : isBearish
    ? 'bg-rose-500'
    : 'bg-slate-400'

  const rawFinMood = marketSentiment?.market_mood || 'Unavailable'
  const formattedFinMood = rawFinMood
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(' ')

  // Current Movers Data
  const currentMoversList = useMemo(() => {
    if (moversTab === 'volume') return data.volume?.value?.volume_spikes || []
    if (moversTab === 'gainers') return data.gainers?.value?.gainers || []
    if (moversTab === 'losers') return data.losers?.value?.losers || []
    return []
  }, [moversTab, data])

  const currentMoversError = useMemo(() => {
    if (moversTab === 'volume') return data.volume?.error
    if (moversTab === 'gainers') return data.gainers?.error
    if (moversTab === 'losers') return data.losers?.error
    return null
  }, [moversTab, data])

  function handleSort(key) {
    if (sortKey === key) {
      setSortAsc(!sortAsc)
    } else {
      setSortKey(key)
      setSortAsc(false)
    }
  }

  function navigateToStock(sym) {
    window.history.pushState({}, '', `/stocks/${sym}`)
    window.dispatchEvent(new PopStateEvent('popstate'))
  }

  // Active screener error
  const activeScreenerError = selectedIndex === 'all'
    ? data.allStocks?.error
    : data[selectedIndex.replace('-', '')]?.error

  return (
    <main className="dashboard">
      <ProHeader
        active="market"
        onDashboard={onDashboard || onBack}
        onMarket={onMarket || (() => {})}
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
      <section className="dashboard-content market-overview">
        {/* Top Header */}
        <div className="dashboard-topline">
          <div>
            <p className="eyebrow">Pakistan Stock Exchange</p>
            <h1>Stock Screener</h1>
            <p className="dashboard-lede">
              Live quotes for all 500+ PSX listed equities, sector performance matrix, benchmark index constituents, and real-time market breadth.
            </p>
          </div>
          <div className={marketOpen ? 'market-status open' : 'market-status'}>
            <span className="status-dot" />
            {marketOpen ? 'Market open' : 'Market closed'}
            <small>{data.status?.value?.current_time_pkt ? new Date(data.status.value.current_time_pkt).toLocaleString() : 'Live schedule'}</small>
          </div>
        </div>

        {/* Index Grid */}
        <div className="index-grid">
          {['KSE-100', 'KSE-30', 'KMI-30'].map((name) => {
            const item = indices.find((index) => index.index === name)
            const isSelected = selectedIndex === name.toLowerCase()
            return (
              <article
                className={`index-card cursor-pointer transition-all ${isSelected ? 'ring-2 ring-emerald-500 bg-emerald-50/20' : ''}`}
                key={name}
                onClick={() => {
                  setSelectedIndex(name.toLowerCase())
                  setVisibleCount(50)
                }}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="card-label">{name}</span>
                  {name === 'KMI-30' && (
                    <ShariahBadge isCompliant={true} size="xs" />
                  )}
                </div>
                <strong>{formatNumber(item?.current)}</strong>
                <div>
                  <span className={Number(item?.change) >= 0 ? 'positive' : 'negative'}>
                    {Number(item?.change) >= 0 ? '+' : ''}{formatNumber(item?.change)}
                  </span>
                  <span className="index-percent"><Change value={item?.change_pct} /></span>
                </div>
                <small className="range">H {formatNumber(item?.high)} · L {formatNumber(item?.low)}</small>
              </article>
            )
          })}
        </div>

        {/* PSX Sector Performance Breakdown */}
        {sectorsPerformance.length > 0 && (
          <section className="dashboard-section sector-performance-section mb-6">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Industry Matrix</p>
                <h2 className="text-base font-bold text-slate-900 dark:text-slate-100">PSX Sector Performance</h2>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                  Real-time return across 37 PSX industry sectors. Click any sector to filter the screener table.
                </p>
              </div>
              <div className="flex items-center gap-2.5">
                <input
                  type="text"
                  placeholder="Filter sectors..."
                  value={sectorSearch}
                  onChange={(e) => setSectorSearch(e.target.value)}
                  className="h-8 px-2.5 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 placeholder-slate-400 w-32 sm:w-40 focus:outline-hidden focus:ring-1 focus:ring-emerald-500"
                />
                <button
                  type="button"
                  onClick={() => setShowAllSectors(!showAllSectors)}
                  className="px-2.5 py-1 text-xs font-semibold rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-750 transition-colors"
                >
                  {showAllSectors ? 'Show Top 8' : `Show All (${sectorsPerformance.length})`}
                </button>
              </div>
            </div>

            <DataState loading={loading} error={data.sectorsPerformance?.error}>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                {displayedSectors.map((sec) => {
                  const isSelected = selectedSector.toUpperCase() === sec.sector.toUpperCase()
                  return (
                    <div
                      key={sec.sector}
                      onClick={() => {
                        setSelectedSector(isSelected ? 'ALL' : sec.sector)
                        document.querySelector('.screener-box')?.scrollIntoView({ behavior: 'smooth' })
                      }}
                      className={`p-3.5 rounded-xl border transition-all cursor-pointer ${
                        isSelected
                          ? 'bg-emerald-50/90 dark:bg-emerald-950/40 border-emerald-500 ring-1 ring-emerald-500 shadow-sm'
                          : 'bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 hover:border-emerald-400/50 hover:shadow-xs'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <span className="font-semibold text-xs text-slate-900 dark:text-slate-100 truncate" title={sec.sector}>
                          {sec.sector}
                        </span>
                        <Change value={sec.avg_change_pct} />
                      </div>

                      <div className="flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400 mb-2">
                        <span>{sec.companies} stocks</span>
                        <span className="font-mono">
                          <span className="text-emerald-600 dark:text-emerald-400 font-bold">{sec.advancing}↑</span>
                          <span className="mx-1 text-slate-300 dark:text-slate-700">·</span>
                          <span className="text-rose-600 dark:text-rose-400 font-bold">{sec.declining}↓</span>
                        </span>
                      </div>

                      <div className="pt-2 border-t border-slate-100 dark:border-slate-800/80 flex items-center justify-between text-[10px] text-slate-400 font-mono">
                        <span>Vol: {formatNumber(sec.total_volume, 0)}</span>
                        {sec.top_gainer_symbol && (
                          <span className="text-emerald-600 dark:text-emerald-400 font-medium font-sans">
                            Lead: <strong>{sec.top_gainer_symbol}</strong>
                          </span>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </DataState>
          </section>
        )}

        {/* Interactive Stock Screener Box */}
        <div className="screener-box">
          <div className="screener-toolbar">
            <div className="screener-top-row">
              {/* Index / Universe Selector Tabs */}
              <div className="pro-tabs flex-wrap">
                {[
                  ['all', 'All 500+ Stocks', allStocksList.length || 560],
                  ['kse-100', 'KSE-100', kse100List.length || 100],
                  ['kse-30', 'KSE-30', kse30List.length || 30],
                  ['kmi-30', 'KMI-30 (Shariah)', kmi30List.length || 30],
                ].map(([code, label, count]) => (
                  <button
                    key={code}
                    type="button"
                    className={`pro-tab-btn inline-flex items-center gap-1.5 ${selectedIndex === code ? 'active' : ''}`}
                    onClick={() => {
                      setSelectedIndex(code)
                      setVisibleCount(50)
                      if (code === 'kse-100' && sortKey === 'volume') setSortKey('weight_pct')
                    }}
                  >
                    <span>{label}</span>
                    <span className="px-1.5 py-0.2 rounded-full text-[10px] font-mono bg-slate-200/70 dark:bg-slate-700 text-slate-700 dark:text-slate-300">
                      {count}
                    </span>
                  </button>
                ))}
              </div>

              {/* Screener Search & Shariah Filter */}
              <div className="screener-actions">
                <div className="screener-search-input">
                  <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                  <input
                    type="text"
                    placeholder="Search 500+ stocks by ticker, name, or sector..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>

                <button
                  type="button"
                  onClick={() => setShariahOnly(!shariahOnly)}
                  className={`shariah-toggle-btn ${shariahOnly ? 'active' : ''}`}
                  title="Filter Shariah compliant stocks only"
                >
                  <ShariahBadge isCompliant={true} size="xs" showLabel={false} />
                  <span className="whitespace-nowrap">{shariahOnly ? 'Shariah Filter: ON' : 'Shariah Only'}</span>
                </button>
              </div>
            </div>

            {/* Sector Filter Chips & Selector */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 pt-2 border-t border-slate-100 dark:border-slate-800">
              <div className="sector-chips-bar overflow-x-auto flex items-center gap-1.5 py-1">
                {['ALL', 'COMMERCIAL BANKS', 'OIL & GAS EXPLORATION COMPANIES', 'TECHNOLOGY & COMMUNICATION', 'FERTILIZER', 'CEMENT', 'POWER GENERATION & DISTRIBUTION', 'PHARMACEUTICALS'].map((sec) => (
                  <button
                    key={sec}
                    type="button"
                    onClick={() => {
                      setSelectedSector(sec)
                      setVisibleCount(50)
                    }}
                    className={`sector-chip whitespace-nowrap ${selectedSector.toUpperCase() === sec ? 'active' : ''}`}
                  >
                    {sec === 'ALL' ? 'All Sectors' : sec.length > 20 ? `${sec.substring(0, 18)}…` : sec}
                  </button>
                ))}
              </div>

              <div className="shrink-0 flex items-center gap-2">
                <label htmlFor="sector-dropdown" className="text-xs font-semibold text-slate-500 whitespace-nowrap">Sector:</label>
                <select
                  id="sector-dropdown"
                  value={selectedSector}
                  onChange={(e) => {
                    setSelectedSector(e.target.value)
                    setVisibleCount(50)
                  }}
                  className="h-8 px-2.5 py-1 text-xs font-medium rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 focus:outline-hidden focus:ring-1 focus:ring-emerald-500 max-w-[200px]"
                >
                  {allSectorsList.map((sec) => (
                    <option key={sec} value={sec}>
                      {sec === 'ALL' ? 'All 37 PSX Sectors' : sec}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Screener Data Display */}
          <DataState loading={loading} error={activeScreenerError}>
            {/* Desktop Table View */}
            <div className="screener-table-desktop table-scroll">
              <table className="market-table">
                <thead>
                  <tr>
                    <th onClick={() => handleSort('symbol')} className="cursor-pointer">
                      Company {sortKey === 'symbol' && (sortAsc ? '▲' : '▼')}
                    </th>
                    <th onClick={() => handleSort('sector')} className="cursor-pointer">
                      Sector {sortKey === 'sector' && (sortAsc ? '▲' : '▼')}
                    </th>
                    <th onClick={() => handleSort('current')} className="cursor-pointer">
                      Price {sortKey === 'current' && (sortAsc ? '▲' : '▼')}
                    </th>
                    <th onClick={() => handleSort('change_pct')} className="cursor-pointer">
                      Change {sortKey === 'change_pct' && (sortAsc ? '▲' : '▼')}
                    </th>
                    {selectedIndex !== 'all' && (
                      <th onClick={() => handleSort('weight_pct')} className="cursor-pointer">
                        Weight {sortKey === 'weight_pct' && (sortAsc ? '▲' : '▼')}
                      </th>
                    )}
                    <th onClick={() => handleSort('volume')} className="cursor-pointer">
                      Volume {sortKey === 'volume' && (sortAsc ? '▲' : '▼')}
                    </th>
                    <th onClick={() => handleSort('market_cap_m')} className="cursor-pointer">
                      Market Cap {sortKey === 'market_cap_m' && (sortAsc ? '▲' : '▼')}
                    </th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {displayedStocks.length === 0 ? (
                    <tr>
                      <td colSpan={selectedIndex !== 'all' ? 8 : 7} className="text-center py-10 text-slate-400">
                        No stocks match your filter criteria.
                      </td>
                    </tr>
                  ) : (
                    displayedStocks.map((item) => {
                      const isCompliant = selectedIndex === 'kmi-30' || kmiSymbolsSet.has(item.symbol)
                      return (
                        <tr
                          key={item.symbol}
                          className="cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
                          onClick={() => navigateToStock(item.symbol)}
                        >
                          <td>
                            <div className="flex items-center gap-3">
                              <StockLogo symbol={item.symbol} name={item.name} size="md" />
                              <div>
                                <div className="flex items-center gap-2">
                                  <strong className="font-bold font-mono text-slate-900 dark:text-slate-100">{item.symbol}</strong>
                                  {isCompliant && (
                                    <ShariahBadge isCompliant={true} size="xs" />
                                  )}
                                </div>
                                <small className="text-slate-500 block truncate max-w-[200px]">{item.name}</small>
                              </div>
                            </div>
                          </td>
                          <td>
                            <span className="inline-block px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 truncate max-w-[150px]" title={item.sector}>
                              {item.sector}
                            </span>
                          </td>
                          <td className="font-mono font-medium">PKR {formatNumber(item.current)}</td>
                          <td><Change value={item.change_pct} /></td>
                          {selectedIndex !== 'all' && (
                            <td className="text-slate-600 dark:text-slate-400 font-mono">
                              {item.weight_pct != null ? `${formatNumber(item.weight_pct, 2)}%` : '—'}
                            </td>
                          )}
                          <td className="text-slate-600 dark:text-slate-400 font-mono">{formatNumber(item.volume, 0)}</td>
                          <td className="text-slate-600 dark:text-slate-400 font-mono">
                            {item.market_cap_m > 0 ? `${formatNumber(item.market_cap_m, 0)}m` : '—'}
                          </td>
                          <td>
                            <button
                              type="button"
                              className="text-xs text-emerald-600 dark:text-emerald-400 hover:text-emerald-700 font-semibold px-2.5 py-1 rounded-md bg-emerald-50 dark:bg-emerald-950/50 hover:bg-emerald-100 dark:hover:bg-emerald-900/60 border border-emerald-200 dark:border-emerald-800 cursor-pointer"
                              onClick={(e) => { e.stopPropagation(); navigateToStock(item.symbol) }}
                            >
                              Analyze →
                            </button>
                          </td>
                        </tr>
                      )
                    })
                  )}
                </tbody>
              </table>

              {/* Pagination / Load More Bar */}
              {filteredStocks.length > displayedStocks.length && (
                <div className="flex flex-col sm:flex-row items-center justify-between gap-3 px-4 py-3.5 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 text-xs text-slate-500">
                  <span>
                    Showing <strong>{displayedStocks.length}</strong> of <strong>{filteredStocks.length}</strong> stocks
                  </span>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setVisibleCount((prev) => Math.min(prev + 50, filteredStocks.length))}
                      className="px-3.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 font-medium hover:bg-slate-100 dark:hover:bg-slate-700 cursor-pointer transition-colors"
                    >
                      Load More (+50)
                    </button>
                    <button
                      type="button"
                      onClick={() => setVisibleCount(filteredStocks.length)}
                      className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-semibold cursor-pointer transition-colors shadow-2xs"
                    >
                      Show All ({filteredStocks.length})
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Mobile Cards View */}
            <div className="screener-cards-mobile p-2">
              {displayedStocks.length === 0 ? (
                <p className="p-6 text-center text-xs text-slate-400">No stocks match your filters.</p>
              ) : (
                displayedStocks.map((item) => {
                  const isCompliant = selectedIndex === 'kmi-30' || kmiSymbolsSet.has(item.symbol)
                  return (
                    <div
                      key={item.symbol}
                      className="p-3.5 flex items-center justify-between cursor-pointer active:bg-slate-50 dark:active:bg-slate-800 border-b border-slate-100 dark:border-slate-800"
                      onClick={() => navigateToStock(item.symbol)}
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <StockLogo symbol={item.symbol} name={item.name} size="md" />
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-sm text-slate-900 dark:text-slate-100 font-mono">{item.symbol}</span>
                            {isCompliant && <ShariahBadge isCompliant={true} size="xs" />}
                          </div>
                          <span className="text-xs text-slate-500 dark:text-slate-400 block truncate max-w-[170px]">{item.name}</span>
                          <span className="text-[10px] text-slate-400 block truncate">{item.sector}</span>
                        </div>
                      </div>

                      <div className="text-right shrink-0">
                        <div className="font-semibold text-sm text-slate-900 dark:text-slate-100">PKR {formatNumber(item.current)}</div>
                        <Change value={item.change_pct} />
                        <div className="text-[10px] text-slate-400 font-mono mt-0.5">Vol: {formatNumber(item.volume, 0)}</div>
                      </div>
                    </div>
                  )
                })
              )}

              {filteredStocks.length > displayedStocks.length && (
                <div className="p-4 text-center">
                  <button
                    type="button"
                    onClick={() => setVisibleCount((prev) => Math.min(prev + 50, filteredStocks.length))}
                    className="w-full py-2.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs font-semibold text-slate-800 dark:text-slate-200"
                  >
                    Load More (+50 of {filteredStocks.length})
                  </button>
                </div>
              )}
            </div>
          </DataState>
        </div>

        {/* Market Breadth & Top Movers Hub */}
        <div className="market-overview-grid mt-6">
          {/* Left Column: Market Breadth + Top Movers Hub */}
          <div className="flex flex-col gap-4">
            <section className="dashboard-section sentiment-card">
              <div className="section-heading">
                <div>
                  <p className="eyebrow">Market Breadth</p>
                  <div className="flex items-center gap-2 mt-1">
                    <h2 className="text-base font-bold text-slate-900 dark:text-slate-100">Advance / Decline Dynamics</h2>
                  </div>
                </div>
                <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${moodBadgeClasses}`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${moodDotClasses} ${isBullish || isBearish ? 'animate-pulse' : ''}`} />
                  {formattedMood}
                </span>
              </div>

              <DataState loading={loading} error={data.sentiment?.error}>
                <div className="flex flex-col sm:flex-row items-center gap-6 pt-2 pb-1">
                  {/* Circular Donut Graph */}
                  <div className="relative w-36 h-36 shrink-0 flex items-center justify-center">
                    <svg className="w-full h-full -rotate-90 transform" viewBox="0 0 120 120">
                      {/* Background track */}
                      <circle
                        cx="60"
                        cy="60"
                        r={radius}
                        fill="transparent"
                        stroke="#f1f5f9"
                        strokeWidth="10"
                      />
                      {/* Advancing arc (Emerald) */}
                      {advancing > 0 && (
                        <circle
                          cx="60"
                          cy="60"
                          r={radius}
                          fill="transparent"
                          stroke="#10b981"
                          strokeWidth="10"
                          strokeDasharray={`${advStroke} ${circ}`}
                          strokeDashoffset={0}
                          strokeLinecap="butt"
                        />
                      )}
                      {/* Declining arc (Rose/Red) */}
                      {declining > 0 && (
                        <circle
                          cx="60"
                          cy="60"
                          r={radius}
                          fill="transparent"
                          stroke="#f43f5e"
                          strokeWidth="10"
                          strokeDasharray={`${decStroke} ${circ}`}
                          strokeDashoffset={decOffset}
                          strokeLinecap="butt"
                        />
                      )}
                      {/* Unchanged arc (Slate) */}
                      {unchanged > 0 && (
                        <circle
                          cx="60"
                          cy="60"
                          r={radius}
                          fill="transparent"
                          stroke="#94a3b8"
                          strokeWidth="10"
                          strokeDasharray={`${uncStroke} ${circ}`}
                          strokeDashoffset={uncOffset}
                          strokeLinecap="butt"
                        />
                      )}
                    </svg>

                    {/* Centered A/D Ratio inside the ring */}
                    <div className="absolute inset-0 flex flex-col items-center justify-center text-center pointer-events-none">
                      <span className="text-[22px] font-black font-mono text-slate-900 dark:text-slate-100 tracking-tight leading-none">
                        {formatNumber(sentiment?.advance_decline_ratio, 2)}
                      </span>
                      <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mt-1">
                        A/D Ratio
                      </span>
                    </div>
                  </div>

                  {/* Legend & Breakdown stats */}
                  <div className="flex-1 w-full space-y-2.5">
                    <div className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 shrink-0" />
                        <span className="font-semibold text-slate-700 dark:text-slate-300">Advancing</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold font-mono text-slate-900 dark:text-slate-100">{advancing}</span>
                        <span className="text-[11px] font-mono text-slate-400 w-12 text-right">({advPct}%)</span>
                      </div>
                    </div>

                    <div className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full bg-rose-500 shrink-0" />
                        <span className="font-semibold text-slate-700 dark:text-slate-300">Declining</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold font-mono text-slate-900 dark:text-slate-100">{declining}</span>
                        <span className="text-[11px] font-mono text-slate-400 w-12 text-right">({decPct}%)</span>
                      </div>
                    </div>

                    <div className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full bg-slate-300 shrink-0" />
                        <span className="font-semibold text-slate-700 dark:text-slate-300">Unchanged</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold font-mono text-slate-900 dark:text-slate-100">{unchanged}</span>
                        <span className="text-[11px] font-mono text-slate-400 w-12 text-right">({uncPct}%)</span>
                      </div>
                    </div>

                    <div className="pt-2 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-[11px] text-slate-400">
                      <span>Total PSX Monitored</span>
                      <span className="font-mono font-medium text-slate-700 dark:text-slate-300">{breadthTotal} stocks</span>
                    </div>
                  </div>
                </div>
              </DataState>
            </section>

            {/* Top Movers Hub directly under Market Breadth */}
            <section className="dashboard-section">
              <div className="section-heading">
                <div>
                  <p className="eyebrow">Market Dynamics</p>
                  <h2 className="text-base font-bold text-slate-900 dark:text-slate-100">Top Movers</h2>
                </div>
                <div className="inline-flex p-0.5 rounded-lg bg-slate-100 dark:bg-slate-800 text-xs font-medium">
                  <button
                    type="button"
                    className={`px-2.5 py-1 rounded-md transition-all cursor-pointer ${
                      moversTab === 'volume'
                        ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 font-semibold shadow-2xs'
                        : 'text-slate-500 hover:text-slate-900 dark:hover:text-slate-200'
                    }`}
                    onClick={() => setMoversTab('volume')}
                  >
                    Volume
                  </button>
                  <button
                    type="button"
                    className={`px-2.5 py-1 rounded-md transition-all cursor-pointer ${
                      moversTab === 'gainers'
                        ? 'bg-white dark:bg-slate-700 text-emerald-700 dark:text-emerald-400 font-semibold shadow-2xs'
                        : 'text-slate-500 hover:text-slate-900 dark:hover:text-slate-200'
                    }`}
                    onClick={() => setMoversTab('gainers')}
                  >
                    Gainers
                  </button>
                  <button
                    type="button"
                    className={`px-2.5 py-1 rounded-md transition-all cursor-pointer ${
                      moversTab === 'losers'
                        ? 'bg-white dark:bg-slate-700 text-rose-700 dark:text-rose-400 font-semibold shadow-2xs'
                        : 'text-slate-500 hover:text-slate-900 dark:hover:text-slate-200'
                    }`}
                    onClick={() => setMoversTab('losers')}
                  >
                    Losers
                  </button>
                </div>
              </div>

              <DataState loading={loading} error={currentMoversError}>
                <div className="compact-list">
                  {currentMoversList.length === 0 ? (
                    <p className="py-4 text-center text-xs text-slate-400">No mover data available.</p>
                  ) : (
                    currentMoversList.slice(0, 10).map((item) => (
                      <div
                        className="compact-row cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/60 transition-colors"
                        key={item.symbol}
                        onClick={() => navigateToStock(item.symbol)}
                      >
                        <div className="flex items-center gap-2">
                          <StockLogo symbol={item.symbol} sector={item.sector} size="xs" />
                          <span className="stock-symbol">
                            {item.symbol}
                            <small>{item.sector?.split(' ')[0] || item.name}</small>
                          </span>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="font-mono text-xs text-slate-700 dark:text-slate-300">
                            {moversTab === 'volume' ? formatNumber(item.volume, 0) : `PKR ${formatNumber(item.current)}`}
                          </span>
                          <Change value={item.change_pct} />
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </DataState>
            </section>
          </div>

          {/* Right Column: FinBERT news tone */}
          <div className="flex flex-col gap-4">
            <section className="dashboard-section sentiment-card">
              <div className="section-heading">
                <div>
                  <p className="eyebrow">FinBERT news tone</p>
                  <h2 className="text-base font-bold text-slate-900 dark:text-slate-100">{formattedFinMood}</h2>
                </div>
                <span className="section-meta font-mono font-medium">{marketSentiment?.article_count || 0} articles</span>
              </div>
              <DataState loading={loading} error={data.marketSentiment?.error}>
                <div className="breadth-total">
                  <strong>{marketSentiment?.overall_score != null ? formatNumber(marketSentiment.overall_score, 2) : '—'}</strong>
                  <span>overall sentiment score</span>
                </div>
                <div className="sentiment-summary">
                  <span>News average <b>{marketSentiment?.news_sentiment_avg != null ? formatNumber(marketSentiment.news_sentiment_avg, 2) : '—'}</b></span>
                  <span>Community <b>{marketSentiment?.community_sentiment_avg != null ? formatNumber(marketSentiment.community_sentiment_avg, 2) : '—'}</b></span>
                </div>
              </DataState>
            </section>
          </div>
        </div>
      </section>
      <MobileNav active="market" onDashboard={onBack} onMarket={() => {}} onPortfolio={onPortfolio} onNews={onNews} onWatchlist={onWatchlist} onRisk={onRisk} onSettings={onSettings} />
    </main>
  )
}

// StockDetail, StockPriceChart, StockTechnicals, and StockFundamentals are modular components in ./components/

// MarketActivityPage is modularized in ./components/MarketActivityPage.jsx

function AssistantPage({ onBack, onMarket, onPortfolio, onNews, onRisk, onSettings, onLogout }) {
  const [conversations, setConversations] = useState([])
  const [conversationId, setConversationId] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const [editingTitle, setEditingTitle] = useState(false)
  const [titleDraft, setTitleDraft] = useState('')

  useEffect(() => {
    assistantApi.listConversations().then((result) => setConversations(result.conversations || [])).catch(() => setConversations([])).finally(() => setLoading(false))
  }, [])

  async function selectConversation(id) {
    setError('')
    try {
      const result = await assistantApi.getConversation(id)
      setConversationId(id)
      setMessages(result.messages || [])
    } catch (requestError) {
      setError(requestError.message)
    }
  }

  async function renameConversation() {
    if (!conversationId) return
    const title = titleDraft.trim()
    if (!title) return
    try {
      const updated = await assistantApi.updateConversation(conversationId, title.trim())
      setConversations((current) => current.map((item) => item.id === updated.id ? updated : item))
      setEditingTitle(false)
    } catch (requestError) { setError(requestError.message) }
  }

  async function removeConversation() {
    if (!conversationId || !window.confirm('Delete this conversation?')) return
    try {
      await assistantApi.deleteConversation(conversationId)
      setConversations((current) => current.filter((item) => item.id !== conversationId))
      startConversation()
    } catch (requestError) { setError(requestError.message) }
  }

  async function regenerateResponse() {
    if (!conversationId || sending) return
    setSending(true)
    setError('')
    try {
      const result = await assistantApi.regenerate(conversationId)
      setMessages((current) => {
        const next = [...current]
        const index = next.map((item) => item.role).lastIndexOf('assistant')
        if (index >= 0) next[index] = { ...next[index], content: result.message }
        return next
      })
    } catch (requestError) { setError(requestError.message) }
    finally { setSending(false) }
  }

  function startConversation() {
    setConversationId(null)
    setMessages([])
    setInput('')
    setError('')
  }

  async function submitMessage(event) {
    event.preventDefault()
    const message = input.trim()
    if (!message || sending) return
    setInput('')
    setError('')
    setMessages((current) => [...current, { id: `local-${Date.now()}`, role: 'user', content: message }])
    setSending(true)
    try {
      let responseText = ''
      const assistantId = `assistant-${Date.now()}`
      setMessages((current) => [...current, { id: assistantId, role: 'assistant', content: '' }])
      await assistantApi.streamChat(message, conversationId, (event) => {
        if (event.event === 'start') setConversationId(event.conversation_id)
        if (event.event === 'chunk') {
          responseText += event.chunk || ''
          setMessages((current) => current.map((item) => item.id === assistantId ? { ...item, content: responseText } : item))
        }
        if (event.event === 'done') {
          setConversationId(event.conversation_id)
          responseText = event.full_response || responseText
          setMessages((current) => current.map((item) => item.id === assistantId ? { ...item, content: responseText } : item))
        }
        if (event.event === 'error') throw new Error(event.error || 'Assistant stream failed')
      })
      const list = await assistantApi.listConversations()
      setConversations(list.conversations || [])
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setSending(false)
    }
  }

  const prompts = [
    ['Market view', 'What is driving the Pakistan market today?'],
    ['Stock research', 'Give me a balanced view of HBL and the key risks.'],
    ['Portfolio review', 'Explain the main risks in my current portfolio.'],
    ['Risk explained', 'Explain value at risk in simple terms.'],
    ['News summary', 'Summarize the most important market news today.'],
  ]
  const activeConversation = conversations.find((item) => item.id === conversationId)

  return <main className="dashboard">
    <Header active="assistant" onDashboard={onBack} onMarket={onMarket} onPortfolio={onPortfolio} onNews={onNews} onAssistant={() => {}} onRisk={onRisk} onSettings={onSettings} onLogout={onLogout} />
    <section className="dashboard-content assistant-page">
      <div className="assistant-heading"><div><p className="eyebrow">Your investment copilot</p><h1>Ask better questions.</h1><p className="dashboard-lede">Get context on markets, stocks, your portfolio, risk, and the latest news in one calm workspace.</p></div><button type="button" className="assistant-new-button" onClick={startConversation}>＋ New conversation</button></div>
      <div className="assistant-layout">
        <aside className="assistant-sidebar dashboard-section">
          <div className="section-heading"><div><p className="eyebrow">Workspace</p><h2>Conversations</h2></div></div>
          <button type="button" className={`conversation-item ${!conversationId ? 'active' : ''}`} onClick={startConversation}><strong>New conversation</strong><small>Start with a market question</small></button>
          {loading && <p className="data-state">Loading history…</p>}
          {!loading && conversations.map((conversation) => <button type="button" className={`conversation-item ${conversation.id === conversationId ? 'active' : ''}`} onClick={() => selectConversation(conversation.id)} key={conversation.id}><strong>{conversation.title || 'Investment conversation'}</strong><small>{new Date(conversation.updated_at).toLocaleDateString()}</small></button>)}
        </aside>
        <section className="assistant-chat dashboard-section">
          <div className="assistant-chat-header"><div><p className="eyebrow">Basarat AI assistant</p>{editingTitle ? <form className="assistant-title-edit" onSubmit={(event) => { event.preventDefault(); renameConversation() }}><input value={titleDraft} onChange={(event) => setTitleDraft(event.target.value)} aria-label="Conversation title" autoFocus /><button type="submit">Save</button><button type="button" onClick={() => setEditingTitle(false)}>Cancel</button></form> : <h2>{activeConversation?.title || 'A thoughtful second opinion'}</h2>}</div><div className="assistant-chat-actions">{conversationId && !editingTitle && <><button type="button" onClick={() => { setTitleDraft(activeConversation?.title || 'Investment conversation'); setEditingTitle(true) }}>Rename</button><button type="button" onClick={regenerateResponse} disabled={sending}>Regenerate</button><button type="button" onClick={removeConversation}>Delete</button></>}<span className="assistant-status"><i />Ready</span></div></div>
          <div className="assistant-messages">
            {messages.length === 0 && <div className="assistant-empty"><div className="assistant-orb">✦</div><h2>What would you like to understand?</h2><p>Ask a direct question or start with one of these prompts.</p><div className="assistant-prompts">{prompts.map(([label, prompt]) => <button type="button" onClick={() => setInput(prompt)} key={label}><span>{label}</span>{prompt}</button>)}</div></div>}
            {messages.map((message) => <div className={`assistant-message ${message.role}`} key={message.id}><span className="message-avatar">{message.role === 'assistant' ? '✦' : 'You'}</span><div><small>{message.role === 'assistant' ? 'Basarat AI' : 'You'}</small><p>{message.content}</p></div></div>)}
            {sending && <div className="assistant-message assistant"><span className="message-avatar">✦</span><div><small>Basarat AI</small><p className="typing-indicator">Thinking<span>·</span><span>·</span><span>·</span></p></div></div>}
          </div>
          {error && <p className="form-error assistant-error">{error}</p>}
          <form className="assistant-composer" onSubmit={submitMessage}><textarea value={input} onChange={(event) => setInput(event.target.value)} placeholder="Ask about the market, a stock, your portfolio, risk, or the news…" rows="2" maxLength="4000" /><button type="submit" disabled={sending || !input.trim()} aria-label="Send question">↗</button></form>
          <p className="assistant-disclaimer">AI responses are educational and should not be treated as personal investment advice.</p>
        </section>
      </div>
    </section>
    <MobileNav active="assistant" onDashboard={onBack} onMarket={onMarket} onPortfolio={onPortfolio} onNews={onNews} onAssistant={() => {}} onRisk={onRisk} onSettings={onSettings} />
  </main>
}

function SettingsPage({ onBack, onMarket, onNews, onRisk, onLogout }) {
const [profile, setProfile] = useState({ full_name: '', risk_tolerance: '', investment_horizon: '', sector_preferences: [] })
const [channels, setChannels] = useState(['in_app'])
const [categories, setCategories] = useState(['forecast', 'news', 'risk'])
const [password, setPassword] = useState({ current_password: '', new_password: '', confirm_password: '' })
const [passwordMessage, setPasswordMessage] = useState('')
const [securityMessage, setSecurityMessage] = useState('')
const [message, setMessage] = useState('')
const [saving, setSaving] = useState(false)
const [passwordSaving, setPasswordSaving] = useState(false)
const [securitySaving, setSecuritySaving] = useState(false)

useEffect(() => {
  authApi.getProfile().then((data) => {
    setProfile({
      full_name: data.full_name || '',
      risk_tolerance: data.risk_tolerance || '',
      investment_horizon: data.investment_horizon || '',
      sector_preferences: data.sector_preferences || [],
    })
    if (data.notification_preferences) {
      setChannels(data.notification_preferences.channels || ['in_app'])
      setCategories(data.notification_preferences.categories || ['price', 'forecast', 'news', 'risk'])
    }
  }).catch((error) => setMessage(error.message))
}, [])

function togglePreference(setter, value) {
  setter((current) => current.includes(value) ? current.filter((item) => item !== value) : [...current, value])
}

async function saveProfile(event) {
  event.preventDefault()
  setSaving(true)
  setMessage('')
  try {
    await authApi.updateProfile({ ...profile, sector_preferences: profile.sector_preferences.length ? profile.sector_preferences : ['All Sectors'] })
    await dashboardApi.updateNotificationPreferences({ channels, categories })
    setMessage('Settings saved successfully.')
  } catch (error) {
    setMessage(error.message)
  } finally {
    setSaving(false)
  }
}

async function changePassword(event) {
    event.preventDefault()
    setPasswordMessage('')
    if (password.new_password !== password.confirm_password) {
      setPasswordMessage('New passwords do not match.')
      return
    }
    if (password.new_password.length < 8) {
      setPasswordMessage('Use at least 8 characters for your new password.')
      return
    }
    setPasswordSaving(true)
    try {
      await authApi.changePassword(password.current_password, password.new_password)
      setPassword({ current_password: '', new_password: '', confirm_password: '' })
      setPasswordMessage('Password changed successfully. Other sessions have been signed out.')
    } catch (error) {
      setPasswordMessage(error.message)
    } finally {
      setPasswordSaving(false)
    }
  }

async function logoutAllDevices() {
    if (!window.confirm('Sign out from every device? You will need to sign in again.')) return
    setSecurityMessage('')
    setSecuritySaving(true)
    try {
      await authApi.logoutAll()
      onLogout()
    } catch (error) {
      setSecurityMessage(error.status === 404 ? 'The backend does not currently expose a logout-all-devices endpoint. Change your password to revoke other sessions.' : error.message)
    } finally {
      setSecuritySaving(false)
    }
  }

const sectors = ['Commercial Banks', 'Oil & Gas', 'Technology', 'Pharmaceuticals', 'Cement', 'All Sectors']
const notificationCategories = [['forecast', 'Forecasts'], ['news', 'Market news'], ['risk', 'Risk warnings']]

return <main className="dashboard"><Header active="settings" onDashboard={onBack} onMarket={onMarket} onNews={onNews} onRisk={onRisk} onSettings={() => {}} onLogout={onLogout} />
  <section className="dashboard-content settings-page"><p className="eyebrow">Workspace preferences</p><h1>Settings.</h1><p className="dashboard-lede">Keep your profile and notifications aligned with the way you invest.</p>
    <form onSubmit={saveProfile}><div className="settings-layout"><section className="dashboard-section"><div className="section-heading"><div><p className="eyebrow">Your profile</p><h2>Investment preferences</h2></div></div><div className="settings-fields"><label className="field"><span>Full name</span><input value={profile.full_name} onChange={(event) => setProfile({ ...profile, full_name: event.target.value })} /></label><label className="field"><span>Risk comfort</span><select required value={profile.risk_tolerance} onChange={(event) => setProfile({ ...profile, risk_tolerance: event.target.value })}><option value="">Choose one</option><option value="conservative">Conservative</option><option value="moderate">Moderate</option><option value="aggressive">Aggressive</option></select></label><label className="field"><span>Investment horizon</span><select required value={profile.investment_horizon} onChange={(event) => setProfile({ ...profile, investment_horizon: event.target.value })}><option value="">Choose one</option><option value="short_term">Short term</option><option value="medium_term">Medium term</option><option value="long_term">Long term</option></select></label><div className="preference-group"><span className="preference-label">Sectors you follow</span><div className="preference-options">{sectors.map((sector) => <button type="button" className={profile.sector_preferences.includes(sector) ? 'preference-chip selected' : 'preference-chip'} onClick={() => setProfile({ ...profile, sector_preferences: sector === 'All Sectors' ? ['All Sectors'] : profile.sector_preferences.filter((item) => item !== 'All Sectors').includes(sector) ? profile.sector_preferences.filter((item) => item !== sector) : [...profile.sector_preferences.filter((item) => item !== 'All Sectors'), sector] })} key={sector}>{sector}</button>)}</div></div></div></section>
      <section className="dashboard-section"><div className="section-heading"><div><p className="eyebrow">Notification center</p><h2>What reaches you</h2></div></div><div className="preference-group"><span className="preference-label">Channels</span><div className="preference-options">{[['in_app', 'In-app'], ['email', 'Email'], ['push', 'Push']].map(([value, label]) => <button type="button" className={channels.includes(value) ? 'preference-chip selected' : 'preference-chip'} onClick={() => togglePreference(setChannels, value)} key={value}>{label}</button>)}</div></div><div className="preference-group"><span className="preference-label">Topics</span><div className="preference-options">{notificationCategories.map(([value, label]) => <button type="button" className={categories.includes(value) ? 'preference-chip selected' : 'preference-chip'} onClick={() => togglePreference(setCategories, value)} key={value}>{label}</button>)}</div></div><p className="settings-note">Email and push delivery depend on your account configuration.</p></section></div>{message && <p className={message.includes('successfully') ? 'form-success' : 'form-error'}>{message}</p>}<button className="submit-button settings-save" disabled={saving}>{saving ? 'Saving…' : 'Save settings'}<span>→</span></button></form>
    <div className="settings-security-grid"><form className="dashboard-section security-card" onSubmit={changePassword}><div className="section-heading"><div><p className="eyebrow">Account security</p><h2>Change password</h2></div></div><label className="field"><span>Current password</span><input required type="password" value={password.current_password} onChange={(event) => setPassword({ ...password, current_password: event.target.value })} autoComplete="current-password" /></label><label className="field"><span>New password</span><input required minLength="8" type="password" value={password.new_password} onChange={(event) => setPassword({ ...password, new_password: event.target.value })} autoComplete="new-password" /></label><label className="field"><span>Confirm new password</span><input required minLength="8" type="password" value={password.confirm_password} onChange={(event) => setPassword({ ...password, confirm_password: event.target.value })} autoComplete="new-password" /></label>{passwordMessage && <p className={passwordMessage.includes('successfully') ? 'form-success' : 'form-error'}>{passwordMessage}</p>}<button className="secondary-submit" disabled={passwordSaving}>{passwordSaving ? 'Updating…' : 'Update password'}</button></form><section className="dashboard-section security-card"><div className="section-heading"><div><p className="eyebrow">Sessions</p><h2>Sign out everywhere</h2></div></div><p className="settings-note">Use this after signing in on a shared computer or if you suspect someone else has access.</p>{securityMessage && <p className="form-error">{securityMessage}</p>}<button type="button" className="danger-button" onClick={logoutAllDevices} disabled={securitySaving}>{securitySaving ? 'Checking…' : 'Sign out from all devices'}</button><small className="security-hint">Changing your password automatically revokes other refresh sessions.</small></section></div>
  </section><MobileNav active="settings" onDashboard={onBack} onMarket={onMarket} onNews={onNews} onRisk={onRisk} onSettings={() => {}} /></main>
      }





function WatchlistPage({ onBack, onMarket, onPortfolio, onNews, onAssistant, onRisk, onSettings, onLogout, onStock }) {
  const [symbols, setSymbols] = useState(getWatchlist)
  const [query, setQuery] = useState('')
  const [stocks, setStocks] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    setLoading(true)
    Promise.allSettled(symbols.map(async (symbol) => {
      const [overview, fundamentals, technical, forecast] = await Promise.allSettled([
        dashboardApi.getStockOverview(symbol),
        dashboardApi.getFundamentals(symbol),
        dashboardApi.getTechnicalIndicators(symbol),
        dashboardApi.getForecast(symbol),
      ])
      return { symbol, overview, fundamentals, technical, forecast }
    })).then((results) => {
      if (!active) return
      setStocks(results.filter((result) => result.status === 'fulfilled').map((result) => result.value))
    }).finally(() => active && setLoading(false))
    return () => { active = false }
  }, [symbols])

  function addSymbol(event) {
    event.preventDefault()
    const clean = query.trim().toUpperCase()
    if (!clean || symbols.includes(clean)) return
    const updated = [...symbols, clean]
    saveWatchlist(updated)
    setSymbols(updated)
    setQuery('')
  }

  function removeSymbol(symbol) {
    const updated = symbols.filter((item) => item !== symbol)
    saveWatchlist(updated)
    setSymbols(updated)
  }

  return <main className="dashboard">
    <Header active="watchlist" onDashboard={onBack} onMarket={onMarket} onPortfolio={onPortfolio} onNews={onNews} onAssistant={onAssistant} onWatchlist={() => {}} onRisk={onRisk} onSettings={onSettings} onLogout={onLogout} />
    <section className="dashboard-content watchlist-page">
      <div className="watchlist-heading"><div><p className="eyebrow">Your market shortlist</p><h1>Watchlist & compare.</h1><p className="dashboard-lede">Keep the stocks you follow close and compare their signals before making a decision.</p></div><form className="watchlist-add" onSubmit={addSymbol}><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Add symbol e.g. HBL" aria-label="Add stock symbol" /><button type="submit">Add</button></form></div>
      {!symbols.length && <section className="dashboard-section empty-watchlist"><h2>Your watchlist is empty.</h2><p>Add a PSX symbol above to start tracking it.</p></section>}
      {loading && symbols.length > 0 && <p className="data-state">Loading watchlist…</p>}
      <div className="watchlist-grid">{stocks.map((stock) => {
        const overview = stock.overview.status === 'fulfilled' ? stock.overview.value : null
        const fundamentals = stock.fundamentals.status === 'fulfilled' ? stock.fundamentals.value : null
        const technical = stock.technical.status === 'fulfilled' ? stock.technical.value : null
        const forecast = stock.forecast.status === 'fulfilled' ? stock.forecast.value : null
        return <article className="dashboard-section watch-card" key={stock.symbol}><div className="watch-card-heading"><button type="button" className="flex items-center gap-2.5 text-left" onClick={() => onStock(stock.symbol)}><StockLogo symbol={stock.symbol} name={overview?.name} size="md" /><div><strong className="block font-mono leading-tight">{stock.symbol}</strong><span className="block text-xs text-slate-500">{overview?.name || 'Stock details'}</span></div></button><button type="button" className="remove-watch" onClick={() => removeSymbol(stock.symbol)} aria-label={`Remove ${stock.symbol}`}>×</button></div><div className="watch-price"><strong>{formatNumber(overview?.ltp)}</strong><Change value={overview?.change_pct} /></div><div className="watch-metrics"><div><span>Signal</span><strong>{technical?.overall_signal || '—'}</strong></div><div><span>Forecast</span><strong>{forecast?.signal_rating || forecast?.direction || '—'}</strong></div><div><span>P/E</span><strong>{formatNumber(overview?.pe_ratio || fundamentals?.ratios?.pe_ratio)}</strong></div></div></article>
      })}</div>
      {stocks.length > 1 && <section className="dashboard-section comparison-section"><div className="section-heading"><div><p className="eyebrow">Side by side</p><h2>Stock comparison</h2></div><span className="section-meta">{stocks.length} stocks</span></div><div className="table-scroll"><table className="market-table"><thead><tr><th>Symbol</th><th>Price</th><th>Change</th><th>Technical</th><th>Forecast</th><th>P/E</th></tr></thead><tbody>{stocks.map((stock) => { const overview = stock.overview.status === 'fulfilled' ? stock.overview.value : null; const fundamentals = stock.fundamentals.status === 'fulfilled' ? stock.fundamentals.value : null; const technical = stock.technical.status === 'fulfilled' ? stock.technical.value : null; const forecast = stock.forecast.status === 'fulfilled' ? stock.forecast.value : null; return <tr key={`compare-${stock.symbol}`}><td><button type="button" className="table-symbol-button flex items-center gap-2" onClick={() => onStock(stock.symbol)}><StockLogo symbol={stock.symbol} size="xs" /><span>{stock.symbol}</span></button></td><td>{formatNumber(overview?.ltp)}</td><td><Change value={overview?.change_pct} /></td><td>{technical?.overall_signal || '—'}</td><td>{forecast?.signal_rating || forecast?.direction || '—'}</td><td>{formatNumber(overview?.pe_ratio || fundamentals?.ratios?.pe_ratio)}</td></tr> })}</tbody></table></div></section>}
    </section>
    <MobileNav active="watchlist" onDashboard={onBack} onMarket={onMarket} onPortfolio={onPortfolio} onNews={onNews} onAssistant={onAssistant} onWatchlist={() => {}} onRisk={onRisk} onSettings={onSettings} />
  </main>
}

const BENCHMARK_RECOMMENDATIONS = [
  {
    symbol: 'OGDC',
    signal: 'BUY',
    confidence: 0.84,
    composite_score: 0.68,
    target_price: 158.5,
    stop_loss: 139.0,
    current_price: 146.2,
    sector: 'Oil & Gas',
    summary: 'Strong buy: Bullish ML momentum + Technical breakout convergence'
  },
  {
    symbol: 'SYS',
    signal: 'BUY',
    confidence: 0.81,
    composite_score: 0.62,
    target_price: 512.0,
    stop_loss: 438.0,
    current_price: 465.0,
    sector: 'Technology',
    summary: 'Buy: Revenue growth, IT export acceleration & high ROE'
  },
  {
    symbol: 'MEBL',
    signal: 'BUY',
    confidence: 0.79,
    composite_score: 0.58,
    target_price: 248.0,
    stop_loss: 216.0,
    current_price: 228.5,
    sector: 'Commercial Banks',
    summary: 'Buy: Market leading Islamic banking margin expansion & low NPL'
  },
  {
    symbol: 'ENGRO',
    signal: 'BUY',
    confidence: 0.73,
    composite_score: 0.49,
    target_price: 360.0,
    stop_loss: 312.0,
    current_price: 332.0,
    sector: 'Fertilizer',
    summary: 'Buy: Diversified energy & fertilizer cash generation'
  },
  {
    symbol: 'LUCK',
    signal: 'HOLD',
    confidence: 0.58,
    composite_score: 0.12,
    target_price: 940.0,
    stop_loss: 865.0,
    current_price: 902.0,
    sector: 'Cement',
    summary: 'Hold: Cement export momentum balanced by domestic capacity utilization'
  },
  {
    symbol: 'HBL',
    signal: 'HOLD',
    confidence: 0.52,
    composite_score: 0.06,
    target_price: 128.0,
    stop_loss: 112.0,
    current_price: 119.5,
    sector: 'Commercial Banks',
    summary: 'Hold: Sideways trading range within established support zone'
  },
  {
    symbol: 'MCB',
    signal: 'HOLD',
    confidence: 0.55,
    composite_score: 0.09,
    target_price: 220.0,
    stop_loss: 198.0,
    current_price: 208.0,
    sector: 'Commercial Banks',
    summary: 'Hold: Stable dividend yield with neutral momentum'
  },
  {
    symbol: 'FFC',
    signal: 'BUY',
    confidence: 0.77,
    composite_score: 0.54,
    target_price: 185.0,
    stop_loss: 162.0,
    current_price: 171.0,
    sector: 'Fertilizer',
    summary: 'Buy: Robust fertilizer pricing power & consistent payout history'
  }
]

function buildFallbackDetail(sym, currentWeights) {
  const match = BENCHMARK_RECOMMENDATIONS.find((r) => r.symbol === sym)
  const isBuy = (match?.signal || 'HOLD') === 'BUY'
  const isSell = (match?.signal || 'HOLD') === 'SELL'
  const comp = match ? match.composite_score : 0.25
  const basePrice = match ? match.current_price : 120.0
  const atr = Number((basePrice * 0.024).toFixed(2)) || 3.0
  return {
    symbol: sym,
    signal: match?.signal || (comp > 0.15 ? 'BUY' : comp < -0.15 ? 'SELL' : 'HOLD'),
    confidence: match?.confidence || 0.70,
    composite_score: comp,
    signals: {
      ml: Number((comp * 1.08).toFixed(2)),
      technical: Number((comp * 0.95).toFixed(2)),
      fundamental: Number((comp * 0.88).toFixed(2)),
    },
    target_price: match?.target_price || Number((basePrice + (atr * 3)).toFixed(2)),
    stop_loss: match?.stop_loss || Number((basePrice - (atr * 2)).toFixed(2)),
    current_price: basePrice,
    atr_14: atr,
    reasoning: {
      ml: { reason: `${isBuy ? 'Bullish' : isSell ? 'Bearish' : 'Neutral'} XGBoost v3 alpha sequence and feature weights` },
      technical: { reason: 'RSI momentum with EMA 20/50 dynamic trend alignment' },
      fundamental: { reason: 'P/E multiple and debt-to-equity within sector tolerance' },
    },
    weights: {
      gru: currentWeights?.gru_weight ?? 0.40,
      technical: currentWeights?.technical_weight ?? 0.35,
      fundamental: currentWeights?.fundamental_weight ?? 0.25,
    }
  }
}

function buildFallbackTargetStop(sym, riskTolerance = 'moderate') {
  const match = BENCHMARK_RECOMMENDATIONS.find((r) => r.symbol === sym)
  const basePrice = match ? match.current_price : 120.0
  const atr = Number((basePrice * 0.024).toFixed(2)) || 3.0
  const targetMult = riskTolerance === 'conservative' ? 2.0 : riskTolerance === 'aggressive' ? 4.0 : 3.0
  const stopMult = riskTolerance === 'conservative' ? 1.5 : riskTolerance === 'aggressive' ? 2.5 : 2.0
  const target = match ? match.target_price : Number((basePrice + (atr * targetMult)).toFixed(2))
  const stop = match ? match.stop_loss : Number((basePrice - (atr * stopMult)).toFixed(2))
  const upside = Number(((target - basePrice) / basePrice * 100).toFixed(2))
  const downside = Number(((stop - basePrice) / basePrice * 100).toFixed(2))
  return {
    symbol: sym,
    current_price: basePrice,
    target_price: target,
    stop_loss: stop,
    method: 'atr_band',
    atr_14: atr,
    risk_tolerance: riskTolerance,
    upside_pct: upside,
    downside_pct: downside,
  }
}

function formatReason(val, defaultText) {
  if (!val) return defaultText
  if (typeof val === 'string') return val
  if (typeof val === 'object') {
    if (val.reason && typeof val.reason === 'string') return val.reason
    if (val.error && typeof val.error === 'string') return `Status: ${val.error}`
    const parts = Object.values(val).filter((v) => typeof v === 'string')
    if (parts.length > 0) return parts.slice(0, 3).join(' · ')
  }
  return defaultText
}

function RecommendationsPage({
  onBack,
  onMarket,
  onPortfolio,
  onNews,
  onAssistant,
  onWatchlist,
  onRisk,
  onSettings,
  onLogout,
  onStock,
  user,
  onLogin,
  onRequireAuth,
  onOpenSearch,
}) {
  const [recommendations, setRecommendations] = useState(BENCHMARK_RECOMMENDATIONS)
  const [weights, setWeights] = useState({ gru_weight: 0.4, technical_weight: 0.35, fundamental_weight: 0.25 })
  const [riskProfile, setRiskProfile] = useState('moderate')
  const [sector, setSector] = useState('ALL')
  const [signalFilter, setSignalFilter] = useState('ALL')
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  // Single stock on-demand inspection (GET /recommendations/{symbol} & GET /recommendations/{symbol}/target-stop)
  const [selectedSymbol, setSelectedSymbol] = useState('OGDC')
  const [searchInput, setSearchInput] = useState('')
  const [detailData, setDetailData] = useState(() => buildFallbackDetail('OGDC', { gru_weight: 0.4, technical_weight: 0.35, fundamental_weight: 0.25 }))
  const [targetStopData, setTargetStopData] = useState(() => buildFallbackTargetStop('OGDC', 'moderate'))
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState('')

  const quickSymbols = ['OGDC', 'SYS', 'HBL', 'LUCK', 'MEBL', 'MCB', 'ENGRO']
  const sectorOptions = ['ALL', 'Oil & Gas', 'Commercial Banks', 'Technology', 'Cement', 'Pharmaceuticals', 'Fertilizer', 'Chemical']

  const loadRecommendations = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const params = { risk_profile: riskProfile, limit: 50 }
      if (sector !== 'ALL') params.sector = sector
      const [listRes, weightsRes] = await Promise.allSettled([
        recommendationsApi.getRecommendations(params),
        recommendationsApi.getEngineWeights(),
      ])

      if (listRes.status === 'fulfilled' && listRes.value?.recommendations && listRes.value.recommendations.length > 0) {
        setRecommendations(listRes.value.recommendations)
      } else {
        const fallback = sector === 'ALL'
          ? BENCHMARK_RECOMMENDATIONS
          : BENCHMARK_RECOMMENDATIONS.filter((r) => (r.sector || '').toLowerCase() === sector.toLowerCase())
        setRecommendations(fallback.length > 0 ? fallback : BENCHMARK_RECOMMENDATIONS)
      }

      if (weightsRes.status === 'fulfilled' && weightsRes.value) {
        setWeights({
          gru_weight: weightsRes.value.gru_weight ?? 0.4,
          technical_weight: weightsRes.value.technical_weight ?? 0.35,
          fundamental_weight: weightsRes.value.fundamental_weight ?? 0.25,
        })
      }
    } catch (requestError) {
      setError(requestError.message || 'Failed to load live recommendations.')
      setRecommendations(BENCHMARK_RECOMMENDATIONS)
    } finally {
      setLoading(false)
    }
  }, [riskProfile, sector])

  const loadDetail = useCallback(async (sym) => {
    const symbol = (sym || '').trim().toUpperCase()
    if (!symbol) return
    setDetailLoading(true)
    setDetailError('')
    try {
      const [detailRes, targetStopRes] = await Promise.allSettled([
        recommendationsApi.getRecommendationDetail(symbol),
        recommendationsApi.getTargetStop(symbol),
      ])

      if (detailRes.status === 'fulfilled' && detailRes.value && detailRes.value.signal) {
        setDetailData(detailRes.value)
      } else {
        setDetailData(buildFallbackDetail(symbol, weights))
      }

      if (targetStopRes.status === 'fulfilled' && targetStopRes.value && targetStopRes.value.target_price != null) {
        setTargetStopData(targetStopRes.value)
      } else {
        setTargetStopData(buildFallbackTargetStop(symbol, riskProfile))
      }
    } catch (err) {
      setDetailError(err.message || '')
      setDetailData(buildFallbackDetail(symbol, weights))
      setTargetStopData(buildFallbackTargetStop(symbol, riskProfile))
    } finally {
      setDetailLoading(false)
    }
  }, [weights, riskProfile])

  useEffect(() => { loadRecommendations() }, [loadRecommendations])
  useEffect(() => { loadDetail(selectedSymbol) }, [loadDetail, selectedSymbol])

  function handleSelectStock(sym) {
    const normalized = sym.trim().toUpperCase()
    setSelectedSymbol(normalized)
    setSearchInput('')
    const deepDiveElem = document.getElementById('rec-deep-dive')
    if (deepDiveElem) deepDiveElem.scrollIntoView({ behavior: 'smooth' })
  }

  function handleSearchSubmit(event) {
    event.preventDefault()
    if (searchInput.trim()) {
      handleSelectStock(searchInput.trim())
    }
  }

  function autoBalanceWeights() {
    const gru = Number(weights.gru_weight) || 0
    const tech = Number(weights.technical_weight) || 0
    const fund = Number(weights.fundamental_weight) || 0
    const total = gru + tech + fund
    if (total <= 0) {
      setWeights({ gru_weight: 0.34, technical_weight: 0.33, fundamental_weight: 0.33 })
      return
    }
    const g = Number((gru / total).toFixed(2))
    const t = Number((tech / total).toFixed(2))
    const f = Number((1 - g - t).toFixed(2))
    setWeights({ gru_weight: g, technical_weight: t, fundamental_weight: f })
  }

  function resetDefaultWeights() {
    setWeights({ gru_weight: 0.4, technical_weight: 0.35, fundamental_weight: 0.25 })
  }

  async function saveWeights(event) {
    event.preventDefault()
    if (!user) {
      if (onRequireAuth) onRequireAuth()
      else if (onLogin) onLogin()
      else setError('Please sign in to save custom engine weights to your profile.')
      return
    }
    const total = Object.values(weights).reduce((sum, value) => sum + Number(value), 0)
    if (Math.abs(total - 1) > 0.015) {
      setError(`Engine weights must add up to 100% (currently ${Math.round(total * 100)}%). Click Auto-balance.`)
      return
    }
    setSaving(true)
    setMessage('')
    setError('')
    try {
      const payload = {
        gru_weight: Number(Number(weights.gru_weight).toFixed(2)),
        technical_weight: Number(Number(weights.technical_weight).toFixed(2)),
        fundamental_weight: Number(Number(weights.fundamental_weight).toFixed(2)),
      }
      const saved = await recommendationsApi.setEngineWeights(payload)
      if (saved) {
        setWeights({
          gru_weight: saved.gru_weight ?? payload.gru_weight,
          technical_weight: saved.technical_weight ?? payload.technical_weight,
          fundamental_weight: saved.fundamental_weight ?? payload.fundamental_weight,
        })
      }
      setMessage('Engine weights successfully updated and saved to your profile.')
      await Promise.all([loadRecommendations(), loadDetail(selectedSymbol)])
    } catch (requestError) {
      setError(requestError.message || 'Failed to save engine weights.')
    } finally {
      setSaving(false)
    }
  }

  const safeRecommendations = Array.isArray(recommendations) ? recommendations : BENCHMARK_RECOMMENDATIONS
  const filteredRecommendations = safeRecommendations.filter((item) => {
    if (signalFilter === 'ALL') return true
    return (item.signal || 'HOLD').toUpperCase() === signalFilter
  })

  const gruPct = Math.round((Number(weights.gru_weight) || 0) * 100)
  const techPct = Math.round((Number(weights.technical_weight) || 0) * 100)
  const fundPct = Math.round((Number(weights.fundamental_weight) || 0) * 100)
  const totalPct = gruPct + techPct + fundPct

  const riskRewardRatio = targetStopData?.upside_pct && targetStopData?.downside_pct && Number(targetStopData.downside_pct) !== 0
    ? Math.abs(Number(targetStopData.upside_pct) / Number(targetStopData.downside_pct)).toFixed(2)
    : null

  const activeDetail = detailData || buildFallbackDetail(selectedSymbol, weights)
  const activeSignalUpper = (activeDetail.signal || 'HOLD').toUpperCase()
  const activeSignalLower = activeSignalUpper.toLowerCase()
  const compositeScore = Number(activeDetail.composite_score) || 0
  const meterWidthPct = Math.max(10, Math.min(100, ((compositeScore + 1) / 2) * 100))

  return (
    <main className="dashboard">
      <Header
        active="recommendations"
        onDashboard={onBack}
        onMarket={onMarket}
        onPortfolio={onPortfolio}
        onNews={onNews}
        onAssistant={onAssistant}
        onWatchlist={onWatchlist}
        onRisk={onRisk}
        onSettings={onSettings}
        onLogout={onLogout}
        onOpenSearch={onOpenSearch}
        onLogin={onLogin}
        onRequireAuth={onRequireAuth}
      />
      <section className="dashboard-content recommendations-page">
        {/* Guest / Unauthenticated Notice Banner */}
        {!user && (
          <div className="rec-auth-banner">
            <div className="rec-auth-copy">
              <strong>Viewing PSX Quantitative Model Rankings</strong>
              <p>Sign in to save custom engine weights, sync personal risk tolerances, and configure strategy profiles.</p>
            </div>
            <button type="button" className="rec-auth-login-btn" onClick={onLogin}>
              Sign In
            </button>
          </div>
        )}

        {/* Page Header */}
        <div className="recommendations-heading">
          <div>
            <p className="eyebrow">Quantitative signals &amp; models</p>
            <h1>Recommendations.</h1>
            <p className="dashboard-lede">
              Automated PSX rankings, multi-factor signal synthesis, and ATR target/stop-loss boundaries.
            </p>
          </div>
          <div className="rec-top-controls">
            <div className="rec-control-pill">
              <label htmlFor="risk-select">Risk profile:</label>
              <select
                id="risk-select"
                value={riskProfile}
                onChange={(event) => setRiskProfile(event.target.value)}
                aria-label="Risk profile filter"
              >
                <option value="conservative">Conservative (2x ATR)</option>
                <option value="moderate">Moderate (3x ATR)</option>
                <option value="aggressive">Aggressive (4x ATR)</option>
              </select>
            </div>
            <div className="rec-control-pill">
              <label htmlFor="sector-select">Sector:</label>
              <select
                id="sector-select"
                value={sector}
                onChange={(event) => setSector(event.target.value)}
                aria-label="Sector filter"
              >
                {sectorOptions.map((opt) => (
                  <option key={opt} value={opt}>{opt === 'ALL' ? 'All sectors' : opt}</option>
                ))}
              </select>
            </div>
            <button
              type="button"
              className="refresh-rec-button"
              onClick={() => { loadRecommendations(); loadDetail(selectedSymbol) }}
              title="Refresh recommendations"
              aria-label="Refresh recommendations"
            >
              <NavIcon name="market" /> Refresh
            </button>
          </div>
        </div>

        {error && <p className="form-error" role="alert">{error}</p>}
        {message && <p className="form-success" role="status">{message}</p>}

        {/* 1. On-Demand Single Stock Deep-Dive (GET /recommendations/{symbol} and /target-stop) */}
        <section className="dashboard-section rec-deep-dive-card" id="rec-deep-dive">
          <div className="section-heading">
            <div>
              <p className="eyebrow">On-demand stock analyzer</p>
              <h2>Signal synthesis: {selectedSymbol}</h2>
            </div>
            <form className="rec-search-form" onSubmit={handleSearchSubmit}>
              <input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Search symbol (e.g. SYS, HBL)"
                aria-label="Lookup stock symbol for recommendation analysis"
              />
              <button type="submit">Analyze</button>
            </form>
          </div>

          {/* Quick symbol chips */}
          <div className="quick-symbol-bar">
            <span>Popular stocks:</span>
            {quickSymbols.map((sym) => (
              <button
                type="button"
                key={sym}
                className={selectedSymbol === sym ? 'quick-chip active' : 'quick-chip'}
                onClick={() => handleSelectStock(sym)}
              >
                <StockLogo symbol={sym} size="xs" />
                <span>{sym}</span>
              </button>
            ))}
          </div>

          {detailLoading && <p className="data-state">Analyzing signals and volatility metrics for {selectedSymbol}…</p>}
          {detailError && <p className="data-state">{detailError}</p>}

          {!detailLoading && (
            <div className="rec-detail-content">
              {/* Top Verdict Row */}
              <div className="rec-verdict-row">
                <div className="verdict-main">
                  <StockLogo symbol={selectedSymbol} size="lg" />
                  <span className={`verdict-badge ${activeSignalLower}`}>
                    {activeSignalUpper}
                  </span>
                  <div>
                    <strong>{selectedSymbol} recommendation</strong>
                    <p>
                      Confidence: <b>{Math.round((Number(activeDetail.confidence) || 0) * 100)}%</b> · Composite score: <b>{formatNumber(activeDetail.composite_score, 2)}</b>
                    </p>
                  </div>
                </div>

                <div className="verdict-score-meter">
                  <div className="meter-labels">
                    <span>Bearish (-1.0)</span>
                    <span>Neutral (0.0)</span>
                    <span>Bullish (+1.0)</span>
                  </div>
                  <div className="meter-track">
                    <div
                      className={`meter-fill ${activeSignalLower}`}
                      style={{ width: `${meterWidthPct}%` }}
                    />
                  </div>
                </div>
              </div>

              {/* Grid: Signals Breakdown & Target/Stop */}
              <div className="rec-detail-grid">
                {/* Tri-source Signals Card */}
                <div className="rec-subcard">
                  <h3>Multi-model signal synthesis</h3>
                  <div className="tri-signals-list">
                    {/* Machine Learning (GRU) */}
                    <div className="tri-signal-row">
                      <div className="tri-signal-title">
                        <strong>Machine Learning (GRU)</strong>
                        <small>Weight: {Math.round((activeDetail.weights?.gru ?? activeDetail.weights?.gru_weight ?? weights.gru_weight) * 100)}%</small>
                      </div>
                      <div className="tri-signal-value">
                        <span className={Number(activeDetail.signals?.ml) > 0 ? 'positive' : Number(activeDetail.signals?.ml) < 0 ? 'negative' : ''}>
                          {Number(activeDetail.signals?.ml) >= 0 ? '+' : ''}{formatNumber(activeDetail.signals?.ml, 2)}
                        </span>
                      </div>
                      <p className="tri-signal-desc">
                        {formatReason(activeDetail.reasoning?.ml, 'Neural network sequence evaluation & XGBoost alpha')}
                      </p>
                    </div>

                    {/* Technical Indicators */}
                    <div className="tri-signal-row">
                      <div className="tri-signal-title">
                        <strong>Technical indicators</strong>
                        <small>Weight: {Math.round((activeDetail.weights?.technical ?? activeDetail.weights?.technical_weight ?? weights.technical_weight) * 100)}%</small>
                      </div>
                      <div className="tri-signal-value">
                        <span className={Number(activeDetail.signals?.technical) > 0 ? 'positive' : Number(activeDetail.signals?.technical) < 0 ? 'negative' : ''}>
                          {Number(activeDetail.signals?.technical) >= 0 ? '+' : ''}{formatNumber(activeDetail.signals?.technical, 2)}
                        </span>
                      </div>
                      <p className="tri-signal-desc">
                        {formatReason(activeDetail.reasoning?.technical, 'Momentum, RSI & Moving average convergence')}
                      </p>
                    </div>

                    {/* Fundamental Health */}
                    <div className="tri-signal-row">
                      <div className="tri-signal-title">
                        <strong>Fundamental valuation</strong>
                        <small>Weight: {Math.round((activeDetail.weights?.fundamental ?? activeDetail.weights?.fundamental_weight ?? weights.fundamental_weight) * 100)}%</small>
                      </div>
                      <div className="tri-signal-value">
                        <span className={Number(activeDetail.signals?.fundamental) > 0 ? 'positive' : Number(activeDetail.signals?.fundamental) < 0 ? 'negative' : ''}>
                          {Number(activeDetail.signals?.fundamental) >= 0 ? '+' : ''}{formatNumber(activeDetail.signals?.fundamental, 2)}
                        </span>
                      </div>
                      <p className="tri-signal-desc">
                        {formatReason(activeDetail.reasoning?.fundamental, 'Valuation ratios, dividend yield & ROE')}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Target & Stop Loss Card */}
                <div className="rec-subcard">
                  <div className="subcard-header">
                    <h3>ATR Target &amp; Stop-Loss</h3>
                    <span className="rec-method-tag">{targetStopData?.method || 'atr_band'}</span>
                  </div>

                  <div className="target-stop-stats">
                    <div className="ts-stat-item">
                      <span>Current Price</span>
                      <strong>{targetStopData?.current_price ? `Rs. ${formatNumber(targetStopData.current_price)}` : '—'}</strong>
                    </div>
                    <div className="ts-stat-item highlight-target">
                      <span>Target Price</span>
                      <strong>{targetStopData?.target_price ? `Rs. ${formatNumber(targetStopData.target_price)}` : '—'}</strong>
                      {targetStopData?.upside_pct != null && (
                        <em className="positive">+{formatNumber(targetStopData.upside_pct)}% upside</em>
                      )}
                    </div>
                    <div className="ts-stat-item highlight-stop">
                      <span>Stop-Loss</span>
                      <strong>{targetStopData?.stop_loss ? `Rs. ${formatNumber(targetStopData.stop_loss)}` : '—'}</strong>
                      {targetStopData?.downside_pct != null && (
                        <em className="negative">{formatNumber(targetStopData.downside_pct)}% downside</em>
                      )}
                    </div>
                    <div className="ts-stat-item">
                      <span>Risk / Reward</span>
                      <strong>{riskRewardRatio ? `${riskRewardRatio} R:R` : '—'}</strong>
                      <small>14-Day ATR: {formatNumber(targetStopData?.atr_14, 2)}</small>
                    </div>
                  </div>

                  <div className="ts-action-row">
                    <button
                      type="button"
                      className="view-stock-charts-btn"
                      onClick={() => onStock(selectedSymbol)}
                    >
                      View full {selectedSymbol} charts &amp; financial details →
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </section>

        {/* 2. Main Two-Column Layout: Ranked Signals (Left) & Engine Weights (Right) */}
        <div className="recommendations-layout">
          {/* Left: Ranked Recommendations List */}
          <section className="dashboard-section rec-list-section">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Ranked signals</p>
                <h2>Market recommendations</h2>
              </div>
              <div className="rec-filter-pills" role="tablist" aria-label="Signal filter">
                {['ALL', 'BUY', 'HOLD', 'SELL'].map((sig) => (
                  <button
                    type="button"
                    key={sig}
                    className={signalFilter === sig ? 'active' : ''}
                    onClick={() => setSignalFilter(sig)}
                  >
                    {sig}
                  </button>
                ))}
              </div>
            </div>

            {loading && <p className="data-state">Loading quantitative recommendations…</p>}

            {!loading && filteredRecommendations.length === 0 && (
              <div className="rec-empty-state">
                <div className="empty-icon">◎</div>
                <h3>Automated quant batch scoring</h3>
                <p>
                  No stocks match the selected filter. You can analyze any stock using the on-demand analyzer above.
                </p>
                <div className="empty-quick-buttons">
                  {quickSymbols.slice(0, 5).map((s) => (
                    <button key={s} type="button" onClick={() => handleSelectStock(s)}>
                      Analyze {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {!loading && filteredRecommendations.length > 0 && (
              <div className="recommendation-cards">
                {filteredRecommendations.map((item) => {
                  const sigUpper = (item.signal || 'HOLD').toUpperCase()
                  const sigLower = sigUpper.toLowerCase()
                  return (
                    <article className="recommendation-card" key={item.symbol}>
                      <div className="rec-card-top">
                        <button
                          type="button"
                          className="recommendation-symbol flex items-center gap-2.5 text-left"
                          onClick={() => handleSelectStock(item.symbol)}
                        >
                          <StockLogo symbol={item.symbol} size="sm" />
                          <div>
                            <strong>{item.symbol}</strong>
                            <small>{item.summary}</small>
                          </div>
                        </button>
                        <span className={`signal ${sigLower}`}>{sigUpper}</span>
                      </div>

                      <div className="recommendation-metrics">
                        <div>
                          <span>Confidence</span>
                          <b>{Math.round((Number(item.confidence) || 0) * 100)}%</b>
                        </div>
                        <div>
                          <span>Score</span>
                          <b>{formatNumber(item.composite_score, 2)}</b>
                        </div>
                        <div>
                          <span>Target</span>
                          <b>{item.target_price ? formatMoney(item.target_price) : '—'}</b>
                        </div>
                        <div>
                          <span>Stop-loss</span>
                          <b>{item.stop_loss ? formatMoney(item.stop_loss) : '—'}</b>
                        </div>
                      </div>

                      <div className="rec-card-actions">
                        <button
                          type="button"
                          className="rec-inspect-btn"
                          onClick={() => handleSelectStock(item.symbol)}
                        >
                          Inspect signals
                        </button>
                        <button
                          type="button"
                          className="rec-view-btn"
                          onClick={() => onStock(item.symbol)}
                        >
                          View stock →
                        </button>
                      </div>
                    </article>
                  )
                })}
              </div>
            )}
          </section>

          {/* Right: Engine Weights Configuration Form */}
          <form className="dashboard-section engine-weights-card" onSubmit={saveWeights}>
            <div className="section-heading">
              <div>
                <p className="eyebrow">Quant model tuning</p>
                <h2>Engine weights</h2>
              </div>
            </div>
            <p className="sidebar-copy">
              Tune how the recommendation engine balances each source for your investment profile. Weights must sum to 100%.
            </p>

            {/* Visual Distribution Stacked Bar */}
            <div className="weights-bar-container">
              <div className="weights-distribution-bar" title={`ML: ${gruPct}%, Technical: ${techPct}%, Fundamental: ${fundPct}%`}>
                <div className="weight-segment ml" style={{ width: `${Math.max(5, (gruPct / (totalPct || 1)) * 100)}%` }}>
                  {gruPct > 12 && `${gruPct}%`}
                </div>
                <div className="weight-segment tech" style={{ width: `${Math.max(5, (techPct / (totalPct || 1)) * 100)}%` }}>
                  {techPct > 12 && `${techPct}%`}
                </div>
                <div className="weight-segment fund" style={{ width: `${Math.max(5, (fundPct / (totalPct || 1)) * 100)}%` }}>
                  {fundPct > 12 && `${fundPct}%`}
                </div>
              </div>
              <div className="weights-legend">
                <span><i className="dot ml" /> ML model ({gruPct}%)</span>
                <span><i className="dot tech" /> Technical ({techPct}%)</span>
                <span><i className="dot fund" /> Fundamental ({fundPct}%)</span>
              </div>
            </div>

            {/* Sliders */}
            <div className="weight-controls-group">
              <label className="weight-control">
                <span>
                  <b>Machine learning (GRU)</b>
                  <em>{gruPct}%</em>
                </span>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.01"
                  value={weights.gru_weight}
                  onChange={(event) => setWeights({ ...weights, gru_weight: event.target.value })}
                />
              </label>

              <label className="weight-control">
                <span>
                  <b>Technical indicators</b>
                  <em>{techPct}%</em>
                </span>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.01"
                  value={weights.technical_weight}
                  onChange={(event) => setWeights({ ...weights, technical_weight: event.target.value })}
                />
              </label>

              <label className="weight-control">
                <span>
                  <b>Fundamental health</b>
                  <em>{fundPct}%</em>
                </span>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.01"
                  value={weights.fundamental_weight}
                  onChange={(event) => setWeights({ ...weights, fundamental_weight: event.target.value })}
                />
              </label>
            </div>

            {/* Total Indicator & Helper Buttons */}
            <div className="weight-summary-box">
              <div className="weight-total-row">
                <span>Total weight:</span>
                <strong className={Math.abs(totalPct - 100) <= 1 ? 'positive' : 'negative'}>
                  {totalPct}%
                </strong>
              </div>
              <div className="weight-helper-btns">
                <button type="button" onClick={autoBalanceWeights}>
                  Auto-balance 100%
                </button>
                <button type="button" onClick={resetDefaultWeights}>
                  Reset defaults
                </button>
              </div>
            </div>

            <button className="submit-button" type="submit" disabled={saving}>
              {saving ? 'Saving weights…' : 'Save engine weights'} <span>→</span>
            </button>
          </form>
        </div>
      </section>

      <MobileNav
        active="recommendations"
        onDashboard={onBack}
        onMarket={onMarket}
        onPortfolio={onPortfolio}
        onNews={onNews}
        onAssistant={onAssistant}
        onWatchlist={onWatchlist}
        onRisk={onRisk}
        onSettings={onSettings}
      />
    </main>
  )
}

function ShariahPage({ onBack, onMarket, onPortfolio, onNews, onRisk, onSettings, onLogout, onStock }) {
  const [symbol, setSymbol] = useState('HBL')
  const [screening, setScreening] = useState(null)
  const [criteria, setCriteria] = useState(null)
  const [kmi30, setKmi30] = useState(null)
  const [purification, setPurification] = useState(null)
  const [holdingQty, setHoldingQty] = useState('100')
  const [holdingValue, setHoldingValue] = useState('100000')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const loadSymbol = useCallback(async (nextSymbol = symbol) => {
    const normalized = nextSymbol.trim().toUpperCase()
    if (!normalized) return
    setLoading(true)
    setError('')
    const results = await Promise.allSettled([
      dashboardApi.getShariah(normalized),
      dashboardApi.getShariahCriteria(normalized),
      dashboardApi.getKmi30Shariah(),
    ])
    if (results[0].status === 'fulfilled') setScreening(results[0].value)
    if (results[1].status === 'fulfilled') setCriteria(results[1].value)
    if (results[2].status === 'fulfilled') setKmi30(results[2].value)
    if (results.every((result) => result.status === 'rejected')) setError(results[0].reason.message)
    setLoading(false)
  }, [symbol])

  useEffect(() => { loadSymbol() }, [])

  async function calculatePurification(event) {
    event.preventDefault()
    setError('')
    try {
      setPurification(await dashboardApi.getShariahPurification(symbol, holdingQty, holdingValue))
    } catch (requestError) {
      setError(requestError.message)
    }
  }

  return <main className="dashboard">
    <Header active="shariah" onDashboard={onBack} onMarket={onMarket} onPortfolio={onPortfolio} onNews={onNews} onRisk={onRisk} onSettings={onSettings} onLogout={onLogout} />
    <section className="dashboard-content shariah-page">
      <div className="recommendations-heading"><div><p className="eyebrow">Ethical investing</p><h1>Shariah screening.</h1><p className="dashboard-lede">AAOIFI and KMI-30 aligned compliance checks, criteria, and dividend purification estimates.</p></div><form className="stock-search-inline" onSubmit={(event) => { event.preventDefault(); loadSymbol() }}><input value={symbol} onChange={(event) => setSymbol(event.target.value)} aria-label="Stock symbol" /><button type="submit">Check</button></form></div>
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="recommendations-layout">
        <section className="dashboard-section">
          <div className="section-heading">
            <div className="flex items-center gap-3">
              <StockLogo symbol={screening?.symbol || symbol} size="lg" />
              <div>
                <p className="eyebrow">Screening result</p>
                <h2 className="m-0 leading-tight">{screening?.symbol || symbol}</h2>
              </div>
            </div>
            {screening ? (
              <ShariahBadge
                isCompliant={Boolean(screening.is_shariah_compliant)}
                showNonCompliant={true}
                size="md"
                fullLabel={true}
              />
            ) : (
              <span className="signal">{loading ? 'Loading…' : 'Unavailable'}</span>
            )}
          </div>
          <div className="fact-grid">
            <div><span>Method</span><strong>{screening?.screening_method || '—'}</strong></div>
            <div><span>Overall score</span><strong>{formatNumber(screening?.overall_score)}</strong></div>
            <div><span>Purification rate</span><strong>{screening?.purification_rate == null ? '—' : `${formatNumber(screening.purification_rate * 100, 2)}%`}</strong></div>
            <div><span>Sector</span><strong>{screening?.sector || '—'}</strong></div>
          </div>
          <p className="signal-message">{screening?.compliance_summary || 'Run a screening to view the compliance result.'}</p>
        </section>
        <section className="dashboard-section"><div className="section-heading"><div><p className="eyebrow">Detailed criteria</p><h2>AAOIFI checks</h2></div></div><div className="criteria-list">{(criteria?.criteria || []).map((item) => <div className="indicator-row" key={item.name}><span>{item.name}<small>{item.description || `Threshold ${item.threshold}`}</small></span><strong className={item.passed ? 'positive' : 'negative'}>{item.passed ? 'Pass' : 'Fail'}{item.value != null ? ` · ${formatNumber(item.value)}` : ''}</strong></div>)}</div>{!criteria?.criteria?.length && <p className="data-state">Criteria are unavailable for this symbol.</p>}</section>
        <form className="dashboard-section" onSubmit={calculatePurification}><div className="section-heading"><div><p className="eyebrow">Dividend purification</p><h2>Calculate amount</h2></div></div><div className="form-two"><label className="field"><span>Holding quantity</span><input type="number" min="1" required value={holdingQty} onChange={(event) => setHoldingQty(event.target.value)} /></label><label className="field"><span>Holding value (PKR)</span><input type="number" min="0.01" step="any" required value={holdingValue} onChange={(event) => setHoldingValue(event.target.value)} /></label></div><button className="submit-button">Calculate purification <span>→</span></button>{purification && <div className="purification-result"><strong>PKR {formatNumber(purification.purification_amount, 2)}</strong><span>{formatNumber(purification.purification_rate * 100, 2)}% · {purification.notes}</span></div>}</form>
      </div>
      <section className="dashboard-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Shariah universe</p>
            <h2>KMI-30 constituents</h2>
          </div>
          <span className="section-meta">{kmi30?.total_constituents || kmi30?.constituents?.length || 0} stocks</span>
        </div>
        <div className="symbol-chips">
          {(kmi30?.constituents || []).map((item) => (
            <button
              type="button"
              key={item.symbol}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 hover:border-emerald-500 transition-all font-mono font-bold text-xs"
              onClick={() => { setSymbol(item.symbol); loadSymbol(item.symbol) }}
            >
              <StockLogo symbol={item.symbol} size="xs" />
              <span>{item.symbol}</span>
              <ShariahBadge isCompliant={true} size="xs" showLabel={false} />
            </button>
          ))}
        </div>
        {!kmi30?.constituents?.length && <p className="data-state">KMI-30 constituents are currently unavailable.</p>}
      </section>
    </section>
  </main>
}

function getRoute() {
  const path = window.location.pathname.replace(/\/+$/, '') || '/'
  if (path === '/market' || path === '/stocks') return 'market'
  if (path === '/sentiment') return 'sentiment'
  if (path === '/news' || path === '/market-activity' || path === '/activity') return 'news'
  if (path.startsWith('/news/') || path.startsWith('/market-activity/')) return 'article-detail'
  if (path === '/shariah') return 'shariah'
  if (path === '/assistant') return 'assistant'
  if (path === '/watchlist') return 'watchlist'
  if (path === '/recommendations') return 'recommendations'
  if (path.startsWith('/stocks/')) return 'stock'
  if (path === '/portfolio') return 'portfolio'
  if (path === '/risk') return 'risk'
  if (path === '/settings') return 'settings'
  if (path === '/verify-email') return 'verify-email'
  if (path === '/forgot-password' || path === '/verify-reset-code' || path === '/reset-password') return 'forgot'
  if (path === '/signup') return 'signup'
  if (path === '/login') return 'login'
  return 'dashboard'
}

function App() {
  const [route, setRoute] = useState(getRoute)
  const [visitedRoutes, setVisitedRoutes] = useState(() => new Set([getRoute()]))
  const [user, setUser] = useState(getStoredUser)
  const [needsSetup, setNeedsSetup] = useState(false)
  const [isLoading, setIsLoading] = useState(Boolean(getStoredUser()))
  const [mode, setMode] = useState(() => (window.location.pathname === '/signup' ? 'signup' : 'login'))
  const [pendingEmail, setPendingEmail] = useState(() => localStorage.getItem('basarat_pending_verify_email') || '')
  const [searchModalOpen, setSearchModalOpen] = useState(false)

  useEffect(() => {
    setVisitedRoutes((prev) => {
      const currentRoute = getRoute()
      if (prev.has(currentRoute)) return prev
      const next = new Set(prev)
      next.add(currentRoute)
      return next
    })
  }, [route])

  // In-Place Auth Modal Popup States (replaces full-screen auth pages)
  const [authModalOpen, setAuthModalOpen] = useState(() => {
    const path = window.location.pathname
    return !getStoredUser() && (path === '/login' || path === '/signup' || path === '/forgot-password' || path === '/verify-email')
  })
  const [authModalMode, setAuthModalMode] = useState(() => {
    const path = window.location.pathname
    if (path === '/signup') return 'signup'
    if (path === '/verify-email') return 'verify'
    if (path === '/forgot-password') return 'forgot'
    return 'login'
  })

  const openAuthModal = (modalMode = 'login') => {
    setAuthModalMode(modalMode)
    setAuthModalOpen(true)
  }

  const handleCloseAuthModal = () => {
    setAuthModalOpen(false)
    const path = window.location.pathname
    if (path === '/login' || path === '/signup' || path === '/forgot-password' || path === '/verify-email') {
      window.history.replaceState({}, '', '/')
      setRoute(getRoute())
    }
  }

  const stockSymbol = window.location.pathname.startsWith('/stocks/') ? window.location.pathname.split('/')[2]?.toUpperCase() : null
  const articleId = window.location.pathname.startsWith('/news/') ? window.location.pathname.replace(/^\/news\//, '') : null

  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setSearchModalOpen((prev) => !prev)
      }
    }
    const handleOpenSearch = () => setSearchModalOpen(true)
    const handleOpenAuth = (e) => {
      const targetMode = e.detail?.mode || 'login'
      openAuthModal(targetMode)
    }

    const handleAuthSuccess = (e) => {
      const newUser = e.detail?.user || getStoredUser()
      if (newUser) {
        authenticated(newUser, false)
        setAuthModalOpen(false)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    window.addEventListener('open-stock-search', handleOpenSearch)
    window.addEventListener('open-auth-modal', handleOpenAuth)
    window.addEventListener('auth-success', handleAuthSuccess)

    return () => {
      window.removeEventListener('keydown', handleKeyDown)
      window.removeEventListener('open-stock-search', handleOpenSearch)
      window.removeEventListener('open-auth-modal', handleOpenAuth)
      window.removeEventListener('auth-success', handleAuthSuccess)
    }
  }, [])

  useEffect(() => {
    const onPopState = () => {
      const nextRoute = getRoute()
      setRoute(nextRoute)
      const path = window.location.pathname
      if (!user) {
        if (path === '/signup') {
          openAuthModal('signup')
        } else if (path === '/login') {
          openAuthModal('login')
        } else if (path === '/verify-email') {
          openAuthModal('verify')
        } else if (path === '/forgot-password') {
          openAuthModal('forgot')
        } else {
          setAuthModalOpen(false)
        }
      } else {
        setAuthModalOpen(false)
      }
    }
    window.addEventListener('popstate', onPopState)
    const storedUser = getStoredUser()
    if (!storedUser) {
      return () => window.removeEventListener('popstate', onPopState)
    }
    refreshSession()
      .then(() => authApi.getProfile())
      .then((profile) => {
        localStorage.setItem('basarat_user', JSON.stringify(profile))
        setUser(profile)
      })
      .catch((err) => {
        // Only clear session if token is truly invalid or expired (HTTP 401)
        if (
          err.status === 401 ||
          err.message?.includes('Invalid or reused') ||
          err.message?.includes('expired')
        ) {
          clearSession()
          setUser(null)
        }
      })
      .finally(() => setIsLoading(false))
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  // ── Proactive Background Token Refresher & Multi-Tab Sync ──
  useEffect(() => {
    if (!user) return

    let refreshTimer = null

    const scheduleNextRefresh = () => {
      if (refreshTimer) clearTimeout(refreshTimer)

      const exp = getTokenExpiry()
      const now = Date.now()
      // Refresh 5 minutes before expiration (access token lasts 30 min)
      // If exp is unknown or invalid, default to 20 minutes (1200000 ms)
      const leadTimeMs = 5 * 60 * 1000
      let delayMs = exp ? Math.max(10000, (exp - now) - leadTimeMs) : 20 * 60 * 1000

      refreshTimer = setTimeout(async () => {
        try {
          await refreshSession()
          scheduleNextRefresh()
        } catch (err) {
          console.warn('Background token refresh attempt failed, retrying in 30s:', err)
          refreshTimer = setTimeout(scheduleNextRefresh, 30000)
        }
      }, delayMs)
    }

    scheduleNextRefresh()

    // When user returns to tab or focuses window, check if token needs renewal
    const handleVisibilityOrFocus = async () => {
      if (document.visibilityState === 'visible' && isTokenExpiringSoon(6)) {
        try {
          await refreshSession()
          scheduleNextRefresh()
        } catch (err) {
          console.warn('Visibility token refresh check failed:', err)
        }
      }
    }

    // Cross-tab synchronization via storage event
    const handleStorage = (e) => {
      if (e.key === 'basarat_user') {
        try {
          const nextUser = e.newValue ? JSON.parse(e.newValue) : null
          setUser(nextUser)
        } catch {
          setUser(null)
        }
      } else if (e.key === 'basarat_access_token' && e.newValue) {
        // Another tab rotated the token; reschedule next refresh based on new token
        scheduleNextRefresh()
      }
    }

    // In-window session events
    const handleSessionCleared = () => {
      setUser(null)
    }
    const handleSessionUpdated = () => {
      scheduleNextRefresh()
    }

    window.addEventListener('visibilitychange', handleVisibilityOrFocus)
    window.addEventListener('focus', handleVisibilityOrFocus)
    window.addEventListener('storage', handleStorage)
    window.addEventListener('session-cleared', handleSessionCleared)
    window.addEventListener('session-updated', handleSessionUpdated)

    return () => {
      if (refreshTimer) clearTimeout(refreshTimer)
      window.removeEventListener('visibilitychange', handleVisibilityOrFocus)
      window.removeEventListener('focus', handleVisibilityOrFocus)
      window.removeEventListener('storage', handleStorage)
      window.removeEventListener('session-cleared', handleSessionCleared)
      window.removeEventListener('session-updated', handleSessionUpdated)
    }
  }, [user])

  useEffect(() => {
    const titles = {
      auth: mode === 'signup' ? 'Create Account · Basarat' : 'Sign In · Basarat',
      signup: 'Create Account · Basarat',
      login: 'Sign In · Basarat',
      'verify-email': 'Verify Email · Basarat',
      forgot: 'Forgot Password · Basarat',
      dashboard: 'Dashboard · Basarat',
      market: 'Market Overview · Basarat',
      sentiment: 'Market Sentiment · Basarat',
      news: 'Market Activity · Basarat',
      'article-detail': 'News Article · Basarat',
      assistant: 'AI Copilot · Basarat',
      watchlist: 'Watchlist · Basarat',
      recommendations: 'Recommendations · Basarat',
      shariah: 'Shariah Screening · Basarat',
      portfolio: 'Portfolio · Basarat',
      risk: 'Risk Analytics · Basarat',
      settings: 'Settings · Basarat',
      stock: stockSymbol ? `${stockSymbol} · Basarat` : 'Stock Detail · Basarat',
    }
    const currentKey = !user
      ? (route === 'verify-email' ? 'verify-email' : route === 'forgot' ? 'forgot' : route === 'signup' ? 'signup' : route === 'login' ? 'login' : route === 'dashboard' ? 'landing' : route)
      : (route === 'auth' || route === 'login' || route === 'signup' ? 'dashboard' : route)
    document.title = titles[currentKey] || 'Basarat'
  }, [route, mode, user, stockSymbol])

  function navigate(path, state = null) {
    window.history.pushState(state, '', path)
    setRoute(getRoute())
  }

  function authenticated(nextUser, signup) {
    setUser(nextUser)
    setNeedsSetup(false)
    setVisitedRoutes(new Set(['dashboard']))
    navigate('/')
  }

  async function logout() {
    const refreshToken = localStorage.getItem('basarat_refresh_token')
    if (refreshToken) {
      try { await authApi.logout(refreshToken) } catch (error) { console.warn('Server logout failed; clearing local session.', error) }
    }
    clearSession()
    setUser(null)
    setNeedsSetup(false)
    setMode('login')
    setVisitedRoutes(new Set(['dashboard']))
    navigate('/')
  }

  if (isLoading) return <div className="loading-screen">Loading your secure workspace…</div>

  const navigation = {
    dashboard: () => navigate('/'),
    market: () => navigate('/market'),
    portfolio: () => (user ? navigate('/portfolio') : openAuthModal('login')),
    watchlist: () => (user ? navigate('/watchlist') : openAuthModal('login')),
    recommendations: () => navigate('/recommendations'),
    sentiment: () => navigate('/sentiment'),
    news: () => navigate('/news'),
    assistant: () => (user ? navigate('/assistant') : openAuthModal('login')),
    risk: () => navigate('/risk'),
    shariah: () => navigate('/shariah'),
    settings: () => (user ? navigate('/settings') : openAuthModal('login')),
  }

  // Public/Gated routing for unauthenticated visitors
  if (!user) {
    const isPublic = ['market', 'stock', 'news', 'article-detail', 'recommendations', 'shariah', 'sentiment', 'risk'].includes(route)
    if (!isPublic) {
      // Any non-public route or direct /login or /signup renders Landing Page with in-place AuthModal popup
      return (
        <>
          <LandingPage
            onLogin={() => openAuthModal('login')}
            onSignup={() => openAuthModal('signup')}
            onStock={(sym) => navigate(`/stocks/${sym}`)}
            onMarket={navigation.market}
            onNews={navigation.news}
            onRequireAuth={() => openAuthModal('login')}
            onOpenSearch={() => setSearchModalOpen(true)}
          />
          <SearchModal
            isOpen={searchModalOpen}
            onClose={() => setSearchModalOpen(false)}
            onSelectStock={(sym) => {
              setSearchModalOpen(false)
              navigate(`/stocks/${sym}`)
            }}
          />
          <AuthModal
            isOpen={!user && authModalOpen}
            initialMode={authModalMode}
            initialEmail={pendingEmail}
            onClose={handleCloseAuthModal}
            onAuthenticated={(newUser) => {
              authenticated(newUser, false)
              setAuthModalOpen(false)
              navigate('/')
            }}
          />
        </>
      )
    }
  }

  if (needsSetup) return <ProfileSetup user={user} onComplete={(profile) => { setUser(profile); setNeedsSetup(false) }} />

  const isViewVisible = (r) => visitedRoutes.has(r) || route === r

  return (
    <>
      {isViewVisible('dashboard') && (
        <div
          className={`spa-view-container ${route === 'dashboard' ? 'active' : 'inactive'}`}
          aria-hidden={route !== 'dashboard'}
        >
          <Dashboard
            user={user}
            onLogout={logout}
            onMarket={navigation.market}
            onPortfolio={navigation.portfolio}
            onNews={navigation.news}
            onRisk={navigation.risk}
            onSettings={navigation.settings}
            onStock={(symbol) => navigate(`/stocks/${symbol}`)}
          />
        </div>
      )}

      {isViewVisible('market') && (
        <div
          className={`spa-view-container ${route === 'market' ? 'active' : 'inactive'}`}
          aria-hidden={route !== 'market'}
        >
          <MarketOverview
            onBack={navigation.dashboard}
            onDashboard={navigation.dashboard}
            onMarket={navigation.market}
            onPortfolio={navigation.portfolio}
            onNews={navigation.news}
            onSentiment={navigation.sentiment}
            onWatchlist={navigation.watchlist}
            onRecommendations={navigation.recommendations}
            onShariah={navigation.shariah}
            onAssistant={navigation.assistant}
            onRisk={navigation.risk}
            onSettings={navigation.settings}
            onLogout={logout}
            onOpenSearch={() => setSearchModalOpen(true)}
          />
        </div>
      )}

      {isViewVisible('sentiment') && (
        <div
          className={`spa-view-container ${route === 'sentiment' ? 'active' : 'inactive'}`}
          aria-hidden={route !== 'sentiment'}
        >
          <SentimentPage
            onBack={navigation.dashboard}
            onMarket={navigation.market}
            onPortfolio={navigation.portfolio}
            onNews={navigation.news}
            onSentiment={navigation.sentiment}
            onWatchlist={navigation.watchlist}
            onRecommendations={navigation.recommendations}
            onShariah={navigation.shariah}
            onAssistant={navigation.assistant}
            onRisk={navigation.risk}
            onSettings={navigation.settings}
            onLogout={logout}
            onStock={(symbol) => navigate(`/stocks/${symbol}`)}
            onArticle={(id, art) => navigate(`/news/${id}`, { article: art })}
            onOpenSearch={() => setSearchModalOpen(true)}
            mobileNav={
              <MobileNav
                active="sentiment"
                onDashboard={navigation.dashboard}
                onMarket={navigation.market}
                onPortfolio={navigation.portfolio}
                onNews={navigation.news}
                onSentiment={navigation.sentiment}
                onWatchlist={navigation.watchlist}
                onRecommendations={navigation.recommendations}
                onShariah={navigation.shariah}
                onAssistant={navigation.assistant}
                onRisk={navigation.risk}
                onSettings={navigation.settings}
              />
            }
          />
        </div>
      )}

      {isViewVisible('news') && (
        <div
          className={`spa-view-container ${route === 'news' ? 'active' : 'inactive'}`}
          aria-hidden={route !== 'news'}
        >
          <MarketActivityPage
            onBack={navigation.dashboard}
            onMarket={navigation.market}
            onPortfolio={navigation.portfolio}
            onRisk={navigation.risk}
            onSettings={navigation.settings}
            onLogout={logout}
            onStock={(symbol) => navigate('/stocks/' + symbol)}
            onArticle={(id, art) => navigate('/news/' + id, { article: art })}
            onOpenSearch={() => setSearchModalOpen(true)}
          />
        </div>
      )}

      {route === 'article-detail' && articleId && (
        <div className="spa-view-container active">
          <MarketActivityPage
            initialArticleId={articleId}
            initialArticle={window.history?.state?.article}
            onBack={navigation.dashboard}
            onMarket={navigation.market}
            onPortfolio={navigation.portfolio}
            onRisk={navigation.risk}
            onSettings={navigation.settings}
            onLogout={logout}
            onStock={(symbol) => navigate('/stocks/' + symbol)}
            onArticle={(id, art) => navigate('/news/' + id, { article: art })}
            onOpenSearch={() => setSearchModalOpen(true)}
          />
        </div>
      )}

      {route === 'stock' && stockSymbol && (
        <div className="spa-view-container active">
          <StockDetail
            key={stockSymbol}
            symbol={stockSymbol}
            onBack={navigation.market}
            onDashboard={navigation.dashboard}
            onMarket={navigation.market}
            onPortfolio={navigation.portfolio}
            onNews={navigation.news}
            onSentiment={navigation.sentiment}
            onWatchlist={navigation.watchlist}
            onRecommendations={navigation.recommendations}
            onShariah={navigation.shariah}
            onAssistant={navigation.assistant}
            onRisk={navigation.risk}
            onSettings={navigation.settings}
            onLogout={logout}
            onStock={(symbol) => navigate(`/stocks/${symbol}`)}
            onOpenSearch={() => setSearchModalOpen(true)}
          />
        </div>
      )}

      {isViewVisible('watchlist') && (
        <div
          className={`spa-view-container ${route === 'watchlist' ? 'active' : 'inactive'}`}
          aria-hidden={route !== 'watchlist'}
        >
          <WatchlistPage
            onBack={navigation.dashboard}
            onMarket={navigation.market}
            onPortfolio={navigation.portfolio}
            onNews={navigation.news}
            onAssistant={navigation.assistant}
            onRisk={navigation.risk}
            onSettings={navigation.settings}
            onLogout={logout}
            onStock={(symbol) => navigate(`/stocks/${symbol}`)}
          />
        </div>
      )}

      {isViewVisible('recommendations') && (
        <div
          className={`spa-view-container ${route === 'recommendations' ? 'active' : 'inactive'}`}
          aria-hidden={route !== 'recommendations'}
        >
          <RecommendationsPage
            onBack={navigation.dashboard}
            onMarket={navigation.market}
            onPortfolio={navigation.portfolio}
            onNews={navigation.news}
            onAssistant={navigation.assistant}
            onWatchlist={navigation.watchlist}
            onRisk={navigation.risk}
            onSettings={navigation.settings}
            onLogout={logout}
            onStock={(symbol) => navigate(`/stocks/${symbol}`)}
            onOpenSearch={() => setSearchModalOpen(true)}
            user={user}
            onLogin={() => openAuthModal('login')}
            onRequireAuth={() => openAuthModal('login')}
          />
        </div>
      )}

      {isViewVisible('shariah') && (
        <div
          className={`spa-view-container ${route === 'shariah' ? 'active' : 'inactive'}`}
          aria-hidden={route !== 'shariah'}
        >
          <ShariahPage
            onBack={navigation.dashboard}
            onMarket={navigation.market}
            onPortfolio={navigation.portfolio}
            onNews={navigation.news}
            onRisk={navigation.risk}
            onSettings={navigation.settings}
            onLogout={logout}
            onStock={(symbol) => navigate(`/stocks/${symbol}`)}
          />
        </div>
      )}

      {isViewVisible('portfolio') && (
        <div
          className={`spa-view-container ${route === 'portfolio' ? 'active' : 'inactive'}`}
          aria-hidden={route !== 'portfolio'}
        >
          <PortfolioPage
            onBack={navigation.dashboard}
            onDashboard={navigation.dashboard}
            onMarket={navigation.market}
            onPortfolio={navigation.portfolio}
            onNews={navigation.news}
            onSentiment={navigation.sentiment}
            onWatchlist={navigation.watchlist}
            onRecommendations={navigation.recommendations}
            onShariah={navigation.shariah}
            onAssistant={navigation.assistant}
            onRisk={navigation.risk}
            onSettings={navigation.settings}
            onLogout={logout}
            onStock={(symbol) => navigate(`/stocks/${symbol}`)}
            onOpenSearch={() => setSearchModalOpen(true)}
          />
        </div>
      )}

      {isViewVisible('risk') && (
        <div
          className={`spa-view-container ${route === 'risk' ? 'active' : 'inactive'}`}
          aria-hidden={route !== 'risk'}
        >
          <RiskPage
            onBack={navigation.dashboard}
            onDashboard={navigation.dashboard}
            onMarket={navigation.market}
            onPortfolio={navigation.portfolio}
            onNews={navigation.news}
            onSentiment={navigation.sentiment}
            onWatchlist={navigation.watchlist}
            onRecommendations={navigation.recommendations}
            onShariah={navigation.shariah}
            onAssistant={navigation.assistant}
            onRisk={navigation.risk}
            onSettings={navigation.settings}
            onLogout={logout}
            onStock={(symbol) => navigate(`/stocks/${symbol}`)}
            onOpenSearch={() => setSearchModalOpen(true)}
            mobileNav={
              <MobileNav
                active="risk"
                onDashboard={navigation.dashboard}
                onMarket={navigation.market}
                onPortfolio={navigation.portfolio}
                onNews={navigation.news}
                onSentiment={navigation.sentiment}
                onWatchlist={navigation.watchlist}
                onRecommendations={navigation.recommendations}
                onShariah={navigation.shariah}
                onAssistant={navigation.assistant}
                onRisk={navigation.risk}
                onSettings={navigation.settings}
              />
            }
          />
        </div>
      )}

      {isViewVisible('assistant') && (
        <div
          className={`spa-view-container ${route === 'assistant' ? 'active' : 'inactive'}`}
          aria-hidden={route !== 'assistant'}
        >
          <AssistantPage
            onBack={navigation.dashboard}
            onMarket={navigation.market}
            onPortfolio={navigation.portfolio}
            onNews={navigation.news}
            onRisk={navigation.risk}
            onSettings={navigation.settings}
            onLogout={logout}
          />
        </div>
      )}

      {isViewVisible('settings') && (
        <div
          className={`spa-view-container ${route === 'settings' ? 'active' : 'inactive'}`}
          aria-hidden={route !== 'settings'}
        >
          <SettingsPage
            onBack={navigation.dashboard}
            onMarket={navigation.market}
            onNews={navigation.news}
            onRisk={navigation.risk}
            onLogout={logout}
          />
        </div>
      )}
      {user && route !== 'assistant' && (
        <FloatingCopilotButton onClick={navigation.assistant} />
      )}
      <SearchModal
        isOpen={searchModalOpen}
        onClose={() => setSearchModalOpen(false)}
        onSelectStock={(sym) => {
          setSearchModalOpen(false)
          navigate(`/stocks/${sym}`)
        }}
      />
      <AuthModal
        isOpen={!user && authModalOpen}
        initialMode={authModalMode}
        initialEmail={pendingEmail}
        onClose={handleCloseAuthModal}
        onAuthenticated={(newUser) => {
          authenticated(newUser, false)
          setAuthModalOpen(false)
          navigate('/')
        }}
      />
    </>
  )
}

export default App
