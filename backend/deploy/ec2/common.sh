#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

DEPLOY_ROOT="${DEPLOY_ROOT:-/opt/basarat/deploy}"
BACKEND_ROOT="${BACKEND_ROOT:-/opt/basarat/backend}"
STATE_DIR="${STATE_DIR:-$DEPLOY_ROOT/state}"
DOCKER_NETWORK="${DOCKER_NETWORK:-backend_default}"
NGINX_ACTIVE="/etc/nginx/basarat-upstreams/active.conf"
NGINX_UPSTREAM_DIR="/etc/nginx/basarat-upstreams"
NGINX_SITE="/etc/nginx/conf.d/basarat-api.conf"
FIREBASE_HOST_FILE="$BACKEND_ROOT/secrets/basarat-4c25b-firebase-adminsdk-fbsvc-afef7aa7e3.json"
FIREBASE_CONTAINER_FILE="/app/secrets/basarat-4c25b-firebase-adminsdk-fbsvc-afef7aa7e3.json"

log() { printf '[basarat-deploy] %s\n' "$*"; }
die() { log "ERROR: $*" >&2; exit 1; }

require_command() {
    command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

require_runtime_resources() {
    docker network inspect "$DOCKER_NETWORK" >/dev/null 2>&1 || die "Docker network $DOCKER_NETWORK is missing. Refusing to create a second service network."
    docker volume inspect backend_market-data backend_feature-data backend_gru-candidates backend_xgb-candidates backend_training-reports >/dev/null 2>&1 \
        || die "One or more existing backend data volumes are missing. Refusing to create replacement volumes."
    [[ -f "$FIREBASE_HOST_FILE" ]] || die "Firebase credential file is missing: $FIREBASE_HOST_FILE"
}

write_runtime_env() {
    local source_container="$1"
    local destination="$2"
    local proxy_gateway
    docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$source_container" \
        | grep -Ev '^(HOSTNAME|PATH|HOME|container|PYTHON_VERSION|PYTHON_PIP_VERSION|PYTHON_SETUPTOOLS_VERSION|PYTHON_GET_PIP_URL|PYTHON_GET_PIP_SHA256|TRUSTED_PROXY_IPS)=' \
        > "$destination"
    [[ -r "$BACKEND_ROOT/.env" ]] || die "Runtime environment file is missing or unreadable: $BACKEND_ROOT/.env"
    # Add newly configured keys without overriding values already active in the current container.
    while IFS= read -r entry || [[ -n "$entry" ]]; do
        [[ "$entry" =~ ^[[:space:]]*(#|$) ]] && continue
        key="${entry%%=*}"
        [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
        if ! grep -q "^${key}=" "$destination"; then
            printf '%s\n' "$entry" >> "$destination"
        fi
    done < "$BACKEND_ROOT/.env"
    proxy_gateway="$(docker network inspect --format '{{range .IPAM.Config}}{{.Gateway}}{{end}}' "$DOCKER_NETWORK")"
    [[ -n "$proxy_gateway" ]] || die "Could not determine the Docker proxy gateway for $DOCKER_NETWORK"
    printf 'TRUSTED_PROXY_IPS=["127.0.0.1","%s"]\n' "$proxy_gateway" >> "$destination"
    chmod 600 "$destination"
    [[ -s "$destination" ]] || die "Could not export runtime settings from $source_container"
}

run_migrations() {
    local image="$1"
    local env_file="$2"
    log "Running the one-shot Alembic migration using $image"
    docker run --rm \
        --network "$DOCKER_NETWORK" \
        --env-file "$env_file" \
        --log-driver json-file \
        --log-opt max-size=10m \
        --log-opt max-file=3 \
        --entrypoint alembic \
        "$image" upgrade head
}

ensure_volume_owner() {
    local image="$1"
    local volume="$2"
    log "Checking UID 1000 ownership of $volume"
    docker run --rm \
        --network none \
        --user 0:0 \
        --mount "type=volume,src=$volume,dst=/volume" \
        --entrypoint sh \
        "$image" \
        -c 'if find /volume \( ! -user 1000 -o ! -group 1000 \) -print -quit | grep -q .; then chown -R 1000:1000 /volume; fi'
}

api_name() { printf 'basarat-api-%s' "$1"; }
api_port() {
    case "$1" in
        blue) printf '8001' ;;
        green) printf '8002' ;;
        *) die "Unknown API slot: $1" ;;
    esac
}
other_slot() {
    case "$1" in
        blue) printf 'green' ;;
        green) printf 'blue' ;;
        *) die "Unknown API slot: $1" ;;
    esac
}

start_api() {
    local slot="$1"
    local image="$2"
    local env_file="$3"
    local name port
    name="$(api_name "$slot")"
    port="$(api_port "$slot")"

    docker volume inspect backend_market-data backend_feature-data backend_gru-candidates backend_xgb-candidates backend_training-reports >/dev/null
    ensure_volume_owner "$image" backend_training-reports
    docker run --detach \
        --name "$name" \
        --label "com.basarat.role=api" \
        --label "com.basarat.slot=$slot" \
        --label "org.opencontainers.image.ref.name=$image" \
        --network "$DOCKER_NETWORK" \
        --publish "127.0.0.1:${port}:8000" \
        --env-file "$env_file" \
        --env RUN_STARTUP_MARKET_WARMUP=false \
        --restart unless-stopped \
        --memory 2g \
        --memory-reservation 768m \
        --cpus 1.0 \
        --log-driver json-file \
        --log-opt max-size=10m \
        --log-opt max-file=3 \
        --mount type=volume,src=backend_market-data,dst=/app/data/raw/ohlcv,readonly \
        --mount type=volume,src=backend_feature-data,dst=/app/data/features,readonly \
        --mount type=volume,src=backend_gru-candidates,dst=/app/models/gru_candidate,readonly \
        --mount type=volume,src=backend_xgb-candidates,dst=/app/models/xgb_candidate,readonly \
        --mount type=volume,src=backend_training-reports,dst=/app/data/reports \
        --mount "type=bind,src=$FIREBASE_HOST_FILE,dst=$FIREBASE_CONTAINER_FILE,readonly" \
        "$image" >/dev/null
    printf '%s\n' "$name"
}

