#!/usr/bin/env bash
# 初始化/重建集合索引。
#
# 设计说明（重要）：
#   索引的**唯一定义处是后端**（apps/api/app/db/mongo.py，字段与 docs/03-数据设计/02-数据字典.md 对齐），
#   由 API 启动时**幂等**创建。本脚本不重复维护一份索引清单，
#   而是通过重启 api 容器触发一次幂等初始化 —— 避免「两处维护、必然漂移」。
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"

cd "$(repo_root)"
load_env
require_cmd docker

if ! docker ps --format '{{.Names}}' | grep -q '^study-club-api$'; then
  log_warn "api 容器未运行，无法触发索引初始化"
  log_info "请先启动后端：scripts/api/up.sh（启动时会自动建索引）"
  exit 1
fi

log_info "重启 api 以幂等创建集合索引"
compose api restart

wait_for_http "http://127.0.0.1:${API_PORT:-8000}${API_PREFIX:-/api/v1}/health" 20 || exit 1
log_success "索引初始化完成"
