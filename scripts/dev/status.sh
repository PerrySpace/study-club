#!/usr/bin/env bash
# 查看全栈容器状态与端口。
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"

cd "$(repo_root)"
load_env

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " study-club · 服务状态"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

for name in sc-mongo study-club-api study-club-web study-club-admin; do
  if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${name}$"; then
    printf '  %-22s %s\n' "$name" "运行中"
  elif docker ps -a --format '{{.Names}}' 2>/dev/null | grep -q "^${name}$"; then
    printf '  %-22s %s\n' "$name" "已停止"
  else
    printf '  %-22s %s\n' "$name" "未创建"
  fi
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
printf '  本机访问\n'
printf '    web    http://localhost:%s/\n' "${WEB_PORT:-8080}"
printf '    admin  http://localhost:%s/   （内部工具，按需启动）\n' "${ADMIN_PORT:-8081}"
printf '    api    http://localhost:%s%s\n' "${API_PORT:-8000}" "${API_PREFIX:-/api/v1}"
printf '    docs   http://localhost:%s/docs\n' "${API_PORT:-8000}"
printf '    mongo  mongodb://localhost:%s/%s\n' "${MONGO_PORT:-27017}" "${MONGODB_DB:-study_club}"

LAN="$(lan_ip)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -n "$LAN" ]; then
  printf '  局域网访问（手机 / iPad 连同一 WiFi）\n'
  printf '    web    http://%s:%s/\n' "$LAN" "${WEB_PORT:-8080}"
  printf '    admin  http://%s:%s/\n' "$LAN" "${ADMIN_PORT:-8081}"
  printf '    api    http://%s:%s%s\n' "$LAN" "${API_PORT:-8000}" "${API_PREFIX:-/api/v1}"
  log_warn "手机连不上时检查：同一 WiFi / macOS 防火墙是否放行 ${WEB_PORT:-8080}"
else
  log_warn "未探测到局域网 IP（可手动执行：ipconfig getifaddr en0）"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if command -v curl >/dev/null 2>&1; then
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "http://127.0.0.1:${API_PORT:-8000}${API_PREFIX:-/api/v1}/health" || true)"
  if [ "$code" = "200" ]; then log_success "api 健康检查通过"; else log_warn "api 健康检查未通过（HTTP ${code:-无响应}）"; fi
fi
