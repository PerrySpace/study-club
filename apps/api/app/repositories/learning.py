"""学习域仓储：档案 / 复习状态 / 答题明细 / 错题本 / 每日任务 / 学习流水 / 徽章。

「全部服务器存储」后，这些集合从「接收前端上报的增量」变成**唯一主存储**，
因此本层要承担原来在客户端做的聚合（正确率、到期数、连续天数、趋势）。

归属安全：所有按 child_id 的查询都要求调用方先通过 ChildRepository.get_owned() 校验归属，
仓储本身不重复做鉴权（避免两处规则漂移）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from bson import ObjectId
from bson.errors import InvalidId

from .base import BaseRepository


def to_object_id(value: str) -> ObjectId | None:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        return None


class ChildRepository(BaseRepository):
    collection = "children"

    async def list_by_account(self, account_id: ObjectId, *, include_archived: bool = False) -> list[dict]:
        flt: dict[str, Any] = {"account_id": account_id}
        if not include_archived:
            flt["status"] = {"$ne": "archived"}
        return await self.find_many(flt, sort=[("created_at", 1)], limit=100)

    async def get_owned(self, account_id: ObjectId, child_id: str) -> dict | None:
        """按账号归属取档案。返回 None 表示「不存在或不属于该账号」——
        由 controller 决定对外报 403 还是 404（当前统一报 403，防枚举）。"""
        oid = to_object_id(child_id)
        if oid is None:
            return None
        child = await self.find_one({"_id": oid})
        if child is None or child.get("account_id") != account_id:
            return None
        return child

    async def update_fields(self, child_id: Any, patch: dict) -> None:
        if patch:
            await self.update_one({"_id": child_id}, {"$set": patch})

    async def archive(self, child_id: Any) -> None:
        """软删除：不物理删学习数据（03-2 §一）。"""
        await self.update_one({"_id": child_id}, {"$set": {"status": "archived"}})

    async def refresh_stats(self, child_id: Any, *, total: int, mastered: int, now: datetime) -> None:
        await self.update_one(
            {"_id": child_id},
            {
                "$set": {
                    "stats.total_learned": total,
                    "stats.mastered": mastered,
                    "stats.last_study_at": now,
                }
            },
        )

    async def ids_for_account(self, account_id: ObjectId) -> list[Any]:
        return [c["_id"] for c in await self.find_many({"account_id": account_id}, limit=200, projection={"_id": 1})]

    async def purge_account(self, account_id: ObjectId) -> int:
        return await self.delete_many({"account_id": account_id})


class ReviewStateRepository(BaseRepository):
    collection = "char_review_states"

    async def get(self, child_id: Any, character_id: str) -> dict | None:
        return await self.find_one({"child_id": child_id, "character_id": character_id})

    async def upsert(self, child_id: Any, character_id: str, fields: dict) -> None:
        await self.update_one(
            {"child_id": child_id, "character_id": character_id},
            {"$set": {"child_id": child_id, "character_id": character_id, **fields}},
            upsert=True,
        )

    async def list_all(self, child_id: Any, *, limit: int = 3000) -> list[dict]:
        return await self.find_many({"child_id": child_id}, sort=[("next_review_at", 1)], limit=limit)

    async def list_due(self, child_id: Any, now: datetime, *, limit: int = 50) -> list[dict]:
        return await self.find_many(
            {"child_id": child_id, "next_review_at": {"$lte": now}},
            sort=[("next_review_at", 1)],
            limit=limit,
        )

    async def due_ids(self, child_id: Any, now: datetime, *, limit: int = 20) -> list[str]:
        docs = await self.find_many(
            {"child_id": child_id, "next_review_at": {"$lte": now}},
            sort=[("next_review_at", 1)],
            limit=limit,
            projection={"character_id": 1},
        )
        return [d["character_id"] for d in docs]

    async def learned_ids(self, child_id: Any, *, limit: int = 5000) -> list[str]:
        docs = await self.find_many({"child_id": child_id}, limit=limit, projection={"character_id": 1})
        return [d["character_id"] for d in docs]

    async def count_all(self, child_id: Any) -> int:
        return await self.count({"child_id": child_id})

    async def count_due(self, child_id: Any, now: datetime) -> int:
        return await self.count({"child_id": child_id, "next_review_at": {"$lte": now}})

    async def count_by_status(self, child_id: Any) -> dict[str, int]:
        return await self.count_by("status", {"child_id": child_id})

    async def count_reviewed_since(self, child_id: Any, since: datetime) -> int:
        return await self.count({"child_id": child_id, "last_reviewed_at": {"$gte": since}})

    async def daily_buckets(self, child_id: Any, since: datetime) -> dict[str, int]:
        rows = await self.aggregate(
            [
                {"$match": {"child_id": child_id, "last_reviewed_at": {"$gte": since}}},
                {
                    "$group": {
                        "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$last_reviewed_at"}},
                        "learned": {"$sum": 1},
                    }
                },
            ]
        )
        return {r["_id"]: int(r.get("learned", 0)) for r in rows}

    async def purge_by_children(self, child_ids: Iterable[Any]) -> int:
        return await self.delete_in("child_id", child_ids)


class AnswerRecordRepository(BaseRepository):
    collection = "answer_records"

    async def has_client_record(self, child_id: Any, client_record_id: str) -> bool:
        return await self.exists({"child_id": child_id, "client_record_id": client_record_id})

    async def insert_answer(self, doc: dict) -> None:
        await self.insert_one(doc)

    async def count_all(self, child_id: Any) -> int:
        return await self.count({"child_id": child_id})

    async def has_any(self, child_id: Any) -> bool:
        return await self.exists({"child_id": child_id})

    async def recent(self, child_id: Any, *, limit: int = 2000) -> list[dict]:
        return await self.find_many(
            {"child_id": child_id}, sort=[("occurred_at", -1)], limit=limit
        )

    async def accuracy(self, child_id: Any, since: datetime | None = None) -> float:
        flt: dict[str, Any] = {"child_id": child_id}
        if since is not None:
            flt["occurred_at"] = {"$gte": since}
        row = await self.aggregate_one(
            [
                {"$match": flt},
                {
                    "$group": {
                        "_id": None,
                        "total": {"$sum": 1},
                        "correct": {"$sum": {"$cond": ["$is_correct", 1, 0]}},
                    }
                },
            ]
        )
        total = int((row or {}).get("total", 0))
        return round(int((row or {}).get("correct", 0)) / total, 4) if total else 0.0

    async def daily_buckets(self, child_id: Any, since: datetime) -> dict[str, dict]:
        rows = await self.aggregate(
            [
                {"$match": {"child_id": child_id, "occurred_at": {"$gte": since}}},
                {
                    "$group": {
                        "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$occurred_at"}},
                        "total": {"$sum": 1},
                        "correct": {"$sum": {"$cond": ["$is_correct", 1, 0]}},
                    }
                },
                {"$sort": {"_id": 1}},
            ]
        )
        return {
            r["_id"]: {
                "date": r["_id"],
                "learned": 0,
                "correct": int(r.get("correct", 0)),
                "total": int(r.get("total", 0)),
            }
            for r in rows
        }

    async def purge_by_children(self, child_ids: Iterable[Any]) -> int:
        return await self.delete_in("child_id", child_ids)


class WrongQuestionRepository(BaseRepository):
    collection = "wrong_questions"

    async def record_wrong(
        self, child_id: Any, character_id: str, char: str, question_type: str, now: datetime
    ) -> None:
        await self.update_one(
            {"child_id": child_id, "character_id": character_id},
            {
                "$inc": {"wrong_count": 1},
                "$set": {"char": char, "last_wrong_at": now, "resolved": False, "resolved_at": None},
                "$setOnInsert": {"first_wrong_at": now},
                "$addToSet": {"question_types": question_type},
            },
            upsert=True,
        )

    async def resolve_on_correct(self, child_id: Any, character_id: str, now: datetime) -> None:
        await self.update_one(
            {"child_id": child_id, "character_id": character_id, "resolved": False},
            {"$set": {"resolved": True, "resolved_at": now}},
        )

    async def list_items(self, child_id: Any, resolved: bool | None = None, *, limit: int = 500) -> list[dict]:
        flt: dict[str, Any] = {"child_id": child_id}
        if resolved is not None:
            flt["resolved"] = resolved
        return await self.find_many(flt, sort=[("last_wrong_at", -1)], limit=limit)

    async def unresolved_ids(self, child_id: Any, *, limit: int = 10) -> list[str]:
        docs = await self.find_many(
            {"child_id": child_id, "resolved": False},
            sort=[("last_wrong_at", -1)],
            limit=limit,
            projection={"character_id": 1},
        )
        return [d["character_id"] for d in docs]

    async def count_unresolved(self, child_id: Any) -> int:
        return await self.count({"child_id": child_id, "resolved": False})

    async def has_any(self, child_id: Any) -> bool:
        return await self.exists({"child_id": child_id})

    async def weakest(self, child_id: Any, *, limit: int = 50) -> list[dict]:
        return await self.find_many(
            {"child_id": child_id, "resolved": False},
            sort=[("wrong_count", -1), ("last_wrong_at", -1)],
            limit=limit,
        )

    async def resolve_by_id(self, wrong_id: str, child_id: Any, now: datetime) -> bool:
        oid = to_object_id(wrong_id)
        if oid is None:
            return False
        res = await self.update_one(
            {"_id": oid, "child_id": child_id}, {"$set": {"resolved": True, "resolved_at": now}}
        )
        return res.matched_count > 0

    async def purge_by_children(self, child_ids: Iterable[Any]) -> int:
        return await self.delete_in("child_id", child_ids)


class DailyTaskRepository(BaseRepository):
    collection = "daily_tasks"

    async def get(self, child_id: Any, date: str) -> dict | None:
        return await self.find_one({"child_id": child_id, "date": date})

    async def create_if_absent(self, doc: dict) -> tuple[dict, bool]:
        """并发安全：唯一索引冲突时回读既有文档。返回 (文档, 是否新建)。"""
        try:
            await self.insert_one(doc)
            return doc, True
        except Exception:  # noqa: BLE001 - 唯一索引冲突
            existing = await self.get(doc["child_id"], doc["date"])
            if existing is not None:
                return existing, False
            raise

    async def complete_chars(self, child_id: Any, date: str, char_ids: list[str], status: str) -> None:
        await self.update_one(
            {"child_id": child_id, "date": date},
            {"$addToSet": {"completed_char_ids": {"$each": char_ids}}, "$set": {"status": status}},
        )

    async def purge_by_children(self, child_ids: Iterable[Any]) -> int:
        return await self.delete_in("child_id", child_ids)


class LearningRecordRepository(BaseRepository):
    collection = "learning_records"

    async def insert_record(self, doc: dict) -> Any:
        return await self.insert_one(doc)

    async def has_any(self, child_id: Any) -> bool:
        return await self.exists({"child_id": child_id})

    async def recent(self, child_id: Any, *, limit: int = 200) -> list[dict]:
        return await self.find_many({"child_id": child_id}, sort=[("occurred_at", -1)], limit=limit)

    async def count_by_event(self, child_id: Any, event_type: str) -> int:
        return await self.count({"child_id": child_id, "event_type": event_type})

    async def total_duration_ms(self, child_id: Any) -> int:
        row = await self.aggregate_one(
            [
                {"$match": {"child_id": child_id}},
                {"$group": {"_id": None, "ms": {"$sum": {"$ifNull": ["$duration_ms", 0]}}}},
            ]
        )
        return int((row or {}).get("ms", 0))

    async def day_buckets(self, child_id: Any, since: datetime) -> set[str]:
        rows = await self.aggregate(
            [
                {"$match": {"child_id": child_id, "occurred_at": {"$gte": since}}},
                {
                    "$group": {
                        "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$occurred_at"}},
                    }
                },
            ]
        )
        return {r["_id"] for r in rows}

    async def purge_by_children(self, child_ids: Iterable[Any]) -> int:
        return await self.delete_in("child_id", child_ids)


class ChildBadgeRepository(BaseRepository):
    collection = "child_badges"

    async def earned_codes(self, child_id: Any) -> set[str]:
        docs = await self.find_many({"child_id": child_id}, limit=500, projection={"badge_code": 1})
        return {d["badge_code"] for d in docs}

    async def list_items(self, child_id: Any, *, limit: int = 200) -> list[dict]:
        return await self.find_many({"child_id": child_id}, sort=[("earned_at", -1)], limit=limit)

    async def grant(self, child_id: Any, badge_code: str, now: datetime) -> None:
        await self.update_one(
            {"child_id": child_id, "badge_code": badge_code},
            {"$setOnInsert": {"child_id": child_id, "badge_code": badge_code, "earned_at": now}},
            upsert=True,
        )

    async def purge_by_children(self, child_ids: Iterable[Any]) -> int:
        return await self.delete_in("child_id", child_ids)
