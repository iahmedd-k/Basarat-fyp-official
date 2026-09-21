import { clearSession, refreshSession } from './auth'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

async function request(endpoint, options = {}, allowRefresh = true) {
  const token = localStorage.getItem('basarat_access_token')
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
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
    const error = await response.json().catch(() => ({ detail: 'Community request failed' }))
    throw new Error(error.detail || `Community request failed (${response.status})`)
  }
  return response.status === 204 ? null : response.json()
}

export const communityApi = {
  getFeed: (params = {}) => {
    const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== ''))
    return request(`/community/feed?${query}`)
  },
  createPost: (content, postType, stockSymbol) => {
    const body = new FormData()
    body.append('content', content)
    body.append('post_type', postType)
    if (stockSymbol) body.append('stock_symbol', stockSymbol.toUpperCase())
    return request('/community/posts', { method: 'POST', body })
  },
  getPost: (id) => request(`/community/posts/${encodeURIComponent(id)}`),
  updatePost: (id, payload) => request(`/community/posts/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  deletePost: (id) => request(`/community/posts/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  likePost: (id) => request(`/community/posts/${encodeURIComponent(id)}/like`, { method: 'POST' }),
  unlikePost: (id) => request(`/community/posts/${encodeURIComponent(id)}/like`, { method: 'DELETE' }),
  getComments: (id) => request(`/community/posts/${encodeURIComponent(id)}/comments?limit=50`),
  createComment: (id, content) => request(`/community/posts/${encodeURIComponent(id)}/comments`, { method: 'POST', body: JSON.stringify({ content }) }),
  reportPost: (id, reason) => {
    const body = new FormData()
    body.append('reason', reason)
    return request(`/community/posts/${encodeURIComponent(id)}/report`, { method: 'POST', body })
  },
  deleteComment: (id) => request(`/community/comments/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  reportComment: (id, reason) => {
    const body = new FormData()
    body.append('reason', reason)
    return request(`/community/comments/${encodeURIComponent(id)}/report`, { method: 'POST', body })
  },
  getMyProfile: () => request('/community/me'),
  getMyPosts: () => request('/community/me/posts'),
  getUserProfile: (id) => request(`/community/users/${encodeURIComponent(id)}`),
  getUserPosts: (id) => request(`/community/users/${encodeURIComponent(id)}/posts`),
  getNotifications: () => request('/community/notifications?limit=20'),
  getUnreadCount: () => request('/community/notifications/unread-count'),
  markNotificationRead: (id) => request(`/community/notifications/${encodeURIComponent(id)}/read`, { method: 'POST' }),
  markAllRead: () => request('/community/notifications/read-all', { method: 'POST' }),
  follow: (id) => request(`/community/users/${encodeURIComponent(id)}/follow`, { method: 'POST' }),
  unfollow: (id) => request(`/community/users/${encodeURIComponent(id)}/follow`, { method: 'DELETE' }),
  getFollowStatus: (id) => request(`/community/users/${encodeURIComponent(id)}/follow-status`),
  getFollowers: (id) => request(`/community/users/${encodeURIComponent(id)}/followers`),
  getFollowing: (id) => request(`/community/users/${encodeURIComponent(id)}/following`),
}
