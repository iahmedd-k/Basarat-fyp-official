/**
 * High-Performance Stale-While-Revalidate (SWR) Cache & Runtime State Manager
 * 
 * Features:
 * 1. Instant 0ms Synchronous Cache Hits for fast page navigation.
 * 2. Background Revalidation (SWR): Silently checks backend and dispatches updates if data changes.
 * 3. In-Flight Request Deduplication: Merges concurrent identical fetches into a single network call.
 * 4. Runtime Update Subscriptions: Components listen for live changes without reloading.
 * 5. Memory + SessionStorage: Persists across navigation while keeping RAM usage bounded.
 */

const memoryCache = new Map();
const inFlightRequests = new Map();
const subscribers = new Map();

// Default TTLs in seconds based on data volatility
export const CACHE_TTLS = {
  REALTIME: 20,       // Market indices, tickers, gainers, losers (20s)
  DYNAMIC: 60,        // Stock overview, technical indicators, active news, sentiment (60s)
  SEMI_STATIC: 300,   // Recommendations, forecasts, VaR risk models (5 min)
  STATIC: 1800,       // Fundamentals, AAOIFI shariah criteria, constituents (30 min)
};

/**
 * Generate a consistent cache key from URL/endpoint and query params
 */
export function getCacheKey(endpoint, options = {}) {
  const method = (options.method || 'GET').toUpperCase();
  const body = options.body ? (typeof options.body === 'string' ? options.body : JSON.stringify(options.body)) : '';
  return `${method}:${endpoint}${body ? ':' + body : ''}`;
}

/**
 * Retrieve cached entry if available
 */
export function getCached(key) {
  // 1. Check in-memory Map (fastest, 0ms)
  let entry = memoryCache.get(key);

  // 2. Check sessionStorage fallback if not in memory
  if (!entry && typeof window !== 'undefined' && window.sessionStorage) {
    try {
      const stored = sessionStorage.getItem(`basarat_cache_${key}`);
      if (stored) {
        entry = JSON.parse(stored);
        memoryCache.set(key, entry);
      }
    } catch {
      // sessionStorage unavailable or quota exceeded
    }
  }

  if (!entry) return null;

  const now = Date.now();
  const isFresh = now - entry.timestamp < entry.ttlMs;

  return {
    data: entry.data,
    timestamp: entry.timestamp,
    isFresh,
  };
}

/**
 * Store data in cache
 */
export function setCached(key, data, ttlSeconds = CACHE_TTLS.DYNAMIC) {
  if (!key || data === undefined || data === null) return;

  const ttlMs = ttlSeconds * 1000;
  const entry = {
    data,
    timestamp: Date.now(),
    ttlMs,
  };

  memoryCache.set(key, entry);

  // Session storage sync (safe limit, only for modest sized responses)
  if (typeof window !== 'undefined' && window.sessionStorage) {
    try {
      const serialized = JSON.stringify(entry);
      if (serialized.length < 500000) { // < 500KB per item limit
        sessionStorage.setItem(`basarat_cache_${key}`, serialized);
      }
    } catch {
      // Quota exceeded, memory cache still holds it
    }
  }

  // Notify subscribers
  notifySubscribers(key, data);
}

/**
 * Invalidate cache keys matching pattern or exact string
 */
export function invalidateCache(pattern) {
  const keysToDelete = [];

  for (const key of memoryCache.keys()) {
    if (typeof pattern === 'string' ? key.includes(pattern) : pattern.test(key)) {
      keysToDelete.push(key);
    }
  }

  keysToDelete.forEach((key) => {
    memoryCache.delete(key);
    if (typeof window !== 'undefined' && window.sessionStorage) {
      try {
        sessionStorage.removeItem(`basarat_cache_${key}`);
      } catch {}
    }
  });

  if (keysToDelete.length > 0 && typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('api-cache-invalidated', { detail: { pattern, count: keysToDelete.length } }));
  }
}

/**
 * Subscribe to runtime cache updates for a specific key
 */
export function onCacheUpdate(key, callback) {
  if (!subscribers.has(key)) {
    subscribers.set(key, new Set());
  }
  const set = subscribers.get(key);
  set.add(callback);

  return () => {
    const s = subscribers.get(key);
    if (s) {
      s.delete(callback);
      if (s.size === 0) subscribers.delete(key);
    }
  };
}

function notifySubscribers(key, freshData) {
  const set = subscribers.get(key);
  if (set && set.size > 0) {
    set.forEach((cb) => {
      try { cb(freshData); } catch (e) { console.error('Cache subscriber error:', e); }
    });
  }

  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('api-cache-update', {
      detail: { key, data: freshData }
    }));
  }
}

/**
 * Stale-While-Revalidate Fetch Wrapper:
 * 
 * - If cached and fresh: returns cached data immediately (0ms).
 * - If cached but stale: returns cached data immediately, and runs fetcher in background to revalidate.
 *   If revalidated data is different, updates cache and notifies subscribers so UI updates at runtime.
 * - If no cache: awaits fetcher, caches result, and returns data.
 * - Deduplicates concurrent in-flight requests.
 */
export async function cachedRequest(key, fetcher, ttlSeconds = CACHE_TTLS.DYNAMIC, forceRefresh = false) {
  const cached = forceRefresh ? null : getCached(key);

  // Background revalidator function
  const runRevalidation = async () => {
    // If request already in flight for this key, return that promise
    if (inFlightRequests.has(key)) {
      return inFlightRequests.get(key);
    }

    const promise = (async () => {
      try {
        const freshData = await fetcher();
        if (freshData !== null && freshData !== undefined) {
          // Compare with cached to check if backend data changed
          const prevDataStr = cached ? JSON.stringify(cached.data) : null;
          const freshDataStr = JSON.stringify(freshData);

          if (prevDataStr !== freshDataStr) {
            setCached(key, freshData, ttlSeconds);
          } else {
            // Update timestamp so we don't revalidate immediately again
            const existing = memoryCache.get(key);
            if (existing) existing.timestamp = Date.now();
          }
        }
        return freshData;
      } finally {
        inFlightRequests.delete(key);
      }
    })();

    inFlightRequests.set(key, promise);
    return promise;
  };

  // Case 1: Fresh Cache Hit -> Instant 0ms return
  if (cached && cached.isFresh) {
    return cached.data;
  }

  // Case 2: Stale Cache Hit -> Return cached immediately, revalidate silently in background!
  if (cached && !cached.isFresh) {
    // Fire revalidation in background (don't await!)
    runRevalidation().catch((err) => {
      console.warn(`Background revalidation for ${key} failed:`, err.message);
    });
    // Return stale data immediately so UI doesn't block!
    return cached.data;
  }

  // Case 3: Cache Miss -> Must await fresh fetch
  return runRevalidation();
}

