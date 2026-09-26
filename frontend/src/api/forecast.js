import { refreshSession } from './auth'
import { cachedRequest, getCacheKey, CACHE_TTLS } from './cache'

const API_BASE = import.meta.env.VITE_API_URL || 'http://16.16.26.247:8000/api/v1'

async function networkRequest(endpoint, options = {}, allowRefresh = true) {
  const token = localStorage.getItem('basarat_access_token')
  const headers = {
    'Content-Type': 'application/json',
    ...(token && { Authorization: `Bearer ${token}` }),
    ...options.headers,
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  })

  if (response.status === 401 && allowRefresh) {
    try {
      const session = await refreshSession()
      return networkRequest(endpoint, {
        ...options,
        headers: {
          ...options.headers,
          Authorization: `Bearer ${session.access_token}`,
        },
      }, false)
    } catch {
      return null
    }
  }

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}))
    throw new Error(errorBody.detail || errorBody.message || `API Error: ${response.status}`)
  }

  return response.json()
}

async function request(endpoint, options = {}, ttlSeconds = CACHE_TTLS.SEMI_STATIC, forceRefresh = false) {
  const method = (options.method || 'GET').toUpperCase()
  if (method !== 'GET') {
    return networkRequest(endpoint, options)
  }
  const key = getCacheKey(endpoint, options)
  return cachedRequest(key, () => networkRequest(endpoint, options), ttlSeconds, forceRefresh)
}

export const forecastApi = {
  /**
   * Get ML forecast for a stock
   * @param {string} symbol - PSX ticker (e.g. 'MEBL', 'OGDC')
   * @param {string} horizon - '1D' | '1W' | '1M'
   */
  getForecast: (symbol, horizon = '1D', force = false) =>
    request(`/forecast/${encodeURIComponent(symbol)}?horizon=${encodeURIComponent(horizon)}`, {}, CACHE_TTLS.SEMI_STATIC, force),

  /**
   * Get historical forecast accuracy and predictions log
   * @param {string} symbol - PSX ticker
   * @param {number} limit - Number of historical records (default 30)
   */
  getForecastHistory: (symbol, limit = 30, force = false) =>
    request(`/forecast/${encodeURIComponent(symbol)}/history?limit=${limit}`, {}, CACHE_TTLS.SEMI_STATIC, force),
}

export default forecastApi
