import { refreshSession } from './auth';
import { cachedRequest, getCacheKey, invalidateCache, CACHE_TTLS } from './cache';

const API_BASE = import.meta.env.VITE_API_URL || 'http://16.16.26.247:8000/api/v1';

async function networkRequest(endpoint, options = {}, allowRefresh = true) {
  const token = localStorage.getItem('basarat_access_token');
  const headers = {
    'Content-Type': 'application/json',
    ...(token && { Authorization: `Bearer ${token}` }),
    ...options.headers,
  };

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (response.status === 401 && allowRefresh) {
    try {
      const session = await refreshSession();
      return networkRequest(endpoint, {
        ...options,
        headers: {
          ...options.headers,
          Authorization: `Bearer ${session.access_token}`,
        },
      }, false);
    } catch (err) {
      console.warn('News request refresh attempt failed:', err.message);
    }
  }

  if (!response.ok) {
    const errData = await response.json().catch(() => ({ detail: 'Request failed' }));
    const msg = errData.detail || errData.error?.message || errData.message || `HTTP ${response.status}`;
    const error = new Error(msg);
    error.status = response.status;
    error.data = errData;
    throw error;
  }

  return response.json();
}

async function request(endpoint, options = {}, ttlSeconds = CACHE_TTLS.DYNAMIC, forceRefresh = false) {
  const method = (options.method || 'GET').toUpperCase();
  if (method !== 'GET') {
    const res = await networkRequest(endpoint, options);
    if (endpoint.includes('/news/refresh')) {
      invalidateCache('/news');
    }
    return res;
  }
  const key = getCacheKey(endpoint, options);
  return cachedRequest(key, () => networkRequest(endpoint, options), ttlSeconds, forceRefresh);
}

export const newsApi = {
  async getNews(params = {}, force = false) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        searchParams.append(key, value);
      }
    });
    const qs = searchParams.toString();
    return request(qs ? `/news?${qs}` : '/news', {}, CACHE_TTLS.DYNAMIC, force);
  },

  async getArticle(articleId) {
    return request(`/news/${encodeURIComponent(articleId)}`, {}, CACHE_TTLS.STATIC);
  },

  async refreshNews(force = false) {
    const endpoint = force ? '/news/refresh?force=true' : '/news/refresh';
    return request(endpoint, {
      method: 'POST',
    });
  },

  async getRefreshStatus() {
    return request('/news/refresh/status', {}, CACHE_TTLS.REALTIME);
  },

  async getMarketStatus() {
    return request('/news/market-status', {}, CACHE_TTLS.REALTIME);
  },

  async getSources() {
    return request('/news/sources', {}, CACHE_TTLS.STATIC);
  },

  async getStockNews(symbol, params = {}, force = false) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        searchParams.append(key, value);
      }
    });
    return request(`/stocks/${symbol}/news?${searchParams.toString()}`, {}, CACHE_TTLS.DYNAMIC, force);
  },

  async getMarketSentiment(force = false) {
    return request('/sentiment/market-overview', {}, CACHE_TTLS.DYNAMIC, force);
  },

  async getStockSentiment(symbol, days = 7, force = false) {
    return request(`/sentiment/${encodeURIComponent(symbol)}?days=${days}`, {}, CACHE_TTLS.DYNAMIC, force);
  },

  async getSentimentHistory(symbol, period = '1M', limit = 100, force = false) {
    return request(`/sentiment/${encodeURIComponent(symbol)}/history?period=${period}&limit=${limit}`, {}, CACHE_TTLS.SEMI_STATIC, force);
  },

  async getSentimentNews(symbol, params = {}, force = false) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        searchParams.append(key, value);
      }
    });
    return request(`/sentiment/${encodeURIComponent(symbol)}/news?${searchParams.toString()}`, {}, CACHE_TTLS.DYNAMIC, force);
  },
};

export async function getAccessToken() {
  return localStorage.getItem('basarat_access_token');
}