#!/usr/bin/env bash
# 跟踪 api 日志（默认尾部 200 行）。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/deploy/api/docker-compose.yml"

if [ -f "$REPO_ROOT/scripts/lib/common.sh" ]; then
  # shellcheck disable=SC1091
  source "$REPO_ROOT/scripts/lib/common.sh"
else
  log_info() { printf '[INFO] %s\n' "$*"; }
  log_warn() { printf '[WARN] %s\n' "$*" >&2; }
  log_error() { printf '[ERROR] %s\n' "$*" >&2; }
  repo_root() { printf '%s\n' "$REPO_ROOT"; }
  require_cmd() { command -v "$1" >/dev/null 2>&1 || { log_error "缺少命令：$1"; exit 1; }; }
  load_env() { :; }
fi

main() {
  require_cmd docker
  docker compose -f "$COMPOSE_FILE" logs -f --tail=200 api "$@"
}

main "$@"
