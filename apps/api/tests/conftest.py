"""pytest 公共配置：把 apps/api 加入 sys.path，并设置测试用环境变量。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# apps/api 目录（tests/ 的上一级）
API_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_DIR))

# 测试用配置：不覆盖已存在的环境变量
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("ADMIN_PASSWORD_HASH", "")
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/study_club_test")
