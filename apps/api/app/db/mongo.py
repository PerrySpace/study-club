"""MongoDB 连接与索引初始化（motor 异步）。

两条硬要求：
1. **幂等**：启动时重复执行不报错；集合不存在也能创建（MongoDB 会隐式建集合）。
2. **索引对齐文档**：每条索引对应 03-1 / 03-2 各节的「索引」行，不即兴发明。
"""

from __future__ import annotations

from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING as ASC
from pymongo import DESCENDING as DESC
from pymongo import TEXT

from ..core.config import settings
from . import collections as C

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongodb_uri, uuidRepresentation="standard")
    return _client


def get_database() -> AsyncIOMotorDatabase:
    return get_client()[settings.mongodb_db]


async def close_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


def _index_specs() -> dict[str, list[tuple[list[tuple[str, Any]], dict[str, Any]]]]:
    """返回 集合名 → [(keys, options)]。options 里的 name 便于幂等与排查。"""
    return {
        C.ACCOUNTS: [
            ([("invite_code_hash", ASC)], {"unique": True, "sparse": True, "name": "uq_invite_code_hash"}),
            # 用户名 / 手机号二选一，均为唯一；sparse 让未填的账号不参与唯一约束
            ([("username", ASC)], {"unique": True, "sparse": True, "name": "uq_username"}),
            ([("phone", ASC)], {"unique": True, "sparse": True, "name": "uq_phone"}),
            ([("status", ASC), ("created_at", DESC)], {"name": "status_created"}),
        ],
        C.INVITES: [
            ([("code_hash", ASC)], {"unique": True, "name": "uq_code_hash"}),
            ([("batch_id", ASC), ("revoked_at", ASC)], {"name": "batch_revoked"}),
            ([("expires_at", ASC)], {"sparse": True, "name": "expires_at"}),
        ],
        C.RECOVERY_CODES: [
            ([("account_id", ASC)], {"unique": True, "name": "uq_account"}),
            ([("code_hash", ASC)], {"name": "code_hash"}),
        ],
        C.CHILDREN: [
            ([("account_id", ASC)], {"name": "account"}),
            ([("account_id", ASC), ("status", ASC)], {"name": "account_status"}),
        ],
        C.DEVICES: [
            # 会话归属键：**(account_id, client_id)** —— 一台设备一条记录，多地可同时登入。
            # unique+sparse：同一账号下同一台设备只应有一条；sparse 是为了跳过
            # 早期版本留下的、没有 client_id 字段的旧记录，避免索引建不上。
            (
                [("account_id", ASC), ("client_id", ASC)],
                {"unique": True, "sparse": True, "name": "uq_account_client_id"},
            ),
            ([("account_id", ASC), ("client", ASC)], {"name": "account_client"}),
            ([("refresh_token_hash", ASC)], {"sparse": True, "name": "refresh_token_hash"}),
            ([("last_active_at", DESC)], {"name": "last_active"}),
        ],
        C.CHARACTERS: [
            ([("char", ASC)], {"unique": True, "name": "uq_char"}),
            ([("grade", ASC), ("difficulty", ASC)], {"name": "grade_difficulty"}),
            ([("level", ASC), ("status", ASC)], {"name": "level_status"}),
            ([("tags", ASC)], {"name": "tags"}),
            ([("unit_refs.unit_id", ASC)], {"name": "unit_refs_unit_id"}),
            ([("status", ASC)], {"name": "status"}),
            ([("char", TEXT), ("meaning", TEXT), ("words", TEXT)], {"name": "text_search"}),
        ],
        C.POEMS: [
            ([("title", ASC)], {"name": "title"}),
            ([("grade", ASC), ("difficulty", ASC)], {"name": "grade_difficulty"}),
            ([("theme_tags", ASC)], {"name": "theme_tags"}),
            ([("source", ASC)], {"name": "source"}),
            ([("key_characters", ASC)], {"name": "key_characters"}),
        ],
        C.CURRICULUM_UNITS: [
            ([("unit_code", ASC)], {"unique": True, "name": "uq_unit_code"}),
            ([("grade_num", ASC), ("semester", ASC), ("order", ASC)], {"name": "grade_semester_order"}),
        ],
        C.LESSONS: [
            ([("level", ASC), ("order", ASC)], {"name": "level_order"}),
            ([("unit_id", ASC)], {"name": "unit_id"}),
        ],
        C.ASSETS: [
            ([("type", ASC), ("subtype", ASC)], {"name": "type_subtype"}),
            ([("storage_key", ASC)], {"unique": True, "sparse": True, "name": "uq_storage_key"}),
            ([("status", ASC)], {"name": "status"}),
        ],
        C.STORIES: [
            ([("level", ASC), ("grade", ASC)], {"name": "level_grade"}),
            ([("status", ASC)], {"name": "status"}),
        ],
        C.BADGES: [
            ([("code", ASC)], {"unique": True, "name": "uq_code"}),
        ],
        C.CHILD_BADGES: [
            ([("child_id", ASC), ("badge_code", ASC)], {"unique": True, "name": "uq_child_badge"}),
        ],
        C.LEARNING_RECORDS: [
            ([("child_id", ASC), ("occurred_at", DESC)], {"name": "child_occurred"}),
            ([("child_id", ASC), ("event_type", ASC), ("occurred_at", DESC)], {"name": "child_event_occurred"}),
            ([("client", ASC), ("occurred_at", DESC)], {"name": "client_occurred"}),
        ],
        C.ANSWER_RECORDS: [
            ([("child_id", ASC), ("character_id", ASC), ("occurred_at", DESC)], {"name": "child_char_occurred"}),
            ([("child_id", ASC), ("is_correct", ASC), ("occurred_at", DESC)], {"name": "child_correct_occurred"}),
            # 幂等去重（04-1 §1.5）：同一孩子下 client_record_id 唯一；离线补报可安全重放
            ([("child_id", ASC), ("client_record_id", ASC)], {"unique": True, "sparse": True, "name": "uq_client_record"}),
        ],
        C.CHAR_REVIEW_STATES: [
            ([("child_id", ASC), ("next_review_at", ASC)], {"name": "child_next_review"}),
            ([("child_id", ASC), ("character_id", ASC)], {"unique": True, "name": "uq_child_char"}),
        ],
        C.WRONG_QUESTIONS: [
            ([("child_id", ASC), ("resolved", ASC), ("last_wrong_at", DESC)], {"name": "child_resolved_last"}),
        ],
        C.DAILY_TASKS: [
            ([("child_id", ASC), ("date", ASC)], {"unique": True, "name": "uq_child_date"}),
        ],
        C.SYNC_OBJECTS: [
            ([("account_id", ASC), ("object_type", ASC), ("object_key", ASC)], {"unique": True, "name": "uq_account_object"}),
            ([("updated_at", DESC)], {"name": "updated_at"}),
        ],
        C.STATS_EVENTS: [
            ([("bucket_date", ASC), ("event_name", ASC)], {"name": "bucket_event"}),
            ([("content_ref", ASC)], {"sparse": True, "name": "content_ref"}),
        ],
        C.FEEDBACKS: [
            ([("status", ASC), ("created_at", DESC)], {"name": "status_created"}),
            ([("category", ASC)], {"name": "category"}),
        ],
        C.AUDIT_LOGS: [
            ([("created_at", DESC)], {"name": "created_at"}),
            ([("action", ASC), ("created_at", DESC)], {"name": "action_created"}),
            ([("target_collection", ASC), ("target_id", ASC)], {"name": "target"}),
        ],
    }


async def init_indexes(db: AsyncIOMotorDatabase) -> None:
    """幂等创建全部索引。集合不存在时由 MongoDB 隐式创建，无需先建集合。"""
    for coll_name, specs in _index_specs().items():
        coll = db[coll_name]
        for keys, options in specs:
            try:
                await coll.create_index(keys, **options)
            except Exception as exc:  # noqa: BLE001
                # 索引冲突（如既有索引同名但定义不同）不应阻断启动，但要能看见
                print(f"[index] 创建失败 {coll_name} {options.get('name')}: {exc}")
