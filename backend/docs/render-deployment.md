# Render deployment notes

The repository-root `render.yaml` describes the Python API service and opts into
deploy-on-commit for a GitHub-connected Render service. The API is in the
`backend` monorepo directory. Before applying the Blueprint to an existing
service, set `name` to that service's exact Render name; otherwise Render can
create a second service. Keep its existing secrets in the Render dashboard.

## Supabase migrations and connection limits

Set `DATABASE_URL` to a Supabase PostgreSQL connection string. For Render's
IPv4 network, use Supabase's shared pooler. Session mode on port 5432 is the
normal option for this long-running API; transaction mode on port 6543 is also
supported (the code disables asyncpg prepared statement caching there). Set
`DATABASE_URL_SYNC` only if a separate psycopg2 string is needed; the startup
command can derive it from `DATABASE_URL`.

Every Render start runs `scripts/render_start.py` before Uvicorn. It upgrades a
versioned database with `alembic upgrade head`. For a fresh database, the
script creates the current mapped schema and establishes the current Alembic
head because the repository's earliest historical migration assumes legacy
tables. For an existing, unversioned database, it checks that mapped tables
and columns are already present before stamping the baseline; if it sees
schema drift, it stops instead of attempting a destructive guess. Back up the
database before the first deployment that runs this command.

SQLAlchemy connection pools are bounded to five async and two sync connections
per service process, to reduce pressure on Supabase's shared database. Keep
Render at one instance on the Free plan. Do not put the direct Supabase IPv6
connection URL in Render unless the project has IPv4 connectivity enabled.

## ML artifacts and inference data

The trained GRU and XGBoost files are tracked under `backend/models`. The
Docker ignore rules no longer omit model files, and the fitted scaler is
tracked under `backend/data/scalers`. The 101 MB daily feature snapshot is
stored as sub-100 MB chunks under `backend/deploy_assets`; Render reconstructs
`data/features/features_daily.parquet` at startup for forecast and
recommendation inference.

That snapshot is a deployment-time snapshot. The filesystem on a Free Render
web service is ephemeral, and the API is not a reliable place to run the daily
feature-generation or retraining pipelines. Refresh and redeploy the snapshot
or move the feature artifact/pipeline to durable object storage and a scheduled
worker before relying on current-day inference.

## Free-tier limits that affect this backend

- Render Free web instances have 512 MB RAM and less than one CPU, sleep after
  15 minutes without inbound traffic, and have ephemeral local files. The
  first request after sleep can wait about a minute. Free web services do not
  provide a background worker or pre-deploy command. The TensorFlow GRU model
  loads at API startup, so the complete ML stack is not guaranteed to fit in
  512 MB; use a larger Render instance for reliable GRU + XGBoost inference.
- Supabase Free currently includes a 500 MB database, 5 GB egress, no automatic
  backups, and can pause projects after a week of low activity. Monitor storage
  and export backups before schema changes.
- If Redis is Upstash Free, it currently includes 256 MB data, 500,000 monthly
  commands, and 10 GB monthly bandwidth. Keep it for cache/rate-limit needs;
  this Render configuration disables Celery because a free Render web service
  cannot run a separate worker. In-process jobs are volatile across restarts,
  and periodic Celery Beat pipelines/retraining are not run on this setup.
- Render Free blocks outbound SMTP ports 25, 465, and 587. This backend's OTP
  email sender uses the SendGrid HTTPS API, so set `SENDGRID_API_KEY` and
  `SENDGRID_FROM_EMAIL` rather than relying on SMTP for account verification
  and password recovery.

Git pushes only trigger deployment after the existing Render service is linked
to this GitHub repository/branch and the Blueprint is synced. `render.yaml`
cannot configure that account-level link or verify the current dashboard
service name by itself.
