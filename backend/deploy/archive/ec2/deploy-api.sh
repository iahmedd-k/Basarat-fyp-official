#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

ROLLBACK=0
if [[ "${1:-}" == "--rollback" ]]; then
    ROLLBACK=1
    [[ -s "$STATE_DIR/active-state" ]] || die "Blue/green is not initialized"
    IFS=$'\t' read -r _ _ IMAGE < "$STATE_DIR/active-state"
    [[ -n "$IMAGE" ]] || die "No previous image is recorded"
else
    IMAGE="${1:?Usage: deploy-api.sh <immutable-image-uri> <git-sha> | --rollback}"
    GIT_SHA="${2:?Usage: deploy-api.sh <immutable-image-uri> <git-sha> | --rollback}"
    [[ "$GIT_SHA" =~ ^[0-9a-f]{40}$ ]] || die "Expected a 40-character Git commit SHA"
    [[ "$IMAGE" == *":$GIT_SHA" ]] || die "Image URI must be tagged with the supplied Git SHA"
    [[ "$IMAGE" != *:latest ]] || die "Refusing mutable :latest image tag"
fi

require_command docker
require_command curl
require_command flock
require_runtime_resources
install -d -m 0700 "$STATE_DIR"
if [[ "${DEPLOY_LOCK_HELD:-0}" != 1 ]]; then
    exec 9>"$STATE_DIR/deploy.lock"
    flock -n 9 || die "Another API deployment is already running"
fi

if [[ ! -s "$STATE_DIR/active-state" ]]; then
    (( ROLLBACK == 0 )) || die "Blue/green is not initialized; rollback is unavailable"
    export DEPLOY_LOCK_HELD=1
    exec "$SCRIPT_DIR/bootstrap-bluegreen.sh" "$IMAGE" "$GIT_SHA"
fi

IFS=$'\t' read -r active_slot active_image prior_rollback_image < "$STATE_DIR/active-state"
inactive_slot="$(other_slot "$active_slot")"
active_container="$(api_name "$active_slot")"
inactive_container="$(api_name "$inactive_slot")"
active_port="$(api_port "$active_slot")"
inactive_port="$(api_port "$inactive_slot")"

env_file="$(mktemp "$STATE_DIR/runtime-env.XXXXXX")"
trap 'rm -f "$env_file"' EXIT
write_runtime_env "$active_container" "$env_file"

if (( ROLLBACK == 1 )) && docker image inspect "$IMAGE" >/dev/null 2>&1; then
    log "Using the already-pulled rollback image $IMAGE"
elif [[ "$IMAGE" == basarat-backend:baseline-* ]]; then
    docker image inspect "$IMAGE" >/dev/null || die "Local rollback image is missing: $IMAGE"
else
    docker pull "$IMAGE"
fi
if (( ROLLBACK == 0 )); then
    run_migrations "$IMAGE" "$env_file"
else
    log "Rollback requested; leaving the database schema unchanged"
fi

if docker container inspect "$inactive_container" >/dev/null 2>&1; then
    docker rm -f "$inactive_container" >/dev/null
fi
new_container="$(start_api "$inactive_slot" "$IMAGE" "$env_file")"
if ! wait_for_health "http://127.0.0.1:${inactive_port}/health" 60 2; then
    docker rm -f "$new_container" >/dev/null 2>&1 || true
    die "New API failed health checks; active API and proxy route were left untouched"
fi

if switch_proxy "$inactive_slot"; then
    :
else
    switch_status=$?
    if (( switch_status == 1 )); then
        docker rm -f "$new_container" >/dev/null 2>&1 || true
        die "Nginx switch failed; the previous API remains active"
    fi
    die "Nginx switch and route restoration failed; both API containers were left running"
fi

if ! wait_for_health http://127.0.0.1:8000/health 30 2; then
    if ! switch_proxy "$active_slot"; then
        die "Post-switch health failed and proxy restoration failed; both API containers were left running"
    fi
    save_state "$active_slot" "$active_image" "$IMAGE"
    docker rm -f "$new_container" >/dev/null 2>&1 || true
    die "Post-switch health check failed; restored the previous API route"
fi

previous_image="$active_image"
save_state "$inactive_slot" "$IMAGE" "$previous_image"
log "API traffic now uses $inactive_slot ($IMAGE). Keeping $active_slot for rollback during stabilization."
sleep "${STABILIZATION_SECONDS:-60}"
if ! wait_for_health http://127.0.0.1:8000/health 15 2; then
    if ! switch_proxy "$active_slot"; then
        die "Stabilization failed and proxy restoration failed; both API containers were left running"
    fi
    save_state "$active_slot" "$active_image" "$IMAGE"
    docker rm -f "$new_container" >/dev/null 2>&1 || true
    die "Stabilization failed; restored the previous API route"
fi

if ! update_background_services "$IMAGE"; then
    log "Background service update failed; restoring the previous service image and API route"
    update_background_services "$active_image" || log "WARNING: restore worker/beat manually using $active_image"
    switch_proxy "$active_slot" || die "Could not restore the previous API route; both API containers remain running"
    save_state "$active_slot" "$active_image" "$IMAGE"
    docker rm -f "$new_container" >/dev/null 2>&1 || true
    die "Worker/Beat update failed; previous API route restored"
fi

if ! wait_for_health http://127.0.0.1:8000/health/ready 90 2; then
    update_background_services "$active_image" || log "WARNING: restore worker/beat manually using $active_image"
    switch_proxy "$active_slot" || die "Readiness failed and proxy restoration failed; both API containers were left running"
    save_state "$active_slot" "$active_image" "$IMAGE"
    docker rm -f "$new_container" >/dev/null 2>&1 || true
    die "Readiness failed after Worker/Beat update; previous API route restored"
fi

docker rm -f "$active_container" >/dev/null 2>&1 || true
if [[ -n "$prior_rollback_image" && "$prior_rollback_image" != "$active_image" && "$prior_rollback_image" != "$IMAGE" ]]; then
    docker image rm "$prior_rollback_image" >/dev/null 2>&1 || log "Keeping prior local image still referenced by another container: $prior_rollback_image"
fi
log "Stabilization passed. Removed only the previous API container; its immutable image remains available."
