# Backup and Recovery

## Current Backup Capabilities

### Database
- **Provider**: Supabase managed PostgreSQL
- **Automated backups**: Provided by Supabase (provider-dependent, typically daily)
- **Point-in-time recovery**: Available on Supabase Pro plan (not verifiable from codebase)
- **Application-level backups**: Not implemented

### Redis
- **Local Docker**: AOF persistence enabled in production compose (`--appendonly yes`)
- **Cloud (Upstash)**: Managed durability by provider
- **Backup**: Not separately backed up

### ML Model Artifacts
- **Storage**: Docker volumes (`gru-candidates`, `xgb-candidates`, `training-reports`)
- **Backup**: Not automatically backed up
- **Recovery**: Models can be retrained from data

### Configuration
- **`.env` files**: Not version-controlled (manual management)
- **Docker Compose**: Version-controlled in Git
- **Deployment scripts**: Version-controlled in Git

## Disaster Recovery

### Database Recovery
1. Restore from Supabase backup
2. Run `alembic upgrade head` to ensure schema is current
3. Data loss: Limited to period since last backup

### Application Recovery
1. Re-deploy from Git using CI/CD pipeline
2. Docker images available in ECR (tagged with Git SHA)
3. Previous image available for rollback

### Migration Rollback
- Alembic supports `downgrade` command
- Not automated in deployment process
- Manual intervention required

## Recommended Improvements

> **Not currently implemented:**

1. Automated database backup verification
2. ML model artifact backup to S3
3. `.env` file backup to AWS Secrets Manager
4. Documented RTO/RPO targets
5. Disaster recovery runbook
6. Regular backup restore testing
