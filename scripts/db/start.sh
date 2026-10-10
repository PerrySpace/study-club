#!/usr/bin/env bash
# 启动 MongoDB（host 网络，监听宿主 27017）。
#
# 用途：数据库服务 —— 单独启动，与 api / web 解耦。
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"

cd "$(repo_root)"
load_env
require_cmd docker "请先安装 Docker"

PORT="${MONGO_PORT:-27017}"

log_info "启动 MongoDB（端口 ${PORT}）"
compose mongo up -d

log_info "等待 MongoDB 就绪…"
for i in $(seq 1 30); do
  if docker exec sc-mongo mongosh --quiet --eval 'db.runCommand({ ping: 1 }).ok' >/dev/null 2>&1; then
    log_success "MongoDB 就绪：mongodb://localhost:${PORT}/${MONGODB_DB:-study_club}"
    exit 0
  fi
  sleep 1
done

log_warn "未在 30 秒内检测到 MongoDB 就绪，查看日志：scripts/db/logs.sh"
exit 1
