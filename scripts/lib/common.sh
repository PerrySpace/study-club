#!/usr/bin/env bash
# ============================================================================
# scripts/lib/common.sh —— 部署脚本公共函数库
#
# 所有 scripts/ 下的脚本都应通过它统一日志、路径解析与环境加载：
#   source "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"
#
# 提供：log_info / log_success / log_warn / log_error / die
#       repo_root / require_cmd / load_env / confirm
#       compose / wait_for_http / random_secret / lan_ip
# ============================================================================

# 防止重复 source
if [ -n "${__SC_COMMON_LOADED:-}" ]; then
  return 0 2>/dev/null || true
fi
__SC_COMMON_LOADED=1

# ---- 颜色（非终端时自动关闭） ----
if [ -t 1 ] && [ "${NO_COLOR:-}" = "" ]; then
  __C_RESET=$'\033[0m'
  __C_INFO=$'\033[36m'
  __C_OK=$'\033[32m'
  __C_WARN=$'\033[33m'
  __C_ERR=$'\033[31m'
  __C_DIM=$'\033[2m'
else
  __C_RESET=''; __C_INFO=''; __C_OK=''; __C_WARN=''; __C_ERR=''; __C_DIM=''
fi

# ---- 日志 ----
# ⚠️ 全部走 **stderr**。看似小事，实则是一条纪律：**stdout 只放数据**。
#    否则调用方 `x="$(某个脚本 --raw)"` 会把日志行一起捕获进来。
#    真实踩过：`load_env` 会 dim 一行「已加载环境变量：.env」到 stdout，
#    于是 `cmd_admin` 里 `hash="$(... hash-password.sh --raw)"` 拿到的是
#    「日志行 + 哈希」两行，`case "$hash" in \$argon2*)` 匹配失败，
#    报的却是「哈希生成失败（api 镜像是否已构建？）」—— 一路往镜像方向查。
log_info()    { printf '%s[INFO]%s %s\n'  "$__C_INFO" "$__C_RESET" "$*" >&2; }
log_success() { printf '%s[ OK ]%s %s\n'  "$__C_OK"   "$__C_RESET" "$*" >&2; }
log_warn()    { printf '%s[WARN]%s %s\n'  "$__C_WARN" "$__C_RESET" "$*" >&2; }
log_error()   { printf '%s[FAIL]%s %s\n'  "$__C_ERR"  "$__C_RESET" "$*" >&2; }
log_dim()     { printf '%s%s%s\n'         "$__C_DIM"  "$*" "$__C_RESET" >&2; }

# 打印错误并退出
die() { log_error "$*"; exit 1; }

# ---- 仓库根路径（回显，不改变当前目录） ----
repo_root() {
  if [ -n "${SC_REPO_ROOT:-}" ]; then
    printf '%s\n' "$SC_REPO_ROOT"
    return 0
  fi
  local dir
  dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
  printf '%s\n' "$dir"
}

# ---- 依赖检查 ----
require_cmd() {
  local cmd="$1"
  local hint="${2:-}"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    log_error "缺少命令：$cmd${hint:+（${hint}）}"
    exit 1
  fi
}

# ---- 加载仓库根 .env（不存在时从 .env.example 生成，避免 compose 的 env_file 报错） ----
load_env() {
  local root file
  root="$(repo_root)"
  file="${ENV_FILE:-$root/.env}"
  if [ ! -f "$file" ] && [ -f "$root/.env.example" ]; then
    cp "$root/.env.example" "$file"
    log_warn "未找到 .env，已从 .env.example 生成（请按需修改，尤其是 JWT_SECRET / ADMIN_PASSWORD_HASH）"
  fi
  if [ -f "$file" ]; then
    # shellcheck disable=SC1090
    set -a
    . "$file"
    set +a
    log_dim "已加载环境变量：${file#"$root"/}"
  else
    log_warn "未找到 ${file}，将使用环境中的变量与默认值"
  fi
}

# ---- 二次确认 ----
confirm() {
  local prompt="${1:-确认继续？}"
  local answer
  printf '%s [y/N] ' "$prompt"
  read -r answer || true
  case "$answer" in
    y|Y|yes|YES) return 0 ;;
    *) return 1 ;;
  esac
}

# ---- docker compose 包装（统一 project name，避免多服务互相顶掉） ----
compose() {
  local service="$1"; shift
  local root compose_file project
  root="$(repo_root)"
  compose_file="$root/deploy/$service/docker-compose.yml"
  project="study-club-$service"
  [ -f "$compose_file" ] || die "找不到编排文件：$compose_file"
  docker compose -p "$project" -f "$compose_file" "$@"
}

# ---- 等待 HTTP 就绪 ----
wait_for_http() {
  local url="$1"
  local tries="${2:-30}"
  local i=1
  while [ "$i" -le "$tries" ]; do
    if curl -fsS -o /dev/null --max-time 3 "$url" 2>/dev/null; then
      log_success "就绪：$url"
      return 0
    fi
    sleep 1
    i=$((i + 1))
  done
  log_warn "等待超时：$url"
  return 1
}

# ---- 生成随机密钥 ----
random_secret() {
  local bytes="${1:-32}"
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex "$bytes"
  else
    LC_ALL=C tr -dc 'a-f0-9' </dev/urandom | head -c $((bytes * 2))
    printf '\n'
  fi
}

# ---- 探测本机局域网 IP（供手机 / iPad 访问用），失败则回显为空 ----
# 用途：容器使用 host 网络，服务监听 0.0.0.0，因此局域网设备直接访问
#       http://<本机局域网 IP>:<端口> 即可，无需额外绑定或端口映射。
#
# ⚠️ 两个踩过的坑，改这段前先看：
#   ① **不要用 `ip route get 1.1.1.1`**。看起来它最「聪明」，但这一带常配
#      fake-ip 代理（Meta / clash 的 198.18.0.0/16 网段并抢占默认路由），
#      结果会返回 `198.18.0.1` / `198.18.0.x` 这种根本连不上的地址。
#   ② **不要只依赖 `hostname -I`**。glibc 版支持，但 Alpine 的 busybox 版
#      没有 `-I`（只支持 -s/-i/-d/-f），在容器里会静默返回空串。
#      发布脚本跑在 alpine 工具容器里，就是这么踩到的。
# 因此顺序固定为：默认路由那块网卡的地址 → 第一个全局地址 → `hostname -I`。
lan_ip() {
  local ip=""
  case "$(uname -s)" in
    Darwin)
      # Wi-Fi 为 en0，有线为 en1 / bridge0；逐个尝试直到拿到地址
      local iface
      for iface in en0 en1 bridge0; do
        ip="$(ipconfig getifaddr "$iface" 2>/dev/null || true)"
        [ -n "$ip" ] && break
      done
      ;;
    Linux)
      local iface
      iface="$(ip route show default 2>/dev/null | awk '{print $5; exit}')"
      if [ -n "$iface" ]; then
        ip="$(ip -4 -o addr show dev "$iface" scope global 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | head -1)"
      fi
      if [ -z "$ip" ]; then
        ip="$(ip -4 -o addr show scope global 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | head -1)"
      fi
      if [ -z "$ip" ]; then
        ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
      fi
      ;;
  esac
  printf '%s\n' "$ip"
}
