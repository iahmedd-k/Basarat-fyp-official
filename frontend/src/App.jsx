import { useCallback, useEffect, useRef, useState } from 'react'
import {
  authApi,
  clearSession,
  getStoredUser,
  refreshSession,
  saveSession,
} from './api/auth'
import { dashboardApi } from './api/dashboard'
import { newsApi } from './api/news'
import { assistantApi } from './api/assistant'
import { communityApi } from './api/community'
import { adminCommunityApi } from './api/adminCommunity'
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

function AuthPage({ mode, onModeChange, onAuthenticated, onForgot }) {
  const isSignup = mode === 'signup'
  const [login, setLogin] = useState(initialLogin)
  const [signup, setSignup] = useState(initialSignup)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')
  const update = (setter) => (event) => {
    const { name, value } = event.target
    setter((current) => ({ ...current, [name]: value }))
    setError('')
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    if (isSignup && signup.password !== signup.confirmPassword) {
      setError('Passwords do not match.')
      return
    }
    setIsSubmitting(true)
    try {
      const response = isSignup
        ? await authApi.signup({ email: signup.email, password: signup.password, full_name: signup.full_name || null })
        : await authApi.login(login)
      saveSession(response)
      onAuthenticated(response.user, isSignup)
    } catch (requestError) {
      setError(requestError.message)
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
          <button type="button" className={!isSignup ? 'active' : ''} onClick={() => onModeChange('login')}>Sign in</button>
          <button type="button" className={isSignup ? 'active' : ''} onClick={() => onModeChange('signup')}>Create account</button>
        </div>
        <form onSubmit={handleSubmit} noValidate>
          {isSignup && <Field label="Full name" name="full_name" value={signup.full_name} onChange={update(setSignup)} placeholder="Your name" autoComplete="name" required={false} />}
          <Field label="Email address" name="email" type="email" value={isSignup ? signup.email : login.email} onChange={update(isSignup ? setSignup : setLogin)} placeholder="you@example.com" autoComplete="email" />
          <Field label="Password" name="password" type="password" value={isSignup ? signup.password : login.password} onChange={update(isSignup ? setSignup : setLogin)} placeholder="Enter your password" autoComplete={isSignup ? 'new-password' : 'current-password'} />
          {isSignup && <Field label="Confirm password" name="confirmPassword" type="password" value={signup.confirmPassword} onChange={update(setSignup)} placeholder="Repeat your password" autoComplete="new-password" />}
          {!isSignup && <button type="button" className="text-button" onClick={onForgot}>Forgot password?</button>}
          {isSignup && <p className="password-hint">Use 8+ characters with one uppercase letter, number, and special character.</p>}
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="submit-button" type="submit" disabled={isSubmitting}>{isSubmitting ? 'Please wait…' : isSignup ? 'Create account' : 'Sign in'}{!isSubmitting && <span aria-hidden="true">→</span>}</button>
        </form>
        <p className="terms">By continuing, you agree to our <a href="#terms">Terms</a> and <a href="#privacy">Privacy Policy</a>.</p>
      </div>
    </AuthShell>
  )
}

function PasswordPage({ resetToken, onBack }) {
  const isReset = Boolean(resetToken)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setMessage('')
    if (isReset && password !== confirm) return setError('Passwords do not match.')
    setIsSubmitting(true)
    try {
      if (isReset) {
        await authApi.resetPassword(resetToken, password)
        setMessage('Your password has been updated. You can sign in now.')
      } else {
        await authApi.forgotPassword(email)
        setMessage('If that email exists, a reset link has been sent.')
      }
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthShell>
      <div className="auth-card">
        <div className="auth-heading">
          <p className="eyebrow">{isReset ? 'Choose a new password' : 'Account recovery'}</p>
          <h2>{isReset ? 'Make it fresh and secure.' : 'Forgot your password?'}</h2>
          <p>{isReset ? 'Use a strong password you have not used before.' : 'We will send a secure reset link to your inbox.'}</p>
        </div>
        <form className="recovery-form" onSubmit={handleSubmit} noValidate>
          {!isReset && <Field label="Email address" name="email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" autoComplete="email" />}
          {isReset && <><Field label="New password" name="password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Enter a new password" autoComplete="new-password" /><Field label="Confirm password" name="confirm" type="password" value={confirm} onChange={(event) => setConfirm(event.target.value)} placeholder="Repeat your password" autoComplete="new-password" /></>}
          {message && <p className="form-success" role="status">{message}</p>}
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="submit-button" type="submit" disabled={isSubmitting}>{isSubmitting ? 'Please wait…' : isReset ? 'Update password' : 'Send reset link'}</button>
        </form>
        <button type="button" className="back-button" onClick={onBack}>← Back to sign in</button>
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

function StockSearch({ onSelect }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [searching, setSearching] = useState(false)

  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([])
      return undefined
    }
    const timeout = setTimeout(() => {
      setSearching(true)
      dashboardApi.searchStocks(query.trim())
        .then((response) => setResults(response.results || []))
        .catch(() => setResults([]))
        .finally(() => setSearching(false))
    }, 260)
    return () => clearTimeout(timeout)
  }, [query])

  return (
    <div className="stock-search">
      <span className="search-icon" aria-hidden="true">⌕</span>
      <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search a company or symbol" aria-label="Search stocks" />
      {query.length > 1 && <div className="search-results">{searching && <span>Searching…</span>}{!searching && results.length === 0 && <span>No matching stocks</span>}{results.map((result) => <button type="button" key={result.symbol} onClick={() => { setQuery(result.symbol); onSelect?.(result.symbol) }}><strong>{result.symbol}</strong><span>{result.name}</span></button>)}</div>}
    </div>
  )
}

function defaultAssistantNavigation() {
  window.history.pushState({}, '', '/assistant')
  window.dispatchEvent(new PopStateEvent('popstate'))
}
function defaultCommunityNavigation() {
  window.history.pushState({}, '', '/community')
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
function defaultAdminCommunityNavigation() {
  window.history.pushState({}, '', '/admin/community')
  window.dispatchEvent(new PopStateEvent('popstate'))
}
function defaultHealthNavigation() {
  window.history.pushState({}, '', '/health')
  window.dispatchEvent(new PopStateEvent('popstate'))
}

function MobileNav({ active, onDashboard, onMarket, onPortfolio, onNews, onAssistant = defaultAssistantNavigation, onWatchlist = defaultWatchlistNavigation, onCommunity = defaultCommunityNavigation, onAlerts, onRisk, onSettings }) {
  return <nav className="mobile-nav"><button type="button" className={active === 'dashboard' ? 'active' : ''} onClick={onDashboard}><span>⌂</span>Home</button><button type="button" className={active === 'market' ? 'active' : ''} onClick={onMarket}><span>↗</span>Market</button><button type="button" className={active === 'portfolio' ? 'active' : ''} onClick={onPortfolio}><span>▣</span>Portfolio</button><button type="button" className={active === 'watchlist' ? 'active' : ''} onClick={onWatchlist}><span>☆</span>Watchlist</button><button type="button" className={active === 'news' ? 'active' : ''} onClick={onNews}><span>▤</span>News</button><button type="button" className={active === 'assistant' ? 'active' : ''} onClick={onAssistant}><span>✦</span>AI</button><button type="button" className={active === 'community' ? 'active' : ''} onClick={onCommunity}><span>◎</span>Community</button><button type="button" className={active === 'alerts' ? 'active' : ''} onClick={onAlerts}><span>♢</span>Alerts</button><button type="button" className={active === 'risk' ? 'active' : ''} onClick={onRisk}><span>◌</span>Risk</button><button type="button" className={active === 'settings' ? 'active' : ''} onClick={onSettings}><span>⚙</span>Settings</button></nav>
}

function Header({ active, onDashboard, onMarket, onPortfolio, onNews = () => {}, onAssistant = defaultAssistantNavigation, onCommunity = defaultCommunityNavigation, onWatchlist = defaultWatchlistNavigation, onRecommendations = defaultRecommendationsNavigation, onShariah = defaultShariahNavigation, onAdminCommunity = defaultAdminCommunityNavigation, onHealth = defaultHealthNavigation, onAlerts, onRisk, onSettings, onLogout }) {
  const user = getStoredUser()
  const name = user?.full_name || user?.username || 'Investor'
  const initials = name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part.charAt(0).toUpperCase()).join('') || 'I'
  const [unread, setUnread] = useState(0)
  const [sidebarExpanded, setSidebarExpanded] = useState(() => localStorage.getItem('basarat_sidebar_expanded') === 'true')
  const sidebarRef = useRef(null)

  function navigateFromSidebar(callback) {
    setSidebarExpanded(false)
    localStorage.setItem('basarat_sidebar_expanded', 'false')
    callback?.()
  }

  useEffect(() => {
    if (!sidebarExpanded) return undefined
    function closeOnOutsideClick(event) {
      if (!sidebarRef.current?.contains(event.target)) setSidebarExpanded(false)
    }
    document.addEventListener('mousedown', closeOnOutsideClick)
    return () => document.removeEventListener('mousedown', closeOnOutsideClick)
  }, [sidebarExpanded])

  useEffect(() => {
    let activeRequest = true
    dashboardApi.getAlerts().then((items) => {
      if (activeRequest) setUnread(items.filter((item) => !item.is_read).length)
    }).catch(() => {
      if (activeRequest) setUnread(0)
    })
    return () => { activeRequest = false }
  }, [])

  const links = <><button type="button" className={active === 'dashboard' ? 'active' : ''} onClick={() => navigateFromSidebar(onDashboard)}><span>⌂</span>Dashboard</button><button type="button" className={active === 'market' ? 'active' : ''} onClick={() => navigateFromSidebar(onMarket)}><span>↗</span>Market</button><button type="button" className={active === 'portfolio' ? 'active' : ''} onClick={() => navigateFromSidebar(onPortfolio)}><span>▣</span>Portfolio</button><button type="button" className={active === 'watchlist' ? 'active' : ''} onClick={() => navigateFromSidebar(onWatchlist)}><span>☆</span>Watchlist</button><button type="button" className={active === 'recommendations' ? 'active' : ''} onClick={() => navigateFromSidebar(onRecommendations)}><span>◆</span>Recommendations</button><button type="button" className={active === 'shariah' ? 'active' : ''} onClick={() => navigateFromSidebar(onShariah)}><span>☾</span>Shariah</button><button type="button" className={active === 'news' ? 'active' : ''} onClick={() => navigateFromSidebar(onNews)}><span>▤</span>News</button><button type="button" className={active === 'assistant' ? 'active' : ''} onClick={() => navigateFromSidebar(onAssistant)}><span>✦</span>AI assistant</button><button type="button" className={active === 'community' ? 'active' : ''} onClick={() => navigateFromSidebar(onCommunity)}><span>◎</span>Community</button><button type="button" className={active === 'admin-community' ? 'active' : ''} onClick={() => navigateFromSidebar(onAdminCommunity)}><span>◆</span>Admin Community</button><button type="button" className={active === 'health' ? 'active' : ''} onClick={() => navigateFromSidebar(onHealth)}><span>♥</span>System health</button><button type="button" className={active === 'alerts' ? 'active' : ''} onClick={() => navigateFromSidebar(onAlerts)}><span>♢</span>Alerts{unread > 0 && <b className="notification-badge">{unread}</b>}</button><button type="button" className={active === 'risk' ? 'active' : ''} onClick={() => navigateFromSidebar(onRisk)}><span>◌</span>Risk</button><button type="button" className={active === 'settings' ? 'active' : ''} onClick={() => navigateFromSidebar(onSettings)}><span>⚙</span>Settings</button></>
  function toggleSidebar() {
    setSidebarExpanded((expanded) => {
      const next = !expanded
      localStorage.setItem('basarat_sidebar_expanded', String(next))
      return next
    })
  }

  return <><aside ref={sidebarRef} className={sidebarExpanded ? 'dashboard-sidebar expanded' : 'dashboard-sidebar'}><div className="sidebar-header">{sidebarExpanded ? <><button type="button" className="sidebar-brand-toggle" onClick={() => navigateFromSidebar(onDashboard)} aria-label="Go to dashboard" title="Go to dashboard"><BrandMark /><span>Basarat</span></button><button type="button" className="sidebar-collapse-button" onClick={toggleSidebar} aria-label="Collapse navigation" title="Collapse navigation"><MenuIcon /></button></> : <button type="button" className="sidebar-expand-button" onClick={toggleSidebar} aria-label="Expand navigation" title="Expand navigation"><MenuIcon /></button>}</div><nav className="sidebar-nav">{links}</nav><div className="sidebar-account"><button type="button" className="avatar" aria-label="Open settings" onClick={() => navigateFromSidebar(onSettings)}>{initials}</button><div><strong>{name}</strong><small>Investor workspace</small></div><button type="button" className="sidebar-logout" onClick={onLogout}>Sign out</button></div></aside><header className="dashboard-mobile-header"><button type="button" className="brand mobile-brand-button" onClick={onDashboard} aria-label="Go to dashboard"><BrandMark /><span>Basarat</span></button><button type="button" className="avatar" aria-label="Open settings" onClick={onSettings}>{initials}</button></header></>
}

