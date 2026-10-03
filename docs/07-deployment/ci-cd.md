# CI/CD Pipeline

## Overview

The project uses GitHub Actions for continuous integration and deployment.

**Workflow file:** `.github/workflows/deploy-ec2.yml`

## Pipeline Triggers
- Push to `main` branch
- Manual dispatch (`workflow_dispatch`)

## Pipeline Stages

### Job 1: `test-build-push`
Runs on: `ubuntu-latest`
Timeout: 90 minutes

| Step | Description |
|------|-------------|
| Checkout | Clone repository |
| Setup Python 3.11.9 | Install runtime with pip caching |
| Install dependencies | Install from `requirements-test.lock` with hash verification |
| Compile modules | `python -m compileall -q backend/app` |
| Validate Alembic | Ensure single migration head |
| Run tests | `pytest backend/tests/api backend/tests/unit` |
| Validate deployment | Syntax-check deploy scripts; validate production Compose |
| AWS OIDC auth | Configure AWS credentials via GitHub OIDC |
| ECR login | Authenticate with Amazon ECR |
| Build & push | Docker build + push with Git SHA tag |
| Upload artifacts | Upload deployment bundle (compose, scripts, nginx) |

### Job 2: `deploy-api`
Runs on: `[self-hosted, linux, x64, basarat-demo]` (EC2 runner)
Timeout: 180 minutes
Environment: `production`

| Step | Description |
|------|-------------|
| Download bundle | Download deployment artifacts |
| Install scripts | Copy files to `/opt/basarat/` |
| AWS OIDC auth | Configure AWS credentials |
| Pull & deploy | Pull ECR image; run `deploy-api.sh` |

## Concurrency
- Group: `basarat-production`
- `cancel-in-progress: false` (deployments complete before starting next)

## Security
- **AWS OIDC**: Federated identity via `id-token: write` permission
- **No secrets in code**: AWS role ARN stored as GitHub secret
- **Immutable images**: Tagged with 40-char Git SHA; `:latest` rejected
- **Hash-verified dependencies**: `--require-hashes` on pip install

## Limitations
- No staging environment in pipeline
- No automated rollback trigger (manual via `--rollback` flag)
- No integration test database in CI (tests use mocks)
