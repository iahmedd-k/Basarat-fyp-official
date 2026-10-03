# Monitoring

## Existing Monitoring

### Health Endpoints
- `GET /health` — Liveness probe: returns `{"status": "ok"}`
- `GET /health/ready` — Readiness probe: checks API, Database, Redis, Celery Worker, Celery Beat

### Docker Health Checks
- API container: Polls `/health` every 30s (start period 120s)
- Celery Worker: Pings Celery control every 30s
- Celery Beat: Checks Redis heartbeat key every 30s

### Celery Beat Heartbeat
- Task `beat_heartbeat` runs every 30 seconds
- Sets Redis key `health:celery_beat:last_seen` with 90s TTL
- Readiness probe checks this key to verify Beat is alive

### Model Monitoring
- `monitor_performance` task runs daily at 06:00 — tracks prediction accuracy
- `detect_drift` task runs daily at 07:00 — detects feature/prediction drift

### Data-refresh protection
- API stock reads use Redis-backed per-symbol single-flight locks. A cache miss
  must not cause every concurrent request to scrape PSX.
- Market session refresh uses a distributed lock that outlives the task hard
  timeout, preventing slow upstream responses from overlapping the next beat
  tick.
- Startup market warmup and daily pipeline dispatches are deduplicated across
  API replicas with Redis keys.
- Fundamentals and news ingestion run on dedicated Celery queues. They must
  not share capacity with the live market queue.
- Monitor these keys and signals in production:
  `lock:stock:*`, `jobs:market-cache:*`,
  `jobs:daily-workflow:*`, `news:ingestion:*`, queue depth, task age,
  upstream 403/429 counts, cache hit ratio, and snapshot age.

## Not Currently Implemented

| Capability | Status |
|-----------|--------|
| External uptime monitoring | Not identified |
| Application metrics (Prometheus) | Not implemented |
| Dashboard (Grafana) | Not implemented |
| Alerting (PagerDuty, Slack) | Not implemented |
| Request tracing | Not implemented |
| Error tracking (Sentry) | Not implemented |
| Database monitoring | Supabase dashboard only |
| Resource utilization monitoring | Not implemented |

## Recommended Monitoring Stack

> **Note:** The following is a recommendation, not current implementation.

1. **Prometheus + Grafana**: API latency, request rates, error rates
2. **Sentry**: Error tracking with stack traces
3. **CloudWatch**: EC2 resource monitoring
4. **Uptime monitoring**: External health check service
