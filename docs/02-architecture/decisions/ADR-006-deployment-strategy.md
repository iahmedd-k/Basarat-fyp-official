# ADR-006: Containerized CI/CD Deployment on Oracle Cloud Infrastructure (OCI)

## Status
Accepted / Implemented

## Context
Production deployment requires high-performance, cost-effective, and reproducible containerized updates with health check verification and zero unhandled downtime.

## Decision
Deploy containerized backend fleet on **Oracle Cloud Infrastructure (OCI) Ampere A1 ARM64 VM** using **GitHub Actions**, **GitHub Container Registry (GHCR)** for immutable image publishing, and SSH-based automated rollout with Alembic database migrations and health probe validation.

## Alternatives Considered
- **AWS EC2 x86_64**: Higher ongoing cost and lower memory allocation on standard free tiers.
- **Kubernetes (EKS/OKE)**: Excessive architectural complexity and overhead for single-node container orchestration.
- **AWS ECS/Fargate**: Significantly higher runtime costs.

## Consequences
- Cost-efficient production compute on high-performance 4-core 24GB ARM64 instance.
- Immutable Docker container images published to GHCR with git commit SHA tagging.
- Automated migrations and health verification (`/health`, `/api/v1/health/ready`) before cutover.

## Current Implementation
- Production Host: `193.123.84.223` (Oracle Cloud Infrastructure)
- Workflow: `.github/workflows/deploy-oracle.yml`
- Docker Compose: `docker-compose.production.yml`
- Documentation: `docs/07-deployment/oracle-deployment.md`
