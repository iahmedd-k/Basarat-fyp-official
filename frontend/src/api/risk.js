import { refreshSession } from './auth'
import { cachedRequest, getCacheKey, invalidateCache, CACHE_TTLS } from './cache'

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
    const res = await networkRequest(endpoint, options)
    if (endpoint.includes('/risk/monte-carlo')) {
      invalidateCache('/risk/monte-carlo')
    }
    return res
  }
  const key = getCacheKey(endpoint, options)
  return cachedRequest(key, () => networkRequest(endpoint, options), ttlSeconds, forceRefresh)
}

export const riskApi = {
  /**
   * Calculate portfolio Value at Risk and CVaR (Historical Simulation)
   * @param {number} confidence - 90, 95, or 99
   * @param {string} horizon - '1D', '1W', or '1M'
   */
  getVar: (confidence = 95, horizon = '1D', force = false) =>
    request(`/risk/var?confidence=${confidence}&horizon=${encodeURIComponent(horizon)}`, {}, CACHE_TTLS.SEMI_STATIC, force),

  /**
   * Run stress test scenario on portfolio
   * @param {string} scenario - '2008_crash' | 'pkr_devaluation' | 'covid_crash' | 'interest_rate_hike'
   */
  getStressTest: (scenario = '2008_crash', force = false) =>
    request(`/risk/stress-test?scenario=${encodeURIComponent(scenario)}`, {}, CACHE_TTLS.SEMI_STATIC, force),

  /**
   * Start async Monte Carlo simulation (GBM)
   * @param {Object} params - { num_simulations, horizon_days }
   */
  startMonteCarlo: (params = { num_simulations: 1000, horizon_days: 30 }) =>
    request('/risk/monte-carlo', {
      method: 'POST',
      body: JSON.stringify(params),
    }),

  /**
   * Poll Monte Carlo simulation result
   * @param {string} taskId - Celery / in-process job ID
   */
  getMonteCarloResult: async (taskId) => {
    // For pending/running tasks, fetch directly without long cache
    return networkRequest(`/risk/monte-carlo/${encodeURIComponent(taskId)}`)
  },
}

export default riskApi
