#!/usr/bin/env bash
# 停止并移除 admin 容器（管理后台建议「按需启动」，不用时常驻）。
set -euo pipefail

source "$(dirname "$0")/../lib/common.sh"

cd "$(repo_root)"

load_env

COMPOSE_FILE="deploy/admin/docker-compose.yml"

require_cmd docker

log_info "停止 admin 服务"
docker compose -f "$COMPOSE_FILE" down

log_info "已停止"
