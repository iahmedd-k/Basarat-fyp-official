# Production operations

For the EC2 immutable-image and API-only blue/green process, see [EC2 API blue/green deployment](ec2-blue-green-deployment.md).
For Oracle ARM64 deployment with Compose-managed Redis, see [Oracle ARM64 deployment](oracle-deployment.md).

## Required environment

Set `ENVIRONMENT=production`, `DEBUG=false`, a random 32+ character `SECRET_KEY`, a production PostgreSQL URL, and `TRUSTED_PROXY_IPS` containing only the ingress proxy addresses. Oracle Compose runs Redis privately inside the deployment network; it does not require an external Redis URL. Production/staging `CORS_ORIGINS` must list explicit frontend origins; wildcards are rejected. `ALLOWED_HOSTS` must list the deployed API hostname explicitly.

Password reset requires `SMTP_HOST`, `SMTP_FROM_EMAIL`, and `PASSWORD_RESET_URL`. The reset URL must be the Android deep link or a trusted HTTPS reset page and can contain `{token}`.

## Firebase Cloud Messaging for Android

1. Create a Firebase project and add the Android application using its exact package name and signing certificate fingerprints.
2. Create a least-privilege Firebase service account and transfer its JSON key to `/opt/basarat/secrets/firebase-admin.json` on the VM. Keep it outside the repository, restrict host permissions, and never commit or copy it into the image.
3. Production Compose mounts the key read-only into the API and Celery worker at `/run/secrets/firebase-service-account.json`. Create the host file before starting Compose; it intentionally fails closed if the key is missing.
4. Production Compose enables Firebase and sets `FIREBASE_CREDENTIALS_PATH=/run/secrets/firebase-service-account.json`. Set `FIREBASE_PROJECT_ID=<project-id>` in the VM's ignored `.env` file.
5. Android obtains the FCM token and calls `POST /api/v1/devices/register` after login and whenever Firebase rotates the token. On logout, call `DELETE /api/v1/devices/{device_id}`.

Only `platform=android` tokens are used for FCM delivery. Delivery happens asynchronously through Celery. Invalid FCM registration tokens are automatically deactivated. A successful device-registration response confirms storage only; it is not proof that Firebase delivered a message.

## Deployment gates

1. Run `alembic upgrade head` as a dedicated, one-shot migration job before API/worker rollout.
2. Run API, worker, and beat from immutable images; never use source bind mounts or Uvicorn reload in production.
3. Keep PostgreSQL and Redis private to the service network, use unique credentials, and enable backups plus restore drills.
4. Configure ingress TLS, host allowlisting, request IDs, metrics, logs, health alerts, and a rollback procedure.
5. Run the complete API/worker integration suite against ephemeral PostgreSQL and Redis in CI before every release.
