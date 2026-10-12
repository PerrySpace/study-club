#!/usr/bin/env bash
# 种子数据导入编排 —— 按文件名顺序依次导入；支持 --only <表名> / --drop / --force。
#
# ⭐ 内容优先级（2026-10-12 起）：
#   集合**为空**时（首次部署初始化）→ 用仓库 content/ 全量灌入；
#   集合**已有数据**时            → 一律以数据库为准：只补缺，不覆盖、不删除。
#   所以后台「内容导入」进来的内容不会再被发布流程清掉。
#   要强制以仓库为准（覆盖同名 + 清理库内多余），显式加 --force。
#
# 用法：
#   scripts/seed/seed.sh                      # 全量导入（幂等）
#   scripts/seed/seed.sh --only characters    # 只导入文件名含 characters 的表
#   scripts/seed/seed.sh --force              # 强制以仓库为准（会覆盖/清理库内内容）
#   scripts/seed/seed.sh --drop               # 导入前清空各目标集合（等于全量重建）
#
# 运行位置（自动选择）：
#   ① api 容器内（优先）—— 依赖与路径都已就绪，需先 scripts/api/up.sh
#   ② 本机 python3 —— 需自行安装 apps/api/requirements.txt
#
# 数据文件：scripts/seed/data/*.json，**每张表 / 每个功能一个文件**（见该目录 00_meta.json）。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CONTAINER="study-club-api"

# 公共函数由 scripts/lib/common.sh 提供；缺失时用内置兜底，保证脚本本身可运行
if [ -f "$REPO_ROOT/scripts/lib/common.sh" ]; then
  # shellcheck disable=SC1091
  source "$REPO_ROOT/scripts/lib/common.sh"
else
  log_info() { printf '[INFO] %s\n' "$*"; }
  log_warn() { printf '[WARN] %s\n' "$*" >&2; }
  log_error() { printf '[ERROR] %s\n' "$*" >&2; }
  log_success() { printf '[ OK ] %s\n' "$*"; }
  repo_root() { printf '%s\n' "$REPO_ROOT"; }
  require_cmd() { command -v "$1" >/dev/null 2>&1 || { log_error "缺少命令：$1"; exit 1; }; }
  load_env() { :; }
fi

# ① 容器内导入：镜像已含 app 与 content，且依赖齐备
run_in_container() {
  docker exec -w /app -e PYTHONPATH=/app "$CONTAINER" \
    python -m app.seed.importer \
    --repo-root /app \
    --data-dir /app/scripts/seed/data "$@"
}

# ② 本机导入：把 apps/api 加进 PYTHONPATH，从仓库根解析 content/
run_on_host() {
  local python_bin="${PYTHON_BIN:-python3}"
  PYTHONPATH="$REPO_ROOT/apps/api${PYTHONPATH:+:$PYTHONPATH}" \
    "$python_bin" -m app.seed.importer \
    --repo-root "$REPO_ROOT" \
    --data-dir "$SCRIPT_DIR/data" "$@"
}

main() {
  load_env || true

  if command -v docker >/dev/null 2>&1 \
    && docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$CONTAINER"; then
    log_info "在 api 容器内导入种子数据（${CONTAINER}）"
    run_in_container "$@"
  else
    log_warn "未检测到运行中的 ${CONTAINER} 容器，改用本机 python3"
    log_warn "若报 ModuleNotFoundError，请先 pip install -r apps/api/requirements.txt，或改用 scripts/api/up.sh 启动容器"
    require_cmd python3
    run_on_host "$@"
  fi

  log_success "种子数据导入完成"
}

main "$@"
