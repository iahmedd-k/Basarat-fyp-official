/**
 * Resilient Real-time Live Market Data Client for Basarat
 * 
 * Strategy: Progressive Enhancement with Automatic REST Fallback
 * 1. Attempts WebSocket connection to ws://.../ws/market
 * 2. If WebSocket fails or drops, seamlessly switches to REST polling (GET /api/v1/market/quotes)
 * 3. Transparently reconnects WebSocket in background with exponential backoff
 * 4. UI never breaks and always has live or freshest-known PSX quotes.
 */

import { API_BASE_URL } from './config';

class LiveMarketStream {
  constructor() {
    this.ws = null;
    this.isConnected = false;
    this.isPollingFallback = false;
    this.pollIntervalId = null;
    this.subscribedSymbols = new Set();
    this.listeners = new Set();
    this.reconnectAttempts = 0;
    this.maxReconnectDelay = 30000;
    this.pollFrequencyMs = 15000; // 15s REST polling when offline
    this.lastQuotes = {};
  }

  /**
   * Derive WebSocket URL from API_BASE_URL
   */
  getWebSocketUrl() {
    const base = API_BASE_URL.replace(/^http/, 'ws');
    return `${base}/ws/market`;
  }

  /**
   * Start the real-time stream connection
   */
  connect() {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    try {
      const url = this.getWebSocketUrl();
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        this.isConnected = true;
        this.reconnectAttempts = 0;
        this.stopRestPolling(); // Stop REST fallback once WS is alive
        this._notifyListeners({ type: 'status', status: 'connected', mode: 'websocket' });

        // Resubscribe any symbols previously tracked
        if (this.subscribedSymbols.size > 0) {
          this.ws.send(JSON.stringify({
            action: 'subscribe',
            symbols: Array.from(this.subscribedSymbols),
          }));
        }
      };

      this.ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.event === 'quote_update') {
            this.lastQuotes[payload.symbol] = payload.data;
            this._notifyListeners({ type: 'quote', symbol: payload.symbol, data: payload.data });
          } else if (payload.event === 'snapshot') {
            Object.assign(this.lastQuotes, payload.data);
            this._notifyListeners({ type: 'snapshot', data: payload.data });
          }
        } catch (err) {
          console.warn('[LiveMarketStream] Error parsing WebSocket message:', err);
        }
      };

      this.ws.onerror = (error) => {
        console.warn('[LiveMarketStream] WebSocket connection issue. Triggering fallback:', error);
        this._triggerFallback();
      };

      this.ws.onclose = () => {
        this.isConnected = false;
        this._triggerFallback();
        this._scheduleReconnect();
      };
    } catch (err) {
      console.warn('[LiveMarketStream] Failed to initialize WebSocket. Using REST fallback:', err);
      this._triggerFallback();
    }
  }

  /**
   * Seamless REST Polling Fallback
   */
  _triggerFallback() {
    if (this.isPollingFallback) return;
    this.isPollingFallback = true;
    this._notifyListeners({ type: 'status', status: 'fallback', mode: 'rest_polling' });
    this._pollRestQuotes();

    if (!this.pollIntervalId) {
      this.pollIntervalId = setInterval(() => {
        this._pollRestQuotes();
      }, this.pollFrequencyMs);
    }
  }

  async _pollRestQuotes() {
    try {
      const response = await fetch(`${API_BASE_URL}/market/quotes`);
      if (response.ok) {
        const data = await response.json();
        const quotes = Array.isArray(data) ? data : (data.quotes || []);
        quotes.forEach((q) => {
          if (q.symbol) {
            this.lastQuotes[q.symbol.toUpperCase()] = q;
          }
        });
        this._notifyListeners({ type: 'snapshot', data: this.lastQuotes });
      }
    } catch (err) {
      console.warn('[LiveMarketStream] REST fallback polling error:', err);
    }
  }

  stopRestPolling() {
    if (this.pollIntervalId) {
      clearInterval(this.pollIntervalId);
      this.pollIntervalId = null;
    }
    this.isPollingFallback = false;
  }

  _scheduleReconnect() {
    this.reconnectAttempts++;
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), this.maxReconnectDelay);
    setTimeout(() => {
      if (!this.isConnected) {
        this.connect();
      }
    }, delay);
  }

  /**
   * Subscribe to specific stock symbols
   */
  subscribe(symbols) {
    const list = Array.isArray(symbols) ? symbols : [symbols];
    list.forEach((s) => this.subscribedSymbols.add(s.toUpperCase()));

    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        action: 'subscribe',
        symbols: list,
      }));
    }
  }

  /**
   * Register a listener callback
   */
  addListener(callback) {
    this.listeners.add(callback);
    return () => this.listeners.delete(callback);
  }

  _notifyListeners(event) {
    this.listeners.forEach((cb) => {
      try {
        cb(event);
      } catch (err) {
        console.error('[LiveMarketStream] Listener threw error:', err);
      }
    });
  }

  disconnect() {
    this.stopRestPolling();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.isConnected = false;
  }
}

export const liveMarketStream = new LiveMarketStream();
export default liveMarketStream;
