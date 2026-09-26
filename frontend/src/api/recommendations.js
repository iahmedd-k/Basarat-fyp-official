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
      const retryResponse = await fetchWithTimeout(`${API_BASE}${endpoint}`, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${session.access_token}`,
          ...options.headers,
        },
      })
      if (!retryResponse.ok) {
        const errPayload = await retryResponse.json().catch(() => null)
        const errorMsg = errPayload?.error?.message || errPayload?.detail || errPayload?.message || `Request failed (${retryResponse.status})`
        throw new Error(errorMsg)
      }
      return retryResponse.status === 204 ? null : retryResponse.json()
    } catch {
      throw new Error('Your session has expired. Please sign in again.')
    }
  }

  if (!response.ok) {
    const errPayload = await response.json().catch(() => null)
    const errorMsg = errPayload?.error?.message || errPayload?.detail || errPayload?.message || `Request failed (${response.status})`
    throw new Error(errorMsg)
  }

  return response.status === 204 ? null : response.json()
}

async function request(endpoint, options = {}, ttlSeconds = CACHE_TTLS.DYNAMIC, forceRefresh = false) {
  const method = (options.method || 'GET').toUpperCase()
  if (method !== 'GET') {
    const res = await networkRequest(endpoint, options)
    invalidateCache('/recommendations')
    return res
  }
  const key = getCacheKey(endpoint, options)
  return cachedRequest(key, () => networkRequest(endpoint, options), ttlSeconds, forceRefresh)
}

export const recommendationsApi = {
  getRecommendations: (params = {}) => {
    const query = new URLSearchParams(
      Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== '')
    )
    const queryStr = query.toString()
    return request(`/recommendations${queryStr ? `?${queryStr}` : ''}`)
  },
  getEngineWeights: () => request('/recommendations/engine-weights'),
  setEngineWeights: (weights) =>
    request('/recommendations/engine-weights', {
      method: 'POST',
      body: JSON.stringify(weights),
    }),
  getRecommendationDetail: (symbol) =>
    request(`/recommendations/${encodeURIComponent(symbol.toUpperCase())}`),
  getTargetStop: (symbol) =>
    request(`/recommendations/${encodeURIComponent(symbol.toUpperCase())}/target-stop`),
}

