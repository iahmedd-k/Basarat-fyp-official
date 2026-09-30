# ADR-007: Real-Time Market Quote Delivery & PubSub Live Bus

## Status
**Accepted / Implemented**

## Context
Delivering live stock price updates for 500+ PSX equities to hundreds of concurrent web and mobile clients presents severe scalability and rate-limiting challenges. If API web handlers directly scrape upstream market portals upon every client request, the exchange portal will issue HTTP 429/403 blocks, and server threads will lock up.

## Decision
Implement a **Decoupled Scraper-to-Client Live Bus Architecture**:

1. **Dedicated Celery Scraper Ingestion:**
   - A single Celery task (`refresh_market_session`) ingests PSX quotes once every 60 seconds exclusively during active market hours (09:15 to 15:30 PKT).
   - Rate-limiting circuit breakers pause scraping for 15 minutes if upstream returns 429/403.
2. **Redis In-Memory Live Snapshot (`quotes:snapshot`):**
   - The worker stores the latest market quote dictionary in Redis with a 90-second TTL.
   - REST API endpoints (`GET /market/quotes`, `GET /stocks/{symbol}/overview`) read directly from this Redis snapshot without touching upstream web portals.
3. **Redis Pub/Sub Live Bus (`market:quotes:live`):**
   - After updating Redis, the scraper worker publishes the quote batch to the Redis channel `market:quotes:live`.
   - FastAPI's lifespan initializes an asynchronous Redis subscriber ([market_live_bus.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/services/market_live_bus.py)) that receives quote messages.
4. **WebSocket Fan-Out (`WebSocketManager`):**
   - Client applications open a single WebSocket connection (`/api/v1/ws/market`) and send subscription payloads (e.g., `{"action": "subscribe", "symbols": ["ENGRO", "LUCK"]}`).
   - The `WebSocketManager` filters the live bus messages and pushes updates only to clients subscribed to those specific symbols.
5. **REST Polling Fallback Protocol (`GET /api/v1/market/live`):**
   - For environments or mobile clients where persistent WebSockets are unavailable or firewalled, the system exposes discovery metadata at `GET /api/v1/market/live` and `GET /api/v1/ws/protocol` guiding the client to poll cached REST endpoints at 15-second intervals.

```mermaid
flowchart LR
    Scraper["Celery Scraper (1 run/min)"] -->|Write Hash (TTL 90s)| RedisHash[("Redis Hash (quotes:snapshot)")]
    Scraper -->|PUBLISH| RedisChannel[("Redis Channel (market:quotes:live)")]
    
    RedisChannel -->|SUBSCRIBE| LiveBusListener["FastAPI LiveBus Listener"]
    LiveBusListener --> WSManager["WebSocketManager"]
    WSManager -->|Stream to Subscribed Sockets| WSClient["Connected Clients"]
    
    RedisHash -->|Read Snapshot| RESTEndpoint["REST API (GET /market/quotes)"]
    RESTEndpoint -->|REST Response| RESTClient["Polling Clients"]
```

## Alternatives Considered
- **Direct Web Scraping per Request:** Rejected due to immediate IP blocking and unscalable latency.
- **Client-Side Polling Only (No WebSockets):** Rejected because continuous polling from thousands of clients creates high server load and drains mobile battery/bandwidth.
- **Third-Party Commercial Socket Providers (Pusher/Ably):** Rejected to eliminate vendor costs and maintain self-hosted infrastructure control.

## Consequences
- **Positive:** Upstream PSX portals see only 1 request per minute regardless of whether 10 or 10,000 users are active; clients receive instant sub-second quote broadcasts; robust fallback for offline/firewalled networks.
- **Negative / Trade-off:** Quote updates reflect the 60-second scraper cadence during live sessions.

## Current Implementation
- Scraper task in [app/tasks/refresh_market_cache.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/tasks/refresh_market_cache.py).
- Pub/Sub listener in [app/services/market_live_bus.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/services/market_live_bus.py).
- WebSocket connection manager in [app/services/websocket_manager.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/services/websocket_manager.py) and router in [app/api/v1/ws.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/api/v1/ws.py).
