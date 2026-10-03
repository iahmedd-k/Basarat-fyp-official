# ADR-006: Blue-Green Deployment on EC2

## Status
Accepted / Implemented

## Context
Production deployment needs zero-downtime updates with automatic rollback.

## Decision
Blue-green deployment on AWS EC2 with Nginx proxy switching, health check verification, automatic rollback, and immutable Docker images tagged with Git SHA.

## Alternatives
- **Rolling update**: Brief downtime during restart
- **Kubernetes**: Over-engineered for single-instance
- **AWS ECS/Fargate**: Higher cost

## Consequences
- Zero-downtime deployments
- Rollback via `deploy-api.sh --rollback`
- Stabilization period (60s) before removing old container
- Self-hosted GitHub Actions runner on EC2

## Current Implementation
- Deploy: `deploy/ec2/deploy-api.sh`
- Bootstrap: `deploy/ec2/bootstrap-bluegreen.sh`
- Nginx: `deploy/nginx/basarat-api.conf`
- CI/CD: `.github/workflows/deploy-ec2.yml`
