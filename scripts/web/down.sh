#!/usr/bin/env bash
# 停止并移除 web 容器。
set -euo pipefail

source "$(dirname "$0")/../lib/common.sh"

cd "$(repo_root)"

load_env

COMPOSE_FILE="deploy/web/docker-compose.yml"

require_cmd docker

log_info "停止 web 服务"
docker compose -f "$COMPOSE_FILE" down

log_info "已停止"
