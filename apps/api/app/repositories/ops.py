"""运维域仓储：匿名统计 / 反馈 / 审计日志。

隐私红线（不可让步）：`stats_events` 只存聚合计数，**不得出现 account_id / child_id / client_id**。
落库维度仅 event_name × content_ref × client × device_form × client_version × bucket_date。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from .base import BaseRepository


class StatsEventRepository(BaseRepository):
    collection = "stats_events"

    async def ingest(self, events: Iterable[Any], *, now: datetime) -> int:
        accepted = 0
        for event in events:
            key = {
                "event_name": event.event_name,
                "content_ref": event.content_ref,
                "client": event.client,
                "device_form": event.device_form,
                "client_version": event.client_version,
                "bucket_date": event.bucket_date,
            }
            await self.update_one(key, {"$inc": {"count": event.count}, "$setOnInsert": {"created_at": now}}, upsert=True)
            accepted += 1
        return accepted


class FeedbackRepository(BaseRepository):
    collection = "feedbacks"

    async def create(self, doc: dict) -> str:
        inserted = await self.insert_one(doc)
        return str(inserted)

    async def list_page(self, *, skip: int, limit: int, status: str | None = None) -> tuple[list[dict], int]:
        flt: dict[str, Any] = {}
        if status:
            flt["status"] = status
        return await self.paginate(flt, sort=[("created_at", -1)], skip=skip, limit=limit)

    async def set_status(self, feedback_id: str, status: str, *, now: datetime) -> bool:
        res = await self.update_one({"_id": feedback_id}, {"$set": {"status": status, "handled_at": now}})
        return res.matched_count > 0


class AuditLogRepository(BaseRepository):
    collection = "audit_logs"

    async def record(self, doc: dict) -> None:
        await self.insert_one(doc)

    async def list_page(
        self,
        *,
        skip: int,
        limit: int,
        action: str | None = None,
        target_collection: str | None = None,
    ) -> tuple[list[dict], int]:
        flt: dict[str, Any] = {}
        if action:
            flt["action"] = action
        if target_collection:
            flt["target_collection"] = target_collection
        return await self.paginate(flt, sort=[("created_at", -1)], skip=skip, limit=limit)

    async def count_all(self) -> int:
        return await self.count()


class SettingsRepository(BaseRepository):
    """站点运行配置（单文档：`_id = "site"`）。

    为什么放 DB 而非只放环境变量：运营参数（邀请码开关、默认学习目标、公告）
    需要在**不发版、不重启**的情况下调整。环境变量仍作为**首次启动的默认值**，
    DB 有值则以 DB 为准（见 core/runtime_config.py）。
    """

    collection = "app_settings"
    DOC_ID = "site"

    async def get_site(self) -> dict | None:
        return await self.find_one({"_id": self.DOC_ID})

    async def save_site(self, doc: dict, *, now: datetime) -> None:
        await self.replace_one({"_id": self.DOC_ID}, {**doc, "_id": self.DOC_ID, "updated_at": now}, upsert=True)
