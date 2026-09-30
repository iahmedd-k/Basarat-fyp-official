# ADR-004: Distributed Task Processing & Dual-Mode Orchestration

## Status
**Accepted / Implemented**

## Context
Basarat requires automated background workflows that cannot run inside the synchronous HTTP request-response cycle:
- Periodic market quote scraping (every 60s during trading hours).
- News ingestion and FinBERT sentiment scoring (every 30m).
- Daily reconciliation and forecast generation (18:00 PKT Mon-Fri).
- Weekly model retraining (Sunday 04:00 PKT).
- Alert rule evaluations (every 5m).
- Heavy CPU-bound Monte Carlo portfolio simulations (10,000 paths).

## Decision
1. Implement **Celery 5.4+** with **Celery Beat** for cron scheduling, using **Redis** as the message broker (`redis://.../1`) and result backend (`redis://.../2`).
2. Configure **Timezone-Aware Crons:** Set Celery timezone to `Asia/Karachi` (`UTC+5`) to align with PSX trading schedules.
3. Establish **Market-Gated Scheduling & Off-Hours Snapshot Caching:**
   - **Intraday Trading Hours (Mon–Fri 09:15–15:30 PKT):** Live quotes refresh every 1 minute (`crontab(minute="*/1", hour="9-15", day_of_week="1-5")`), alert rules evaluate every 5 minutes (`crontab(minute="*/5", hour="9-15", day_of_week="1-5")`), and news is ingested every 30 minutes (`crontab(minute="*/30", hour="9-17", day_of_week="1-5")`).
   - **Market Close & Master Pipeline (Mon–Fri 17:00–18:30 PKT):** Ingests the final closing quote snapshot at 17:00 PKT (locked in Redis with 7-day fallback) and executes the master daily pipeline at 18:00 PKT (saves closing OHLCV, generates features, runs predictions & recs).
   - **Nights & Weekends (18:30–09:15 PKT Next Day & Sat/Sun):** All recurring polling, quote scraping, and alert checking tasks completely halt. Zero unnecessary Celery/Redis broker calls occur off-hours. The saved 17:00/18:00 snapshot serves all user requests in `<5ms` from Redis/PostgreSQL.
4. Establish a **Dual-Mode Execution Strategy (`USE_CELERY` flag):**
   - **Production Mode (`USE_CELERY=true`):** Tasks are dispatched to Redis queues and executed by isolated worker processes (`celery worker`).
   - **In-Process Cloud Mode (`USE_CELERY=false`):** Lightweight background tasks run via Python's `asyncio.create_task` or `BackgroundTasks` when running in serverless / ephemeral environments without separate worker containers.
5. Implement **Worker Reliability Settings:**
   - `task_acks_late = True`: Acknowledges task completion only after execution finishes.
   - `task_reject_on_worker_lost = True`: Re-queues tasks if a worker process crashes.
   - `worker_prefetch_multiplier = 1`: Prevents worker starvation on long-running ML jobs.

## Alternatives Considered
- **Unconditional 24/7 Interval Polling:** Rejected because running scrapers and rule evaluators at night and over weekends generates tens of thousands of wasted Redis/task operations when markets are closed and prices are static.
- **APScheduler in FastAPI Lifespan:** Rejected because running scheduled jobs inside the web application process risks blocking HTTP threads and causes duplicate task executions when running multiple web container replicas.
- **RQ (Redis Queue):** Considered, but lacked native complex cron scheduling (Beat) and fine-grained canvas workflow primitives.

## Consequences
- **Positive:** Reduces off-hours Redis broker command volume by ~90% (saving Upstash quotas); guarantees instant read-only serving of closing snapshots during evenings and weekends; complete isolation between HTTP traffic and heavy background tasks.
- **Negative / Trade-off:** Requires running and monitoring two long-running daemon processes (`celery-worker` and `celery-beat`).

## Current Implementation
- Configuration and beat schedule in [app/celery_app.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/celery_app.py).
- Task definitions in [app/tasks/](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/tasks/).
