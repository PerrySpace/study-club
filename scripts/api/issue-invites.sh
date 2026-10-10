#!/usr/bin/env bash
# 离线签发一批邀请码（不依赖后端）。
# 生成 12 位 Crockford Base32 码（60 bit 熵），**明文码只输出一次**，
# 同时写出 ① 明文码 CSV（供分发）② 只含哈希的种子 JSON（供导入 MongoDB）。
# 用法：
#   scripts/api/issue-invites.sh --count 20 --channel friend --max-uses 1
# 可选：--batch-id <id> --expires-in-days <n> --out-dir <dir>
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

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

# 用纯标准库实现，避免依赖 argon2/jwt 等运行时依赖
PY_SNIPPET='import os, csv, json, secrets, hashlib, datetime
ALPHA = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
count = int(os.environ["COUNT"])
channel = os.environ["CHANNEL"]
max_uses = int(os.environ["MAX_USES"])
batch_id = os.environ["BATCH_ID"]
expires_days = os.environ.get("EXPIRES_DAYS", "")
out_csv = os.environ["OUT_CSV"]
out_json = os.environ["OUT_JSON"]

expires_at = None
if expires_days:
    expires_at = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=int(expires_days))).isoformat().replace("+00:00", "Z")

codes, docs = [], []
for _ in range(count):
    raw = "".join(secrets.choice(ALPHA) for _ in range(12))
    fmt = "-".join(raw[i:i+4] for i in range(0, 12, 4))
    hint = raw[:4] + "-****-****"
    code_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    codes.append((fmt, hint))
    docs.append({
        "code_hash": code_hash,
        "code_hint": hint,
        "batch_id": batch_id,
        "channel": channel,
        "max_uses": max_uses,
        "used_count": 0,
        "bound_account_ids": [],
        "expires_at": expires_at,
        "revoked_at": None,
        "note": None,
        "created_by": None,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
    })

with open(out_csv, "w", encoding="utf-8", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["invite_code", "code_hint", "batch_id", "channel", "max_uses", "expires_at"])
    for (fmt, hint) in codes:
        w.writerow([fmt, hint, batch_id, channel, max_uses, expires_at or ""])

with open(out_json, "w", encoding="utf-8") as fh:
    json.dump({"collection": "invites", "feature": "邀请码批次 " + batch_id,
               "unique_key": "code_hash", "documents": docs}, fh, ensure_ascii=False, indent=2)

for (fmt, _hint) in codes:
    print(fmt)
'

main() {
  load_env || true
  require_cmd python3

  local count=10 channel=self max_uses=1 batch_id="" expires_days="" out_dir=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --count) count="${2:-}"; shift 2 ;;
      --channel) channel="${2:-}"; shift 2 ;;
      --max-uses) max_uses="${2:-}"; shift 2 ;;
      --batch-id) batch_id="${2:-}"; shift 2 ;;
      --expires-in-days) expires_days="${2:-}"; shift 2 ;;
      --out-dir) out_dir="${2:-}"; shift 2 ;;
      *) log_error "未知参数：$1"; exit 1 ;;
    esac
  done

  [ -z "$batch_id" ] && batch_id="batch-$(date -u +%Y%m%d)-$RANDOM"
  [ -z "$out_dir" ] && out_dir="$REPO_ROOT/scripts/seed/data"

  local stamp
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  local out_csv="$out_dir/invites-${batch_id}-${stamp}.csv"
  local out_json="$out_dir/invites-${batch_id}-${stamp}.json"

  log_warn "明文邀请码只在本终端输出一次，请立即保存 CSV 并妥善分发" >&2
  COUNT="$count" CHANNEL="$channel" MAX_USES="$max_uses" BATCH_ID="$batch_id" \
  EXPIRES_DAYS="$expires_days" OUT_CSV="$out_csv" OUT_JSON="$out_json" \
    python3 -c "$PY_SNIPPET"

  log_info "明文码 CSV：$out_csv" >&2
  log_info "哈希种子：${out_json}（只含哈希，可提交/导入）" >&2
  log_info "导入：scripts/seed/seed.sh --only invites" >&2
}

main "$@"
