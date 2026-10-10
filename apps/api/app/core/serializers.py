"""文档 → 可 JSON 化的序列化（**唯一实现**）。

放置层级：放在 `core/` 而不是 `controllers/`，因为有两个不同层的使用方：
  ① `controllers/serializers.py` —— 控制器做**字段级显式整形**时转出（保留原入口名）；
  ② `core/response.py` —— 构造响应信封时**兜底**。

为什么必须兜底（这是踩过的坑）：`JSONResponse` 内部就是 `json.dumps`，
遇到 `datetime` / `ObjectId` 会直接抛 TypeError →
本来只是「少写一句序列化」，结果表现为整个接口 500。
`GET /content/lessons` 就是这么挂的：`list_units` 走的是带投影的查询所以没事，
`list_lessons` 返回完整文档（含 `created_at`），一上线就 500。
与其在每个端点上各补一句（漏一个就再炸一次），不如在唯一出口处统一兜住。

约定（06-1 §四）：出参一律 snake_case；ObjectId 以字符串传输；时间为 ISO 8601 UTC。
内容集合的 `_id` 本身就是字符串（如 `ch_4e00`），保持不变，保证与 content/*.json 完全一致。
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from bson import ObjectId


def to_iso(value: datetime | None) -> str | None:
    """统一输出 `...Z` 形式（UTC）。naive 时间按 UTC 处理，避免前端时区歧义。"""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def serialize(value: Any) -> Any:
    """递归转换：ObjectId→str、datetime→ISO、date→YYYY-MM-DD、Decimal→float、list/dict 保结构。

    对**无法识别**的类型原样返回：这里不是「万能转 JSON」，而是「把 Mongo 带出来的
    非 JSON 原生类型转掉」。真出现别的类型应当在编码阶段暴露出来（错误信息比静默
    字符串化更有用）。
    """
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return to_iso(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {k: serialize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialize(v) for v in value]
    return value


def serialize_many(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [serialize(d) for d in docs]
