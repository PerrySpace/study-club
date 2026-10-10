#!/usr/bin/env bash
# 备份 MongoDB 到 backups/ 目录（不入库，已在 .gitignore 忽略）。
#
# 用法： scripts/db/backup.sh [输出目录]
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"

cd "$(repo_root)"
load_env
require_cmd docker

STAMP="$(date +%Y%m%d-%H%M%S)"
OUT_DIR="${1:-backups}"
DB="${MONGODB_DB:-study_club}"
ARCHIVE="sc-mongo-${DB}-${STAMP}.archive.gz"

mkdir -p "$OUT_DIR"

log_info "备份数据库 ${DB} → ${OUT_DIR}/${ARCHIVE}"

# 容器内先落盘再取出，避免 mongodump 直接写宿主路径产生权限问题
docker exec sc-mongo rm -rf /tmp/sc-backup
docker exec sc-mongo mkdir -p /tmp/sc-backup
docker exec sc-mongo mongodump --quiet --db "$DB" --archive="/tmp/sc-backup/${ARCHIVE}" --gzip
docker cp "sc-mongo:/tmp/sc-backup/${ARCHIVE}" "${OUT_DIR}/${ARCHIVE}"
docker exec sc-mongo rm -rf /tmp/sc-backup

log_success "备份完成：${OUT_DIR}/${ARCHIVE}（$(du -h "${OUT_DIR}/${ARCHIVE}" | cut -f1)）"
