/**
 * Resilient Real-time Live Market Data Client for Basarat
 *
 * Strategy: Progressive Enhancement with Automatic REST Fallback
 * 1. GET /market/live for discovery (poll interval, WS URL)
 * 2. WebSocket primary → board_update / snapshot / quote_update
 * 3. On WS failure → REST poll GET /market/quotes (cache-only, safe)
 * 4. Background reconnect with exponential backoff
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
    this.pollFrequencyMs = 15000;
    this.reconnectTimer = null;
    this.lastQuotes = {};
    this.discovery = null;
    this._intentionalClose = false;
  }

  getWebSocketUrl() {
    if (this.discovery?.transport?.websocket_url) {
      return this.discovery.transport.websocket_url;
    }
    const base = API_BASE_URL.replace(/^http/, 'ws');
    return `${base}/ws/market`;
  }

  async loadDiscovery() {
    try {
      const response = await fetch(`${API_BASE_URL}/market/live`);
      if (response.ok) {
        this.discovery = await response.json();
        const pollSec = this.discovery?.transport?.recommended_rest_poll_seconds;
        if (pollSec && Number(pollSec) > 0) {
          this.pollFrequencyMs = Number(pollSec) * 1000;
        }
      }
    } catch (err) {
      console.warn('[LiveMarketStream] Discovery fetch failed; using defaults:', err);
    }
  }

  async connect() {
    this._intentionalClose = false;
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    if (!this.discovery) {
      await this.loadDiscovery();
    }

    try {
      const url = this.getWebSocketUrl();
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        this.isConnected = true;
        this.reconnectAttempts = 0;
        this.stopRestPolling();
        this._notifyListeners({ type: 'status', status: 'connected', mode: 'websocket' });

        if (this.subscribedSymbols.size > 0) {
          this.ws.send(JSON.stringify({
            action: 'subscribe',
            symbols: Array.from(this.subscribedSymbols),
            snapshot: true,
          }));
        }
      };

      this.ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          const eventName = payload.event;

          if (eventName === 'ping') {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
              this.ws.send(JSON.stringify({ action: 'ping' }));
            }
            return;
          }

          if (eventName === 'quote_update') {
            this.lastQuotes[payload.symbol] = payload.data;
            this._notifyListeners({ type: 'quote', symbol: payload.symbol, data: payload.data, meta: payload });
          } else if (eventName === 'board_update' || eventName === 'snapshot') {
            const data = payload.data || {};
            Object.assign(this.lastQuotes, data);
            this._notifyListeners({
              type: eventName === 'board_update' ? 'board_update' : 'snapshot',
              data,
              as_of: payload.as_of,
              is_stale: payload.is_stale,
            });
          } else if (eventName === 'connected') {
            this._notifyListeners({ type: 'status', status: 'connected', mode: 'websocket', meta: payload });
          } else if (eventName === 'error') {
            this._notifyListeners({ type: 'error', message: payload.message, code: payload.code });
          }
        } catch (err) {
          console.warn('[LiveMarketStream] Error parsing WebSocket message:', err);
        }
      };

      this.ws.onerror = () => {
        // onclose will trigger fallback; avoid double-start
      };

      this.ws.onclose = () => {
        this.isConnected = false;
        if (!this._intentionalClose) {
          this._triggerFallback();
          this._scheduleReconnect();
        }
      };
    } catch (err) {
      console.warn('[LiveMarketStream] Failed to initialize WebSocket. Using REST fallback:', err);
      this._triggerFallback();
      this._scheduleReconnect();
    }
  }

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
      const symbols = Array.from(this.subscribedSymbols);
      let url = `${API_BASE_URL}/market/quotes?limit=500`;
      if (symbols.length > 0 && !symbols.includes('ALL') && !symbols.includes('*')) {
        url += `&symbols=${encodeURIComponent(symbols.join(','))}`;
      }
      const response = await fetch(url);
      if (response.ok) {
        const data = await response.json();
        const quotes = Array.isArray(data) ? data : (data.stocks || data.quotes || []);
        const map = {};
        quotes.forEach((q) => {
          if (q.symbol) {
            const sym = q.symbol.toUpperCase();
            this.lastQuotes[sym] = q;
            map[sym] = q;
          }
        });
        this._notifyListeners({
          type: 'snapshot',
          data: map,
          as_of: data.as_of,
          is_stale: data.is_stale,
          mode: 'rest_polling',
        });
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
    if (this._intentionalClose) return;
    if (this.reconnectTimer) return;
    this.reconnectAttempts += 1;
    const delay = Math.min(1000 * (2 ** this.reconnectAttempts), this.maxReconnectDelay);
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      if (!this.isConnected && !this._intentionalClose) {
        this.connect();
      }
    }, delay);
  }

  subscribe(symbols) {
    const list = Array.isArray(symbols) ? symbols : [symbols];
    list.forEach((s) => this.subscribedSymbols.add(String(s).toUpperCase()));

    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        action: 'subscribe',
        symbols: list,
        snapshot: true,
      }));
    } else if (this.isPollingFallback) {
      this._pollRestQuotes();
    }
  }

  unsubscribe(symbols) {
    const list = Array.isArray(symbols) ? symbols : [symbols];
    list.forEach((s) => this.subscribedSymbols.delete(String(s).toUpperCase()));
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action: 'unsubscribe', symbols: list }));
    }
  }

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
    this._intentionalClose = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
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
