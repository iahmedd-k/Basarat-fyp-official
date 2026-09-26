import { refreshSession } from './auth';
import { cachedRequest, getCacheKey, CACHE_TTLS } from './cache';

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
      console.warn('Sentiment request refresh attempt failed:', err.message);
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
    return networkRequest(endpoint, options);
  }
  const key = getCacheKey(endpoint, options);
  return cachedRequest(key, () => networkRequest(endpoint, options), ttlSeconds, forceRefresh);
}

export const sentimentApi = {
  /**
   * Get overall market sentiment from the sentiment service.
   * Returns symbol "MARKET-OVERVIEW", score, label, article_count, trend, etc.
   */
  async getMarketSentiment(force = false) {
    return request('/sentiment/market-overview', {}, CACHE_TTLS.DYNAMIC, force);
  },

  /**
   * Get comprehensive market breadth & sector performance overview.
   * Returns market_mood, advancing, declining, unchanged, advance_decline_ratio, sector_performance, top_movers.
   */
  async getMarketSentimentOverview(force = false) {
    return request('/market/sentiment-overview', {}, CACHE_TTLS.DYNAMIC, force);
  },

  /**
   * Get sentiment analysis for a specific stock over a rolling window.
   * @param {string} symbol - PSX symbol (e.g. MEBL, OGDC)
   * @param {number} days - Rolling window in days (1 to 90, default 7)
   */
  async getStockSentiment(symbol, days = 7, force = false) {
    if (!symbol) throw new Error('Symbol is required');
    return request(`/sentiment/${encodeURIComponent(symbol.toUpperCase())}?days=${encodeURIComponent(days)}`, {}, CACHE_TTLS.DYNAMIC, force);
  },

  /**
   * Get historical sentiment time series for a stock.
   * @param {string} symbol - PSX symbol
   * @param {string} period - '1D' | '1W' | '1M' | '3M' | '6M' | '1Y' (default '1M')
   * @param {number} limit - Maximum points to return (default 100)
   */
  async getSentimentHistory(symbol, period = '1M', limit = 100, force = false) {
    if (!symbol) throw new Error('Symbol is required');
    return request(`/sentiment/${encodeURIComponent(symbol.toUpperCase())}/history?period=${encodeURIComponent(period)}&limit=${encodeURIComponent(limit)}`, {}, CACHE_TTLS.SEMI_STATIC, force);
  },

  /**
   * Get paginated news articles with sentiment for a stock.
   * @param {string} symbol - PSX symbol
   * @param {object} params - { page: 1, limit: 20, sentiment: 'POSITIVE'|'NEGATIVE'|'NEUTRAL', from_date, to_date }
   */
  async getSentimentNews(symbol, params = {}, force = false) {
    if (!symbol) throw new Error('Symbol is required');
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        searchParams.append(key, value);
      }
    });
    const qs = searchParams.toString();
    return request(`/sentiment/${encodeURIComponent(symbol.toUpperCase())}/news${qs ? `?${qs}` : ''}`, {}, CACHE_TTLS.DYNAMIC, force);
  },
};
