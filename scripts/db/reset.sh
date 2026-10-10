#!/usr/bin/env bash
# 重置 MongoDB：停止并**删除数据卷**，然后重新启动。
#
# ⚠️ 危险操作：会不可逆地删除本机所有学习数据与内容。需要显式 --yes 才跳过确认。
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"

cd "$(repo_root)"
load_env
require_cmd docker

if [ "${1:-}" != "--yes" ]; then
  log_warn "本操作将删除数据卷 study-club-mongo-data（不可恢复）"
  confirm "确认重置数据库？" || die "已取消"
fi

log_info "停止并删除数据卷"
compose mongo down -v

log_info "重新启动"
compose mongo up -d

for i in $(seq 1 30); do
  if docker exec sc-mongo mongosh --quiet --eval 'db.runCommand({ ping: 1 }).ok' >/dev/null 2>&1; then
    log_success "数据库已重置并启动"
    log_info "下一步：scripts/seed/seed.sh 导入初始化数据"
    exit 0
  fi
  sleep 1
done
log_warn "启动超时，请查看：scripts/db/logs.sh"
exit 1
