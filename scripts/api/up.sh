#!/usr/bin/env bash
# 启动 api 容器（host 网络，监听 API_PORT，默认 8000）。
#
# 依赖：MongoDB 已在宿主的 MONGO_PORT 上就绪（scripts/db/start.sh）。
# 说明：api 是「可选增强」——即使它没起来，前端仍可完整使用（本地优先）。
set -euo pipefail

source "$(dirname "$0")/../lib/common.sh"

cd "$(repo_root)"

load_env

PORT="${API_PORT:-8000}"
PREFIX="${API_PREFIX:-/api/v1}"

require_cmd docker

log_info "启动 api 容器（端口 ${PORT}，前缀 ${PREFIX}）"
compose api up -d "$@"

log_info "等待 api 就绪…"
if wait_for_http "http://127.0.0.1:${PORT}${PREFIX}/health" 40; then
  log_success "api 已就绪"
  log_dim "  本机   : http://localhost:${PORT}${PREFIX}"
  log_dim "  接口文档: http://localhost:${PORT}/docs"
  LAN="$(lan_ip)"
  [ -n "$LAN" ] && log_dim "  局域网 : http://${LAN}:${PORT}${PREFIX}"
else
  log_warn "api 未在 40 秒内就绪，查看日志： scripts/api/logs.sh"
  log_warn "常见原因：MongoDB 未启动（scripts/db/start.sh）或 MONGODB_URI 配置不对"
  exit 1
fi
