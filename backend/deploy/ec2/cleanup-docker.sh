#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
    echo "Usage: $0 [--apply]"
    echo "Without --apply, only reports Docker and disk usage."
    exit 2
}

[[ $# -le 1 ]] || usage
mode="${1:-report}"
[[ "$mode" == report || "$mode" == --apply ]] || usage

show_usage() {
    echo
    echo "=== Docker images ==="
    docker image ls
    echo
    echo "=== Containers (including writable size) ==="
    docker ps -a --size
    echo
    echo "=== Volumes (listing only; never pruned) ==="
    docker volume ls
    echo
    echo "=== Docker totals, including build cache and volumes ==="
    docker system df -v
    echo
    echo "=== Container JSON log sizes ==="
    while IFS= read -r container; do
        [[ -n "$container" ]] || continue
        name="$(docker inspect --format '{{.Name}}' "$container" | sed 's#^/##')"
        log_path="$(docker inspect --format '{{.LogPath}}' "$container")"
        [[ -n "$log_path" && -f "$log_path" ]] || continue
        if sudo -n true >/dev/null 2>&1; then
            sudo -n du -h "$log_path" 2>/dev/null | awk -v name="$name" '{print $1 "\t" name "\t" $2}' || true
        else
            echo "permission required to measure $name log: $log_path"
        fi
    done < <(docker ps -aq)
    echo
    df -h /
}

show_usage

if [[ "$mode" == --apply ]]; then
    echo
    echo "Removing stopped containers, dangling images, and unused build cache only."
    docker container prune --force
    docker image prune --force
    docker builder prune --force
    echo
    echo "=== After cleanup ==="
    show_usage
else
    echo
    echo "Report only. Run with --apply to prune stopped containers, dangling images, and unused build cache."
fi
