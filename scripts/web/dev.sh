#!/usr/bin/env bash
# 本机启动 apps/web 开发服务器（不走 Docker，便于热更新调试）。
set -euo pipefail

source "$(dirname "$0")/../lib/common.sh"

cd "$(repo_root)"

load_env

require_cmd node
require_cmd pnpm

# 首次运行需先安装依赖（workspace 级）
if [ ! -d node_modules ] || [ ! -d apps/web/node_modules ]; then
  log_warn "未检测到依赖，正在执行 pnpm install"
  pnpm install
fi

log_info "启动 apps/web dev server（默认 http://localhost:5173/）"
pnpm --filter @study-club/web dev
