#!/usr/bin/env bash
# 一键停全栈（按依赖逆序：web → api → db）。
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"

cd "$(repo_root)"
load_env

log_info "① 停止 web"
"$(repo_root)/scripts/web/down.sh" || log_warn "web 停止失败（可能本就未运行）"

log_info "② 停止 api"
"$(repo_root)/scripts/api/down.sh" || log_warn "api 停止失败（可能本就未运行）"

log_info "③ 停止 MongoDB"
"$(repo_root)/scripts/db/stop.sh" || log_warn "mongodb 停止失败（可能本就未运行）"

log_success "全栈已停止（数据卷保留）"
