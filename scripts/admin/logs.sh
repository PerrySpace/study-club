#!/usr/bin/env bash
# 跟随查看 admin 容器日志。
set -euo pipefail

source "$(dirname "$0")/../lib/common.sh"

cd "$(repo_root)"

load_env

COMPOSE_FILE="deploy/admin/docker-compose.yml"
TAIL="${TAIL:-200}"

require_cmd docker

log_info "跟随 admin 日志（最近 ${TAIL} 行，Ctrl+C 退出）"
docker compose -f "$COMPOSE_FILE" logs -f --tail "$TAIL"
