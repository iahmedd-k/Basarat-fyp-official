# Oracle ARM64 deployment

The `Backend CI and Oracle ARM64 deploy` workflow tests the backend, publishes an immutable `linux/arm64` image to GHCR, then deploys it to the Oracle VM over SSH when `main` is updated. The Oracle VM runs the API, Alembic migration, Celery worker, Celery Beat, Prometheus, Grafana, and private, persistent Redis and monitoring storage. PostgreSQL remains external.

## One-time Oracle preparation

The VM should be Ubuntu ARM64 with Docker Engine, the Docker Compose v2 plugin, and SSH access. The workflow deploys to `/home/ubuntu/basarat`; it does not clone the repository onto Oracle.

Create the deployment directory and download the tracked example as an ignored runtime environment file:

```bash
mkdir -p ~/basarat/secrets
chmod 700 ~/basarat/secrets
cd ~/basarat
curl --fail --silent --show-error --location \
  https://raw.githubusercontent.com/iahmedd-k/Basarat-fyp-official/main/backend/.env.example \
  --output .env
chmod 600 .env
nano .env
```

Do not use or upload a development machine's `.env`. Set at least:

- `ENVIRONMENT=production`, `DEBUG=false`, and a fresh random `SECRET_KEY` of at least 32 characters.
- `CLOUD_DATABASE_URL` to the production PostgreSQL URL. Use a TLS-enabled database connection where supported.
- `CORS_ORIGINS=["https://basarat.live","https://www.basarat.live"]` with the exact deployed frontend origin. Wildcards are only for development and are rejected in production.
- `ALLOWED_HOSTS=["api.basarat.live","193.123.84.223","app"]`, or the actual public API hostname.
- Include `app` in `ALLOWED_HOSTS` so Prometheus can scrape the API using its Compose service hostname.
- `FIREBASE_PROJECT_ID` to the Firebase project ID.

Compose points API and Celery at the included Redis container and explicitly disables the external Redis fallback; do not set Redis URLs to localhost or an external service. The API is published on host port 8000. Prometheus (9090) and Grafana (3000) bind to loopback only; access them with an SSH tunnel rather than exposing these ports publicly. Restrict Oracle ingress to the required sources and configure TLS before sending credentials or production user traffic.

## GitHub Actions configuration

Create the `oracle-production` GitHub Actions environment and add these environment secrets:

- `ORACLE_HOST`: Oracle VM public IP or DNS name.
- `ORACLE_USER`: SSH account (normally `ubuntu`).
- `ORACLE_SSH_PRIVATE_KEY`: a deployment SSH private key authorized for that account. Add it through GitHub's secret UI; never commit it.
- `ORACLE_SSH_KNOWN_HOSTS`: the verified SSH host-key line for the VM. Verify the fingerprint through a trusted channel; do not use an unverified `ssh-keyscan` result.
- `ORACLE_GHCR_TOKEN`: a GitHub token with read-only `read:packages` access for the published package.
- `PROMETHEUS_METRICS_USERNAME`: metrics scrape username, 1–64 characters using only letters, numbers, dots, underscores, and hyphens (for example, `metrics_reader`; no spaces or quotes).
- `PROMETHEUS_METRICS_PASSWORD`: randomly generated 32–128-character hexadecimal scrape password.
- `PROMETHEUS_METRICS_HOST_HEADER`: the production API hostname or IP, without a port, and included in `ALLOWED_HOSTS`.
- `GRAFANA_ADMIN_PASSWORD`: a separate randomly generated 32–128-character hexadecimal Grafana admin password.

The workflow uses `GITHUB_TOKEN` with `packages: write` to publish the image. The Oracle host uses `ORACLE_GHCR_TOKEN` to pull the private GHCR package.

Generate independent passwords with `openssl rand -hex 32` and save each as a secret in the `oracle-production` GitHub Actions environment. On each deployment, the workflow transfers them over SSH into `/home/ubuntu/basarat/.env.monitoring` with owner-only permissions. The file is not part of the image or repository. The workflow deploys the API and monitoring stack together from the versioned Compose/configuration files.

## Firebase credential delivery

Firebase is enabled in the Oracle Compose deployment. Before transferring the service-account key, the application can start but push delivery remains unavailable until the credential file exists. Transfer the Firebase Admin service-account JSON out-of-band to:

```text
/home/ubuntu/basarat/secrets/firebase-admin.json
```

Restrict it to the app's container UID and owner-only permissions:

```bash
sudo chown 1000:1000 ~/basarat/secrets/firebase-admin.json
sudo chmod 600 ~/basarat/secrets/firebase-admin.json
```

The secrets directory is mounted read-only into only the API and Celery worker. The key is excluded from the Docker build context and must never be committed, included in `.env`, or added to the image. After transferring or rotating the key, restart the API and worker:

```bash
cd ~/basarat
docker compose --env-file .env -f docker-compose.yml restart app celery-worker
```

## Deploy and verify

After the VM `.env` and GitHub environment secrets are ready, push a change to `main` or manually run the workflow. It builds and pushes the ARM64 image under the commit SHA, uploads the Compose file, runs the one-shot migrations, and waits for the API and Redis health checks.

On the VM, inspect the deployment with:

```bash
cd ~/basarat
docker compose --env-file .env --env-file .env.monitoring \
  -f docker-compose.yml -f docker-compose.monitoring.yml ps
docker compose --env-file .env --env-file .env.monitoring \
  -f docker-compose.yml -f docker-compose.monitoring.yml \
  logs --tail=100 app celery-worker celery-beat redis prometheus grafana
curl --fail http://127.0.0.1:8000/health
```

The monitoring UI ports bind to loopback on the VM. From your local terminal, open an SSH tunnel:

```bash
ssh -N -L 9090:127.0.0.1:9090 -L 3000:127.0.0.1:3000 ubuntu@193.123.84.223
```

Then open `http://localhost:9090` for Prometheus and `http://localhost:3000` for Grafana (`admin` and `GRAFANA_ADMIN_PASSWORD`). The provisioned **Basarat API Overview** dashboard is available after sign-in. Do not add public ingress rules for ports 3000 or 9090. The `/metrics` endpoint on API port 8000 is currently unauthenticated; configure authenticated scraping or restrict access before using it with sensitive traffic.

Prometheus scrapes the API at `app:8000`; the API's `ALLOWED_HOSTS` must include `app`. Prometheus does not permit setting the reserved `Host` header through `http_headers`.

The workflow's deploy job must complete successfully before the release is considered deployed.
