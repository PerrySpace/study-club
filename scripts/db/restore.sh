#!/usr/bin/env bash
# 从备份文件恢复 MongoDB。
#
# ⚠️ 会覆盖同名集合，需要二次确认。
# 用法： scripts/db/restore.sh backups/sc-mongo-study_club-20261008-120000.archive.gz
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"

cd "$(repo_root)"
load_env
require_cmd docker

ARCHIVE_FILE="${1:-}"
[ -n "$ARCHIVE_FILE" ] || die "用法： scripts/db/restore.sh <备份文件路径>"
[ -f "$ARCHIVE_FILE" ] || die "备份文件不存在：$ARCHIVE_FILE"

DB="${MONGODB_DB:-study_club}"
BASE="$(basename "$ARCHIVE_FILE")"

confirm "将把 ${BASE} 恢复到数据库 ${DB}（同集合会被覆盖），继续？" || die "已取消"

docker exec sc-mongo rm -rf /tmp/sc-restore
docker exec sc-mongo mkdir -p /tmp/sc-restore
docker cp "$ARCHIVE_FILE" "sc-mongo:/tmp/sc-restore/${BASE}"
docker exec sc-mongo mongorestore --quiet --gzip --drop --db "$DB" --archive="/tmp/sc-restore/${BASE}"
docker exec sc-mongo rm -rf /tmp/sc-restore

log_success "恢复完成：${BASE} → ${DB}"
