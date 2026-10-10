"""数据访问层基类（MVC —— Model 层的持久化职责）。

分层纪律（改动前请先读这段）：

    view  → 只做 HTTP 绑定 / 鉴权依赖 / 响应信封
    controller → 只做业务编排，**不得出现 motor 集合对象**
    repository → **唯一**允许直接操作集合的地方（本模块及其子类）
    model  → 领域数据结构（Pydantic schema）

这样「换存储」「加缓存」「加读写分离」都收敛在本层，业务逻辑一行不用改。
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from motor.motor_asyncio import AsyncIOMotorDatabase

SortSpec = Sequence[tuple[str, int]]


class BaseRepository:
    """单个集合的通用数据访问。子类通过 `collection` 指定集合名并补领域方法。"""

    collection: str = ""

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.db = db
        self.coll = db[self.collection]

    # ------------------------------------------------------------------
    # 读
    # ------------------------------------------------------------------
    async def find_one(
        self,
        flt: Mapping[str, Any] | None = None,
        projection: Mapping[str, Any] | None = None,
    ) -> dict | None:
        return await self.coll.find_one(dict(flt or {}), projection)

    async def find_many(
        self,
        flt: Mapping[str, Any] | None = None,
        *,
        sort: SortSpec | None = None,
        skip: int = 0,
        limit: int | None = 100,
        projection: Mapping[str, Any] | None = None,
    ) -> list[dict]:
        cursor = self.coll.find(dict(flt or {}), projection)
        if sort:
            cursor = cursor.sort(list(sort))
        if skip:
            cursor = cursor.skip(skip)
        return await cursor.to_list(limit if limit is not None else None)

    async def find_in(
        self,
        field: str,
        values: Iterable[Any],
        *,
        sort: SortSpec | None = None,
        projection: Mapping[str, Any] | None = None,
    ) -> list[dict]:
        vals = list(values)
        if not vals:
            return []
        return await self.find_many({field: {"$in": vals}}, sort=sort, limit=len(vals), projection=projection)

    async def count(self, flt: Mapping[str, Any] | None = None) -> int:
        return await self.coll.count_documents(dict(flt or {}))

    async def exists(self, flt: Mapping[str, Any]) -> bool:
        return await self.coll.count_documents(dict(flt), limit=1) > 0

    async def distinct(self, field: str, flt: Mapping[str, Any] | None = None) -> list:
        return list(await self.coll.distinct(field, dict(flt or {})))

    async def paginate(
        self,
        flt: Mapping[str, Any] | None,
        *,
        sort: SortSpec | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict], int]:
        """返回 (items, total)。total 是筛选后的总数，用于前端分页控件。"""
        total = await self.count(flt)
        items = await self.find_many(flt, sort=sort, skip=skip, limit=limit)
        return items, total

    async def aggregate(self, pipeline: list[dict]) -> list[dict]:
        return await self.coll.aggregate(pipeline).to_list(None)

    async def aggregate_one(self, pipeline: list[dict]) -> dict | None:
        rows = await self.aggregate(pipeline)
        return rows[0] if rows else None

    async def count_by(self, field: str, flt: Mapping[str, Any] | None = None) -> dict[str, int]:
        """按字段分组计数；字段缺失归入「未知」。"""
        rows = await self.aggregate(
            [
                {"$match": dict(flt or {})},
                {"$group": {"_id": f"${field}", "count": {"$sum": 1}}},
                {"$sort": {"_id": 1}},
            ]
        )
        return {("未知" if r["_id"] is None else str(r["_id"])): r["count"] for r in rows}

    # ------------------------------------------------------------------
    # 写
    # ------------------------------------------------------------------
    async def insert_one(self, doc: dict) -> Any:
        return (await self.coll.insert_one(doc)).inserted_id

    async def insert_many(self, docs: list[dict]) -> int:
        if not docs:
            return 0
        result = await self.coll.insert_many(docs)
        return len(result.inserted_ids)

    async def update_one(self, flt: Mapping[str, Any], update: dict, *, upsert: bool = False):
        return await self.coll.update_one(dict(flt), update, upsert=upsert)

    async def replace_one(self, flt: Mapping[str, Any], doc: dict, *, upsert: bool = False):
        return await self.coll.replace_one(dict(flt), doc, upsert=upsert)

    async def delete_one(self, flt: Mapping[str, Any]) -> int:
        return (await self.coll.delete_one(dict(flt))).deleted_count

    async def delete_many(self, flt: Mapping[str, Any]) -> int:
        return (await self.coll.delete_many(dict(flt))).deleted_count

    async def delete_in(self, field: str, values: Iterable[Any]) -> int:
        vals = list(values)
        if not vals:
            return 0
        return await self.delete_many({field: {"$in": vals}})

    async def upsert_by_id(self, doc_id: Any, doc: dict) -> dict:
        """按 `_id` 幂等 upsert（seed / 内容导入用）。返回最终文档。"""
        await self.coll.replace_one({"_id": doc_id}, doc, upsert=True)
        return doc
