#!/usr/bin/env bash
# 一键起全栈（按依赖顺序：db → api → web），并做健康检查。
#
# 各服务仍是**各自独立编排**（deploy/mongo、deploy/api、deploy/web 三份 compose），
# 本脚本只是按顺序调用它们，不改变「单独构建」的设计。
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"

cd "$(repo_root)"
load_env
require_cmd docker

API_HEALTH="http://127.0.0.1:${API_PORT:-8000}${API_PREFIX:-/api/v1}/health"
WEB_PORT="${WEB_PORT:-8080}"

log_info "① 启动 MongoDB"
"$(repo_root)/scripts/db/start.sh"

log_info "② 启动 api"
"$(repo_root)/scripts/api/up.sh"

log_info "等待 api 就绪…"
wait_for_http "$API_HEALTH" 40 || die "api 未就绪，查看：scripts/api/logs.sh"

log_info "③ 启动 web"
"$(repo_root)/scripts/web/up.sh" || log_warn "web 启动失败（可先只跑 api + 本地 dev server）"

log_success "全栈已启动"
log_dim "  web : http://localhost:${WEB_PORT}/"
log_dim "  api : http://localhost:${API_PORT:-8000}${API_PREFIX:-/api/v1}"
log_dim "  docs: http://localhost:${API_PORT:-8000}/docs"
LAN="$(lan_ip)"
if [ -n "$LAN" ]; then
  log_dim "  局域网（手机 / iPad 同 WiFi）: http://${LAN}:${WEB_PORT}/"
fi
log_dim "  首次运行若数据库为空，请执行： scripts/seed/seed.sh"
log_dim "  查看状态与全部访问地址： scripts/dev/status.sh"
