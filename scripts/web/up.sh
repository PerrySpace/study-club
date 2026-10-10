#!/usr/bin/env bash
# 启动 web 容器（host 网络，监听 WEB_PORT，默认 8080）。
set -euo pipefail

source "$(dirname "$0")/../lib/common.sh"

cd "$(repo_root)"

load_env

COMPOSE_FILE="deploy/web/docker-compose.yml"
PORT="${WEB_PORT:-8080}"

require_cmd docker

log_info "启动 web 容器（端口 ${PORT}）"
docker compose -f "$COMPOSE_FILE" up -d

log_info "已启动。访问： http://localhost:${PORT}/"
LAN="$(lan_ip)"
if [ -n "$LAN" ]; then
  log_info "局域网访问（手机 / iPad 同 WiFi）： http://${LAN}:${PORT}/"
else
  log_warn "未探测到局域网 IP（可手动执行：ipconfig getifaddr en0）"
fi
log_warn "若修改了 VITE_* 变量，需要重新构建： scripts/web/build.sh"
