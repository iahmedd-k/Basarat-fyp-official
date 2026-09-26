const API_BASE = import.meta.env.VITE_API_URL || 'http://16.16.26.247:8000/api/v1'

async function parseError(response) {
  const payload = await response.json().catch(() => null)
  
  if (payload?.error?.message) {
    return payload.error.message
  }

  if (payload?.detail) {
    if (Array.isArray(payload.detail)) {
      return payload.detail.map((item) => item.msg || JSON.stringify(item)).join(' ')
    }
    if (typeof payload.detail === 'string') {
      return payload.detail
    }
  }

  if (payload?.message) {
    return payload.message
  }

  if (response.status === 400) return 'Invalid request or expired verification code.'
  if (response.status === 401) return 'Invalid email or password.'
  if (response.status === 403) return 'Your account is not verified or access is forbidden.'
  if (response.status === 422) return 'Validation error. Please check your inputs.'
  if (response.status === 429) return 'Too many requests. Please slow down and try again.'
  if (response.status === 500) return 'Internal server error. Please try again later.'
  if (response.status === 503) {
    return 'The authentication service is temporarily unavailable. Please try again after the backend database is connected.'
  }

  return `Request failed (${response.status})`
}

async function send(endpoint, options = {}, token = getAccessToken()) {
  let response
  try {
    response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token && { Authorization: `Bearer ${token}` }),
        ...options.headers,
      },
    })
  } catch (networkErr) {
    const error = new Error('Unable to connect to the authentication server. Please check your network or CORS settings.')
    error.status = 0
    error.isNetworkError = true
    throw error
  }

  if (!response.ok) {
    const error = new Error(await parseError(response))
    error.status = response.status
    throw error
  }

  return response.status === 204 ? null : response.json()
}

async function request(endpoint, options = {}, allowRefresh = true) {
  try {
    return await send(endpoint, options)
  } catch (error) {
    if (error.status !== 401 || !allowRefresh || endpoint === '/auth/refresh') throw error
    const refreshed = await refreshSession()
    return send(endpoint, options, refreshed.access_token)
  }
}

function getAccessToken() {
  return localStorage.getItem('basarat_access_token')
}

export const authApi = {
  login: (credentials) => request('/auth/login', {
    method: 'POST',
    body: JSON.stringify(credentials),
  }, false),

  signup: (details) => request('/auth/signup', {
    method: 'POST',
    body: JSON.stringify(details),
  }, false),

  verifyEmail: (email, code) => request('/auth/verify-email', {
    method: 'POST',
    body: JSON.stringify({ email, code }),
  }, false),

  resendVerification: (email) => request('/auth/resend-verification', {
    method: 'POST',
    body: JSON.stringify({ email }),
  }, false),

  forgotPassword: (email) => request('/auth/forgot-password', {
    method: 'POST',
    body: JSON.stringify({ email }),
  }, false),

  verifyResetCode: (email, code) => request('/auth/verify-reset-code', {
    method: 'POST',
    body: JSON.stringify({ email, code }),
  }, false),

  resetPassword: ({ reset_token, new_password, confirm_password, email, code }) => request('/auth/reset-password', {
    method: 'POST',
    body: JSON.stringify({ reset_token, new_password, confirm_password, email, code }),
  }, false),

  changePassword: (current_password, new_password, confirm_password) => request('/auth/change-password', {
    method: 'POST',
    body: JSON.stringify({
      current_password,
      new_password,
      ...(confirm_password && { confirm_password }),
    }),
  }, true),

  logout: (refresh_token) => request('/auth/logout', {
    method: 'POST',
    body: JSON.stringify({ refresh_token }),
  }, false),

  refresh: (refresh_token) => send('/auth/refresh', {
    method: 'POST',
    body: JSON.stringify({ refresh_token }),
  }, null),

  logoutAll: () => request('/auth/logout-all', { method: 'POST' }),
  getProfile: () => request('/users/me'),
  setProfile: (profile) => request('/users/me', {
    method: 'POST',
    body: JSON.stringify(profile),
  }),
  updateProfile: (profile) => request('/users/me', {
    method: 'PATCH',
    body: JSON.stringify(profile),
  }),
  getInvestmentProfileOptions: () => request('/users/investment-profile/options'),
}

let refreshPromise = null

export function getTokenExpiry(token = getAccessToken()) {
  if (!token) return null
  try {
    const parts = token.split('.')
    if (parts.length < 2) return null
    const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    )
    const payload = JSON.parse(jsonPayload)
    return payload.exp ? payload.exp * 1000 : null
  } catch {
    return null
  }
}

export function isTokenExpiringSoon(thresholdMinutes = 5) {
  const exp = getTokenExpiry()
  if (!exp) return true
  const remainingMs = exp - Date.now()
  return remainingMs <= thresholdMinutes * 60 * 1000
}

export async function refreshSession() {
  if (refreshPromise) return refreshPromise

  refreshPromise = (async () => {
    try {
      const refreshToken = localStorage.getItem('basarat_refresh_token')
      if (!refreshToken) throw new Error('Your session has expired. Please sign in again.')

      const refreshExp = getTokenExpiry(refreshToken)
      if (refreshExp && refreshExp <= Date.now()) {
        clearSession()
        throw new Error('Refresh token expired. Please log in again.')
      }

      const response = await authApi.refresh(refreshToken)
      if (response && response.access_token) {
        saveSession(response)
        return response
      }
      throw new Error('Invalid refresh response from server')
    } catch (err) {
      // ONLY clear session if server explicitly returned 401 (invalid/revoked token)
      // Never clear on temporary network disconnects, timeouts, or 429/500 errors
      if (
        err.status === 401 ||
        err.message?.includes('Invalid or reused refresh token') ||
        err.message?.includes('Refresh token expired')
      ) {
        clearSession()
      }
      throw err
    } finally {
      refreshPromise = null
    }
  })()

  return refreshPromise
}

export function saveSession({ access_token, refresh_token, user }) {
  if (access_token) localStorage.setItem('basarat_access_token', access_token)
  if (refresh_token) localStorage.setItem('basarat_refresh_token', refresh_token)
  if (user) localStorage.setItem('basarat_user', JSON.stringify(user))

  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('session-updated', {
      detail: { access_token, refresh_token, user }
    }))
  }
}

export function getStoredUser() {
  const storedUser = localStorage.getItem('basarat_user')
  try {
    return storedUser ? JSON.parse(storedUser) : null
  } catch {
    return null
  }
}

export function clearSession() {
  localStorage.removeItem('basarat_access_token')
  localStorage.removeItem('basarat_refresh_token')
  localStorage.removeItem('basarat_user')

  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('session-cleared'))
  }
}
