const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

async function parseError(response) {
  const payload = await response.json().catch(() => null)
  const detail = Array.isArray(payload?.detail)
    ? payload.detail.map((item) => item.msg).join(' ')
    : payload?.detail
  if (response.status === 503) {
    return 'The authentication service is temporarily unavailable. Please try again after the backend database is connected.'
  }
  return detail || `Request failed (${response.status})`
}

async function send(endpoint, options = {}, token = getAccessToken()) {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
      ...options.headers,
    },
  })

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
  }),
  signup: (details) => request('/auth/signup', {
    method: 'POST',
    body: JSON.stringify(details),
  }),
  logout: (refresh_token) => request('/auth/logout', {
    method: 'POST',
    body: JSON.stringify({ refresh_token }),
  }),
  refresh: (refresh_token) => send('/auth/refresh', {
    method: 'POST',
    body: JSON.stringify({ refresh_token }),
  }, null),
  forgotPassword: (email) => request('/auth/forgot-password', {
    method: 'POST',
    body: JSON.stringify({ email }),
  }),
  resetPassword: (token, new_password) => request('/auth/reset-password', {
    method: 'POST',
    body: JSON.stringify({ token, new_password }),
  }),
  changePassword: (current_password, new_password) => request('/auth/change-password', {
    method: 'POST',
    body: JSON.stringify({ current_password, new_password }),
  }),
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

export async function refreshSession() {
  const refreshToken = localStorage.getItem('basarat_refresh_token')
  if (!refreshToken) throw new Error('Your session has expired. Please sign in again.')
  const response = await authApi.refresh(refreshToken)
  saveSession(response)
  return response
}

export function saveSession({ access_token, refresh_token, user }) {
  localStorage.setItem('basarat_access_token', access_token)
  localStorage.setItem('basarat_refresh_token', refresh_token)
  localStorage.setItem('basarat_user', JSON.stringify(user))
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
}
