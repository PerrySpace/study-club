#!/usr/bin/env bash
# 生成 ADMIN_PASSWORD_HASH —— Argon2id 口令哈希（与后端 core/security.py 参数一致）。
# 优先用本机 python3；缺少 argon2-cffi 时回退到 api 容器内执行。
# 用法：scripts/api/hash-password.sh   然后按提示输入口令（不回显）。
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

PY_SNIPPET='import os
from argon2 import PasswordHasher
ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
print(ph.hash(os.environ["PASSCODE"]))'

read_password() {
  # 已由环境提供口令时直接采用（供流水线 / 自动化调用，避免交互式 read 挂住）。
  if [ -n "${PASSCODE:-}" ]; then
    return 0
  fi
  local p1 p2
  printf '请输入管理员口令: ' >&2
  read -rs p1
  printf '\n请再次输入确认: ' >&2
  read -rs p2
  printf '\n' >&2
  if [ "$p1" != "$p2" ]; then
    log_error "两次输入不一致"
    exit 1
  fi
  if [ -z "$p1" ]; then
    log_error "口令不能为空"
    exit 1
  fi
  PASSCODE="$p1"
}

main() {
  load_env || true

  # --raw：只把哈希打到 stdout，便于部署脚本捕获；
  #        不带该参数时保持原有的人工交互提示。
  local raw=0
  case "${1:-}" in
    --raw) raw=1; shift ;;
    "") : ;;
    *) log_error "未知参数：$1"; exit 1 ;;
  esac

  read_password

  local hash
  if command -v python3 >/dev/null 2>&1 && python3 -c "import argon2" >/dev/null 2>&1; then
    [ "$raw" = "1" ] || log_info "使用本机 python3 生成哈希" >&2
    hash="$(PASSCODE="$PASSCODE" python3 -c "$PY_SNIPPET")"
  elif command -v docker >/dev/null 2>&1; then
    [ "$raw" = "1" ] || log_info "本机缺少 argon2-cffi，改用 api 容器生成（首次会构建镜像）" >&2
    hash="$(docker compose -f "$COMPOSE_FILE" run --rm --no-deps -T -e PASSCODE="$PASSCODE" api python -c "$PY_SNIPPET" | tr -d '\r')"
  else
    log_error "既无 argon2 也无法使用 docker，请在装有 argon2-cffi 的环境执行"
    exit 1
  fi

  # 拿去喂给自动化时只输出裸哈希，不夹带任何提示行（否则调用方要解析 stderr）
  if [ "$raw" = "1" ]; then
    printf '%s\n' "$hash"
    return 0
  fi

  # ⚠️ 必须带【单引号】。
  # Argon2 哈希形如 $argon2id$v=19$m=65536,t=3,p=2$<salt>$<digest>，含有大量 `$`。
  # Docker Compose 会用 dotenv 解析 .env / env_file，**未加引号时会把 `$m`、`$xxxx`
  # 当成变量引用替换成空串**，哈希被悄悄改坏，表现为「口令明明对，却一直返回
  # 40301 管理员口令不正确」。dotenv 对**单引号值不做变量插值**，因此这个写法是安全的。
  printf '\n把下面这一行（含单引号）整行替换进仓库根 .env：\n\n' >&2
  printf "ADMIN_PASSWORD_HASH='%s'\n\n" "$hash" >&2
  log_info "改完执行 scripts/api/restart.sh 让 api 重新读取" >&2
}

main "$@"
