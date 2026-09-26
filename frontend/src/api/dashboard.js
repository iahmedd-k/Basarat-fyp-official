import { refreshSession } from './auth'
import { cachedRequest, getCacheKey, invalidateCache, CACHE_TTLS } from './cache'

const API_BASE = import.meta.env.VITE_API_URL || 'http://16.16.26.247:8000/api/v1'
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

async function networkRequest(endpoint, options = {}, allowRefresh = true) {
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
    } catch (err) {
      console.warn('Dashboard request refresh attempt failed:', err.message)
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

async function request(endpoint, options = {}, ttlSeconds = CACHE_TTLS.DYNAMIC, forceRefresh = false) {
  const method = (options.method || 'GET').toUpperCase()
  if (method !== 'GET') {
    const result = await networkRequest(endpoint, options)
    if (endpoint.includes('/portfolio')) invalidateCache('/portfolio')
    if (endpoint.includes('/recommendations')) invalidateCache('/recommendations')
    if (endpoint.includes('/alerts')) invalidateCache('/alerts')
    return result
  }
  const key = getCacheKey(endpoint, options)
  return cachedRequest(key, () => networkRequest(endpoint, options), ttlSeconds, forceRefresh)
}

export const dashboardApi = {
  getIndices: (force = false) => request('/market/indices', {}, CACHE_TTLS.REALTIME, force),
  getKse100Constituents: () => request('/market/indices/kse-100', {}, CACHE_TTLS.STATIC),
  getKse30Constituents: () => request('/market/indices/kse-30', {}, CACHE_TTLS.STATIC),
  getKmi30Constituents: () => request('/market/indices/kmi-30', {}, CACHE_TTLS.STATIC),
  getMarketStatus: () => request('/news/market-status', {}, CACHE_TTLS.REALTIME),
  getGainers: (limit = 10, force = false) => request(`/market/gainers?limit=${limit}`, {}, CACHE_TTLS.REALTIME, force),
  getLosers: (limit = 10, force = false) => request(`/market/losers?limit=${limit}`, {}, CACHE_TTLS.REALTIME, force),
  getMostActive: (limit = 10, force = false) => request(`/market/volume-spikes?limit=${limit}`, {}, CACHE_TTLS.REALTIME, force),
  getSectorPerformance: () => request('/market/sectors/performance', {}, CACHE_TTLS.DYNAMIC),
  getQuotes: (params = {}) => {
    const query = new URLSearchParams(
      Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== '')
    ).toString()
    return request(`/market/quotes${query ? `?${query}` : ''}`)
  },
  getAllStocks: (params = {}) => {
    const query = new URLSearchParams(
      Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== '')
    ).toString()
    return request(`/market/all-stocks${query ? `?${query}` : ''}`)
  },
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
  searchStocks: (query, limit = 10) => request(`/stocks/search?q=${encodeURIComponent(query)}&limit=${limit}`),
  getStockOverview: (symbol) => request(`/stocks/${encodeURIComponent(symbol)}/overview`),
  getPriceHistory: (symbol, range = '1M') => request(`/stocks/${encodeURIComponent(symbol)}/price-history?range=${range}`),
  getTechnicalIndicators: (symbol, params = {}) => {
    const query = new URLSearchParams(
      Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== '')
    ).toString()
    return request(`/stocks/${encodeURIComponent(symbol)}/technical-indicators${query ? `?${query}` : ''}`)
  },
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
