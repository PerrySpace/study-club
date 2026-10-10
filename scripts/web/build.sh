#!/usr/bin/env bash
# 构建 apps/web 的 Docker 镜像（单服务独立编排）。
set -euo pipefail

source "$(dirname "$0")/../lib/common.sh"

cd "$(repo_root)"

load_env

COMPOSE_FILE="deploy/web/docker-compose.yml"

require_cmd docker

log_info "构建 web 镜像（context: 仓库根，dockerfile: apps/web/Dockerfile）"
docker compose -f "$COMPOSE_FILE" build

log_info "构建完成：study-club-web:latest"
