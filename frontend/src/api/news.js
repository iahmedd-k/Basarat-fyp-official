const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

async function request(endpoint, options = {}) {
  const token = localStorage.getItem('clerk_token');
  const headers = {
    'Content-Type': 'application/json',
    ...(token && { Authorization: `Bearer ${token}` }),
    ...options.headers,
  };

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

export const newsApi = {
  async getNews(params = {}) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        searchParams.append(key, value);
      }
    });
    return request(`/news?${searchParams.toString()}`);
  },

  async getArticle(articleId) {
    return request(`/news/${articleId}`);
  },

  async refreshNews(force = false) {
    return request('/news/refresh', {
      method: 'POST',
      body: JSON.stringify({ force }),
    });
  },

  async getRefreshStatus() {
    return request('/news/refresh/status');
  },

  async getMarketStatus() {
    return request('/news/market-status');
  },

  async getSources() {
    return request('/news/sources');
  },

  async getStockNews(symbol, params = {}) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        searchParams.append(key, value);
      }
    });
    return request(`/stocks/${symbol}/news?${searchParams.toString()}`);
  },
};

export async function getClerkToken() {
  if (window.Clerk && window.Clerk.session) {
    return window.Clerk.session.getToken();
  }
  return null;
}