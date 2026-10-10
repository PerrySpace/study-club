"""素材仓储（图片 / 音频 / 笔顺数据）。

素材是「内容全部由后台管理」的必要条件：字卡配图、古诗朗读、笔顺数据都不能再随前端包分发，
必须由服务端托管、后台可替换。文件落磁盘（ASSET_DIR），元数据落本集合。

出参 `url` 默认是**相对路径**（`/api/v1/assets/<id>`），由前端按 API 源拼接 ——
这样换局域网 IP 不需要重建素材链接。配置 ASSET_BASE_URL 时则输出绝对地址（CDN 场景）。
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from .base import BaseRepository

# 可被素材引用的「素材类型」。与 models/asset.py 的校验保持一致。
ASSET_TYPES = ("image", "audio", "stroke", "other")

_SAFE_SEGMENT = re.compile(r"[^0-9A-Za-z._-]")


def safe_storage_key(*parts: str) -> str:
    """把任意输入拼成安全的相对存储路径。

    为什么必须净化：`storage_key` 最终会拼进文件系统路径，
    不净化就会出现 `../` 逃逸（路径穿越），这是真实可利用的漏洞。
    """
    cleaned = [_SAFE_SEGMENT.sub("_", p.strip()) for p in parts if p]
    return "/".join(c for c in cleaned if c)


class AssetRepository(BaseRepository):
    collection = "assets"

    # ------------------------------------------------------------------
    # 读
    # ------------------------------------------------------------------
    async def url_map(self, asset_ids: Iterable[str]) -> dict[str, str]:
        """批量把素材 id 映射为可访问 URL（`*_ref` → `*_url` 用）。"""
        ids = [str(i) for i in asset_ids if i]
        if not ids:
            return {}
        docs = await self.find_many({"_id": {"$in": ids}, "status": "active"}, limit=len(ids), projection={"url": 1})
        return {str(d["_id"]): d.get("url", "") for d in docs}

    async def list_page(
        self,
        *,
        skip: int,
        limit: int,
        asset_type: str | None = None,
        keyword: str | None = None,
        include_deleted: bool = False,
    ) -> tuple[list[dict], int]:
        flt: dict[str, Any] = {}
        if not include_deleted:
            flt["status"] = "active"
        if asset_type:
            flt["type"] = asset_type
        if keyword:
            flt["$or"] = [
                {"original_name": {"$regex": re.escape(keyword), "$options": "i"}},
                {"_id": {"$regex": re.escape(keyword)}},
                {"subtype": {"$regex": re.escape(keyword), "$options": "i"}},
            ]
        return await self.paginate(flt, sort=[("created_at", -1)], skip=skip, limit=limit)

    async def stats(self) -> dict[str, int]:
        """素材体量（概览页用）：按类型计数 + 总字节数。"""
        by_type = await self.count_by("type", {"status": "active"})
        row = await self.aggregate_one(
            [{"$match": {"status": "active"}}, {"$group": {"_id": None, "bytes": {"$sum": {"$ifNull": ["$bytes", 0]}}}}]
        )
        by_type["total_bytes"] = int((row or {}).get("bytes", 0))
        return by_type

    async def ref_counts(self, asset_ids: list[str]) -> dict[str, int]:
        """统计每个素材被多少条内容引用（删除前提示用）。

        只查各内容集合的 `*_ref` 字段 —— 不做全库扫描。
        """
        if not asset_ids:
            return {}
        counts: dict[str, int] = {i: 0 for i in asset_ids}
        specs = (
            ("characters", "image_ref"),
            ("characters", "audio_ref"),
            ("characters", "stroke_order_ref"),
            ("poems", "audio_ref"),
            ("stories", "audio_ref"),
        )
        for coll_name, field in specs:
            rows = await self.db[coll_name].aggregate(
                [
                    {"$match": {field: {"$in": asset_ids}}},
                    {"$group": {"_id": f"${field}", "count": {"$sum": 1}}},
                ]
            ).to_list(None)
            for row in rows:
                key = str(row["_id"])
                counts[key] = counts.get(key, 0) + int(row.get("count", 0))
        return counts

    # ------------------------------------------------------------------
    # 写
    # ------------------------------------------------------------------
    async def soft_delete(self, asset_id: str, *, now: Any = None) -> bool:
        """软删除：置 status=deleted（不删文件，便于误删恢复）。"""
        res = await self.update_one(
            {"_id": asset_id, "status": "active"},
            {"$set": {"status": "deleted", "deleted_at": now}},
        )
        return res.matched_count > 0

    async def upsert_generated(self, doc: dict) -> None:
        """生成器写入：同 storage_key 视为同一素材，幂等覆盖。"""
        await self.coll.replace_one({"storage_key": doc["storage_key"], "source": "generated"}, doc, upsert=True)
