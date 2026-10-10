"""儿童档案控制器（MVC —— Controller 层，04-1 §三 / 03-2 §3.4）。

**全部服务端存储**后，档案不再是「前端主存 + 云端镜像」，MongoDB 是唯一真源。
归属校验：跨账号访问返回 40301（不是 404），避免泄漏「该档案是否存在」。
"""

from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId

from ..core import errors as E
from ..models.child import ChildCreate, ChildUpdate
from ..repositories import Repositories
from .serializers import serialize


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def get_owned_child(repos: Repositories, account_id: ObjectId, child_id: str) -> dict:
    """取当前账号下的档案，不存在/不属于本账号统一报 40301（防枚举）。"""
    child = await repos.children.get_owned(account_id, child_id)
    if child is None:
        raise E.BizException(E.FORBIDDEN, "无权访问该儿童档案")
    return child


async def list_children(repos: Repositories, account_id: ObjectId) -> list[dict]:
    return serialize(await repos.children.list_by_account(account_id))


async def create_child(repos: Repositories, account_id: ObjectId, req: ChildCreate) -> dict:
    now = _now()
    doc = {
        "account_id": account_id,
        "nickname": req.nickname,
        "avatar_key": req.avatar_key,
        "grade": req.grade,
        "birth_year": req.birth_year,
        "unit_preference": req.unit_preference,
        "daily_new_char_target": req.daily_new_char_target,
        "daily_review_target": req.daily_review_target,
        "daily_time_limit_min": req.daily_time_limit_min,
        "status": "active",
        "stats": {
            "total_learned": 0,
            "mastered": 0,
            "streak_days": 0,
            "last_study_at": None,
        },
        "created_at": now,
    }
    inserted = await repos.children.insert_one(doc)
    doc["_id"] = inserted
    return serialize(doc)


async def get_child(repos: Repositories, account_id: ObjectId, child_id: str) -> dict:
    return serialize(await get_owned_child(repos, account_id, child_id))


async def update_child(
    repos: Repositories, account_id: ObjectId, child_id: str, req: ChildUpdate
) -> dict:
    child = await get_owned_child(repos, account_id, child_id)
    patch = req.model_dump(exclude_none=True)
    await repos.children.update_fields(child["_id"], patch)
    return serialize(await get_owned_child(repos, account_id, child_id))


async def delete_child(repos: Repositories, account_id: ObjectId, child_id: str) -> dict:
    child = await get_owned_child(repos, account_id, child_id)
    # 软删除：children.status 取值为 active/archived（03-2 §3.4），不物理删除学习数据
    await repos.children.archive(child["_id"])
    return {"deleted": True, "child_id": child_id}


async def child_stats(repos: Repositories, account_id: ObjectId, child_id: str) -> dict:
    child = await get_owned_child(repos, account_id, child_id)
    stats = child.get("stats") or {}
    child_oid = child["_id"]
    return {
        "total_learned": stats.get("total_learned", 0),
        "mastered": stats.get("mastered", 0),
        "streak_days": stats.get("streak_days", 0),
        "last_study_at": serialize(stats.get("last_study_at")),
        "due_count": await repos.review_states.count_due(child_oid, _now()),
        "wrong_count": await repos.wrong_questions.count_unresolved(child_oid),
    }
