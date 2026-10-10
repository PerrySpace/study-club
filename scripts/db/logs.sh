#!/usr/bin/env bash
# 查看 MongoDB 日志。
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"

cd "$(repo_root)"
require_cmd docker

exec docker logs -f --tail 200 sc-mongo
