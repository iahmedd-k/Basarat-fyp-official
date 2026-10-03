# Troubleshooting Guide

## Application Fails to Start

**Symptoms:** Container exits immediately; no `/health` response
**Possible Cause:** Invalid environment variables; ML model files missing
**How to Diagnose:** Check container logs: `docker logs basarat-api`
**Resolution:**
- Verify `.env` file has valid `SECRET_KEY` (32+ chars, not a placeholder)
- Verify `DATABASE_URL` is reachable
- Verify ML model files exist in `models/final/final_v3/`
- Check for import errors in logs

## Database Connection Errors

**Symptoms:** 503 errors; health/ready shows database "down"
**Possible Cause:** Wrong DATABASE_URL; Supabase connection limit
**How to Diagnose:** Check logs for SQLAlchemy connection errors
**Resolution:**
- Verify `DATABASE_URL` is correct
- Check Supabase dashboard for connection count
- Restart API to reset connection pool
- Check SSL configuration for Supabase

## Migration Failures

**Symptoms:** `alembic upgrade head` fails
**Possible Cause:** Schema conflict; migration dependency issue
**How to Diagnose:** Run `alembic heads` (should show exactly 1 head)
**Resolution:**
- Ensure single migration head: `alembic heads`
- Check for uncommitted migration files
- If stuck, check `alembic_version` table in database

## Authentication Failures

**Symptoms:** 401 Unauthorized on protected endpoints
**Possible Cause:** Expired token; invalid SECRET_KEY; user not verified
**How to Diagnose:** Decode JWT token to check expiry and claims
**Resolution:**
- Refresh token via `POST /auth/refresh`
- Ensure user `is_verified = True` and `is_active = True`
- Verify SECRET_KEY matches between token creation and validation

## CORS Issues

**Symptoms:** Browser/client CORS errors
**Possible Cause:** Frontend origin not in CORS_ORIGINS
**How to Diagnose:** Check request Origin header vs configured CORS_ORIGINS
**Resolution:**
- Add frontend origin to `CORS_ORIGINS` in `.env`
- Note: Code currently uses `allow_origins=["*"]` regardless of config

## External API Failures

### Groq (AI Assistant)
**Symptoms:** 502/503 on assistant chat
**Possible Cause:** Invalid API key; rate limit; model unavailable
**Resolution:** Check `GROQ_API_KEY`; system retries with fallback model

### HuggingFace (Sentiment)
**Symptoms:** Sentiment scores missing
**Possible Cause:** Invalid HF_API_TOKEN; API rate limit
**Resolution:** Check token; failed sentiment rescored hourly by Celery

### SendGrid (Email)
**Symptoms:** OTP emails not received
**Possible Cause:** Invalid API key; sender email not verified
**Resolution:** Check `SENDGRID_API_KEY` and `SENDGRID_FROM_EMAIL`

## Celery Worker Not Processing Tasks

**Symptoms:** Tasks stuck in queue; health/ready shows worker "down"
**Possible Cause:** Worker crashed; Redis unreachable
**How to Diagnose:** `docker logs basarat-celery-worker`
**Resolution:**
- Restart worker: `docker compose restart celery-worker`
- Verify Redis connectivity
- Check for memory issues (ML models consume significant RAM)

## Docker Compose Issues

**Symptoms:** Containers fail to start
**Possible Cause:** Missing POSTGRES_PASSWORD; port conflicts
**Resolution:**
- Ensure `POSTGRES_PASSWORD` is set in `.env`
- Check for port conflicts on 5432, 6379, 8000
- Run `docker compose down -v` and restart fresh
