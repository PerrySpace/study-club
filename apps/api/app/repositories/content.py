"""内容域仓储（汉字 / 古诗 / 单元 / 关卡 / 故事 / 徽章 / 内容清单）。

内容已从「内容即仓库」切换为「全部后台管理」：MongoDB 是唯一真源，
仓库里的 `content/*.json` 降级为**一次性导入的种子**（见 controllers/content_import_controller.py）。
因此本模块同时提供「读」（前台内容接口）与「写」（后台 CRUD + 导入 upsert）。
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from .base import BaseRepository


def _keyword_or(fields: tuple[str, ...], keyword: str | None) -> dict | None:
    if not keyword:
        return None
    kw = re.escape(keyword.strip())
    return {"$or": [{f: {"$regex": kw, "$options": "i"}} for f in fields]}


# ===========================================================================
# 汉字
# ===========================================================================
class CharacterRepository(BaseRepository):
    collection = "characters"

    @staticmethod
    def build_filter(
        *,
        status: str | None = None,
        grade: int | None = None,
        level: str | None = None,
        unit_id: str | None = None,
        tags: Iterable[str] | None = None,
        keyword: str | None = None,
        all_status: bool = False,
    ) -> dict[str, Any]:
        flt: dict[str, Any] = {}
        # 前台只读 published；后台要能看见 draft/offline，用 all_status 放开。
        if not all_status:
            flt["status"] = status or "published"
        elif status:
            flt["status"] = status
        if grade is not None:
            flt["grade"] = grade
        if level:
            flt["level"] = level
        if unit_id:
            flt["unit_refs.unit_id"] = unit_id
        tag_list = [t for t in (tags or []) if t]
        if tag_list:
            flt["tags"] = {"$all": tag_list}
        kw = _keyword_or(("char", "meaning", "words", "pinyin"), keyword)
        if kw:
            flt.update(kw)
        return flt

    async def list_page(self, flt: dict, *, skip: int, limit: int) -> tuple[list[dict], int]:
        return await self.paginate(
            flt, sort=[("grade", 1), ("difficulty", 1), ("_id", 1)], skip=skip, limit=limit
        )

    async def admin_list_page(self, flt: dict, *, skip: int, limit: int) -> tuple[list[dict], int]:
        return await self.paginate(flt, sort=[("updated_at", -1), ("_id", 1)], skip=skip, limit=limit)

    async def get_by_char(self, char: str) -> dict | None:
        return await self.find_one({"char": char})

    async def briefs(self, ids: Iterable[str]) -> list[dict]:
        """只要 `_id` / `char`（题目干扰项、字表用），字段越少越好。"""
        docs = await self.find_in("_id", ids, projection={"_id": 1, "char": 1, "pinyin": 1, "grade": 1})
        by_id = {d["_id"]: d for d in docs}
        return [by_id[i] for i in ids if i in by_id]

    async def find_by_ids(self, ids: Iterable[str]) -> list[dict]:
        return await self.find_in("_id", ids)

    async def similar(self, char: str) -> list[dict]:
        return await self.find_many({"char": char}, limit=1)

    async def distractor_pool(self, grade: int, exclude_ids: Iterable[str], limit: int = 12) -> list[dict]:
        return await self.find_many(
            {"grade": grade, "_id": {"$nin": list(exclude_ids)}, "status": "published"},
            limit=limit,
            projection={"_id": 1, "char": 1},
        )

    async def new_candidates(self, grade: int, exclude_ids: Iterable[str], limit: int) -> list[str]:
        """每日任务的「新学字」：按难度升序取该年级未学过的字。"""
        docs = await self.find_many(
            {"grade": grade, "status": "published", "_id": {"$nin": list(exclude_ids)}},
            sort=[("difficulty", 1), ("_id", 1)],
            limit=limit,
            projection={"_id": 1},
        )
        return [d["_id"] for d in docs]

    async def candidate_ids_for_grade(self, grade: int) -> list[dict]:
        """客户端每日任务候选池（服务端给客户端自己算时的入参）。"""
        return await self.find_many(
            {"status": "published", "grade": {"$lte": grade}},
            sort=[("difficulty", 1), ("stroke_count", 1)],
            limit=3000,
            projection={"_id": 1},
        )

    async def create(self, doc: dict) -> dict:
        await self.insert_one(doc)
        return doc

    async def save(self, char_id: str, patch: dict) -> dict | None:
        await self.update_one({"_id": char_id}, {"$set": patch})
        return await self.find_one({"_id": char_id})

    async def soft_delete(self, char_id: str, *, now: Any = None) -> bool:
        res = await self.update_one({"_id": char_id}, {"$set": {"status": "offline", "updated_at": now}})
        return res.matched_count > 0

    async def upsert_many(self, docs: list[dict]) -> dict[str, int]:
        """导入用：按 `_id` 幂等 upsert，返回 created/updated 计数。"""
        created = updated = 0
        for doc in docs:
            exists = await self.exists({"_id": doc["_id"]})
            await self.replace_one({"_id": doc["_id"]}, doc, upsert=True)
            if exists:
                updated += 1
            else:
                created += 1
        return {"created": created, "updated": updated}

    async def asset_completeness(self) -> dict[str, int]:
        return {
            "audio": await self.count({"audio_ref": {"$ne": None}}),
            "image": await self.count({"image_ref": {"$ne": None}}),
            "stroke_order": await self.count({"stroke_order_ref": {"$ne": None}}),
        }


# ===========================================================================
# 古诗
# ===========================================================================
class PoemRepository(BaseRepository):
    collection = "poems"

    @staticmethod
    def build_filter(
        *,
        grade: int | None = None,
        theme_tags: Iterable[str] | None = None,
        source: str | None = None,
        keyword: str | None = None,
        all_status: bool = False,
        status: str | None = None,
    ) -> dict[str, Any]:
        flt: dict[str, Any] = {}
        if not all_status:
            flt["status"] = status or "published"
        elif status:
            flt["status"] = status
        if grade is not None:
            flt["grade"] = grade
        if source:
            flt["source"] = source
        tags = [t for t in (theme_tags or []) if t]
        if tags:
            flt["theme_tags"] = {"$all": tags}
        kw = _keyword_or(("title", "full_text", "author"), keyword)
        if kw:
            flt.update(kw)
        return flt

    async def list_page(self, flt: dict, *, skip: int, limit: int, admin: bool = False) -> tuple[list[dict], int]:
        sort = [("updated_at", -1)] if admin else [("grade", 1), ("difficulty", 1), ("_id", 1)]
        return await self.paginate(flt, sort=sort, skip=skip, limit=limit)

    async def by_key_character(self, char: str, limit: int = 50) -> list[dict]:
        return await self.find_many(
            {"key_characters": char, "status": "published"},
            limit=limit,
            projection={"_id": 1, "title": 1, "author": 1, "full_text": 1},
        )

    async def upsert_many(self, docs: list[dict]) -> dict[str, int]:
        created = updated = 0
        for doc in docs:
            exists = await self.exists({"_id": doc["_id"]})
            await self.replace_one({"_id": doc["_id"]}, doc, upsert=True)
            if exists:
                updated += 1
            else:
                created += 1
        return {"created": created, "updated": updated}


# ===========================================================================
# 单元 / 关卡 / 故事 / 徽章（结构同构，收敛为一个基类）
# ===========================================================================
class _ContentCollectionRepository(BaseRepository):
    """带 status 软删的内容集合通用实现。"""

    default_sort: tuple[tuple[str, int], ...] = (("order", 1),)

    async def list_published(self, flt: dict | None = None, *, limit: int = 1000) -> list[dict]:
        merged = {"status": "published", **(flt or {})}
        return await self.find_many(merged, sort=list(self.default_sort), limit=limit)

    async def list_admin_page(self, flt: dict, *, skip: int, limit: int) -> tuple[list[dict], int]:
        return await self.paginate(flt, sort=[("updated_at", -1), ("_id", 1)], skip=skip, limit=limit)

    async def soft_delete(self, doc_id: str, *, now: Any = None) -> bool:
        res = await self.update_one({"_id": doc_id}, {"$set": {"status": "offline", "updated_at": now}})
        return res.matched_count > 0

    async def upsert_many(self, docs: list[dict]) -> dict[str, int]:
        created = updated = 0
        for doc in docs:
            exists = await self.exists({"_id": doc["_id"]})
            await self.replace_one({"_id": doc["_id"]}, doc, upsert=True)
            if exists:
                updated += 1
            else:
                created += 1
        return {"created": created, "updated": updated}


class UnitRepository(_ContentCollectionRepository):
    collection = "curriculum_units"
    default_sort = (("grade_num", 1), ("semester", 1), ("order", 1))

    async def list_for_grade(self, grade: int) -> list[dict]:
        return await self.find_many(
            {"grade_num": grade, "status": "published"}, sort=list(self.default_sort), limit=200
        )


class LessonRepository(_ContentCollectionRepository):
    collection = "lessons"
    default_sort = (("level", 1), ("order", 1))

    async def list_by_level(self, level: str | None, *, limit: int = 1000) -> list[dict]:
        flt: dict[str, Any] = {"status": "published"}
        if level:
            flt["level"] = level
        return await self.find_many(flt, sort=list(self.default_sort), limit=limit)


class StoryRepository(_ContentCollectionRepository):
    collection = "stories"
    default_sort = (("level", 1), ("grade", 1))


class ReadingRepository(_ContentCollectionRepository):
    """识字短文（阅读承接）。

    与 Story 的区别：Story 是"给孩子听/读的故事"，Reading 是**按已学字覆盖率分级**
    的短文 —— 每篇都标注 `character_ids`（用到的字），客户端据此判断
    「这篇里孩子已经认识几个字」，只推覆盖率够高的那几篇。
    这是主流识字产品「认字之后有东西可读」的关键一环：读不了 = 白学。
    """

    collection = "readings"
    default_sort = (("grade", 1), ("difficulty", 1), ("order", 1))


class BadgeRepository(_ContentCollectionRepository):
    collection = "badges"
    default_sort = (("order", 1),)

    async def list_active(self, *, limit: int = 200) -> list[dict]:
        return await self.find_many({"status": "active"}, sort=[("order", 1)], limit=limit)


# ===========================================================================
# 内容清单
# ===========================================================================
class ContentManifestRepository(BaseRepository):
    collection = "content_manifest"

    async def get_current(self) -> dict | None:
        return await self.find_one({"_id": "current"})

    async def save_current(self, doc: dict) -> None:
        await self.replace_one({"_id": "current"}, doc, upsert=True)

    async def recount(self, counts: dict[str, int]) -> None:
        """内容变更后刷新清单计数，让客户端能判断内容是否更新。"""
        doc = await self.get_current() or {"_id": "current"}
        doc["counts"] = counts
        await self.replace_one({"_id": "current"}, doc, upsert=True)