function Dashboard({ user, onLogout, onMarket, onStock, onPortfolio, onNews, onAlerts, onRisk, onSettings }) {
  const firstName = user?.full_name?.split(' ')[0] || user?.username || 'Investor'
  const [data, setData] = useState({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    const sources = {
      indices: dashboardApi.getIndices(),
      marketStatus: dashboardApi.getMarketStatus(),
      gainers: dashboardApi.getGainers(),
      losers: dashboardApi.getLosers(),
      mostActive: dashboardApi.getMostActive(),
      portfolio: dashboardApi.getPortfolio(),
      news: dashboardApi.getNews(),
      recommendations: dashboardApi.getRecommendations(),
    }
    Promise.allSettled(Object.entries(sources).map(async ([key, promise]) => [key, await promise]))
      .then((results) => {
        if (!active) return
        const next = {}
        results.forEach((result) => {
          if (result.status === 'fulfilled') next[result.value[0]] = { value: result.value[1] }
          else next[Object.keys(sources)[results.indexOf(result)]] = { error: result.reason }
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
  const statusOpen = marketStatus?.status === 'market_hours' || marketStatus?.is_market_open || marketStatus?.market_open

  return (
    <main className="dashboard">
      <Header active="dashboard" onDashboard={() => {}} onMarket={onMarket} onPortfolio={onPortfolio} onNews={onNews} onAlerts={onAlerts} onRisk={onRisk} onSettings={onSettings} onLogout={onLogout} />
      <section className="dashboard-content">
        <StockSearch onSelect={onStock} />
        <div className="dashboard-topline">
          <div><p className="eyebrow">Your market workspace</p><h1>Good morning, {firstName}.</h1><p className="dashboard-lede">A focused view of what is moving across the Pakistan market.</p></div>
          <div className={statusOpen ? 'market-status open' : 'market-status'}><span className="status-dot" />{statusOpen ? 'Market open' : 'Market closed'}<small>{marketStatus?.next_scheduled_run_at ? `Next update ${new Date(marketStatus.next_scheduled_run_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}` : 'PSX market hours'}</small></div>
        </div>
        <div className="index-grid">
          {['KSE-100', 'KSE-30', 'KMI-30'].map((name) => {
            const item = indices.find((index) => index.index === name)
            return <article className="index-card" key={name}><span className="card-label">{name}</span><strong>{formatNumber(item?.current)}</strong><div><span className={Number(item?.change) >= 0 ? 'positive' : 'negative'}>{Number(item?.change) >= 0 ? '+' : ''}{formatNumber(item?.change)}</span><span className="index-percent"><Change value={item?.change_pct} /></span></div></article>
          })}
        </div>
        <div className="dashboard-main-grid">
          <section className="dashboard-section movers-section"><div className="section-heading"><div><p className="eyebrow">Market movers</p><h2>What is moving today</h2></div><span className="section-meta">Top 5</span></div><div className="movers-columns"><MoverList title="Top gainers" items={data.gainers?.value?.gainers} type="gainers" loading={loading} error={data.gainers?.error} /><MoverList title="Top losers" items={data.losers?.value?.losers} type="losers" loading={loading} error={data.losers?.error} /></div></section>
          <section className="dashboard-section"><div className="section-heading"><div><p className="eyebrow">Your portfolio</p><h2>Portfolio summary</h2></div><span className="section-meta">Live</span></div><DataState loading={loading} error={data.portfolio?.error}>{portfolio && <><div className="portfolio-total"><span>Total value</span><strong>{formatMoney(portfolio.summary?.current_value)}</strong><Change value={portfolio.summary?.total_pnl_percent} /></div><div className="portfolio-stats"><div><span>Invested</span><strong>{formatMoney(portfolio.summary?.total_invested)}</strong></div><div><span>Today’s P&amp;L</span><strong className={Number(portfolio.summary?.today_pnl) >= 0 ? 'positive' : 'negative'}>{formatMoney(portfolio.summary?.today_pnl)}</strong></div></div></>}</DataState></section>
          <section className="dashboard-section"><div className="section-heading"><div><p className="eyebrow">Volume watch</p><h2>Most active</h2></div></div><DataState loading={loading} error={data.mostActive?.error}><div className="compact-list">{(data.mostActive?.value?.volume_spikes || []).map((item) => <div className="compact-row" key={item.symbol}><span className="stock-symbol">{item.symbol}</span><span>{formatNumber(item.volume, 0)} shares</span><Change value={item.change_pct} /></div>)}</div></DataState></section>
          <section className="dashboard-section"><div className="section-heading"><div><p className="eyebrow">For your strategy</p><h2>Recommendations</h2></div></div><DataState loading={loading} error={data.recommendations?.error}><div className="compact-list">{recommendations.map((item) => <div className="recommendation-row" key={item.symbol}><span><strong>{item.symbol}</strong><small>{item.summary || 'Market signal'}</small></span><span className={`signal ${item.signal?.toLowerCase()}`}>{item.signal}</span></div>)}</div></DataState></section>
        </div>
        <section className="dashboard-section news-section"><div className="section-heading"><div><p className="eyebrow">The latest</p><h2>Financial news</h2></div><span className="section-meta">Today</span></div><DataState loading={loading} error={data.news?.error}><div className="news-list">{news.map((article) => <a className="news-row" href={article.url} target="_blank" rel="noreferrer" key={article.id}><span><strong>{article.title}</strong><small>{article.source?.name || 'Market update'} · {article.published_at ? new Date(article.published_at).toLocaleDateString() : 'Latest'}</small></span><span aria-hidden="true">↗</span></a>)}</div></DataState></section>
      </section>
      <MobileNav active="dashboard" onDashboard={() => {}} onMarket={onMarket} onPortfolio={onPortfolio} onNews={onNews} onAlerts={onAlerts} onRisk={onRisk} onSettings={onSettings} />
    </main>
  )
}

function MoverList({ title, items = [], loading, error }) {
  return <div className="mover-list"><h3>{title}</h3><DataState loading={loading} error={error}><div>{items.map((item) => <div className="mover-row" key={item.symbol}><span className="stock-symbol">{item.symbol}<small>{item.sector}</small></span><span>{formatNumber(item.current)}</span><Change value={item.change_pct} /></div>)}</div></DataState></div>
}

function MarketOverview({ onBack, onPortfolio, onNews, onWatchlist, onAlerts, onRisk, onSettings, onLogout }) {
  const [data, setData] = useState({})
  const [selectedIndex, setSelectedIndex] = useState('kse-100')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    const sources = {
      indices: dashboardApi.getIndices(),
      status: dashboardApi.getMarketStatus(),
      gainers: dashboardApi.getGainers(),
      losers: dashboardApi.getLosers(),
      volume: dashboardApi.getMostActive(),
      sentiment: dashboardApi.getSentiment(),
      marketSentiment: newsApi.getMarketSentiment(),
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
  const constituentKey = selectedIndex.replace('-', '')
  const constituents = data[constituentKey]?.value?.constituents || []
  const marketOpen = data.status?.value?.status === 'market_hours'
  const movers = [
    ...(data.gainers?.value?.gainers || []).map((item) => ({ ...item, direction: 'up' })),
    ...(data.losers?.value?.losers || []).map((item) => ({ ...item, direction: 'down' })),
  ].sort((a, b) => Math.abs(b.change_pct) - Math.abs(a.change_pct))

  return (
    <main className="dashboard">
      <Header active="market" onDashboard={onBack} onMarket={() => {}} onPortfolio={onPortfolio} onNews={onNews} onAlerts={onAlerts} onRisk={onRisk} onSettings={onSettings} onLogout={onLogout} />
      <section className="dashboard-content market-overview">
        <StockSearch onSelect={(symbol) => { window.history.pushState({}, '', `/stocks/${symbol}`); window.dispatchEvent(new PopStateEvent('popstate')) }} />
        <div className="dashboard-topline">
          <div><p className="eyebrow">Pakistan Stock Exchange</p><h1>Market overview.</h1><p className="dashboard-lede">A live view of indices, breadth, liquidity, and the stocks moving the market.</p></div>
          <div className={marketOpen ? 'market-status open' : 'market-status'}><span className="status-dot" />{marketOpen ? 'Market open' : 'Market closed'}<small>{data.status?.value?.current_time_pkt ? new Date(data.status.value.current_time_pkt).toLocaleString() : 'Live schedule'}</small></div>
        </div>
        <div className="index-grid">
          {['KSE-100', 'KSE-30', 'KMI-30'].map((name) => {
            const item = indices.find((index) => index.index === name)
            return <article className="index-card" key={name}><span className="card-label">{name}</span><strong>{formatNumber(item?.current)}</strong><div><span className={Number(item?.change) >= 0 ? 'positive' : 'negative'}>{Number(item?.change) >= 0 ? '+' : ''}{formatNumber(item?.change)}</span><span className="index-percent"><Change value={item?.change_pct} /></span></div><small className="range">H {formatNumber(item?.high)} · L {formatNumber(item?.low)}</small></article>
          })}
        </div>
        <div className="market-overview-grid">
          <section className="dashboard-section sentiment-card"><div className="section-heading"><div><p className="eyebrow">Market breadth</p><h2>{sentiment?.market_mood || 'Market sentiment'}</h2></div></div><DataState loading={loading} error={data.sentiment?.error}><div className="breadth-total"><strong>{formatNumber(sentiment?.advance_decline_ratio, 2)}</strong><span>advance / decline ratio</span></div><div className="breadth-bars"><div><span>Advancing <b>{sentiment?.advancing || 0}</b></span><i style={{ width: `${sentiment?.gainers_pct || 0}%` }} /></div><div><span>Declining <b>{sentiment?.declining || 0}</b></span><i className="declining" style={{ width: `${sentiment?.losers_pct || 0}%` }} /></div><div><span>Unchanged <b>{sentiment?.unchanged || 0}</b></span></div></div></DataState></section>
          <section className="dashboard-section sentiment-card"><div className="section-heading"><div><p className="eyebrow">FinBERT news tone</p><h2>{marketSentiment?.market_mood || 'Unavailable'}</h2></div><span className="section-meta">{marketSentiment?.article_count || 0} articles</span></div><DataState loading={loading} error={data.marketSentiment?.error}><div className="breadth-total"><strong>{formatNumber(marketSentiment?.overall_score, 2)}</strong><span>overall sentiment score</span></div><div className="sentiment-summary"><span>News average <b>{formatNumber(marketSentiment?.news_sentiment_avg, 2)}</b></span><span>Community <b>{formatNumber(marketSentiment?.community_sentiment_avg, 2)}</b></span></div></DataState></section>
          <section className="dashboard-section"><div className="section-heading"><div><p className="eyebrow">Liquidity</p><h2>Most active</h2></div></div><DataState loading={loading} error={data.volume?.error}><div className="compact-list">{(data.volume?.value?.volume_spikes || []).map((item) => <div className="compact-row" key={item.symbol}><span className="stock-symbol">{item.symbol}<small>{item.sector}</small></span><span>{formatNumber(item.volume, 0)}</span><Change value={item.change_pct} /></div>)}</div></DataState></section>
        </div>
        <section className="dashboard-section"><div className="section-heading"><div><p className="eyebrow">Index constituents</p><h2>Explore the market</h2></div><div className="index-tabs">{[['kse-100', 'KSE-100'], ['kse-30', 'KSE-30'], ['kmi-30', 'KMI-30']].map(([code, label]) => <button type="button" className={selectedIndex === code ? 'active' : ''} onClick={() => setSelectedIndex(code)} key={code}>{label}</button>)}</div></div><DataState loading={loading} error={data[constituentKey]?.error}><div className="table-scroll"><table className="market-table"><thead><tr><th>Company</th><th>Price</th><th>Change</th><th>Weight</th><th>Volume</th><th>Market cap</th></tr></thead><tbody>{constituents.slice(0, 12).map((item) => <tr key={item.symbol}><td><strong>{item.symbol}</strong><small>{item.name}</small></td><td>{formatNumber(item.current)}</td><td><Change value={item.change_pct} /></td><td>{formatNumber(item.weight_pct)}%</td><td>{formatNumber(item.volume, 0)}</td><td>{formatNumber(item.market_cap_m, 0)}m</td></tr>)}</tbody></table></div></DataState></section>
        <div className="market-overview-grid">
          <section className="dashboard-section"><div className="section-heading"><div><p className="eyebrow">Top movers</p><h2>Biggest moves</h2></div></div><DataState loading={loading} error={data.gainers?.error || data.losers?.error}><div className="compact-list">{movers.slice(0, 8).map((item) => <div className="compact-row" key={`${item.direction}-${item.symbol}`}><span className="stock-symbol">{item.symbol}<small>{item.sector}</small></span><span>{formatNumber(item.current)}</span><Change value={item.change_pct} /></div>)}</div></DataState></section>
          <section className="dashboard-section"><div className="section-heading"><div><p className="eyebrow">Sector performance</p><h2>Where momentum is</h2></div></div><DataState loading={loading} error={data.sentiment?.error}><div className="sector-list">{(sentiment?.sector_performance || []).slice(0, 6).map((sector) => <div className="sector-row" key={sector.sector}><span>{sector.sector}<small>{sector.companies} companies</small></span><Change value={sector.avg_change_pct} /></div>)}</div></DataState></section>
        </div>
      </section>
      <MobileNav active="market" onDashboard={onBack} onMarket={() => {}} onPortfolio={onPortfolio} onNews={onNews} onWatchlist={onWatchlist} onAlerts={onAlerts} onRisk={onRisk} onSettings={onSettings} />
    </main>
  )
}

function PriceChart({ bars }) {
  const closes = bars.map((bar) => Number(bar.close)).filter(Number.isFinite)
  if (!closes.length) return <p className="data-state">No price history available.</p>
  const min = Math.min(...closes)
  const max = Math.max(...closes)
  const points = closes.map((value, index) => `${(index / Math.max(closes.length - 1, 1)) * 100},${92 - ((value - min) / Math.max(max - min, 1)) * 78}`).join(' ')
  return <svg className="price-chart" viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="Price history chart"><polyline points={points} fill="none" vectorEffect="non-scaling-stroke" /></svg>
}

function StockDetail({ symbol, onBack, onPortfolio, onNews, onWatchlist, onAlerts, onRisk, onSettings, onLogout, onStock, onAlert }) {
 const [overview, setOverview] = useState(null)
 const [history, setHistory] = useState([])
 const [news, setNews] = useState([])
 const [extras, setExtras] = useState({})
 const [range, setRange] = useState('1M')
 const [forecastHorizon, setForecastHorizon] = useState('1D')
 const [forecastHistory, setForecastHistory] = useState(null)
 const [stockSentiment, setStockSentiment] = useState(null)
 const [sentimentHistory, setSentimentHistory] = useState(null)
 const [sentimentNews, setSentimentNews] = useState([])
 const [loading, setLoading] = useState(true)
 const [watchlisted, setWatchlisted] = useState(() => getWatchlist().includes(symbol))

 function toggleWatchlist() {
   const next = getWatchlist()
   const updated = watchlisted ? next.filter((item) => item !== symbol) : [...next, symbol]
   saveWatchlist(updated)
   setWatchlisted(!watchlisted)
 }

 useEffect(() => {
   let active = true
   const coreRequests = Promise.allSettled([
     dashboardApi.getStockOverview(symbol),
     dashboardApi.getPriceHistory(symbol, range),
     dashboardApi.getStockNews(symbol),
   ])
   const extraRequests = Promise.allSettled([
     dashboardApi.getTechnicalIndicators(symbol),
     dashboardApi.getFundamentals(symbol),
     dashboardApi.getForecast(symbol, forecastHorizon),
     dashboardApi.getRecommendation(symbol),
     dashboardApi.getTargetStop(symbol),
     dashboardApi.getShariah(symbol),
     dashboardApi.getForecastHistory(symbol),
     newsApi.getStockSentiment(symbol),
     newsApi.getSentimentHistory(symbol),
     newsApi.getSentimentNews(symbol, { limit: 5 }),
   ])
   coreRequests.then(([overviewResult, historyResult, newsResult]) => {
     if (!active) return
     if (overviewResult.status === 'fulfilled') setOverview(overviewResult.value)
     if (historyResult.status === 'fulfilled') setHistory(historyResult.value.bars || [])
     if (newsResult.status === 'fulfilled') setNews(newsResult.value.items || [])
     setLoading(false)
   })
   extraRequests.then(([technical, fundamentals, forecast, recommendation, targetStop, shariah, historyForecast, stockSentimentResult, sentimentHistoryResult, sentimentNewsResult]) => {
     if (!active) return
     if (historyForecast.status === 'fulfilled') setForecastHistory(historyForecast.value)
     if (stockSentimentResult.status === 'fulfilled') setStockSentiment(stockSentimentResult.value)
     if (sentimentHistoryResult.status === 'fulfilled') setSentimentHistory(sentimentHistoryResult.value)
     if (sentimentNewsResult.status === 'fulfilled') setSentimentNews(sentimentNewsResult.value.items || [])
     setExtras({ technical, fundamentals, forecast, recommendation, targetStop, shariah })
   })
   return () => { active = false }
 }, [symbol, range, forecastHorizon])

 const technical = extras.technical?.status === 'fulfilled' ? extras.technical.value : null
 const fundamentals = extras.fundamentals?.status === 'fulfilled' ? extras.fundamentals.value : null
 const forecast = extras.forecast?.status === 'fulfilled' ? extras.forecast.value : null
 const targetStop = extras.targetStop?.status === 'fulfilled' ? extras.targetStop.value : null
 const ratios = fundamentals?.ratios || {}
 const summaryMetrics = [
   ['EPS', ratios.eps],
   ['Dividend yield', ratios.dividend_yield_pct, '%'],
   ['Net margin', ratios.net_profit_margin_pct, '%'],
   ['PEG ratio', ratios.peg_ratio],
 ]
 const recommendation = extras.recommendation?.status === 'fulfilled' ? extras.recommendation.value : null
 const indicators = [
   ['RSI', technical?.summary?.rsi],
   ['MACD', technical?.summary?.macd],
   ['SMA', technical?.summary?.sma],
   ['ADX', technical?.summary?.adx],
 ]

 return (
   <main className="dashboard">
     <Header active="market" onDashboard={onBack} onMarket={onBack} onPortfolio={onPortfolio} onNews={onNews} onAlerts={onAlerts} onRisk={onRisk} onSettings={onSettings} onLogout={onLogout} />
     <section className="dashboard-content stock-detail"><StockSearch onSelect={onStock} /><button type="button" className="back-button stock-back" onClick={onBack}>← Back to market</button>{loading ? <p className="data-state">Loading stock data…</p> : <><div className="stock-heading"><div><p className="eyebrow">{overview?.sector || 'Pakistan Stock Exchange'}</p><h1>{overview?.name || symbol}</h1><p className="stock-symbol-large">{symbol}</p></div><div className="stock-quote"><strong>{formatNumber(overview?.ltp)}</strong><Change value={overview?.change_pct} /><small>Volume {formatNumber(overview?.volume, 0)}</small><div className="stock-actions"><button type="button" className="alert-button" onClick={() => onAlert(symbol)}>Set price alert</button><button type="button" className={watchlisted ? 'watch-button active' : 'watch-button'} onClick={toggleWatchlist}>{watchlisted ? '★ Watching' : '☆ Watchlist'}</button><button type="button" className="watch-button" onClick={onWatchlist}>Compare</button></div></div></div><div className="detail-grid"><section className="dashboard-section chart-card"><div className="section-heading"><div><p className="eyebrow">Price history</p><h2>{symbol} performance</h2></div><div className="range-tabs">{['1D', '1W', '1M', '1Y'].map((item) => <button type="button" className={range === item ? 'active' : ''} onClick={() => setRange(item)} key={item}>{item}</button>)}</div></div><PriceChart bars={history} /></section><section className="dashboard-section"><div className="section-heading"><div><p className="eyebrow">Company profile</p><h2>Market snapshot</h2></div></div><div className="fact-grid"><div><span>Sector</span><strong>{overview?.sector || '—'}</strong></div><div><span>Day high</span><strong>{formatNumber(overview?.day_range?.high)}</strong></div><div><span>Day low</span><strong>{formatNumber(overview?.day_range?.low)}</strong></div><div><span>Market cap</span><strong>{formatMoney(overview?.market_cap)}</strong></div><div><span>P/E ratio</span><strong>{formatNumber(overview?.pe_ratio || ratios.pe_ratio)}</strong></div><div><span>Shariah</span><strong className={extras.shariah?.value?.is_shariah_compliant ? 'positive' : 'negative'}>{extras.shariah?.value ? extras.shariah.value.is_shariah_compliant ? 'Compliant' : 'Not classified' : '—'}</strong></div></div></section><section className="dashboard-section"><div className="section-heading"><div><p className="eyebrow">Signals</p><h2>{extras.recommendation?.value?.signal || technical?.overall_signal || '—'}</h2></div></div><p className="signal-message">{extras.recommendation?.value?.summary || technical?.summary_message || 'Technical and model signals are loading.'}</p>     <div className="forecast-row"><span>Recommendation</span><strong>{recommendation?.signal || forecast?.signal_rating || forecast?.direction || '—'}</strong></div></section><section className="dashboard-section sentiment-card"><div className="section-heading"><div><p className="eyebrow">FinBERT sentiment</p><h2>{stockSentiment?.label || 'Unavailable'}</h2></div><span className="section-meta">{stockSentiment?.article_count || 0} articles</span></div><div className="breadth-total"><strong>{stockSentiment ? formatNumber(stockSentiment.score, 2) : '—'}</strong><span>{stockSentiment?.trend || 'Recent news tone'}</span></div>{stockSentiment?.source_breakdown && <div className="sentiment-summary">{Object.entries(stockSentiment.source_breakdown).slice(0, 2).map(([source, value]) => <span key={source}>{source} <b>{formatNumber(value, 2)}</b></span>)}</div>}<div className="sentiment-history">{(sentimentHistory?.data || []).slice(-7).map((point) => <span key={point.date} title={`${point.date}: ${point.label}` } style={{ height: `${Math.max(12, Math.min(100, ((Number(point.score) + 1) / 2) * 100))}%` }} />)}</div></section></div><div className="stock-data-grid"><section className="dashboard-section"><div className="section-heading"><div><p className="eyebrow">Technical indicators</p><h2>{technical?.overall_signal || 'Technical view'}</h2></div></div><div className="indicator-list">{indicators.map(([label, item]) => <div className="indicator-row" key={label}><span>{label}<small>{item?.description || 'No reading available'}</small></span><strong>{formatNumber(item?.value)} <em className={item?.signal === 'buy' ? 'positive' : item?.signal === 'sell' ? 'negative' : ''}>{item?.signal || '—'}</em></strong></div>)}</div></section><section className="dashboard-section"><div className="section-heading"><div><p className="eyebrow">Fundamentals</p><h2>Key metrics</h2></div></div><div className="fact-grid">{summaryMetrics.map(([label, value, suffix]) => <div key={label}><span>{label}</span><strong>{value == null ? '—' : `${formatNumber(value)}${suffix || ''}`}</strong></div>)}</div>{fundamentals?.company_profile?.business_description && <p className="fundamental-description">{fundamentals.company_profile.business_description}</p>}</section><section className="dashboard-section forecast-card"><div className="section-heading"><div><p className="eyebrow">AI forecast</p><h2>{forecast?.signal_rating || 'Unavailable'}</h2></div><select value={forecastHorizon} onChange={(event) => setForecastHorizon(event.target.value)}><option value="1D">1 day</option><option value="1W">1 week</option><option value="1M">1 month</option></select></div>{forecast ? <><div className="forecast-direction"><strong>{forecast.direction}</strong><span>{Math.round((forecast.confidence || 0) * 100)}% confidence</span></div><div className="probability-bars">{Object.entries(forecast.probabilities || {}).map(([key, value]) => <div key={key}><span>{key}<b>{formatNumber(value)}%</b></span><i><u style={{ width: `${Math.min(Number(value), 100)}%` }} /></i></div>)}</div>     <div className="fact-grid forecast-facts"><div><span>Target</span><strong>{formatNumber(forecast.target_price ?? targetStop?.target_price)}</strong></div><div><span>Stop loss</span><strong>{formatNumber(forecast.stop_loss ?? targetStop?.stop_loss)}</strong></div><div><span>Risk / reward</span><strong>{formatNumber(forecast.risk_reward_ratio)}</strong></div></div></> : <p className="data-state">Forecast unavailable. The model may still be warming up.</p>}</section></div>{forecastHistory && <section className="dashboard-section forecast-history"><div className="section-heading"><div><p className="eyebrow">Model track record</p><h2>Forecast history</h2></div><span className="section-meta">{forecastHistory.accuracy == null ? 'Not scored yet' : `${Math.round(forecastHistory.accuracy * 100)}% accuracy`}</span></div><div className="table-scroll"><table className="market-table"><thead><tr><th>Predicted</th><th>Direction</th><th>Confidence</th><th>Outcome</th></tr></thead><tbody>{(forecastHistory.history || []).slice(0, 10).map((item) => <tr key={`${item.predicted_at}-${item.target_date}`}><td>{new Date(item.predicted_at).toLocaleDateString()}</td><td>{item.direction}</td><td>{Math.round((item.confidence || 0) * 100)}%</td><td className={item.actual?.was_correct ? 'positive' : item.actual ? 'negative' : ''}>{item.actual ? item.actual.was_correct ? 'Correct' : 'Missed' : 'Pending'}</td></tr>)}</tbody></table></div>     </section>}<section className="dashboard-section detail-news"><div className="section-heading"><div><p className="eyebrow">Latest coverage</p><h2>{symbol} news</h2></div></div><div className="news-list">{sentimentNews.length ? sentimentNews.map((article) => <a className="news-row" href={article.url || '#'} target="_blank" rel="noreferrer" key={article.id}><span><strong>{article.title}</strong><small>{article.source || 'Market update'} · {article.sentiment || 'Unscored'}</small></span><span>↗</span></a>) : news.length ? news.map((article) => <a className="news-row" href={article.url} target="_blank" rel="noreferrer" key={article.id}><span><strong>{article.title}</strong><small>{article.source?.name || 'Market update'}</small></span><span>↗</span></a>) : <p className="data-state">No recent news for this stock.</p>}</div></section></>}     </section><MobileNav active="market" onDashboard={onBack} onMarket={onBack} onPortfolio={onPortfolio} onNews={onNews} onWatchlist={onWatchlist} onAlerts={onAlerts} onRisk={onRisk} onSettings={onSettings} />
   </main>
 )
}

function NewsPage({ onBack, onMarket, onPortfolio, onAlerts, onRisk, onSettings, onLogout }) {
  const [articles, setArticles] = useState([])
  const [selected, setSelected] = useState(null)
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('')
  const [sentiment, setSentiment] = useState('')
  const [symbol, setSymbol] = useState('')
  const [marketSentiment, setMarketSentiment] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [lastUpdated, setLastUpdated] = useState('')

  const loadNews = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [feed, sentimentResult] = await Promise.all([
        newsApi.getNews({ limit: 50, q: query.trim() || undefined, event_type: category || undefined, sentiment: sentiment || undefined, symbol: symbol.trim().toUpperCase() || undefined }),
        newsApi.getMarketSentiment().catch(() => null),
      ])
      setArticles(feed.items || [])
      setLastUpdated(feed.last_updated_at || '')
      setMarketSentiment(sentimentResult)
    } catch (requestError) {
      setError(requestError.message)
      setArticles([])
    } finally {
      setLoading(false)
    }
  }, [category, query, sentiment, symbol])

  useEffect(() => {
    const timer = setTimeout(loadNews, query ? 350 : 0)
    return () => clearTimeout(timer)
  }, [loadNews, query])

  async function openArticle(article) {
    try {
      const detail = await newsApi.getArticle(article.id)
      setSelected(detail)
    } catch {
      setSelected(article)
    }
  }

  const sentimentLabel = marketSentiment?.label || marketSentiment?.market_sentiment || marketSentiment?.overall_label
  const sentimentScore = marketSentiment?.score ?? marketSentiment?.overall_score
  const categories = [['', 'All categories'], ['results', 'Results'], ['dividend', 'Dividends'], ['board_meeting', 'Board meetings'], ['company_notice', 'Company notices'], ['regulatory', 'Regulatory'], ['policy_rate', 'Policy rate'], ['fuel_price', 'Fuel prices']]
  const sentimentOptions = [['', 'All sentiment'], ['bullish', 'Bullish'], ['neutral', 'Neutral'], ['bearish', 'Bearish']]

  return <main className="dashboard">
    <Header active="news" onDashboard={onBack} onMarket={onMarket} onPortfolio={onPortfolio} onNews={() => {}} onAlerts={onAlerts} onRisk={onRisk} onSettings={onSettings} onLogout={onLogout} />
    <section className="dashboard-content news-page">
      <div className="news-page-heading">
        <div><p className="eyebrow">Market intelligence</p><h1>News that moves markets.</h1><p className="dashboard-lede">Stay close to the announcements, analysis, and signals shaping Pakistan equities.</p></div>
        <div className="news-sentiment-card"><span>Market sentiment</span><strong className={`sentiment-${String(sentimentLabel || 'neutral').toLowerCase()}`}>{sentimentLabel || 'Unavailable'}</strong><small>{sentimentScore !== undefined && sentimentScore !== null ? `${Math.round(Number(sentimentScore) * 100)}% confidence` : 'Based on the latest coverage'}</small></div>
      </div>
      <div className="news-toolbar">
        <label className="news-search"><span aria-hidden="true">⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search headlines, companies, or topics" aria-label="Search news" /></label>
        <label><span className="sr-only">Category</span><select value={category} onChange={(event) => setCategory(event.target.value)}>{categories.map(([value, label]) => <option value={value} key={value || 'all'}>{label}</option>)}</select></label>
        <label><span className="sr-only">Sentiment</span><select value={sentiment} onChange={(event) => setSentiment(event.target.value)}>{sentimentOptions.map(([value, label]) => <option value={value} key={value || 'all'}>{label}</option>)}</select></label>
        <label className="symbol-filter"><span className="sr-only">Stock symbol</span><input value={symbol} onChange={(event) => setSymbol(event.target.value)} placeholder="Stock symbol e.g. HBL" /></label>
      </div>
      <div className="news-layout">
        <section className="dashboard-section news-feed-panel">
          <div className="section-heading"><div><p className="eyebrow">Latest coverage</p><h2>{symbol ? `${symbol.toUpperCase()} news` : 'The daily brief'}</h2></div><small className="news-updated">{lastUpdated ? `Updated ${new Date(lastUpdated).toLocaleString()}` : ''}</small></div>
          {loading && <p className="data-state">Loading the latest coverage…</p>}
          {!loading && error && <p className="form-error">{error}</p>}
          {!loading && !error && articles.length === 0 && <p className="data-state">No stories match these filters.</p>}
          {!loading && !error && <div className="news-feed">{articles.map((article) => <button type="button" className="news-card" key={article.id} onClick={() => openArticle(article)}><div className="news-card-top"><span className={article.is_official ? 'source-tag official' : 'source-tag'}>{article.source?.name || 'Market source'}</span><time>{article.published_at ? new Date(article.published_at).toLocaleDateString() : 'Recent'}</time></div><h3>{article.title}</h3><p>{article.summary || 'Read the full market update for more context.'}</p><div className="news-card-bottom"><span>{article.event_type?.replaceAll('_', ' ') || 'Market update'}</span>{article.sentiment?.label && <strong className={`sentiment-${article.sentiment.label}`}>{article.sentiment.label} {article.sentiment.score ? `${Math.round(article.sentiment.score * 100)}%` : ''}</strong>}</div></button>)}</div>}
        </section>
        <aside className="news-sidebar">
          <section className="dashboard-section"><p className="eyebrow">Quick filters</p><h2>Follow a stock</h2><p className="sidebar-copy">Enter a PSX symbol above to focus the feed on one company.</p><div className="symbol-chips">{['HBL', 'OGDC', 'LUCK', 'ENGRO', 'SYS'].map((item) => <button type="button" className={symbol.toUpperCase() === item ? 'selected' : ''} onClick={() => setSymbol(item)} key={item}>{item}</button>)}</div></section>
          <section className="dashboard-section"><p className="eyebrow">Sentiment guide</p><h2>Read the tone</h2><div className="sentiment-guide"><span><i className="sentiment-dot bullish" />Bullish</span><span><i className="sentiment-dot neutral" />Neutral</span><span><i className="sentiment-dot bearish" />Bearish</span></div><p className="sidebar-copy">Sentiment is model-generated for eligible news sources. Official notices remain objective until analyzed.</p></section>
        </aside>
      </div>
    </section>
    {selected && <div className="article-overlay" role="presentation" onClick={() => setSelected(null)}><article className="article-detail" role="dialog" aria-modal="true" aria-labelledby="article-title" onClick={(event) => event.stopPropagation()}><button type="button" className="article-close" onClick={() => setSelected(null)} aria-label="Close article">×</button><span className={selected.is_official ? 'source-tag official' : 'source-tag'}>{selected.source?.name || 'Market source'}</span><p className="eyebrow">{selected.event_type?.replaceAll('_', ' ') || 'Market update'}</p><h2 id="article-title">{selected.title}</h2><time>{selected.published_at ? new Date(selected.published_at).toLocaleString() : ''}</time>{selected.sentiment?.label && <strong className={`article-sentiment sentiment-${selected.sentiment.label}`}>{selected.sentiment.label} sentiment</strong>}<p className="article-summary">{selected.summary || 'Open the source article for the full report.'}</p>{selected.symbols?.length > 0 && <div className="article-symbols">{selected.symbols.map((item) => <span key={item.symbol}>{item.symbol}</span>)}</div>}<a className="article-link" href={selected.external_url || selected.url} target="_blank" rel="noreferrer">Read original article ↗</a></article></div>}
    <MobileNav active="news" onDashboard={onBack} onMarket={onMarket} onPortfolio={onPortfolio} onNews={() => {}} onAlerts={onAlerts} onRisk={onRisk} onSettings={onSettings} />
  </main>
}

function AssistantPage({ onBack, onMarket, onPortfolio, onNews, onAlerts, onRisk, onSettings, onLogout }) {
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
    <Header active="assistant" onDashboard={onBack} onMarket={onMarket} onPortfolio={onPortfolio} onNews={onNews} onAssistant={() => {}} onAlerts={onAlerts} onRisk={onRisk} onSettings={onSettings} onLogout={onLogout} />
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
    <MobileNav active="assistant" onDashboard={onBack} onMarket={onMarket} onPortfolio={onPortfolio} onNews={onNews} onAssistant={() => {}} onAlerts={onAlerts} onRisk={onRisk} onSettings={onSettings} />
  </main>
}

function CommunityPage({ onBack, onMarket, onPortfolio, onNews, onAssistant, onCommunity, onAlerts, onRisk, onSettings, onLogout }) {
  const [posts, setPosts] = useState([])
  const [comments, setComments] = useState({})
  const [profile, setProfile] = useState(null)
  const [filter, setFilter] = useState('all')
  const [stockFilter, setStockFilter] = useState('')
  const [content, setContent] = useState('')
  const [postType, setPostType] = useState('GENERAL_MARKET')
  const [stockSymbol, setStockSymbol] = useState('')
  const [commentDrafts, setCommentDrafts] = useState({})
  const [expanded, setExpanded] = useState({})
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(true)
  const [posting, setPosting] = useState(false)

  async function loadFeed() {
    setLoading(true)
    try {
      const params = filter === 'following' ? { following: true } : filter === 'mine' ? { mine: true } : {}
      if (stockFilter.trim()) params.stock_symbol = stockFilter.trim().toUpperCase()
      const [feed, myProfile] = await Promise.all([communityApi.getFeed(params), communityApi.getMyProfile()])
      setPosts(feed.posts || [])
      setProfile(myProfile)
      setMessage('')
    } catch (error) {
      setMessage(error.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadFeed() }, [filter, stockFilter])

  async function submitPost(event) {
    event.preventDefault()
    if (!content.trim() || posting) return
    setPosting(true)
    try {
      await communityApi.createPost(content, postType, postType === 'STOCK' ? stockSymbol : '')
      setContent('')
      setStockSymbol('')
      setMessage('Post published.')
      await loadFeed()
    } catch (error) {
      setMessage(error.message)
    } finally {
      setPosting(false)
    }
  }

  async function toggleLike(post) {
    try {
      await (post.liked_by_me ? communityApi.unlikePost(post.id) : communityApi.likePost(post.id))
      setPosts((current) => current.map((item) => item.id === post.id ? { ...item, liked_by_me: !item.liked_by_me, like_count: item.like_count + (item.liked_by_me ? -1 : 1) } : item))
    } catch (error) { setMessage(error.message) }
  }

  async function toggleComments(post) {
    if (expanded[post.id]) {
      setExpanded((current) => ({ ...current, [post.id]: false }))
      return
    }
    try {
      const result = await communityApi.getComments(post.id)
      setComments((current) => ({ ...current, [post.id]: result.comments || [] }))
      setExpanded((current) => ({ ...current, [post.id]: true }))
    } catch (error) { setMessage(error.message) }
  }

  async function submitComment(event, postId) {
    event.preventDefault()
    const draft = commentDrafts[postId]?.trim()
    if (!draft) return
    try {
      const comment = await communityApi.createComment(postId, draft)
      setComments((current) => ({ ...current, [postId]: [...(current[postId] || []), comment] }))
      setCommentDrafts((current) => ({ ...current, [postId]: '' }))
      setPosts((current) => current.map((post) => post.id === postId ? { ...post, comment_count: post.comment_count + 1 } : post))
    } catch (error) { setMessage(error.message) }
  }

  async function reportPost(postId) {
    const reason = window.prompt('Reason: SPAM, OFF_TOPIC, MISLEADING, ABUSIVE, or OTHER', 'OTHER')
    if (!reason) return
    try {
      await communityApi.reportPost(postId, reason.toUpperCase())
      setMessage('Thanks. The post was sent for moderation review.')
    } catch (error) { setMessage(error.message) }
  }

  const formatTime = (value) => value ? new Date(value).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : 'Recently'
  return <main className="dashboard">
    <Header active="community" onDashboard={onBack} onMarket={onMarket} onPortfolio={onPortfolio} onNews={onNews} onAssistant={onAssistant} onCommunity={() => {}} onAlerts={onAlerts} onRisk={onRisk} onSettings={onSettings} onLogout={onLogout} />
    <section className="dashboard-content community-page">
      <div className="community-heading"><div><p className="eyebrow">Social investing</p><h1>Ideas worth discussing.</h1><p className="dashboard-lede">Share market perspectives, follow thoughtful investors, and keep every discussion grounded in the data.</p></div><div className="community-profile-card"><span>{profile?.full_name || profile?.username || 'Investor'}</span><small>{profile?.followers_count || 0} followers · {profile?.following_count || 0} following</small></div></div>
      <div className="community-layout">
        <section className="community-main">
          <form className="dashboard-section community-composer" onSubmit={submitPost}><div className="section-heading"><div><p className="eyebrow">Start a discussion</p><h2>What are you seeing?</h2></div></div><textarea value={content} onChange={(event) => setContent(event.target.value)} placeholder="Share a market observation, thesis, or question…" maxLength="5000" rows="4" /><div className="composer-controls"><select value={postType} onChange={(event) => setPostType(event.target.value)}><option value="GENERAL_MARKET">Market discussion</option><option value="STOCK">Stock discussion</option></select>{postType === 'STOCK' && <input value={stockSymbol} onChange={(event) => setStockSymbol(event.target.value)} placeholder="Symbol e.g. HBL" required />}<button className="submit-button" disabled={posting || !content.trim()}>{posting ? 'Publishing…' : 'Publish post'}<span>→</span></button></div></form>
          <div className="community-toolbar"><div className="community-tabs">{[['all', 'For you'], ['following', 'Following'], ['mine', 'My posts']].map(([value, label]) => <button type="button" className={filter === value ? 'active' : ''} onClick={() => setFilter(value)} key={value}>{label}</button>)}</div><input value={stockFilter} onChange={(event) => setStockFilter(event.target.value)} placeholder="Filter by stock" aria-label="Filter community by stock" /></div>
          {message && <p className={message.includes('published') || message.includes('Thanks') ? 'form-success' : 'form-error'}>{message}</p>}
          {loading && <p className="data-state">Loading community discussions…</p>}
          {!loading && !posts.length && <div className="dashboard-section data-state">No discussions match this view yet.</div>}
          {!loading && posts.map((post) => <article className="dashboard-section community-post" key={post.id}><div className="post-meta"><div className="post-avatar">{(post.author_full_name || post.author_username || 'U').slice(0, 1).toUpperCase()}</div><div><strong>{post.author_full_name || post.author_username || 'Community member'}</strong><small>{post.stock_symbol ? `${post.stock_symbol} · ` : ''}{formatTime(post.created_at)}</small></div><span className="post-type">{post.post_type === 'STOCK' ? 'Stock' : 'Market'}</span></div><p className="post-content">{post.content}</p>{post.stock_symbol && <button type="button" className="stock-pill" onClick={() => setStockFilter(post.stock_symbol)}>{post.stock_symbol} {post.stock_name ? `· ${post.stock_name}` : ''}</button>}<div className="post-actions"><button type="button" className={post.liked_by_me ? 'liked' : ''} onClick={() => toggleLike(post)}>♡ {post.like_count}</button><button type="button" onClick={() => toggleComments(post)}>▢ {post.comment_count} comments</button><button type="button" onClick={() => reportPost(post.id)}>Report</button></div>{expanded[post.id] && <div className="comment-area">{(comments[post.id] || []).map((comment) => <div className="comment-row" key={comment.id}><strong>{comment.author_full_name || comment.author_username || 'Member'}</strong><p>{comment.content}</p></div>)}<form onSubmit={(event) => submitComment(event, post.id)} className="comment-form"><input value={commentDrafts[post.id] || ''} onChange={(event) => setCommentDrafts((current) => ({ ...current, [post.id]: event.target.value }))} placeholder="Add a thoughtful comment…" /><button type="submit">Send</button></form></div>}</article>)}
        </section>
        <aside className="community-sidebar"><section className="dashboard-section"><p className="eyebrow">Community guidelines</p><h2>Invest with respect.</h2><p className="sidebar-copy">Share evidence, label opinions clearly, and never present speculation as guaranteed returns. Report posts that cross the line.</p></section><section className="dashboard-section"><p className="eyebrow">Your activity</p><div className="community-stats"><div><strong>{profile?.published_post_count || 0}</strong><span>Posts</span></div><div><strong>{profile?.followers_count || 0}</strong><span>Followers</span></div><div><strong>{profile?.following_count || 0}</strong><span>Following</span></div></div></section></aside>
      </div>
    </section>
    <MobileNav active="community" onDashboard={onBack} onMarket={onMarket} onPortfolio={onPortfolio} onNews={onNews} onAssistant={onAssistant} onCommunity={onCommunity} onAlerts={onAlerts} onRisk={onRisk} onSettings={onSettings} />
  </main>
}

function SettingsPage({ onBack, onMarket, onNews, onAlerts, onRisk, onLogout }) {
const [profile, setProfile] = useState({ full_name: '', risk_tolerance: '', investment_horizon: '', sector_preferences: [] })
const [channels, setChannels] = useState(['in_app'])
const [categories, setCategories] = useState(['price', 'forecast', 'news', 'risk'])
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
const notificationCategories = [['price', 'Price alerts'], ['forecast', 'Forecasts'], ['news', 'Market news'], ['risk', 'Risk warnings']]

return <main className="dashboard"><Header active="settings" onDashboard={onBack} onMarket={onMarket} onNews={onNews} onAlerts={onAlerts} onRisk={onRisk} onSettings={() => {}} onLogout={onLogout} />
  <section className="dashboard-content settings-page"><p className="eyebrow">Workspace preferences</p><h1>Settings.</h1><p className="dashboard-lede">Keep your profile and notifications aligned with the way you invest.</p>
    <form onSubmit={saveProfile}><div className="settings-layout"><section className="dashboard-section"><div className="section-heading"><div><p className="eyebrow">Your profile</p><h2>Investment preferences</h2></div></div><div className="settings-fields"><label className="field"><span>Full name</span><input value={profile.full_name} onChange={(event) => setProfile({ ...profile, full_name: event.target.value })} /></label><label className="field"><span>Risk comfort</span><select required value={profile.risk_tolerance} onChange={(event) => setProfile({ ...profile, risk_tolerance: event.target.value })}><option value="">Choose one</option><option value="conservative">Conservative</option><option value="moderate">Moderate</option><option value="aggressive">Aggressive</option></select></label><label className="field"><span>Investment horizon</span><select required value={profile.investment_horizon} onChange={(event) => setProfile({ ...profile, investment_horizon: event.target.value })}><option value="">Choose one</option><option value="short_term">Short term</option><option value="medium_term">Medium term</option><option value="long_term">Long term</option></select></label><div className="preference-group"><span className="preference-label">Sectors you follow</span><div className="preference-options">{sectors.map((sector) => <button type="button" className={profile.sector_preferences.includes(sector) ? 'preference-chip selected' : 'preference-chip'} onClick={() => setProfile({ ...profile, sector_preferences: sector === 'All Sectors' ? ['All Sectors'] : profile.sector_preferences.filter((item) => item !== 'All Sectors').includes(sector) ? profile.sector_preferences.filter((item) => item !== sector) : [...profile.sector_preferences.filter((item) => item !== 'All Sectors'), sector] })} key={sector}>{sector}</button>)}</div></div></div></section>
      <section className="dashboard-section"><div className="section-heading"><div><p className="eyebrow">Notification center</p><h2>What reaches you</h2></div></div><div className="preference-group"><span className="preference-label">Channels</span><div className="preference-options">{[['in_app', 'In-app'], ['email', 'Email'], ['push', 'Push']].map(([value, label]) => <button type="button" className={channels.includes(value) ? 'preference-chip selected' : 'preference-chip'} onClick={() => togglePreference(setChannels, value)} key={value}>{label}</button>)}</div></div><div className="preference-group"><span className="preference-label">Topics</span><div className="preference-options">{notificationCategories.map(([value, label]) => <button type="button" className={categories.includes(value) ? 'preference-chip selected' : 'preference-chip'} onClick={() => togglePreference(setCategories, value)} key={value}>{label}</button>)}</div></div><p className="settings-note">In-app alerts are always available in your Alerts workspace. Email and push delivery depend on your account configuration.</p></section></div>{message && <p className={message.includes('successfully') ? 'form-success' : 'form-error'}>{message}</p>}<button className="submit-button settings-save" disabled={saving}>{saving ? 'Saving…' : 'Save settings'}<span>→</span></button></form>
    <div className="settings-security-grid"><form className="dashboard-section security-card" onSubmit={changePassword}><div className="section-heading"><div><p className="eyebrow">Account security</p><h2>Change password</h2></div></div><label className="field"><span>Current password</span><input required type="password" value={password.current_password} onChange={(event) => setPassword({ ...password, current_password: event.target.value })} autoComplete="current-password" /></label><label className="field"><span>New password</span><input required minLength="8" type="password" value={password.new_password} onChange={(event) => setPassword({ ...password, new_password: event.target.value })} autoComplete="new-password" /></label><label className="field"><span>Confirm new password</span><input required minLength="8" type="password" value={password.confirm_password} onChange={(event) => setPassword({ ...password, confirm_password: event.target.value })} autoComplete="new-password" /></label>{passwordMessage && <p className={passwordMessage.includes('successfully') ? 'form-success' : 'form-error'}>{passwordMessage}</p>}<button className="secondary-submit" disabled={passwordSaving}>{passwordSaving ? 'Updating…' : 'Update password'}</button></form><section className="dashboard-section security-card"><div className="section-heading"><div><p className="eyebrow">Sessions</p><h2>Sign out everywhere</h2></div></div><p className="settings-note">Use this after signing in on a shared computer or if you suspect someone else has access.</p>{securityMessage && <p className="form-error">{securityMessage}</p>}<button type="button" className="danger-button" onClick={logoutAllDevices} disabled={securitySaving}>{securitySaving ? 'Checking…' : 'Sign out from all devices'}</button><small className="security-hint">Changing your password automatically revokes other refresh sessions.</small></section></div>
  </section><MobileNav active="settings" onDashboard={onBack} onMarket={onMarket} onNews={onNews} onAlerts={onAlerts} onRisk={onRisk} onSettings={() => {}} /></main>
      }


function RiskPage({ onBack, onMarket, onNews, onAlerts, onLogout }) {
  const [confidence, setConfidence] = useState('95')
  const [horizon, setHorizon] = useState('1D')
  const [scenario, setScenario] = useState('2008_crash')
  const [risk, setRisk] = useState(null)
  const [stress, setStress] = useState(null)
  const [job, setJob] = useState(null)
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState('')

  useEffect(() => {
    let active = true
    setLoading(true)
    Promise.allSettled([dashboardApi.getRiskVar(confidence, horizon), dashboardApi.getStressTest(scenario)])
      .then(([riskResult, stressResult]) => {
        if (!active) return
        setRisk(riskResult.status === 'fulfilled' ? riskResult.value : null)
        setStress(stressResult.status === 'fulfilled' ? stressResult.value : null)
        setMessage(riskResult.status === 'rejected' && stressResult.status === 'rejected' ? 'Risk analytics are temporarily unavailable.' : '')
      })
      .finally(() => active && setLoading(false))
    return () => { active = false }
  }, [confidence, horizon, scenario])

  useEffect(() => {
    if (!job?.job_id || job.status === 'completed' || job.status === 'failed') return undefined
    const timer = setTimeout(async () => {
      try {
        const result = await dashboardApi.getMonteCarlo(job.job_id)
        setJob(result)
      } catch (error) {
        setMessage(error.message)
        setJob((current) => ({ ...current, status: 'failed' }))
      }

    }, 2000)
    return () => clearTimeout(timer)
  }, [job])

  async function runSimulation() {
    setMessage('')
    setJob({ status: 'running' })
    try {
      setJob(await dashboardApi.startMonteCarlo({ num_simulations: 1000, horizon_days: 30 }))
    } catch (error) {
      setMessage(error.message)
      setJob(null)
    }
  }

  const formatPercent = (value) => value == null ? '—' : `${(Number(value) * 100).toFixed(2)}%`
  const riskLabel = risk?.var_value == null ? 'Not enough history' : Number(risk.var_value) < -0.05 ? 'Elevated risk' : Number(risk.var_value) < -0.02 ? 'Moderate risk' : 'Lower risk'

  return <main className="dashboard"><Header active="risk" onDashboard={onBack} onMarket={onMarket} onNews={onNews} onAlerts={onAlerts} onRisk={() => {}} onLogout={onLogout} />
    <section className="dashboard-content risk-page"><p className="eyebrow">Portfolio protection</p><h1>Risk analytics.</h1><p className="dashboard-lede">Understand downside before the market makes the decision for you.</p>
      <div className="risk-controls"><label className="field"><span>Confidence</span><select value={confidence} onChange={(event) => setConfidence(event.target.value)}><option value="90">90%</option><option value="95">95%</option><option value="99">99%</option></select></label><label className="field"><span>Horizon</span><select value={horizon} onChange={(event) => setHorizon(event.target.value)}><option>1D</option><option>1W</option><option>1M</option></select></label><label className="field"><span>Stress scenario</span><select value={scenario} onChange={(event) => setScenario(event.target.value)}><option value="2008_crash">2008 global crisis</option><option value="pkr_devaluation">PKR devaluation</option><option value="covid_crash">COVID crash</option><option value="interest_rate_hike">Interest rate hike</option></select></label></div>
      {message && <p className="form-error">{message}</p>}
      <div className="risk-summary-grid"><article className="risk-score-card"><span>Portfolio risk view</span><strong>{loading ? 'Loading…' : riskLabel}</strong><small>Historical simulation · {risk?.num_observations || 0} observations</small></article><article className="dashboard-section"><span className="card-label">Value at Risk</span><strong className="metric-value">{formatPercent(risk?.var_value)}</strong><small>{confidence}% confidence · {horizon}</small></article><article className="dashboard-section"><span className="card-label">Annualized volatility</span><strong className="metric-value">{formatPercent(risk?.annualized_volatility)}</strong><small>Portfolio price movement</small></article></div>
      <div className="risk-layout"><section className="dashboard-section"><div className="section-heading"><div><p className="eyebrow">Downside estimate</p><h2>VaR &amp; expected shortfall</h2></div></div><div className="risk-metric-list"><div><span>Value at Risk</span><strong>{formatPercent(risk?.var_value)}</strong></div><div><span>Conditional VaR</span><strong>{formatPercent(risk?.cvar_value)}</strong></div><div><span>Calculation method</span><strong>{risk?.method === 'historical_simulation' ? 'Historical simulation' : risk?.method || '—'}</strong></div></div><p className="risk-note">VaR estimates the potential portfolio loss at your selected confidence level. CVaR shows the average loss in the worst outcomes beyond that threshold.</p></section>
        <section className="dashboard-section"><div className="section-heading"><div><p className="eyebrow">Scenario planning</p><h2>{stress?.name || 'Stress test'}</h2></div></div><p className="risk-note">{stress?.description || 'Select a scenario to estimate portfolio impact.'}</p><div className="stress-grid"><div><span>Portfolio impact</span><strong className="negative">{formatPercent(stress?.portfolio_impact)}</strong></div><div><span>Stressed value</span><strong>{formatMoney(stress?.stressed_value)}</strong></div><div><span>Recovery estimate</span><strong>{stress?.recovery_days ? `${stress.recovery_days} days` : '—'}</strong></div></div></section></div>
      <section className="dashboard-section monte-carlo-card"><div className="section-heading"><div><p className="eyebrow">Forward-looking simulation</p><h2>Monte Carlo forecast</h2></div><button type="button" className="submit-button simulation-button" onClick={runSimulation} disabled={job?.status === 'pending' || job?.status === 'running'}>{job?.status === 'pending' || job?.status === 'running' ? 'Running…' : 'Run simulation'}<span>→</span></button></div><p className="risk-note">Run 1,000 simulated portfolio paths over the next 30 trading days using historical return behaviour.</p>{job?.status === 'completed' && <div className="simulation-results"><div><span>Probability of loss</span><strong>{formatPercent(job.stats?.prob_loss)}</strong></div><div><span>Expected return</span><strong>{formatPercent(job.stats?.mean_return)}</strong></div><div><span>Worst drawdown</span><strong>{formatPercent(job.stats?.max_drawdown)}</strong></div></div>}{job?.status === 'failed' && <p className="form-error">{job.error || 'Simulation failed.'}</p>}</section>
    </section><MobileNav active="risk" onDashboard={onBack} onMarket={onMarket} onNews={onNews} onAlerts={onAlerts} onRisk={() => {}} /></main>
}


function AlertsPage({ onBack, onMarket, onNews, onRisk, onLogout }) {
const [rules, setRules] = useState([])
const [alerts, setAlerts] = useState([])
const [form, setForm] = useState({ symbol: new URLSearchParams(window.location.search).get('symbol') || '', condition: 'price_above', threshold: '' })
const [message, setMessage] = useState('')

async function load() {
  const results = await Promise.allSettled([dashboardApi.getAlertRules(), dashboardApi.getAlerts()])
  setRules(results[0].status === 'fulfilled' ? results[0].value : [])
  setAlerts(results[1].status === 'fulfilled' ? results[1].value : [])
}

useEffect(() => { load() }, [])

async function createRule(event) {
  event.preventDefault()
  setMessage('')
  try {
    await dashboardApi.createAlertRule({
      stock_id: null,
      condition: `${form.condition}:${form.symbol.trim().toUpperCase()}`,
      threshold: Number(form.threshold),
    })
    setForm({ symbol: '', condition: 'price_above', threshold: '' })
    setMessage('Alert created successfully.')
    await load()
  } catch (error) {
    setMessage(error.message)
  }
}

async function toggleRule(rule) {
  try {
    await dashboardApi.updateAlertRule(rule.id, { is_active: !rule.is_active })
    await load()
  } catch (error) {
    setMessage(error.message)
  }
}

async function deleteRule(rule) {
  if (!window.confirm('Delete this alert?')) return
  try {
    await dashboardApi.deleteAlertRule(rule.id)
    await load()
  } catch (error) {
    setMessage(error.message)
  }
}

async function readAlert(alert) {
  if (alert.is_read) return
  try {
    await dashboardApi.markAlertRead(alert.id)
    setAlerts((current) => current.map((item) => item.id === alert.id ? { ...item, is_read: true } : item))
  } catch (error) {
    setMessage(error.message)
  }
}

return <main className="dashboard"><Header active="alerts" onDashboard={onBack} onMarket={onMarket} onNews={onNews} onAlerts={() => {}} onRisk={onRisk} onLogout={onLogout} />
  <section className="dashboard-content alerts-page"><p className="eyebrow">Stay informed</p><h1>Alerts.</h1><p className="dashboard-lede">Set simple triggers and keep important market updates close.</p>
    <div className="alerts-layout"><section className="dashboard-section"><div className="section-heading"><div><p className="eyebrow">Create a trigger</p><h2>Price alert</h2></div></div><form className="transaction-form" onSubmit={createRule}><label className="field"><span>Symbol</span><input required value={form.symbol} onChange={(event) => setForm({ ...form, symbol: event.target.value })} placeholder="e.g. HBL" /></label><div className="form-two"><label className="field"><span>Condition</span><select value={form.condition} onChange={(event) => setForm({ ...form, condition: event.target.value })}><option value="price_above">Price rises above</option><option value="price_below">Price falls below</option></select></label><label className="field"><span>Threshold</span><input required min="0" step="any" type="number" value={form.threshold} onChange={(event) => setForm({ ...form, threshold: event.target.value })} /></label></div>{message && <p className={message.includes('successfully') ? 'form-success' : 'form-error'}>{message}</p>}<button className="submit-button">Create alert <span>→</span></button></form></section>
      <section className="dashboard-section"><div className="section-heading"><div><p className="eyebrow">Your triggers</p><h2>Alert rules</h2></div><span className="section-meta">{rules.length} active setup{rules.length === 1 ? '' : 's'}</span></div><div className="alert-rule-list">{rules.map((rule) => { const [condition, symbol] = rule.condition.split(':'); return <div className="alert-rule" key={rule.id}><div><strong>{symbol || 'Market'}</strong><small>{condition === 'price_below' ? 'Price below' : 'Price above'} {formatNumber(rule.threshold)}</small></div><button type="button" className={rule.is_active ? 'toggle active' : 'toggle'} onClick={() => toggleRule(rule)}>{rule.is_active ? 'On' : 'Off'}</button><button type="button" className="icon-action" onClick={() => deleteRule(rule)} aria-label={`Delete ${symbol} alert`}>×</button></div>})}{!rules.length && <p className="data-state">No alerts yet. Create one for a stock you follow.</p>}</div></section></div>
    <section className="dashboard-section notification-list"><div className="section-heading"><div><p className="eyebrow">Updates</p><h2>Notifications</h2></div><span className="section-meta">{alerts.filter((alert) => !alert.is_read).length} unread</span></div>{alerts.map((alert) => <button type="button" className={alert.is_read ? 'notification-row read' : 'notification-row'} key={alert.id} onClick={() => readAlert(alert)}><span className="notification-dot" /><span><strong>{alert.title}</strong><small>{alert.message || 'Market update'} · {alert.created_at ? new Date(alert.created_at).toLocaleString() : 'Recently'}</small></span></button>)}{!alerts.length && <p className="data-state">You are all caught up.</p>}</section>
  </section><MobileNav active="alerts" onDashboard={onBack} onMarket={onMarket} onNews={onNews} onAlerts={() => {}} onRisk={onRisk} /></main>
}



function PortfolioPage({ onBack, onNews, onRisk, onLogout }) {
  const [data, setData] = useState({})
  const [period, setPeriod] = useState('1M')
  const [form, setForm] = useState({ symbol: '', transaction_type: 'BUY', quantity: '', price: '', fee: '0', transaction_date: new Date().toISOString().slice(0, 10) })
  const [editingId, setEditingId] = useState(null)
  const [message, setMessage] = useState('')
  const [saving, setSaving] = useState(false)

  async function load() {
    const results = await Promise.allSettled([
      dashboardApi.getPortfolio(), dashboardApi.getPortfolioPnl(), dashboardApi.getPortfolioAllocation(),
      dashboardApi.getPortfolioPerformance(period), dashboardApi.getTransactions(),
    ])
    const [portfolio, pnl, allocation, performance, transactions] = results.map((result) => result.status === 'fulfilled' ? result.value : null)
    setData({ portfolio, pnl, allocation, performance, transactions })
  }

  useEffect(() => { load() }, [period])

  async function saveTransaction(event) {
    event.preventDefault()
    setSaving(true)
    setMessage('')
    try {
      const payload = { quantity: Number(form.quantity), price: Number(form.price), fee: Number(form.fee), transaction_date: form.transaction_date }
      if (editingId) {
        await dashboardApi.updateTransaction(editingId, payload)
        setMessage('Transaction updated successfully.')
      } else {
        await dashboardApi.createTransaction({ ...form, symbol: form.symbol.toUpperCase(), quantity: payload.quantity, price: payload.price, fee: payload.fee })
        setMessage('Transaction added successfully.')
      }
      setEditingId(null)
      setForm((current) => ({ ...current, symbol: '', quantity: '', price: '' }))
      await load()
    } catch (error) {
      setMessage(error.message)
    } finally {
      setSaving(false)
    }

  }

  function editTransaction(transaction) {
    setEditingId(transaction.id)
    setForm({
      symbol: transaction.symbol,
      transaction_type: transaction.transaction_type,
      quantity: String(transaction.quantity),
      price: String(transaction.price),
      fee: String(transaction.fee || 0),
      transaction_date: transaction.transaction_date,
    })
    setMessage('')
  }

  async function removeTransaction(transaction) {
    if (!window.confirm(`Delete the ${transaction.transaction_type} transaction for ${transaction.symbol}?`)) return
    setMessage('')
    try {
      await dashboardApi.deleteTransaction(transaction.id)
      setMessage('Transaction deleted successfully.')
      await load()
    } catch (error) {
      setMessage(error.message)
    }
  }

  const summary = data.portfolio?.summary || data.pnl
  const performance = data.performance?.data || []
  const maxPerformance = Math.max(...performance.map((item) => Number(item.value)), 1)

  return <main className="dashboard"><Header active="portfolio" onDashboard={onBack} onMarket={onBack} onPortfolio={() => {}} onNews={onNews} onRisk={onRisk} onLogout={onLogout} />
    <section className="dashboard-content portfolio-page"><p className="eyebrow">Your investments</p><h1>Portfolio.</h1><p className="dashboard-lede">Track your holdings, performance, and every move in one place.</p>
      <div className="portfolio-summary-grid"><article className="portfolio-hero-card"><span>Total portfolio value</span><strong>{formatMoney(summary?.current_value)}</strong><Change value={summary?.total_pnl_percent} /><small>Updated from your latest holdings</small></article><article className="dashboard-section"><span className="card-label">Invested</span><strong className="metric-value">{formatMoney(summary?.total_invested)}</strong><small>Capital deployed</small></article><article className="dashboard-section"><span className="card-label">Today’s P&amp;L</span><strong className={`metric-value ${Number(summary?.today_pnl) >= 0 ? 'positive' : 'negative'}`}>{formatMoney(summary?.today_pnl)}</strong><small>Daily movement</small></article></div>
      <div className="portfolio-layout"><section className="dashboard-section holdings-section"><div className="section-heading"><div><p className="eyebrow">Your positions</p><h2>Holdings</h2></div><span className="section-meta">{data.portfolio?.holdings?.length || 0} stocks</span></div><div className="table-scroll"><table className="market-table"><thead><tr><th>Stock</th><th>Qty</th><th>Avg cost</th><th>Price</th><th>Value</th><th>P&amp;L</th></tr></thead><tbody>{(data.portfolio?.holdings || []).map((holding) => <tr key={holding.symbol}><td><strong>{holding.symbol}</strong><small>{holding.company_name || holding.sector || 'PSX holding'}</small></td><td>{formatNumber(holding.quantity, 0)}</td><td>{formatNumber(holding.average_cost)}</td><td>{formatNumber(holding.current_price)}</td><td>{formatMoney(holding.market_value)}</td><td><Change value={holding.unrealized_pnl_percent} /></td></tr>)}</tbody></table></div>{!data.portfolio?.holdings?.length && <p className="data-state">No holdings yet. Add your first transaction to start tracking your portfolio.</p>}</section>
        <section className="dashboard-section transaction-card"><div className="section-heading"><div><p className="eyebrow">Make a move</p><h2>{editingId ? 'Edit transaction' : 'Add transaction'}</h2></div></div><form onSubmit={saveTransaction} className="transaction-form"><label className="field"><span>Symbol</span><input required disabled={Boolean(editingId)} value={form.symbol} onChange={(event) => setForm({ ...form, symbol: event.target.value })} placeholder="e.g. HBL" /></label><div className="form-two"><label className="field"><span>Type</span><select disabled={Boolean(editingId)} value={form.transaction_type} onChange={(event) => setForm({ ...form, transaction_type: event.target.value })}><option>BUY</option><option>SELL</option></select></label><label className="field"><span>Date</span><input required type="date" value={form.transaction_date} onChange={(event) => setForm({ ...form, transaction_date: event.target.value })} /></label></div><div className="form-two"><label className="field"><span>Quantity</span><input required min="0.0001" step="any" type="number" value={form.quantity} onChange={(event) => setForm({ ...form, quantity: event.target.value })} /></label><label className="field"><span>Price</span><input required min="0" step="any" type="number" value={form.price} onChange={(event) => setForm({ ...form, price: event.target.value })} /></label></div>{message && <p className={message.includes('successfully') ? 'form-success' : 'form-error'}>{message}</p>}<div className="transaction-actions"><button className="submit-button" disabled={saving}>{saving ? 'Saving…' : editingId ? 'Save changes' : 'Add transaction'}<span>→</span></button>{editingId && <button type="button" className="cancel-button" onClick={() => { setEditingId(null); setMessage(''); setForm((current) => ({ ...current, symbol: '', quantity: '', price: '' })) }}>Cancel</button>}</div></form></section></div>
      <div className="portfolio-layout lower"><section className="dashboard-section"><div className="section-heading"><div><p className="eyebrow">Performance</p><h2>Portfolio value</h2></div><div className="range-tabs">{['1W', '1M', '3M', '1Y', 'ALL'].map((item) => <button type="button" className={period === item ? 'active' : ''} onClick={() => setPeriod(item)} key={item}>{item}</button>)}</div></div><div className="performance-bars">{performance.map((item) => <div key={item.date} title={`${item.date}: ${formatMoney(item.value)}`} style={{ height: `${(Number(item.value) / maxPerformance) * 100}%` }} />)}</div></section><section className="dashboard-section"><div className="section-heading"><div><p className="eyebrow">Allocation</p><h2>By sector</h2></div></div><div className="sector-list">{(data.allocation?.by_sector || []).map((item) => <div className="sector-row" key={item.sector}><span>{item.sector}<small>{formatMoney(item.market_value)}</small></span><Change value={item.percentage} /></div>)}</div></section></div>
      <section className="dashboard-section transaction-history"><div className="section-heading"><div><p className="eyebrow">Activity</p><h2>Transaction history</h2></div></div><div className="table-scroll"><table className="market-table"><thead><tr><th>Date</th><th>Stock</th><th>Type</th><th>Quantity</th><th>Price</th><th>Fee</th><th>Actions</th></tr></thead><tbody>{(data.transactions?.items || []).map((transaction) => <tr key={transaction.id}><td>{transaction.transaction_date}</td><td><strong>{transaction.symbol}</strong></td><td><span className={transaction.transaction_type === 'BUY' ? 'positive' : 'negative'}>{transaction.transaction_type}</span></td><td>{formatNumber(transaction.quantity, 0)}</td><td>{formatNumber(transaction.price)}</td><td>{formatNumber(transaction.fee)}</td><td><div className="row-actions"><button type="button" onClick={() => editTransaction(transaction)}>Edit</button><button type="button" onClick={() => removeTransaction(transaction)}>Delete</button></div></td></tr>)}</tbody></table></div>{!data.transactions?.items?.length && <p className="data-state">No transactions recorded yet.</p>}</section>
    </section><MobileNav active="portfolio" onDashboard={onBack} onMarket={onBack} onPortfolio={() => {}} onNews={onNews} onRisk={onRisk} /></main>
}

function AdminCommunityPage({ onBack, onMarket, onPortfolio, onNews, onAssistant, onCommunity, onAlerts, onRisk, onSettings, onLogout }) {
  const [reports, setReports] = useState([])
  const [actions, setActions] = useState([])
  const [status, setStatus] = useState('PENDING')
  const [selectedPost, setSelectedPost] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [reportResult, actionResult] = await Promise.all([
        adminCommunityApi.getReports({ status, limit: 100 }),
        adminCommunityApi.getActions({ limit: 50 }),
      ])
      setReports(reportResult?.reports || [])
      setActions(actionResult?.actions || [])
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }, [status])

  useEffect(() => { load() }, [load])

  async function updateReport(report, nextStatus) {
    setBusy(report.id)
    setMessage('')
    try {
      await adminCommunityApi.updateReportStatus(report.id, nextStatus)
      setMessage(`Report marked ${nextStatus.toLowerCase()}.`)
      await load()
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setBusy('')
    }
  }

  async function moderatePost(report, action) {
    if (!report.post_id) return
    if (!window.confirm(`${action === 'restore' ? 'Restore' : 'Remove'} this post?`)) return
    setBusy(report.post_id)
    setMessage('')
    try {
      if (action === 'restore') await adminCommunityApi.restorePost(report.post_id)
      else if (action === 'remove') await adminCommunityApi.removePost(report.post_id)
      else await adminCommunityApi.deletePost(report.post_id)
      setMessage('Moderation action completed.')
      await load()
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setBusy('')
    }
  }

  async function deleteComment(report) {
    if (!report.comment_id || !window.confirm('Delete this comment?')) return
    setBusy(report.comment_id)
    try {
      await adminCommunityApi.deleteComment(report.comment_id)
      setMessage('Comment deleted.')
      await load()
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setBusy('')
    }
  }

  async function inspectPost(postId) {
    setBusy(postId)
    try {
      setSelectedPost(await adminCommunityApi.getPost(postId))
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setBusy('')
    }
  }

  return <main className="dashboard">
    <Header active="admin-community" onDashboard={onBack} onMarket={onMarket} onPortfolio={onPortfolio} onNews={onNews} onAssistant={onAssistant} onCommunity={onCommunity} onAdminCommunity={() => {}} onAlerts={onAlerts} onRisk={onRisk} onSettings={onSettings} onLogout={onLogout} />
    <section className="dashboard-content admin-community-page">
      <div className="admin-community-heading"><div><p className="eyebrow">Moderation workspace</p><h1>Admin Community.</h1><p className="dashboard-lede">Review reports, protect discussion quality, and keep a clear audit trail of every action.</p></div><div className="admin-status-card"><strong>{reports.length}</strong><span>{status.toLowerCase()} reports</span></div></div>
      {error && <p className="form-error" role="alert">{error}</p>}
      {message && <p className="form-success" role="status">{message}</p>}
      <div className="admin-community-layout">
        <section className="dashboard-section">
          <div className="section-heading"><div><p className="eyebrow">Reports queue</p><h2>Reported content</h2></div><select className="admin-status-filter" value={status} onChange={(event) => setStatus(event.target.value)}><option value="PENDING">Pending</option><option value="REVIEWED">Reviewed</option><option value="DISMISSED">Dismissed</option></select></div>
          {loading && <p className="data-state">Loading moderation queue…</p>}
          {!loading && !error && reports.length === 0 && <p className="data-state">No {status.toLowerCase()} reports.</p>}
          <div className="admin-report-list">{reports.map((report) => <article className="admin-report" key={report.id}><div className="admin-report-top"><span className="report-reason">{report.reason.replace('_', ' ')}</span><time>{new Date(report.created_at).toLocaleString()}</time></div><p className="admin-report-content">{report.post_content || report.comment_content || 'Content unavailable'}</p><div className="admin-report-meta">Reported by <strong>{report.reporter_username}</strong>{report.post_author_username && <> · Author <strong>{report.post_author_username}</strong></>}{report.stock_symbol && <span className="stock-pill">{report.stock_symbol}</span>}</div><div className="admin-report-actions">{report.post_id && <><button type="button" onClick={() => inspectPost(report.post_id)} disabled={busy === report.post_id}>Review post</button><button type="button" onClick={() => moderatePost(report, 'remove')} disabled={busy === report.post_id}>Remove</button><button type="button" onClick={() => moderatePost(report, 'delete')} disabled={busy === report.post_id}>Delete</button></>}{report.comment_id && <button type="button" onClick={() => deleteComment(report)} disabled={busy === report.comment_id}>Delete comment</button>}<button type="button" onClick={() => updateReport(report, 'DISMISSED')} disabled={busy === report.id}>Dismiss</button><button type="button" onClick={() => updateReport(report, 'REVIEWED')} disabled={busy === report.id}>Mark reviewed</button></div></article>)}</div>
        </section>
        <aside className="admin-community-sidebar">
          {selectedPost && <section className="dashboard-section admin-post-review"><div className="section-heading"><div><p className="eyebrow">Post review</p><h2>{selectedPost.status.replace('_', ' ')}</h2></div><button type="button" className="close-button" onClick={() => setSelectedPost(null)}>×</button></div><p>{selectedPost.content}</p><small>{selectedPost.author_username || selectedPost.author_full_name || 'Unknown author'} · {selectedPost.like_count} likes · {selectedPost.comment_count} comments</small><div className="admin-review-actions">{selectedPost.status === 'TEMPORARILY_HIDDEN' && <button type="button" onClick={() => moderatePost({ post_id: selectedPost.id }, 'restore')}>Restore</button>}<button type="button" onClick={() => moderatePost({ post_id: selectedPost.id }, 'remove')}>Remove</button><button type="button" onClick={() => moderatePost({ post_id: selectedPost.id }, 'delete')}>Delete</button></div></section>}
          <section className="dashboard-section"><p className="eyebrow">Audit trail</p><h2>Recent actions</h2><div className="admin-actions-list">{actions.length === 0 && <p className="data-state">No moderation actions yet.</p>}{actions.map((action) => <div className="admin-action-row" key={action.id}><strong>{action.action.replaceAll('_', ' ')}</strong><small>{action.moderator_username || 'Admin'} · {new Date(action.created_at).toLocaleString()}</small></div>)}</div></section>
        </aside>
      </div>
    </section>
    <MobileNav active="community" onDashboard={onBack} onMarket={onMarket} onPortfolio={onPortfolio} onNews={onNews} onAssistant={onAssistant} onCommunity={onCommunity} onAlerts={onAlerts} onRisk={onRisk} onSettings={onSettings} />
  </main>
}

function WatchlistPage({ onBack, onMarket, onPortfolio, onNews, onAssistant, onCommunity, onAlerts, onRisk, onSettings, onLogout, onStock }) {
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
    <Header active="watchlist" onDashboard={onBack} onMarket={onMarket} onPortfolio={onPortfolio} onNews={onNews} onAssistant={onAssistant} onCommunity={onCommunity} onWatchlist={() => {}} onAlerts={onAlerts} onRisk={onRisk} onSettings={onSettings} onLogout={onLogout} />
    <section className="dashboard-content watchlist-page">
      <div className="watchlist-heading"><div><p className="eyebrow">Your market shortlist</p><h1>Watchlist & compare.</h1><p className="dashboard-lede">Keep the stocks you follow close and compare their signals before making a decision.</p></div><form className="watchlist-add" onSubmit={addSymbol}><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Add symbol e.g. HBL" aria-label="Add stock symbol" /><button type="submit">Add</button></form></div>
      {!symbols.length && <section className="dashboard-section empty-watchlist"><h2>Your watchlist is empty.</h2><p>Add a PSX symbol above to start tracking it.</p></section>}
      {loading && symbols.length > 0 && <p className="data-state">Loading watchlist…</p>}
      <div className="watchlist-grid">{stocks.map((stock) => {
        const overview = stock.overview.status === 'fulfilled' ? stock.overview.value : null
        const fundamentals = stock.fundamentals.status === 'fulfilled' ? stock.fundamentals.value : null
        const technical = stock.technical.status === 'fulfilled' ? stock.technical.value : null
        const forecast = stock.forecast.status === 'fulfilled' ? stock.forecast.value : null
        return <article className="dashboard-section watch-card" key={stock.symbol}><div className="watch-card-heading"><button type="button" onClick={() => onStock(stock.symbol)}><strong>{stock.symbol}</strong><span>{overview?.name || 'Stock details'}</span></button><button type="button" className="remove-watch" onClick={() => removeSymbol(stock.symbol)} aria-label={`Remove ${stock.symbol}`}>×</button></div><div className="watch-price"><strong>{formatNumber(overview?.ltp)}</strong><Change value={overview?.change_pct} /></div><div className="watch-metrics"><div><span>Signal</span><strong>{technical?.overall_signal || '—'}</strong></div><div><span>Forecast</span><strong>{forecast?.signal_rating || forecast?.direction || '—'}</strong></div><div><span>P/E</span><strong>{formatNumber(overview?.pe_ratio || fundamentals?.ratios?.pe_ratio)}</strong></div></div></article>
      })}</div>
      {stocks.length > 1 && <section className="dashboard-section comparison-section"><div className="section-heading"><div><p className="eyebrow">Side by side</p><h2>Stock comparison</h2></div><span className="section-meta">{stocks.length} stocks</span></div><div className="table-scroll"><table className="market-table"><thead><tr><th>Symbol</th><th>Price</th><th>Change</th><th>Technical</th><th>Forecast</th><th>P/E</th></tr></thead><tbody>{stocks.map((stock) => { const overview = stock.overview.status === 'fulfilled' ? stock.overview.value : null; const fundamentals = stock.fundamentals.status === 'fulfilled' ? stock.fundamentals.value : null; const technical = stock.technical.status === 'fulfilled' ? stock.technical.value : null; const forecast = stock.forecast.status === 'fulfilled' ? stock.forecast.value : null; return <tr key={`compare-${stock.symbol}`}><td><button type="button" className="table-symbol-button" onClick={() => onStock(stock.symbol)}>{stock.symbol}</button></td><td>{formatNumber(overview?.ltp)}</td><td><Change value={overview?.change_pct} /></td><td>{technical?.overall_signal || '—'}</td><td>{forecast?.signal_rating || forecast?.direction || '—'}</td><td>{formatNumber(overview?.pe_ratio || fundamentals?.ratios?.pe_ratio)}</td></tr> })}</tbody></table></div></section>}
    </section>
    <MobileNav active="watchlist" onDashboard={onBack} onMarket={onMarket} onPortfolio={onPortfolio} onNews={onNews} onAssistant={onAssistant} onWatchlist={() => {}} onCommunity={onCommunity} onAlerts={onAlerts} onRisk={onRisk} onSettings={onSettings} />
  </main>
}

function RecommendationsPage({ onBack, onMarket, onPortfolio, onNews, onAssistant, onCommunity, onWatchlist, onAlerts, onRisk, onSettings, onLogout, onStock }) {
  const [recommendations, setRecommendations] = useState([])
  const [weights, setWeights] = useState({ gru_weight: 0.4, technical_weight: 0.35, fundamental_weight: 0.25 })
  const [riskProfile, setRiskProfile] = useState('moderate')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [list, currentWeights] = await Promise.all([dashboardApi.getRecommendationList({ risk_profile: riskProfile, limit: 50 }), dashboardApi.getEngineWeights()])
      setRecommendations(list.recommendations || [])
      setWeights(currentWeights)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }, [riskProfile])

  useEffect(() => { load() }, [load])

  async function saveWeights(event) {
    event.preventDefault()
    const total = Object.values(weights).reduce((sum, value) => sum + Number(value), 0)
    if (Math.abs(total - 1) > 0.01) {
      setError('Engine weights must add up to 1.00.')
      return
    }
    setSaving(true)
    setMessage('')
    setError('')
    try {
      const saved = await dashboardApi.setEngineWeights(Object.fromEntries(Object.entries(weights).map(([key, value]) => [key, Number(value)])))
      setWeights(saved)
      setMessage('Recommendation engine weights updated.')
      await load()
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setSaving(false)
    }
  }

  return <main className="dashboard">
    <Header active="recommendations" onDashboard={onBack} onMarket={onMarket} onPortfolio={onPortfolio} onNews={onNews} onAssistant={onAssistant} onCommunity={onCommunity} onWatchlist={onWatchlist} onAlerts={onAlerts} onRisk={onRisk} onSettings={onSettings} onLogout={onLogout} />
    <section className="dashboard-content recommendations-page">
      <div className="recommendations-heading"><div><p className="eyebrow">Quantitative signals</p><h1>Recommendations.</h1><p className="dashboard-lede">Ranked buy, hold, and sell signals built from model, technical, and fundamental evidence.</p></div><select value={riskProfile} onChange={(event) => setRiskProfile(event.target.value)}><option value="conservative">Conservative</option><option value="moderate">Moderate</option><option value="aggressive">Aggressive</option></select></div>
      {error && <p className="form-error" role="alert">{error}</p>}
      {message && <p className="form-success" role="status">{message}</p>}
      <div className="recommendations-layout"><section className="dashboard-section"><div className="section-heading"><div><p className="eyebrow">Market ranking</p><h2>Latest signals</h2></div><span className="section-meta">{recommendations.length} stocks</span></div>{loading && <p className="data-state">Loading recommendations…</p>}{!loading && !recommendations.length && <p className="data-state">Recommendations are currently unavailable.</p>}<div className="recommendation-cards">{recommendations.map((item) => <article className="recommendation-card" key={item.symbol}><button type="button" className="recommendation-symbol" onClick={() => onStock(item.symbol)}><strong>{item.symbol}</strong><small>{item.summary}</small></button><span className={`signal ${item.signal.toLowerCase()}`}>{item.signal}</span><div className="recommendation-metrics"><span>Confidence <b>{Math.round(item.confidence * 100)}%</b></span><span>Score <b>{formatNumber(item.composite_score)}</b></span><span>Target <b>{formatNumber(item.target_price)}</b></span><span>Stop <b>{formatNumber(item.stop_loss)}</b></span></div></article>)}</div></section><form className="dashboard-section engine-weights-card" onSubmit={saveWeights}><div className="section-heading"><div><p className="eyebrow">Signal model</p><h2>Engine weights</h2></div></div><p className="sidebar-copy">Tune how the recommendation engine balances each source. Weights must total 100%.</p>{[['gru_weight', 'ML model'], ['technical_weight', 'Technical'], ['fundamental_weight', 'Fundamental']].map(([key, label]) => <label className="weight-control" key={key}><span>{label}<b>{Math.round(Number(weights[key]) * 100)}%</b></span><input type="range" min="0" max="1" step="0.01" value={weights[key]} onChange={(event) => setWeights({ ...weights, [key]: event.target.value })} /></label>)}<div className="weight-total">Total <strong>{Math.round(Object.values(weights).reduce((sum, value) => sum + Number(value), 0) * 100)}%</strong></div><button className="submit-button" disabled={saving}>{saving ? 'Saving…' : 'Save weights'}<span>→</span></button></form></div>
    </section>
    <MobileNav active="market" onDashboard={onBack} onMarket={onMarket} onPortfolio={onPortfolio} onNews={onNews} onAssistant={onAssistant} onWatchlist={onWatchlist} onCommunity={onCommunity} onAlerts={onAlerts} onRisk={onRisk} onSettings={onSettings} />
  </main>
}

function ShariahPage({ onBack, onMarket, onPortfolio, onNews, onAlerts, onRisk, onSettings, onLogout, onStock }) {
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
    <Header active="shariah" onDashboard={onBack} onMarket={onMarket} onPortfolio={onPortfolio} onNews={onNews} onAlerts={onAlerts} onRisk={onRisk} onSettings={onSettings} onLogout={onLogout} />
    <section className="dashboard-content shariah-page">
      <div className="recommendations-heading"><div><p className="eyebrow">Ethical investing</p><h1>Shariah screening.</h1><p className="dashboard-lede">AAOIFI and KMI-30 aligned compliance checks, criteria, and dividend purification estimates.</p></div><form className="stock-search-inline" onSubmit={(event) => { event.preventDefault(); loadSymbol() }}><input value={symbol} onChange={(event) => setSymbol(event.target.value)} aria-label="Stock symbol" /><button type="submit">Check</button></form></div>
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="recommendations-layout"><section className="dashboard-section"><div className="section-heading"><div><p className="eyebrow">Screening result</p><h2>{screening?.symbol || symbol}</h2></div><span className={screening?.is_shariah_compliant ? 'signal buy' : 'signal sell'}>{screening ? screening.is_shariah_compliant ? 'Compliant' : 'Not compliant' : loading ? 'Loading…' : 'Unavailable'}</span></div><div className="fact-grid"><div><span>Method</span><strong>{screening?.screening_method || '—'}</strong></div><div><span>Overall score</span><strong>{formatNumber(screening?.overall_score)}</strong></div><div><span>Purification rate</span><strong>{screening?.purification_rate == null ? '—' : `${formatNumber(screening.purification_rate * 100, 2)}%`}</strong></div><div><span>Sector</span><strong>{screening?.sector || '—'}</strong></div></div><p className="signal-message">{screening?.compliance_summary || 'Run a screening to view the compliance result.'}</p></section>
        <section className="dashboard-section"><div className="section-heading"><div><p className="eyebrow">Detailed criteria</p><h2>AAOIFI checks</h2></div></div><div className="criteria-list">{(criteria?.criteria || []).map((item) => <div className="indicator-row" key={item.name}><span>{item.name}<small>{item.description || `Threshold ${item.threshold}`}</small></span><strong className={item.passed ? 'positive' : 'negative'}>{item.passed ? 'Pass' : 'Fail'}{item.value != null ? ` · ${formatNumber(item.value)}` : ''}</strong></div>)}</div>{!criteria?.criteria?.length && <p className="data-state">Criteria are unavailable for this symbol.</p>}</section>
        <form className="dashboard-section" onSubmit={calculatePurification}><div className="section-heading"><div><p className="eyebrow">Dividend purification</p><h2>Calculate amount</h2></div></div><div className="form-two"><label className="field"><span>Holding quantity</span><input type="number" min="1" required value={holdingQty} onChange={(event) => setHoldingQty(event.target.value)} /></label><label className="field"><span>Holding value (PKR)</span><input type="number" min="0.01" step="any" required value={holdingValue} onChange={(event) => setHoldingValue(event.target.value)} /></label></div><button className="submit-button">Calculate purification <span>→</span></button>{purification && <div className="purification-result"><strong>PKR {formatNumber(purification.purification_amount, 2)}</strong><span>{formatNumber(purification.purification_rate * 100, 2)}% · {purification.notes}</span></div>}</form>
      </div>
      <section className="dashboard-section"><div className="section-heading"><div><p className="eyebrow">Shariah universe</p><h2>KMI-30 constituents</h2></div><span className="section-meta">{kmi30?.total_constituents || kmi30?.constituents?.length || 0} stocks</span></div><div className="symbol-chips">{(kmi30?.constituents || []).map((item) => <button type="button" key={item.symbol} onClick={() => { setSymbol(item.symbol); loadSymbol(item.symbol) }}>{item.symbol}</button>)}</div>{!kmi30?.constituents?.length && <p className="data-state">KMI-30 constituents are currently unavailable.</p>}</section>
    </section>
  </main>
}

function HealthPage({ onBack, onMarket, onAlerts, onRisk, onSettings, onLogout }) {
  const [probes, setProbes] = useState({ liveness: null, readiness: null })
  const [loading, setLoading] = useState(true)
  const [lastChecked, setLastChecked] = useState(null)

  const loadHealth = useCallback(async () => {
    setLoading(true)
    const [liveness, readiness] = await Promise.allSettled([
      dashboardApi.getHealth(),
      dashboardApi.getReadiness(),
    ])
    setProbes({
      liveness: liveness.status === 'fulfilled' ? liveness.value : { status: 'unavailable', error: liveness.reason?.message },
      readiness: readiness.status === 'fulfilled' ? readiness.value : { status: 'unavailable', error: readiness.reason?.message },
    })
    setLastChecked(new Date())
    setLoading(false)
  }, [])

  useEffect(() => { loadHealth() }, [loadHealth])

  const readinessServices = probes.readiness?.services || {}
  const readinessHealthy = probes.readiness?.status === 'healthy'
  const livenessHealthy = probes.liveness?.status === 'ok'
  const statusLabel = (healthy) => healthy ? 'Operational' : 'Needs attention'

  return <main className="dashboard">
    <Header active="health" onDashboard={onBack} onMarket={onMarket} onAlerts={onAlerts} onRisk={onRisk} onSettings={onSettings} onLogout={onLogout} />
    <section className="dashboard-content health-page">
      <div className="dashboard-topline">
        <div><p className="eyebrow">Platform diagnostics</p><h1>System health.</h1><p className="dashboard-lede">A live view of the API process and the services required to power your workspace.</p></div>
        <button type="button" className="health-refresh-button" onClick={loadHealth} disabled={loading}>{loading ? 'Checking…' : 'Refresh checks'}</button>
      </div>
      <p className="health-last-checked">{lastChecked ? `Last checked ${lastChecked.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}` : 'Checking services…'}</p>
      <div className="health-summary-grid">
        <section className={`dashboard-section health-card ${livenessHealthy ? 'healthy' : 'unhealthy'}`}>
          <div className="health-card-heading"><span className="health-icon">●</span><span className="health-status">{statusLabel(livenessHealthy)}</span></div>
          <p className="eyebrow">Liveness</p><h2>API process</h2>
          <p>{livenessHealthy ? 'The backend is running and responding to HTTP requests.' : probes.liveness?.error || 'The API process did not respond successfully.'}</p>
          {probes.liveness?.http_status && <small>HTTP {probes.liveness.http_status}</small>}
        </section>
        <section className={`dashboard-section health-card ${readinessHealthy ? 'healthy' : 'unhealthy'}`}>
          <div className="health-card-heading"><span className="health-icon">●</span><span className="health-status">{statusLabel(readinessHealthy)}</span></div>
          <p className="eyebrow">Readiness</p><h2>Dependencies</h2>
          <p>{readinessHealthy ? 'All required services are ready to serve requests.' : probes.readiness?.error || 'One or more required services need attention.'}</p>
          {probes.readiness?.http_status && <small>HTTP {probes.readiness.http_status}</small>}
        </section>
      </div>
      <section className="dashboard-section health-services">
        <div className="section-heading"><div><p className="eyebrow">Dependency checks</p><h2>Service availability</h2></div><span className="section-meta">{Object.values(readinessServices).filter((value) => value === 'ready').length}/{Object.keys(readinessServices).length || 0} ready</span></div>
        {Object.keys(readinessServices).length === 0
          ? <p className="data-state">Dependency details are unavailable until the readiness probe responds.</p>
          : <div className="health-service-list">{Object.entries(readinessServices).map(([service, status]) => <div className="health-service-row" key={service}><span>{service.replaceAll('_', ' ')}</span><strong className={status === 'ready' ? 'positive' : 'negative'}><i />{status}</strong></div>)}</div>}
      </section>
    </section>
  </main>
}

function getRoute() {
  const path = window.location.pathname
  if (path === '/market') return 'market'
  if (path === '/news') return 'news'
  if (path === '/shariah') return 'shariah'
  if (path === '/assistant') return 'assistant'
  if (path === '/community') return 'community'
  if (path === '/watchlist') return 'watchlist'
  if (path === '/recommendations') return 'recommendations'
  if (path === '/admin/community') return 'admin-community'
  if (path === '/health') return 'health'
  if (path.startsWith('/stocks/')) return 'stock'
  if (path === '/portfolio') return 'portfolio'
  if (path === '/alerts') return 'alerts'
  if (path === '/risk') return 'risk'
  if (path === '/settings') return 'settings'
  if (path === '/forgot-password') return 'forgot'
  if (path === '/reset-password') return 'reset'
  return 'auth'
}

function App() {
  const [route, setRoute] = useState(getRoute)
  const [user, setUser] = useState(getStoredUser)
  const [needsSetup, setNeedsSetup] = useState(false)
  const [isLoading, setIsLoading] = useState(Boolean(getStoredUser()))
  const [mode, setMode] = useState('login')
  const resetToken = new URLSearchParams(window.location.search).get('token')
  const stockSymbol = window.location.pathname.split('/')[2]?.toUpperCase()

  useEffect(() => {
    const onPopState = () => setRoute(getRoute())
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
      .catch(() => {
        clearSession()
        setUser(null)
      })
      .finally(() => setIsLoading(false))
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  function navigate(path) {
    window.history.pushState({}, '', path)
    setRoute(getRoute())
  }

  function authenticated(nextUser, signup) {
    setUser(nextUser)
    setNeedsSetup(signup)
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
  }

  if (isLoading) return <div className="loading-screen">Loading your secure workspace…</div>
  if (route === 'forgot' || route === 'reset') return <PasswordPage resetToken={route === 'reset' ? resetToken : null} onBack={() => navigate('/')} />
  if (!user) return <AuthPage mode={mode} onModeChange={setMode} onAuthenticated={authenticated} onForgot={() => navigate('/forgot-password')} />
  if (needsSetup) return <ProfileSetup user={user} onComplete={(profile) => { setUser(profile); setNeedsSetup(false) }} />
  const navigation = {
    dashboard: () => navigate('/'),
    market: () => navigate('/market'),
    portfolio: () => navigate('/portfolio'),
    watchlist: () => navigate('/watchlist'),
    recommendations: () => navigate('/recommendations'),
    news: () => navigate('/news'),
    assistant: () => navigate('/assistant'),
    community: () => navigate('/community'),
    adminCommunity: () => navigate('/admin/community'),
    alerts: () => navigate('/alerts'),
    risk: () => navigate('/risk'),
    shariah: () => navigate('/shariah'),
    settings: () => navigate('/settings'),
    health: () => navigate('/health'),
  }
  if (route === 'market') return <MarketOverview onBack={navigation.dashboard} onPortfolio={navigation.portfolio} onNews={navigation.news} onWatchlist={navigation.watchlist} onAlerts={navigation.alerts} onRisk={navigation.risk} onSettings={navigation.settings} onLogout={logout} />
  if (route === 'news') return <NewsPage onBack={navigation.dashboard} onMarket={navigation.market} onPortfolio={navigation.portfolio} onAlerts={navigation.alerts} onRisk={navigation.risk} onSettings={navigation.settings} onLogout={logout} />
  if (route === 'assistant') return <AssistantPage onBack={navigation.dashboard} onMarket={navigation.market} onPortfolio={navigation.portfolio} onNews={navigation.news} onAlerts={navigation.alerts} onRisk={navigation.risk} onSettings={navigation.settings} onLogout={logout} />
  if (route === 'community') return <CommunityPage onBack={navigation.dashboard} onMarket={navigation.market} onPortfolio={navigation.portfolio} onNews={navigation.news} onAssistant={navigation.assistant} onCommunity={navigation.community} onAlerts={navigation.alerts} onRisk={navigation.risk} onSettings={navigation.settings} onLogout={logout} />
  if (route === 'admin-community') return <AdminCommunityPage onBack={navigation.dashboard} onMarket={navigation.market} onPortfolio={navigation.portfolio} onNews={navigation.news} onAssistant={navigation.assistant} onCommunity={navigation.community} onAlerts={navigation.alerts} onRisk={navigation.risk} onSettings={navigation.settings} onLogout={logout} />
  if (route === 'health') return <HealthPage onBack={navigation.dashboard} onMarket={navigation.market} onAlerts={navigation.alerts} onRisk={navigation.risk} onSettings={navigation.settings} onLogout={logout} />
  if (route === 'stock' && stockSymbol) return <StockDetail symbol={stockSymbol} onBack={navigation.market} onPortfolio={navigation.portfolio} onNews={navigation.news} onWatchlist={navigation.watchlist} onAlerts={navigation.alerts} onRisk={navigation.risk} onSettings={navigation.settings} onLogout={logout} onStock={(symbol) => navigate(`/stocks/${symbol}`)} onAlert={(symbol) => navigate(`/alerts?symbol=${encodeURIComponent(symbol)}`)} />
  if (route === 'watchlist') return <WatchlistPage onBack={navigation.dashboard} onMarket={navigation.market} onPortfolio={navigation.portfolio} onNews={navigation.news} onAssistant={navigation.assistant} onCommunity={navigation.watchlist} onAlerts={navigation.alerts} onRisk={navigation.risk} onSettings={navigation.settings} onLogout={logout} onStock={(symbol) => navigate(`/stocks/${symbol}`)} />
  if (route === 'recommendations') return <RecommendationsPage onBack={navigation.dashboard} onMarket={navigation.market} onPortfolio={navigation.portfolio} onNews={navigation.news} onAssistant={navigation.assistant} onCommunity={navigation.community} onWatchlist={navigation.watchlist} onAlerts={navigation.alerts} onRisk={navigation.risk} onSettings={navigation.settings} onLogout={logout} onStock={(symbol) => navigate(`/stocks/${symbol}`)} />
  if (route === 'shariah') return <ShariahPage onBack={navigation.dashboard} onMarket={navigation.market} onPortfolio={navigation.portfolio} onNews={navigation.news} onAlerts={navigation.alerts} onRisk={navigation.risk} onSettings={navigation.settings} onLogout={logout} onStock={(symbol) => navigate(`/stocks/${symbol}`)} />
  if (route === 'portfolio') return <PortfolioPage onBack={navigation.dashboard} onNews={navigation.news} onRisk={navigation.risk} onLogout={logout} />
  if (route === 'alerts') return <AlertsPage onBack={navigation.dashboard} onMarket={navigation.market} onNews={navigation.news} onRisk={navigation.risk} onLogout={logout} />
  if (route === 'risk') return <RiskPage onBack={navigation.dashboard} onMarket={navigation.market} onNews={navigation.news} onAlerts={navigation.alerts} onLogout={logout} />
  if (route === 'settings') return <SettingsPage onBack={navigation.dashboard} onMarket={navigation.market} onNews={navigation.news} onAlerts={navigation.alerts} onRisk={navigation.risk} onLogout={logout} />
  return <Dashboard user={user} onLogout={logout} onMarket={navigation.market} onPortfolio={navigation.portfolio} onNews={navigation.news} onAlerts={navigation.alerts} onRisk={navigation.risk} onSettings={navigation.settings} onStock={(symbol) => navigate(`/stocks/${symbol}`)} />
}

export default App
