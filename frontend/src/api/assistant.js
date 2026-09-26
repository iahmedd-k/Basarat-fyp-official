import { refreshSession } from './auth'
import { cachedRequest, getCacheKey, invalidateCache, CACHE_TTLS } from './cache'

const API_BASE = import.meta.env.VITE_API_URL || 'http://16.16.26.247:8000/api/v1'

async function networkRequest(endpoint, options = {}, allowRefresh = true) {
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
      return networkRequest(endpoint, {
        ...options,
        headers: { ...options.headers, Authorization: `Bearer ${session.access_token}` },
      }, false)
    } catch (err) {
      console.warn('Assistant request refresh attempt failed:', err.message)
    }
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Assistant request failed' }))
    throw new Error(error.detail || `Assistant request failed (${response.status})`)
  }
  return response.status === 204 ? null : response.json()
}

async function request(endpoint, options = {}, ttlSeconds = CACHE_TTLS.DYNAMIC, forceRefresh = false) {
  const method = (options.method || 'GET').toUpperCase()
  if (method !== 'GET') {
    const res = await networkRequest(endpoint, options)
    if (endpoint.includes('/assistant/conversations')) {
      invalidateCache('/assistant/conversations')
    }
    return res
  }
  const key = getCacheKey(endpoint, options)
  return cachedRequest(key, () => networkRequest(endpoint, options), ttlSeconds, forceRefresh)
}

async function streamChat(message, conversationId, onEvent) {
  const token = localStorage.getItem('basarat_access_token')
  const response = await fetch(`${API_BASE}/assistant/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token && { Authorization: 'Bearer ' + token }),
    },
    body: JSON.stringify({ message, conversation_id: conversationId || null }),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Assistant stream failed' }))
    throw new Error(error.detail || `Assistant stream failed (${response.status})`)
  }
  if (!response.body) throw new Error('Assistant streaming is unavailable.')
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done })
    const events = buffer.split('\n\n')
    buffer = events.pop() || ''
    events.forEach((event) => {
      const line = event.split('\n').find((item) => item.startsWith('data:'))
      if (!line) return
      try { onEvent(JSON.parse(line.slice(5).trim())) } catch { /* Ignore incomplete SSE frames. */ }
    })
    if (done) break
  }
}

export const assistantApi = {
  chat: (message, conversationId) => request('/assistant/chat', {
    method: 'POST',
    body: JSON.stringify({ message, conversation_id: conversationId || null }),
  }),
  streamChat,
  listConversations: (force = false) => request('/assistant/conversations?limit=50', {}, CACHE_TTLS.DYNAMIC, force),
  getConversation: (id, force = false) => request(`/assistant/conversations/${encodeURIComponent(id)}`, {}, CACHE_TTLS.DYNAMIC, force),
  createConversation: (title) => request('/assistant/conversations', {
    method: 'POST',
    body: JSON.stringify({ title: title || null }),
  }),
  updateConversation: (id, title) => request(`/assistant/conversations/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: JSON.stringify({ title }),
  }),
  deleteConversation: (id) => request(`/assistant/conversations/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  regenerate: (id) => request(`/assistant/conversations/${encodeURIComponent(id)}/regenerate`, { method: 'POST' }),
}