wait_for_health() {
    local url="$1"
    local attempts="${2:-60}"
    local delay="${3:-2}"
    local attempt
    for ((attempt = 1; attempt <= attempts; attempt++)); do
        if curl --silent --show-error --fail --max-time 2 "$url" >/dev/null 2>&1; then
            log "Health check passed: $url"
            return 0
        fi
        sleep "$delay"
    done
    log "Health check timed out: $url"
    return 1
}

install_nginx_config() {
    command -v nginx >/dev/null 2>&1 || sudo dnf install -y nginx
    if [[ -f /etc/nginx/conf.d/default.conf ]]; then
        sudo mv /etc/nginx/conf.d/default.conf /etc/nginx/conf.d/default.conf.disabled
    fi
    sudo install -d -m 0755 "$NGINX_UPSTREAM_DIR"
    sudo install -m 0644 "$DEPLOY_ROOT/nginx/basarat-api.conf" "$NGINX_SITE"
    sudo install -m 0644 "$DEPLOY_ROOT/nginx/basarat-nginx.logrotate" /etc/logrotate.d/basarat-nginx
}

write_upstream() {
    local slot="$1"
    local port temp_link
    port="$(api_port "$slot")"
    sudo install -d -m 0755 "$NGINX_UPSTREAM_DIR"
    printf 'server 127.0.0.1:%s max_fails=2 fail_timeout=5s;\n' "$port" \
        | sudo tee "$NGINX_UPSTREAM_DIR/$slot.conf" >/dev/null
    temp_link="$NGINX_UPSTREAM_DIR/.active.$$.tmp"
    sudo ln -s "$NGINX_UPSTREAM_DIR/$slot.conf" "$temp_link"
    sudo mv -Tf "$temp_link" "$NGINX_ACTIVE"
}

switch_proxy() {
    local slot="$1"
    local previous_target=""
    if [[ -L "$NGINX_ACTIVE" ]]; then
        previous_target="$(readlink -f "$NGINX_ACTIVE")"
    fi

    write_upstream "$slot"
    if ! sudo nginx -t; then
        if [[ -n "$previous_target" ]]; then
            sudo ln -sfn "$previous_target" "$NGINX_ACTIVE"
        fi
        return 1
    fi

    if sudo systemctl is-active --quiet nginx; then
        if ! sudo systemctl reload nginx; then
            [[ -n "$previous_target" ]] && sudo ln -sfn "$previous_target" "$NGINX_ACTIVE"
            sudo nginx -t && sudo systemctl reload nginx || true
            return 1
        fi
    else
        if ! sudo systemctl enable --now nginx; then
            [[ -n "$previous_target" ]] && sudo ln -sfn "$previous_target" "$NGINX_ACTIVE"
            return 1
        fi
    fi

    if ! wait_for_health http://127.0.0.1:8000/health 15 2; then
        if [[ -n "$previous_target" ]]; then
            sudo ln -sfn "$previous_target" "$NGINX_ACTIVE"
            sudo nginx -t && sudo systemctl reload nginx || true
            if wait_for_health http://127.0.0.1:8000/health 15 2; then
                return 1
            fi
        fi
        return 2
    fi
}

save_state() {
    local slot="$1"
    local image="$2"
    local previous_image="$3"
    install -d -m 0700 "$STATE_DIR"
    printf '%s\t%s\t%s\n' "$slot" "$image" "$previous_image" > "$STATE_DIR/active-state.tmp"
    chmod 0600 "$STATE_DIR/active-state.tmp"
    mv -f "$STATE_DIR/active-state.tmp" "$STATE_DIR/active-state"
}

update_background_services() {
    local image="$1"
    BACKEND_IMAGE="$image" docker compose \
        --project-directory "$BACKEND_ROOT" \
        --env-file "$BACKEND_ROOT/.env" \
        -f "$BACKEND_ROOT/docker-compose.production.yml" \
        stop --timeout 30 celery-beat
    BACKEND_IMAGE="$image" docker compose \
        --project-directory "$BACKEND_ROOT" \
        --env-file "$BACKEND_ROOT/.env" \
        -f "$BACKEND_ROOT/docker-compose.production.yml" \
        stop --timeout 7200 celery-worker
    ensure_volume_owner "$image" backend_market-data
    ensure_volume_owner "$image" backend_feature-data
    ensure_volume_owner "$image" backend_gru-candidates
    ensure_volume_owner "$image" backend_xgb-candidates
    ensure_volume_owner "$image" backend_training-reports
    ensure_volume_owner "$image" backend_beat-state
    BACKEND_IMAGE="$image" docker compose \
        --project-directory "$BACKEND_ROOT" \
        --env-file "$BACKEND_ROOT/.env" \
        -f "$BACKEND_ROOT/docker-compose.production.yml" \
        --parallel 1 up -d --no-deps --force-recreate --scale celery-worker=1 celery-worker celery-beat
}
