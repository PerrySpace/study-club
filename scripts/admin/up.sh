#!/usr/bin/env bash
# 启动管理后台容器（host 网络，监听 ADMIN_PORT，默认 8081）。
set -euo pipefail

source "$(dirname "$0")/../lib/common.sh"

cd "$(repo_root)"

load_env

COMPOSE_FILE="deploy/admin/docker-compose.yml"
PORT="${ADMIN_PORT:-8081}"

require_cmd docker

log_info "启动 admin 容器（端口 ${PORT}）"
docker compose -f "$COMPOSE_FILE" up -d

log_info "已启动。访问： http://localhost:${PORT}/"
LAN="$(lan_ip)"
if [ -n "$LAN" ]; then
  log_info "局域网访问： http://${LAN}:${PORT}/"
fi
log_warn "管理后台是内部工具，请勿暴露到公网；用完可执行： scripts/admin/down.sh"
log_warn "若修改了 VITE_API_BASE_URL 或 ADMIN_PORT，需要重新构建： scripts/admin/build.sh"
