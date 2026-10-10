#!/usr/bin/env python3
"""种子数据导入入口（薄封装）。

把 `apps/api` 加入 sys.path 后调用通用导入器，避免与后端包结构重复实现。
用法见 scripts/seed/README.md。
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

from app.seed.importer import main as importer_main  # noqa: E402


def main() -> int:
    argv = sys.argv[1:]
    # 默认补齐 repo-root 与 data-dir，允许命令行覆盖
    if "--repo-root" not in argv:
        argv += ["--repo-root", str(REPO_ROOT)]
    if "--data-dir" not in argv:
        argv += ["--data-dir", str(REPO_ROOT / "scripts" / "seed" / "data")]
    return importer_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
