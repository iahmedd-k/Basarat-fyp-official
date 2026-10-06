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

## Prometheus API Metrics

The API exposes Prometheus metrics at `GET /metrics` when
`PROMETHEUS_METRICS_ENABLED=true`. Metrics are disabled by default. The
authenticated mode uses HTTP Basic authentication with
`PROMETHEUS_METRICS_USERNAME` and `PROMETHEUS_METRICS_PASSWORD`.

> **Temporary development-only exposure:** The Oracle monitoring Compose
> overlay currently sets `PROMETHEUS_METRICS_PUBLIC=true`, publishes
> Prometheus on port 9090 and Grafana on port 3000 on all network interfaces,
> and lists `/metrics` in Swagger. Anyone who can reach the VM can read API
> traffic metrics and query Prometheus. Grafana still requires its admin
> password, but without HTTPS its login is not encrypted in transit. Do not
> use this configuration for production or sensitive traffic. Before
> production lockdown, set `PROMETHEUS_METRICS_PUBLIC=false`, remove the
> public port mappings (bind to `127.0.0.1`), and access the tools through an
> SSH tunnel or a TLS-protected authenticated proxy.

The optional Compose overlay starts Prometheus and Grafana alongside the local
stack. Configure the three credentials in `backend/.env` (do not commit them),
then run from the repository root:

```bash
make monitoring-up
```

Prometheus scrapes the API every 15 seconds. The scrape request uses
`PROMETHEUS_METRICS_HOST_HEADER` (default `localhost`) so it can pass the API's
trusted-host check; when monitoring a deployment, set it to one of that
deployment's configured `ALLOWED_HOSTS`. Grafana is available at
`http://localhost:3000` (user `admin`, password from `GRAFANA_ADMIN_PASSWORD`)
with the provisioned **Basarat API Overview** dashboard. This overlay
temporarily publishes Prometheus and Grafana on all host interfaces at ports
9090 and 3000; restrict those bindings before using it in production.

The dashboard reports API request rate by route and method, HTTP status
distribution, server-side 5xx rate, and p50/p95 request latency. Labels use
registered route templates rather than raw URLs, avoiding user IDs or query
values as high-cardinality metric labels. The endpoint also includes the
Prometheus client's standard Python process and runtime metrics. This does not
yet measure database query latency, Celery queue depth, container/host
resources, or business/ML accuracy. The same overlay is deployed to the Oracle
production VM by the Oracle GitHub Actions workflow using credentials stored
in its `oracle-production` environment; production access instructions are in
[Oracle deployment](../07-deployment/oracle-deployment.md).

Stop the local monitoring stack without deleting its persistent data:

```bash
make monitoring-down
```

## Additional Monitoring Gaps

| Capability | Status |
|-----------|--------|
| External uptime monitoring | Not identified |
| Alerting (PagerDuty, Slack) | Not implemented |
| Request tracing | Not implemented |
| Error tracking (Sentry) | Not implemented |
| Database monitoring | Supabase dashboard only |
| Resource utilization monitoring | Not implemented |

## Additional Monitoring Recommendations

The following capabilities remain recommendations, not current implementation:

1. **Sentry**: Error tracking with stack traces
2. **CloudWatch**: EC2 resource monitoring
3. **Uptime monitoring**: External health check service
