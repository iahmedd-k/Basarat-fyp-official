# EC2 API Blue/Green Deployment (Historical Architecture)

> [!NOTE]
> **Historical Reference**: This document records the initial AWS EC2 x86_64 blue-green rollout specification. For the active production deployment running on **Oracle Cloud Infrastructure (OCI) ARM64** with GitHub Actions and GHCR, refer to **[oracle-deployment.md](file:///d:/FYP/Basarat-fyp-official/docs/07-deployment/oracle-deployment.md)** and **[ci-cd.md](file:///d:/FYP/Basarat-fyp-official/docs/07-deployment/ci-cd.md)**.

## Deployment shape

The API is the only blue/green service. It runs in two named slots, `basarat-api-blue` and `basarat-api-green`, bound only to `127.0.0.1:8001` and `127.0.0.1:8002`. Host Nginx owns the existing public port `8000` and proxies HTTP, SSE, and WebSocket requests to the active slot.

The deployment scripts reuse the existing `backend_default` network and `backend_market-data`, `backend_feature-data`, `backend_gru-candidates`, `backend_xgb-candidates`, and `backend_training-reports` volumes. PostgreSQL remains the existing managed database. Redis is represented by one Compose service and reuses the existing `backend_redis-data` volume. API releases never create or recreate PostgreSQL or Redis. Worker and Beat are updated in place, one at a time, after the API is healthy; they are never duplicated.

The legacy API container owns public port 8000. Nginx has been installed on the host but remains stopped and disabled until the first cutover. That one-time handoff starts and checks the new API first, disables the package welcome-site config, then stops the legacy container and starts Nginx on 8000. This handoff may cause a brief interruption. Subsequent API switches are Nginx reloads and keep both API slots running during stabilization.

At inspection, the EC2 host had 2 vCPUs, 7.6 GiB RAM, and a 30 GB root disk (7.4 GB used). The previous backend image was about 3.06 GB. The new build excludes the 11.5 MB local data tree and non-serving model files, but TensorFlow/XGBoost remain substantial runtime dependencies.

## GitHub and AWS setup

Create an immutable ECR repository (run once from an AWS-authenticated administrator shell):

```bash
aws ecr create-repository \
  --repository-name "$ECR_REPOSITORY" \
  --image-tag-mutability IMMUTABLE \
  --image-scanning-configuration scanOnPush=true \
  --region "$AWS_REGION"
```

Set these GitHub repository variables:

- `AWS_REGION`
- `ECR_REPOSITORY`

Set this GitHub repository secret:

- `AWS_ROLE_ARN`: a GitHub OIDC role allowed to assume from both the `main` branch build job and the `production` environment deploy job. The role needs ECR push and pull actions for this repository (`ecr:GetAuthorizationToken` on `*`; `ecr:BatchCheckLayerAvailability`, `ecr:CompleteLayerUpload`, `ecr:GetDownloadUrlForLayer`, `ecr:InitiateLayerUpload`, `ecr:PutImage`, `ecr:UploadLayerPart`, and `ecr:BatchGetImage` on the repository).

The OIDC trust policy must allow the repository's `refs/heads/main` subject for the build job and its `environment:production` subject for the deploy job. Restrict the GitHub `production` environment to the `main` branch. The deploy job assumes the same role before logging into ECR; no EC2 instance-profile AWS credentials are used. The existing EC2 GitHub runner must retain labels `self-hosted`, `linux`, `x64`, and `basarat-demo`, have Docker access, and have passwordless sudo for Nginx installation/reload. The workflow builds on GitHub-hosted Linux; the EC2 job only logs in, pulls, migrates, and deploys.

Application secrets and runtime settings belong in `/opt/basarat/backend/.env` on EC2, not in GitHub Actions. The deploy job passes only AWS deployment configuration and the immutable image URI; the test job uses isolated dummy settings. During blue/green deploy, the candidate starts with the active container's environment; keys present in the EC2 `.env` but absent from that container are added to the candidate environment. Add a new key to the EC2 `.env` before deploying the image that consumes it. Existing keys continue using the active container's value, so changing or rotating an existing key requires an explicit runtime configuration update/recreation rather than only adding another line to `.env`.

Do not set an ECR lifecycle rule that expires SHA-tagged releases needed for rollback. ECR tag immutability prevents a published commit tag from being overwritten. The deploy script keeps the active and immediate rollback images tagged locally and removes only the older local image after successful stabilization; ECR retains all SHA-tagged releases.

## Local checks

From the repository root on Windows PowerShell:

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-test.lock
$env:POSTGRES_PASSWORD = 'choose-a-local-only-password'

$env:ENVIRONMENT = 'test'
$env:SECRET_KEY = 'local-ci-only-signing-key-at-least-32-chars'
$env:DATABASE_URL = 'postgresql+asyncpg://local:local@127.0.0.1:5432/local_only'
$env:DATABASE_URL_SYNC = 'postgresql+psycopg2://local:local@127.0.0.1:5432/local_only'
$env:REDIS_ENABLED = 'false'
$env:USE_CELERY = 'false'
$env:TESTING = 'true'
.\.venv\Scripts\python.exe -m compileall -q app
.\.venv\Scripts\python.exe -m pytest -c pytest.ini tests/api tests/unit -q

docker compose -f docker-compose.yml config --quiet
$env:BACKEND_IMAGE = '123456789012.dkr.ecr.us-east-2.amazonaws.com/basarat-api:validation'
docker compose -f docker-compose.production.yml config --quiet

docker buildx build --load -f dockerfile -t basarat-backend:local .
docker run --rm --name basarat-api-local -p 127.0.0.1:8010:8000 `
  -e SECRET_KEY='local-smoke-only-signing-key-32-characters' `
  -e DATABASE_URL='postgresql+asyncpg://local:local@127.0.0.1:5432/local_only' `
  -e DATABASE_URL_SYNC='postgresql+psycopg2://local:local@127.0.0.1:5432/local_only' `
  -e REDIS_ENABLED=false -e USE_CELERY=false -e FIREBASE_ENABLED=false `
  basarat-backend:local
```

The development Compose file requires `POSTGRES_PASSWORD`; keep it in the ignored `.env` or set it only in the current shell as above. URL-encode reserved characters if that password is included in a database URL. In a second terminal, verify `curl.exe -f http://127.0.0.1:8010/health`. The command above intentionally does not use the repository `.env` for the API smoke container and does not require PostgreSQL or Redis to answer `/health`. It loads the tracked model artifacts at API startup. Root-level tests include live-production/live-server audits and are excluded from CI. The full non-live API/unit suite currently has failures in portfolio, recommendation, authorization, sentiment, alert-evaluation, and model tests; the workflow gates deployment on the entire API/unit set, so releases remain blocked until those failures are resolved.

Regenerate locks after changing dependencies (requires `uv==0.12.21`):

```bash
python -m uv pip compile --universal --python-version 3.11 --generate-hashes --no-annotate -o requirements.lock requirements.txt
python -m uv pip compile --universal --python-version 3.11 --generate-hashes --no-annotate -o requirements-test.lock requirements-test.txt
```

## EC2 deployment

The push to `main` workflow runs the isolated tests, builds an image tagged with the full Git SHA, pushes it to ECR, then dispatches deployment to the existing EC2 runner. The EC2 deploy script runs `alembic upgrade head` as a one-shot container using the current API environment, starts the inactive API slot, and polls its lightweight `/health` endpoint. Before health succeeds, it does not stop the current API or change Nginx. On failure it removes only the failed candidate container and exits unsuccessfully.

After the candidate passes, the script atomically changes Nginx's active upstream and checks the public local route. It keeps the old API through a 60-second stabilization window, then updates the existing Celery worker and Beat sequentially in place (never in parallel), allowing the worker up to two hours to finish an active task. `/health/ready` must pass after the new Beat heartbeat arrives. Only then is the old API container removed; its immutable image remains available for rollback. PostgreSQL and Redis are not part of these recreate commands.

Manual deploy command on EC2 (normally the workflow runs this):

```bash
IMAGE_URI="<account>.dkr.ecr.<region>.amazonaws.com/<repository>:<40-character-git-sha>"
GIT_SHA="<40-character-git-sha>"
REGISTRY="${IMAGE_URI%%/*}"
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$REGISTRY"
bash /opt/basarat/deploy/ec2/deploy-api.sh "$IMAGE_URI" "$GIT_SHA"
```

Rollback command on EC2:

```bash
bash /opt/basarat/deploy/ec2/rollback-api.sh
```

Rollback deploys the recorded prior image (cached locally or pulled by its immutable tag), checks it on the inactive loopback port, then switches Nginx. It does not rebuild an image or downgrade the database. Database migrations must be backward-compatible expand/contract changes; a schema downgrade is intentionally not attempted.

The API deployment does not restart Redis. The current Redis container predates this Compose file and has no log-size options; the updated production Compose now represents that same single service and explicitly references `backend_redis-data`. To apply the new Redis log policy once during a maintenance window, using the same existing volume:

```bash
cd /opt/basarat/backend
BACKEND_IMAGE="<an-immutable-ECR-image-URI>" \
  docker compose -f docker-compose.production.yml up -d --no-deps --force-recreate redis
```

This is an in-place Redis restart, not part of API deployment, and can briefly interrupt Redis clients. Do not use `down`, change the volume name, or add another Redis service.

## Docker storage and logs

The maintenance script reports image, container, volume, build-cache, JSON-log, and filesystem usage without changing anything:

```bash
bash /opt/basarat/deploy/ec2/cleanup-docker.sh
```

Explicitly opt in to safe cleanup:

```bash
bash /opt/basarat/deploy/ec2/cleanup-docker.sh --apply
```

`--apply` removes stopped containers, dangling images, and unused build cache only. It never removes running containers, tagged rollback images, volumes, PostgreSQL data, or application log files. Docker-managed JSON logs for new API/worker/Beat/Redis containers are limited to 10 MB × 3 files. Existing containers receive new logging settings only when individually recreated. Nginx logs under `/var/log/nginx` are rotated daily, compressed, and retained for 14 rotations by `/etc/logrotate.d/basarat-nginx`.

## Assumptions and risks

- The current EC2 Docker network and named volumes exist under the inspected `backend_*` names. Scripts fail rather than silently create replacement state if required API volumes or the network are missing.
- The Firebase file is mode 600 and owned by `ec2-user` (UID 1000); the production API image uses UID 1000 so it can read the existing read-only bind mount. Runtime `TRUSTED_PROXY_IPS` includes loopback and the exact `backend_default` Docker gateway; Nginx overwrites `X-Forwarded-For` with its peer address.
- Nginx applies a 20-request/second per-IP limit with a burst of 50 and caps each source IP at 20 concurrent connections. This also counts long-lived WebSocket connections; review the cap if many users share a NAT address.
- Two API containers are limited to 2 GiB each and 1 CPU each. The EC2 host has 2 vCPUs and 7.6 GiB RAM; watch memory during real forecast traffic and adjust if the worker is training.
- TensorFlow/XGBoost remain large runtime dependencies; generated datasets and non-serving models are excluded from the image, but the ML runtime still makes the image substantial.
- The current public API is HTTP on port 8000. This Nginx config preserves that address and supports WebSockets/SSE, but does not add TLS because no domain/certificate was provided. Restrict SSH to known sources and plan TLS termination before handling sensitive traffic.
- Keep the previous API image in ECR and locally; do not prune tagged SHA/baseline images required for rollback.
- The uploaded `.env` and PEM are ignored by Git and are not copied into the Docker build context. Rotate the credentials previously exposed in chat and keep runtime values only in the EC2 secret file/instance role.
