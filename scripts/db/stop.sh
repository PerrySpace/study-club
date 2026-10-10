#!/usr/bin/env bash
# 停止 MongoDB（保留数据卷）。
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"

cd "$(repo_root)"
load_env
require_cmd docker

log_info "停止 MongoDB"
compose mongo down
log_success "已停止（数据卷保留，可用 scripts/db/start.sh 再次启动）"
