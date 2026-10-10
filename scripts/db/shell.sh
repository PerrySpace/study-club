#!/usr/bin/env bash
# 打开 mongosh 交互式会话（连到本机库）。
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"

cd "$(repo_root)"
load_env
require_cmd docker

DB="${MONGODB_DB:-study_club}"
log_info "进入 mongosh（数据库 ${DB}）"
exec docker exec -it sc-mongo mongosh "$DB"
