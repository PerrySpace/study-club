#!/usr/bin/env bash
# 生成 Ed25519 邀请码签发密钥对（离线签名码用）。
# 私钥仅签发方持有，绝不入库/入仓；公钥随开源代码公开。
# 用法：
#   scripts/api/gen-invite-keys.sh                # 仅打印（默认）
#   scripts/api/gen-invite-keys.sh --out-dir DIR  # 同时写入 DIR/invite_ed25519.{key,pub}
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

PY_SNIPPET='from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization as s
sk = Ed25519PrivateKey.generate()
priv = sk.private_bytes(s.Encoding.Raw, s.PrivateFormat.Raw, s.NoEncryption()).hex()
pub = sk.public_key().public_bytes(s.Encoding.Raw, s.PublicFormat.Raw).hex()
print(priv)
print(pub)'

generate() {
  if command -v python3 >/dev/null 2>&1 && python3 -c "import cryptography" >/dev/null 2>&1; then
    python3 -c "$PY_SNIPPET"
  elif command -v docker >/dev/null 2>&1; then
    docker compose -f "$COMPOSE_FILE" run --rm --no-deps -T api python -c "$PY_SNIPPET"
  else
    log_error "本机无 cryptography 且无 docker，请在装有 cryptography 的环境执行"
    exit 1
  fi
}

main() {
  load_env || true
  local out_dir=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --out-dir) out_dir="${2:-}"; shift 2 ;;
      *) log_error "未知参数：$1"; exit 1 ;;
    esac
  done

  local keys priv pub
  keys="$(generate)"
  priv="$(printf '%s\n' "$keys" | sed -n '1p')"
  pub="$(printf '%s\n' "$keys" | sed -n '2p')"

  printf 'INVITE_SIGNING_PRIVATE_KEY=%s\n' "$priv"
  printf 'INVITE_SIGNING_PUBLIC_KEY=%s\n' "$pub"

  if [ -n "$out_dir" ]; then
    mkdir -p "$out_dir"
    printf '%s\n' "$priv" > "$out_dir/invite_ed25519.key"
    printf '%s\n' "$pub" > "$out_dir/invite_ed25519.pub"
    log_warn "私钥已写入 $out_dir/invite_ed25519.key，务必确保该文件未被提交（.gitignore 已忽略 *.key）"
  fi
  log_info "私钥仅供离线签发工具使用；公钥可随代码公开" >&2
}

main "$@"
