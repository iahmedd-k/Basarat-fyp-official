import { clearSession, refreshSession } from './auth'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'
const REQUEST_TIMEOUT_MS = 15000

async function fetchWithTimeout(url, options) {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
  try {
    return await fetch(url, { ...options, signal: controller.signal })
  } finally {
    clearTimeout(timeout)
  }
}

async function request(endpoint, options = {}, allowRefresh = true) {
  const token = localStorage.getItem('basarat_access_token')
  const response = await fetchWithTimeout(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
      ...options.headers,
    },
  })

  if (response.status === 401 && allowRefresh) {
    try {
      const session = await refreshSession()
      return requestWithToken(endpoint, session.access_token, options)
    } catch {
      clearSession()
    }
  }

  if (!response.ok) throw new Error(`Dashboard request failed (${response.status})`)
  return response.status === 204 ? null : response.json()
}

async function requestWithToken(endpoint, token, options = {}) {
  const response = await fetchWithTimeout(`${API_BASE}${endpoint}`, {
    ...options,
    headers: { ...options.headers, Authorization: `Bearer ${token}` },
  })
  if (!response.ok) throw new Error(`Dashboard request failed (${response.status})`)
  return response.status === 204 ? null : response.json()
}

async function requestHealthProbe(endpoint) {
  const response = await fetchWithTimeout(`${API_BASE}${endpoint}`, {
    headers: { Accept: 'application/json' },
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok && !payload.status) {
    throw new Error(`Health probe failed (${response.status})`)
  }
  return { ...payload, http_status: response.status, ok: response.ok }
}

export const dashboardApi = {
  getHealth: () => requestHealthProbe('/health'),
  getReadiness: () => requestHealthProbe('/health/ready'),
  getIndices: () => request('/market/indices'),
  getKse100Constituents: () => request('/market/indices/kse-100'),
  getKse30Constituents: () => request('/market/indices/kse-30'),
  getKmi30Constituents: () => request('/market/indices/kmi-30'),
  getMarketStatus: () => request('/news/market-status'),
  getGainers: () => request('/market/gainers?limit=5'),
  getLosers: () => request('/market/losers?limit=5'),
  getMostActive: () => request('/market/volume-spikes?limit=5'),
  getPortfolio: () => request('/portfolio'),
  getHoldings: () => request('/portfolio/holdings'),
  getHolding: (symbol) => request(`/portfolio/holdings/${encodeURIComponent(symbol)}`),
  getNews: () => request('/news?limit=5'),
  getRecommendations: () => request('/recommendations?limit=5'),
  getRecommendationList: (params = {}) => {
    const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== ''))
    return request(`/recommendations?${query}`)
  },
  getEngineWeights: () => request('/recommendations/engine-weights'),
  setEngineWeights: (weights) => request('/recommendations/engine-weights', { method: 'POST', body: JSON.stringify(weights) }),
  getSentiment: () => request('/market/sentiment-overview'),
  getConstituents: (code) => request(`/market/indices/${code}`),
  searchStocks: (query) => request(`/stocks/search?q=${encodeURIComponent(query)}&limit=6`),
  getStockOverview: (symbol) => request(`/stocks/${encodeURIComponent(symbol)}/overview`),
  getPriceHistory: (symbol, range = '1M') => request(`/stocks/${encodeURIComponent(symbol)}/price-history?range=${range}`),
  getTechnicalIndicators: (symbol) => request(`/stocks/${encodeURIComponent(symbol)}/technical-indicators`),
  getFundamentals: (symbol) => request(`/stocks/${encodeURIComponent(symbol)}/fundamentals`),
  getStockNews: (symbol) => request(`/stocks/${encodeURIComponent(symbol)}/news?limit=5`),
  getForecast: (symbol, horizon = '1D') => request(`/forecast/${encodeURIComponent(symbol)}?horizon=${horizon}`),
  getForecastHistory: (symbol, limit = 30) => request(`/forecast/${encodeURIComponent(symbol)}/history?limit=${limit}`),
  getRecommendation: (symbol) => request(`/recommendations/${encodeURIComponent(symbol)}`),
  getTargetStop: (symbol) => request(`/recommendations/${encodeURIComponent(symbol)}/target-stop`),
  getShariah: (symbol) => request(`/shariah/${encodeURIComponent(symbol)}`),
  getShariahCriteria: (symbol) => request(`/shariah/${encodeURIComponent(symbol)}/criteria`),
  getShariahPurification: (symbol, holdingQty, holdingValue) => request(`/shariah/${encodeURIComponent(symbol)}/purification?holding_qty=${encodeURIComponent(holdingQty)}&holding_value=${encodeURIComponent(holdingValue)}`),
  getKmi30Shariah: () => request('/shariah/kmi30'),
  getPortfolioPnl: () => request('/portfolio/pnl'),
  getPortfolioAllocation: () => request('/portfolio/allocation'),
  getPortfolioPerformance: (period = '1M') => request(`/portfolio/performance?period=${period}`),
  getTransactions: () => request('/portfolio/transactions?limit=20'),
  getTransaction: (id) => request(`/portfolio/transactions/${encodeURIComponent(id)}`),
  createTransaction: (transaction) => request('/portfolio/transactions', { method: 'POST', body: JSON.stringify(transaction) }),
  createCompletedTrade: (trade) => request('/portfolio/transactions/completed-trade', { method: 'POST', body: JSON.stringify(trade) }),
  updateTransaction: (id, transaction) => request(`/portfolio/transactions/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(transaction) }),
  deleteTransaction: (id) => request(`/portfolio/transactions/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  getAlertRules: () => request('/alerts/rules'),
  createAlertRule: (rule) => request('/alerts/rules', { method: 'POST', body: JSON.stringify(rule) }),
  updateAlertRule: (id, rule) => request(`/alerts/rules/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(rule) }),
  deleteAlertRule: (id) => request(`/alerts/rules/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  getAlerts: () => request('/alerts?limit=20'),
  markAlertRead: (id) => request(`/alerts/${encodeURIComponent(id)}/read`, { method: 'PATCH' }),
  getNotifications: () => request('/notifications?limit=20'),
  markNotificationRead: (id) => request(`/notifications/${encodeURIComponent(id)}/read`, { method: 'PATCH' }),
  updateNotificationPreferences: (preferences) => request('/users/me/notification-preferences', { method: 'PATCH', body: JSON.stringify(preferences) }),
  getRiskVar: (confidence = 95, horizon = '1D') => request(`/risk/var?confidence=${confidence}&horizon=${horizon}`),
  getStressTest: (scenario = '2008_crash') => request(`/risk/stress-test?scenario=${scenario}`),
  startMonteCarlo: (payload) => request('/risk/monte-carlo', { method: 'POST', body: JSON.stringify(payload) }),
  getMonteCarlo: (jobId) => request(`/risk/monte-carlo/${encodeURIComponent(jobId)}`),
  getEvents: (params = {}) => {
    const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== ''))
    return request(`/events/calendar${query.toString() ? `?${query}` : ''}`)
  },
  registerDevice: (device) => request('/devices/register', { method: 'POST', body: JSON.stringify(device) }),
  unregisterDevice: (deviceId) => request(`/devices/${encodeURIComponent(deviceId)}`, { method: 'DELETE' }),
}
