#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

IMAGE="${1:?Usage: bootstrap-bluegreen.sh <immutable-image-uri> <git-sha>}"
GIT_SHA="${2:?Usage: bootstrap-bluegreen.sh <immutable-image-uri> <git-sha>}"
[[ "$IMAGE" != *:latest ]] || die "Refusing mutable :latest image tag"
[[ "$GIT_SHA" =~ ^[0-9a-f]{40}$ ]] || die "Expected a 40-character Git commit SHA"
[[ "$IMAGE" == *":$GIT_SHA" ]] || die "Image URI must be tagged with the supplied Git SHA"
[[ ! -e "$STATE_DIR/active-state" ]] || die "Blue/green is already initialized; use deploy-api.sh"

require_command docker
require_command curl
require_runtime_resources

legacy_container="$(docker ps -q --filter label=com.docker.compose.project=backend --filter label=com.docker.compose.service=app | head -n 1)"
[[ -n "$legacy_container" ]] || die "Could not find the currently running Compose API container"
old_image_id="$(docker inspect --format '{{.Image}}' "$legacy_container")"
old_short_id="${old_image_id#sha256:}"
old_short_id="${old_short_id:0:12}"
baseline_image="basarat-backend:baseline-${old_short_id}"
docker image tag "$old_image_id" "$baseline_image"

env_file="$(mktemp "$STATE_DIR/runtime-env.XXXXXX")"
trap 'rm -f "$env_file"' EXIT
write_runtime_env "$legacy_container" "$env_file"

log "Pulling immutable API image $IMAGE"
docker pull "$IMAGE"
run_migrations "$IMAGE" "$env_file"

new_container="$(start_api green "$IMAGE" "$env_file")"
if ! wait_for_health http://127.0.0.1:8002/health 60 2; then
    docker rm -f "$new_container" >/dev/null 2>&1 || true
    die "New API failed health checks; the legacy API was not stopped and Nginx was not switched"
fi

if ! install_nginx_config || ! write_upstream green || ! sudo nginx -t; then
    docker rm -f "$new_container" >/dev/null 2>&1 || true
    die "Nginx setup failed before the legacy API was stopped; the original API remains active"
fi

log "Handing public port 8000 from the legacy API to Nginx; this is a one-time cutover"
docker update --restart=no "$legacy_container" >/dev/null
docker stop --time 30 "$legacy_container" >/dev/null
if ! sudo systemctl enable --now nginx || ! wait_for_health http://127.0.0.1:8000/health 15 2; then
    sudo systemctl stop nginx >/dev/null 2>&1 || true
    docker update --restart=unless-stopped "$legacy_container" >/dev/null 2>&1 || true
    docker start "$legacy_container" >/dev/null 2>&1 || true
    docker rm -f "$new_container" >/dev/null 2>&1 || true
    die "Initial proxy cutover failed; restored the original API container"
fi

rollback_initial() {
    if DEPLOY_LOCK_HELD=1 bash "$SCRIPT_DIR/deploy-api.sh" --rollback; then
        docker rm -f "$legacy_container" >/dev/null 2>&1 || true
        return 0
    fi
    sudo systemctl stop nginx >/dev/null 2>&1 || true
    docker update --restart=unless-stopped "$legacy_container" >/dev/null 2>&1 || true
    docker start "$legacy_container" >/dev/null 2>&1 || return 1
    docker rm -f "$new_container" >/dev/null 2>&1 || true
    return 0
}

save_state green "$IMAGE" "$baseline_image"
log "Blue/green initialized. Keeping the stopped legacy container and baseline image during stabilization."
sleep "${STABILIZATION_SECONDS:-60}"
if ! wait_for_health http://127.0.0.1:8000/health 15 2; then
    rollback_initial || die "Initial stabilization and blue/green rollback failed; restored the legacy API directly"
    die "Initial proxy stabilization failed; rolled traffic back to the baseline image"
fi

if ! update_background_services "$IMAGE"; then
    rollback_initial || die "Worker/Beat update and API rollback failed; restored the legacy API directly"
    die "Worker/Beat update failed; rolled API traffic back to the baseline image"
fi

if ! wait_for_health http://127.0.0.1:8000/health/ready 90 2; then
    rollback_initial || die "Readiness rollback failed; restored the legacy API directly"
    die "Readiness failed after Worker/Beat update; rolled API traffic back"
fi

docker rm "$legacy_container" >/dev/null
log "Initial cutover stabilized. The legacy container is removed; its baseline image remains for rollback."
