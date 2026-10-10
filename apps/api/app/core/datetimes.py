"""时间字段归一化（导入路径共用）。

内容 JSON 里的时间是人写的 ISO 8601 字符串，落库要变成 `datetime`（UTC ISODate），
否则后续按时间排序/范围查询会退化成字符串比较 —— 那是个很隐蔽的 bug。

seed 导入器与后台「内容导入」共用本模块，避免两处规则漂移。
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

# 只匹配带时间的 ISO 8601（含 T）；纯日期 "2026-10-08" 不匹配，保持字符串。
_ISO_DATETIME = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})?$"
)


def parse_iso_datetime(value: str) -> datetime | None:
    if not _ISO_DATETIME.match(value):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def normalize_dates(value: Any) -> Any:
    """递归把 ISO 8601 时间字符串转成 datetime；其余类型原样返回。"""
    if isinstance(value, str):
        return parse_iso_datetime(value) or value
    if isinstance(value, dict):
        return {k: normalize_dates(v) for k, v in value.items()}
    if isinstance(value, list):
        return [normalize_dates(v) for v in value]
    return value
