# ADR-004: Celery for Background Job Processing

## Status
Accepted / Implemented

## Context
The system requires scheduled and async background processing for ML inference, news scraping, sentiment analysis, alert evaluation, and model retraining.

## Decision
Celery with Redis broker, supporting dual-mode operation:
- `USE_CELERY=True` (default): Full Celery worker + Beat scheduler
- `USE_CELERY=False`: In-process ThreadPoolExecutor fallback (4 threads)

## Alternatives
- **APScheduler**: Simpler but no distributed task support
- **Dramatiq**: Less mature ecosystem
- **Cloud Functions**: Vendor lock-in

## Consequences
- 15+ Celery Beat schedules for automated workflows
- Separate worker and beat containers in Docker Compose
- Redis required as broker (system degrades gracefully without it)
- In-process fallback enables serverless deployment

## Current Implementation
- Celery config: `app/celery_app.py`
- Task runner: `app/core/task_runner.py`
- Tasks: `app/tasks/` (16 task modules)
