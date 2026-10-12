#!/usr/bin/env bash
# 首次部署一键引导：准备 .env → 生成密钥 → 起全栈 → 导入初始化数据。
#
# 幂等：可重复执行；已有 .env 与已导入的数据不会被破坏（seed 为 upsert）。
#
# 用法： scripts/dev/bootstrap.sh
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"

cd "$(repo_root)"
require_cmd docker "请先安装 Docker"

ROOT="$(repo_root)"
ENV_FILE="$ROOT/.env"

log_info "① 准备环境变量"
if [ ! -f "$ENV_FILE" ]; then
  cp "$ROOT/.env.example" "$ENV_FILE"
  log_success "已由 .env.example 生成 .env"
else
  log_dim ".env 已存在，跳过"
fi

# 生成缺失的密钥（不覆盖已填写的值）
if grep -qE '^JWT_SECRET=(|dev-only-change-me)$' "$ENV_FILE"; then
  secret="$(random_secret 32)"
  if sed --version >/dev/null 2>&1; then
    sed -i "s|^JWT_SECRET=.*|JWT_SECRET=${secret}|" "$ENV_FILE"
  else
    sed -i '' "s|^JWT_SECRET=.*|JWT_SECRET=${secret}|" "$ENV_FILE"
  fi
  log_success "已生成随机 JWT_SECRET"
fi

if grep -qE '^INVITE_SIGNING_PRIVATE_KEY=$' "$ENV_FILE"; then
  log_info "生成 Ed25519 邀请码签发密钥对…"
  "$ROOT/scripts/api/gen-invite-keys.sh" || log_warn "密钥生成失败，可稍后手动执行 scripts/api/gen-invite-keys.sh"
fi

if grep -qE '^ADMIN_PASSWORD_HASH=$' "$ENV_FILE"; then
  log_warn "ADMIN_PASSWORD_HASH 为空 —— 单管理员后台不可登录"
  log_dim "  生成方式： scripts/api/hash-password.sh '你的密码'   然后把输出填入 .env"
fi

log_info "② 启动全栈"
"$ROOT/scripts/dev/up-all.sh"

log_info "③ 导入初始化数据（按表/功能）"
"$ROOT/scripts/seed/seed.sh"

log_success "引导完成"
log_dim "  访问： http://localhost:${WEB_PORT:-8080}/"
log_dim "  状态： scripts/dev/status.sh"
