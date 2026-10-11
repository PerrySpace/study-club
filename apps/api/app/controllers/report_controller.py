"""报告控制器（MVC —— Controller 层，04-1 §七）。

学习数据全部服务端化，MongoDB 是唯一真源，
因此报告不再需要 `compute_locally` 降级路径。该字段保留（恒为 false）以兼容既有客户端契约：
字段只增不改不删（04-1 §1.2）。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from bson import ObjectId

from ..repositories import Repositories
from . import child_controller
from . import srs
from .serializers import serialize


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _basic_counts(repos: Repositories, child_oid: ObjectId) -> dict:
    by_status = await repos.review_states.count_by_status(child_oid)
    total = sum(by_status.values())
    return {
        "total_learned": total,
        "mastered": by_status.get(srs.MASTERED, 0),
        "reviewing": by_status.get(srs.REVIEWING, 0),
        "learning": by_status.get(srs.LEARNING, 0),
        "struggling": await repos.wrong_questions.count_unresolved(child_oid),
    }


async def overview(repos: Repositories, account_id: ObjectId, child_id: str) -> dict:
    child = await child_controller.get_owned_child(repos, account_id, child_id)
    child_oid = child["_id"]
    counts = await _basic_counts(repos, child_oid)
    stats = child.get("stats") or {}

    now = _now()
    recent = await _recent_summary(repos, child_oid, now - timedelta(days=7))

    return {
        "child": {
            "id": str(child_oid),
            "_id": str(child_oid),
            "nickname": child.get("nickname"),
            "grade": child.get("grade"),
        },
        "summary": {
            **counts,
            "streak_days": stats.get("streak_days", 0),
            "total_duration_min": await _duration_min(repos, child_oid),
        },
        "period": {
            "from": (child.get("created_at") or now).date().isoformat(),
            "to": now.date().isoformat(),
        },
        "recent_7d": recent,
        "available": True,
        "source": "server",
        "compute_locally": False,
        "note": None,
    }


async def _recent_summary(repos: Repositories, child_oid: ObjectId, since: datetime) -> dict:
    studied_days = await repos.learning_records.day_buckets(child_oid, since)
    learned = await repos.review_states.count_reviewed_since(child_oid, since)
    return {
        "studied_days": len(studied_days),
        "chars_learned": learned,
        "accuracy": await repos.answer_records.accuracy(child_oid, since),
    }


async def _duration_min(repos: Repositories, child_oid: ObjectId) -> int:
    return int(await repos.learning_records.total_duration_ms(child_oid) // 60000)


async def trend(repos: Repositories, account_id: ObjectId, child_id: str, days: int = 30) -> dict:
    child = await child_controller.get_owned_child(repos, account_id, child_id)
    child_oid = child["_id"]
    since = _now() - timedelta(days=days)

    buckets = await repos.answer_records.daily_buckets(child_oid, since)
    for date, learned in (await repos.review_states.daily_buckets(child_oid, since)).items():
        b = buckets.setdefault(date, {"date": date, "learned": 0, "correct": 0, "total": 0})
        b["learned"] = learned
    items = [buckets[k] for k in sorted(buckets)]
    return {"items": items, "days": days, "compute_locally": False}


async def mastery(repos: Repositories, account_id: ObjectId, child_id: str) -> dict:
    child = await child_controller.get_owned_child(repos, account_id, child_id)
    counts = await _basic_counts(repos, child["_id"])
    total = counts["total_learned"] or 0
    return {
        "distribution": {
            "mastered": counts["mastered"],
            "reviewing": counts["reviewing"],
            "learning": counts["learning"],
        },
        "mastery_rate": round(counts["mastered"] / total, 4) if total else 0.0,
        "compute_locally": False,
    }


async def weak_chars(
    repos: Repositories, account_id: ObjectId, child_id: str, limit: int = 50
) -> dict:
    child = await child_controller.get_owned_child(repos, account_id, child_id)
    docs = await repos.wrong_questions.weakest(child["_id"], limit=limit)
    items = [
        {
            "character_id": d.get("character_id"),
            "char": d.get("char"),
            "wrong_count": d.get("wrong_count", 0),
            "question_types": d.get("question_types", []),
            "last_wrong_at": serialize(d.get("last_wrong_at")),
        }
        for d in docs
    ]
    return {"items": items, "compute_locally": False}


async def weekly(repos: Repositories, account_id: ObjectId, child_id: str) -> dict:
    child = await child_controller.get_owned_child(repos, account_id, child_id)
    child_oid = child["_id"]
    since = _now() - timedelta(days=7)
    recent = await _recent_summary(repos, child_oid, since)
    counts = await _basic_counts(repos, child_oid)
    return {
        "week_start": since.date().isoformat(),
        "week_end": _now().date().isoformat(),
        "studied_days": recent["studied_days"],
        "chars_learned": recent["chars_learned"],
        "accuracy": recent["accuracy"],
        "total_learned": counts["total_learned"],
        "mastered": counts["mastered"],
        "available": True,
    }
