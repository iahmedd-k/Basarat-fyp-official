import { clearSession, refreshSession } from './auth'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

async function request(endpoint, options = {}, allowRefresh = true) {
  const token = localStorage.getItem('basarat_access_token')
  const response = await fetch(`${API_BASE}${endpoint}`, {
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
      return request(endpoint, { ...options, headers: { ...options.headers, Authorization: `Bearer ${session.access_token}` } }, false)
    } catch {
      clearSession()
    }
  }
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Admin Community request failed' }))
    throw new Error(error.detail || `Admin Community request failed (${response.status})`)
  }
  return response.status === 204 ? null : response.json()
}

const queryString = (params) => {
  const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== ''))
  return query.toString() ? `?${query}` : ''
}

export const adminCommunityApi = {
  getReports: (params = {}) => request(`/admin/community/reports${queryString(params)}`),
  updateReportStatus: (id, status) => request(`/admin/community/reports/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify({ status }) }),
  getPost: (id) => request(`/admin/community/posts/${encodeURIComponent(id)}`),
  restorePost: (id) => request(`/admin/community/posts/${encodeURIComponent(id)}/restore`, { method: 'POST' }),
  deletePost: (id) => request(`/admin/community/posts/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  removePost: (id) => request(`/admin/community/posts/${encodeURIComponent(id)}/remove`, { method: 'POST' }),
  deleteComment: (id) => request(`/admin/community/comments/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  getActions: (params = {}) => request(`/admin/community/moderation-actions${queryString(params)}`),
}
