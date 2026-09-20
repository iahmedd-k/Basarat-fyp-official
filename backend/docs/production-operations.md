# Production operations

## Required environment

Set `ENVIRONMENT=production`, `DEBUG=false`, a random 32+ character `SECRET_KEY`, explicit JSON `CORS_ORIGINS`, production PostgreSQL/Redis URLs (with authentication and TLS where supported), and `TRUSTED_PROXY_IPS` containing only the ingress proxy addresses.

Password reset requires `SMTP_HOST`, `SMTP_FROM_EMAIL`, and `PASSWORD_RESET_URL`. The reset URL must be the Android deep link or a trusted HTTPS reset page and can contain `{token}`.

## Firebase Cloud Messaging for Android

1. Create a Firebase project and add the Android application using its exact package name and signing certificate fingerprints.
2. Create a least-privilege Firebase service account, download its JSON key, and store it only in the deployment secret manager. Never commit it.
3. Mount the key read-only into the API and Celery worker containers.
4. Set `FIREBASE_ENABLED=true`, `FIREBASE_CREDENTIALS_PATH=/run/secrets/firebase-service-account.json`, and `FIREBASE_PROJECT_ID=<project-id>`.
5. Android obtains the FCM token and calls `POST /api/v1/devices/register` after login and whenever Firebase rotates the token. On logout, call `DELETE /api/v1/devices/{device_id}`.

Only `platform=android` tokens are used for FCM delivery. Delivery happens asynchronously through Celery. Invalid FCM registration tokens are automatically deactivated. A successful device-registration response confirms storage only; it is not proof that Firebase delivered a message.

## Deployment gates

1. Run `alembic upgrade head` as a dedicated, one-shot migration job before API/worker rollout.
2. Run API, worker, and beat from immutable images; never use source bind mounts or Uvicorn reload in production.
3. Keep PostgreSQL and Redis private to the service network, use unique credentials, and enable backups plus restore drills.
4. Configure ingress TLS, host allowlisting, request IDs, metrics, logs, health alerts, and a rollback procedure.
5. Run the complete API/worker integration suite against ephemeral PostgreSQL and Redis in CI before every release.
