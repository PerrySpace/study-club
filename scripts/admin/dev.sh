#!/usr/bin/env bash
# 本机启动 apps/admin 开发服务器（不走 Docker，便于热更新调试）。
#
# ⚠️ 需要**可用的 pnpm**。若宿主机 pnpm 损坏（本机曾出现
#    「Failed to switch pnpm to v9.12.0 ... CLI is missing」），
#    请改在容器内开发/验证，见仓库根 README 的「容器内迭代」说明。
set -euo pipefail

source "$(dirname "$0")/../lib/common.sh"

cd "$(repo_root)"

load_env

require_cmd node
require_cmd pnpm

# 首次运行需先安装依赖（workspace 级）
if [ ! -d node_modules ] || [ ! -d apps/admin/node_modules ]; then
  log_warn "未检测到依赖，正在执行 pnpm install"
  pnpm install
fi

log_info "启动 apps/admin dev server（默认 http://localhost:5174/）"
log_dim "接口地址取自 apps/admin/.env 的 VITE_API_BASE_URL；未配置时按「同主机 8000 端口」推断"
pnpm --filter @study-club/admin dev
