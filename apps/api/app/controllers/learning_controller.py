"""学习控制器（MVC —— Controller 层，04-1 §五 / 03-2 §五）。

**全部服务端存储**后，本层从「接收前端上报的增量」升级为**唯一主存储 + 服务端聚合**：
SRS 调度、每日任务生成、正确率/到期数/连续天数都在这里算，客户端只负责渲染。

写入策略优先单文档 upsert，规避跨文档事务（06-1 §3.2）。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from bson import ObjectId

from ..core import errors as E
from ..core.client_headers import ClientContext
from ..repositories import Repositories
from . import badges as badges_svc
from . import child_controller
from . import srs
from .serializers import serialize, to_iso


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _today_str(now: datetime | None = None) -> str:
    return (now or _now()).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# 每日任务（懒生成）
# ---------------------------------------------------------------------------
async def daily_task(
    repos: Repositories,
    account_id: ObjectId,
    child_id: str,
    date: str | None = None,
) -> dict:
    child = await child_controller.get_owned_child(repos, account_id, child_id)
    date = date or _today_str()
    task = await repos.daily_tasks.get(child["_id"], date)
    if task is None:
        task = await _generate_daily_task(repos, child, date)
    return await _render_daily_task(repos, task)


async def _generate_daily_task(repos: Repositories, child: dict, date: str) -> dict:
    child_oid = child["_id"]
    now = _now()

    review_ids = await repos.review_states.due_ids(
        child_oid, now, limit=int(child.get("daily_review_target", 12)) or 12
    )

    seen_ids = await repos.review_states.learned_ids(child_oid)
    new_ids = await repos.characters.new_candidates(
        int(child.get("grade", 1)),
        seen_ids,
        limit=int(child.get("daily_new_char_target", 8)) or 8,
    )

    wrong_ids = await repos.wrong_questions.unresolved_ids(child_oid, limit=10)

    doc: dict[str, Any] = {
        "child_id": child_oid,
        "date": date,
        "new_char_ids": [i for i in new_ids if i not in review_ids],
        "review_char_ids": review_ids,
        "wrong_char_ids": wrong_ids,
        "completed_char_ids": [],
        "status": "in_progress" if (new_ids or review_ids or wrong_ids) else "pending",
        "generated_at": now,
    }
    task, _ = await repos.daily_tasks.create_if_absent(doc)
    return task


async def _render_daily_task(repos: Repositories, task: dict) -> dict:
    ids = list(
        dict.fromkeys(
            (task.get("new_char_ids") or [])
            + (task.get("review_char_ids") or [])
            + (task.get("wrong_char_ids") or [])
        )
    )
    chars = await repos.characters.briefs(ids)
    by_id = {c["_id"]: c for c in chars}

    def brief(cid: str) -> dict:
        c = by_id.get(cid)
        return {"id": cid, "_id": cid, "char": c.get("char") if c else None}

    completed = task.get("completed_char_ids") or []
    return {
        "date": task.get("date"),
        "status": task.get("status"),
        "new_chars": [brief(i) for i in task.get("new_char_ids", [])],
        "review_chars": [brief(i) for i in task.get("review_char_ids", [])],
        "wrong_chars": [brief(i) for i in task.get("wrong_char_ids", [])],
        "completed_count": len(completed),
        "total_count": len(ids),
    }


# ---------------------------------------------------------------------------
# 答题
# ---------------------------------------------------------------------------
async def submit_answer(
    repos: Repositories,
    account_id: ObjectId,
    record,
    client: ClientContext,
) -> dict:
    child = await child_controller.get_owned_child(repos, account_id, record.child_id)
    result = await _apply_answer(repos, child, record, client)
    # 答完即把该字计入当日任务的完成集（服务端持有任务，客户端不必再回报进度）
    await repos.daily_tasks.complete_chars(child["_id"], _today_str(), [record.character_id], "in_progress")
    return result


async def submit_answers_batch(
    repos: Repositories,
    account_id: ObjectId,
    child_id: str,
    records: list,
    client: ClientContext,
) -> dict:
    child = await child_controller.get_owned_child(repos, account_id, child_id)
    accepted = 0
    skipped = 0
    seen_in_batch: set[str] = set()
    touched: list[str] = []
    for record in records:
        record.child_id = child_id
        crid = record.client_record_id
        if crid:
            if crid in seen_in_batch:
                skipped += 1
                continue
            seen_in_batch.add(crid)
            if await repos.answer_records.has_client_record(child["_id"], crid):
                skipped += 1
                continue
        await _apply_answer(repos, child, record, client)
        touched.append(record.character_id)
        accepted += 1
    if touched:
        await repos.daily_tasks.complete_chars(child["_id"], _today_str(), touched, "in_progress")
    return {"accepted": accepted, "skipped_duplicate": skipped}


async def _apply_answer(repos: Repositories, child: dict, record, client: ClientContext) -> dict:
    child_oid = child["_id"]
    now = record.occurred_at or _now()

    # 冗余汉字：优先用上报值，否则按 character_id 回填
    char = record.char
    if not char:
        c = await repos.characters.find_one({"_id": record.character_id}, {"char": 1})
        char = (c or {}).get("char", "")

    answer_doc: dict[str, Any] = {
        "child_id": child_oid,
        "character_id": record.character_id,
        "char": char,
        "question_type": record.question_type,
        "answer": record.answer,
        "correct_answer": record.correct_answer,
        "is_correct": record.is_correct,
        "response_ms": record.response_ms,
        "session_id": record.session_id or "",
        "occurred_at": now,
        "created_at": _now(),
    }
    if record.client_record_id:
        answer_doc["client_record_id"] = record.client_record_id
    await repos.answer_records.insert_answer(answer_doc)

    review_state = await _update_review_state(
        repos, child_oid, record.character_id, record.is_correct, now
    )

    if not record.is_correct:
        await repos.wrong_questions.record_wrong(
            child_oid, record.character_id, char, record.question_type, now
        )
    else:
        # 答对视为订正
        await repos.wrong_questions.resolve_on_correct(child_oid, record.character_id, now)

    newly = await _maybe_earn_badges(repos, child)
    await _refresh_child_stats(repos, child_oid)

    return {
        "is_correct": record.is_correct,
        "next_review_at": to_iso(review_state["next_review_at"]),
        "interval_days": review_state["interval_days"],
        "newly_earned_badges": newly,
    }


async def _update_review_state(
    repos: Repositories, child_oid: ObjectId, character_id: str, is_correct: bool, now: datetime
) -> dict:
    existing = await repos.review_states.get(child_oid, character_id)
    base = existing or srs.initial_state()
    updated = srs.compute_next(
        ease_factor=base.get("ease_factor", 2.5),
        interval_days=base.get("interval_days", 0),
        repetitions=base.get("repetitions", 0),
        total_correct=base.get("total_correct", 0),
        total_wrong=base.get("total_wrong", 0),
        # 旧文档没有这个字段：缺省 0 即可 —— 掌握会在接下来的答对里自然重新累积
        consecutive_correct=base.get("consecutive_correct", 0),
        is_correct=is_correct,
        now=now,
    )
    await repos.review_states.upsert(child_oid, character_id, updated)
    return updated


# ---------------------------------------------------------------------------
# 关卡完成
# ---------------------------------------------------------------------------
async def complete_lesson(
    repos: Repositories, account_id: ObjectId, req, client: ClientContext
) -> dict:
    child = await child_controller.get_owned_child(repos, account_id, req.child_id)
    now = req.occurred_at or _now()
    doc: dict[str, Any] = {
        "child_id": child["_id"],
        "event_type": req.event_type,
        "lesson_id": req.lesson_id,
        "poem_id": None,
        "character_ids": req.character_ids,
        "score": req.score,
        "total": req.total,
        "accuracy": req.accuracy,
        "stars": req.stars,
        "duration_ms": req.duration_ms,
        "client": client.client,
        "platform": client.platform,
        "device_form": client.device_form,
        "client_version": client.client_version,
        "occurred_at": now,
        "created_at": _now(),
    }
    if req.client_record_id:
        doc["client_record_id"] = req.client_record_id
    record_id = await repos.learning_records.insert_record(doc)
    newly = await _maybe_earn_badges(repos, child)
    return {"record_id": str(record_id), "newly_earned_badges": newly}


# ---------------------------------------------------------------------------
# 复习到期
# ---------------------------------------------------------------------------
async def review_due(
    repos: Repositories, account_id: ObjectId, child_id: str, limit: int = 50
) -> dict:
    child = await child_controller.get_owned_child(repos, account_id, child_id)
    states = await repos.review_states.list_due(child["_id"], _now(), limit=limit)
    ids = [s["character_id"] for s in states]
    chars = await repos.characters.briefs(ids)
    by_id = {c["_id"]: c for c in chars}
    items = [
        {
            "character_id": s["character_id"],
            "char": (by_id.get(s["character_id"]) or {}).get("char"),
            "ease_factor": s.get("ease_factor"),
            "interval_days": s.get("interval_days"),
            "next_review_at": to_iso(s.get("next_review_at")),
            "status": s.get("status"),
        }
        for s in states
    ]
    return {"items": items, "total": len(items)}


# ---------------------------------------------------------------------------
# 错题本
# ---------------------------------------------------------------------------
async def list_wrong_questions(
    repos: Repositories, account_id: ObjectId, child_id: str, resolved: bool | None = None
) -> dict:
    child = await child_controller.get_owned_child(repos, account_id, child_id)
    docs = await repos.wrong_questions.list_items(child["_id"], resolved)
    return {"items": serialize(docs), "total": len(docs)}


async def resolve_wrong_question(
    repos: Repositories, account_id: ObjectId, child_id: str, wrong_id: str
) -> dict:
    child = await child_controller.get_owned_child(repos, account_id, child_id)
    ok = await repos.wrong_questions.resolve_by_id(wrong_id, child["_id"], _now())
    if not ok:
        raise E.BizException(E.CONTENT_NOT_FOUND, "错题不存在")
    return {"resolved": True, "id": wrong_id}


# ---------------------------------------------------------------------------
# 进度总览
# ---------------------------------------------------------------------------
async def progress(repos: Repositories, account_id: ObjectId, child_id: str) -> dict:
    child = await child_controller.get_owned_child(repos, account_id, child_id)
    child_oid = child["_id"]
    by_status = await repos.review_states.count_by_status(child_oid)
    return {
        "total_learned": await repos.review_states.count_all(child_oid),
        "mastered": by_status.get(srs.MASTERED, 0),
        "reviewing": by_status.get(srs.REVIEWING, 0),
        "learning": by_status.get(srs.LEARNING, 0),
        "due_count": await repos.review_states.count_due(child_oid, _now()),
        "wrong_count": await repos.wrong_questions.count_unresolved(child_oid),
        "accuracy": await repos.answer_records.accuracy(child_oid),
    }


# ---------------------------------------------------------------------------
# 学习状态总览（服务端唯一真源 → 客户端一个请求拿全）
# ---------------------------------------------------------------------------
async def state(
    repos: Repositories,
    account_id: ObjectId,
    child_id: str,
    *,
    include_daily: bool = True,
) -> dict:
    """把「客户端首页 + 进度页」所需的全部学习状态一次下发。

    为什么要有它：改成服务端存储后，客户端不再持有主数据，
    首页若仍靠 5 个并发请求（任务 / 进度 / 到期 / 错题 / 徽章）拼装，
    既有「部分成功」的一致性问题，也拖慢首屏。这里一次聚合、一次返回。
    """
    child = await child_controller.get_owned_child(repos, account_id, child_id)
    child_oid = child["_id"]
    now = _now()

    by_status = await repos.review_states.count_by_status(child_oid)
    progress_block = {
        "total_learned": sum(by_status.values()),
        "mastered": by_status.get(srs.MASTERED, 0),
        "reviewing": by_status.get(srs.REVIEWING, 0),
        "learning": by_status.get(srs.LEARNING, 0),
        "due_count": await repos.review_states.count_due(child_oid, now),
        "wrong_count": await repos.wrong_questions.count_unresolved(child_oid),
        "accuracy": await repos.answer_records.accuracy(child_oid),
        "streak_days": (child.get("stats") or {}).get("streak_days", 0),
    }

    daily = await daily_task(repos, account_id, child_id) if include_daily else None
    due = await review_due(repos, account_id, child_id, limit=50)
    badges = await repos.child_badges.list_items(child_oid)

    return {
        "child": {
            "id": str(child_oid),
            "_id": str(child_oid),
            "nickname": child.get("nickname"),
            "grade": child.get("grade"),
            "avatar_key": child.get("avatar_key"),
            "daily_new_char_target": child.get("daily_new_char_target"),
            "daily_review_target": child.get("daily_review_target"),
            "daily_time_limit_min": child.get("daily_time_limit_min"),
        },
        "progress": progress_block,
        "daily_task": daily,
        "due_reviews": due["items"],
        "badges": [b.get("badge_code") for b in badges],
        "server_time": serialize(now),
    }


# ---------------------------------------------------------------------------
# 内部：统计与徽章
# ---------------------------------------------------------------------------
async def _compute_metrics(repos: Repositories, child: dict) -> dict:
    child_oid = child["_id"]
    stats = child.get("stats") or {}
    return {
        "char_count": await repos.review_states.count_all(child_oid),
        "lesson_count": await repos.learning_records.count_by_event(child_oid, "lesson_complete"),
        "poem_count": await repos.learning_records.count_by_event(child_oid, "poem_read"),
        "streak_days": stats.get("streak_days", 0),
        "accuracy": await repos.answer_records.accuracy(child_oid),
    }


async def _maybe_earn_badges(repos: Repositories, child: dict) -> list[dict]:
    child_oid = child["_id"]
    badge_defs = await repos.badges.list_active(limit=200)
    if not badge_defs:
        return []
    earned = await repos.child_badges.earned_codes(child_oid)
    metrics = await _compute_metrics(repos, child)
    newly = badges_svc.evaluate_badges(badge_defs=badge_defs, earned_codes=earned, metrics=metrics)
    now = _now()
    for badge in newly:
        await repos.child_badges.grant(child_oid, badge["code"], now)
    return newly


async def _refresh_child_stats(repos: Repositories, child_oid: ObjectId) -> None:
    by_status = await repos.review_states.count_by_status(child_oid)
    await repos.children.refresh_stats(
        child_oid,
        total=sum(by_status.values()),
        mastered=by_status.get(srs.MASTERED, 0),
        now=_now(),
    )


async def compute_streak(repos: Repositories, child_oid: ObjectId, *, days: int = 60) -> int:
    """连续学习天数（服务端算，客户端不再自行推导）。"""
    since = _now() - timedelta(days=days)
    buckets = await repos.learning_records.day_buckets(child_oid, since)
    buckets |= set((await repos.review_states.daily_buckets(child_oid, since)).keys())
    if not buckets:
        return 0
    streak = 0
    cursor = _now().date()
    while cursor.isoformat() in buckets:
        streak += 1
        cursor = cursor - timedelta(days=1)
    return streak


# ---------------------------------------------------------------------------
# 复习状态 / 徽章（客户端「全量同步」用）
# ---------------------------------------------------------------------------
async def list_review_states(
    repos: Repositories,
    account_id: ObjectId,
    child_id: str,
    *,
    character_id: str | None = None,
    limit: int = 3000,
) -> dict:
    """复习状态全量或单字查询。

    为什么要有全量接口：客户端首页的字表标注（已掌握/复习中）需要完整状态集，
    而 `/learning/state` 只带「到期」与聚合计数 —— 两者用途不同，不能互相替代。
    """
    child = await child_controller.get_owned_child(repos, account_id, child_id)
    child_oid = child["_id"]
    if character_id:
        state = await repos.review_states.get(child_oid, character_id)
        return {"items": [serialize(state)] if state else [], "total": 1 if state else 0}

    docs = await repos.review_states.list_all(child_oid, limit=limit)
    items = [
        {
            **serialize(d),
            # 与前端约定：复合键形态
            "_id": f"{child_oid}:{d.get('character_id')}",
            "child_id": str(child_oid),
        }
        for d in docs
    ]
    return {"items": items, "total": len(items)}


async def list_child_badges(
    repos: Repositories, account_id: ObjectId, child_id: str
) -> dict:
    """已获徽章（含定义信息，客户端可直接渲染徽章墙）。"""
    child = await child_controller.get_owned_child(repos, account_id, child_id)
    child_oid = child["_id"]
    earned = await repos.child_badges.list_items(child_oid)
    defs = {b.get("code"): b for b in await repos.badges.list_active(limit=200)}
    items = []
    for row in earned:
        code = row.get("badge_code")
        definition = defs.get(code, {})
        items.append(
            {
                "_id": f"{child_oid}:{code}",
                "child_id": str(child_oid),
                "badge_code": code,
                "title": definition.get("title", code),
                "description": definition.get("description"),
                "earned_at": serialize(row.get("earned_at")),
            }
        )
    return {"items": items, "total": len(items)}


async def list_learning_records(
    repos: Repositories, account_id: ObjectId, child_id: str, *, limit: int = 200
) -> dict:
    child = await child_controller.get_owned_child(repos, account_id, child_id)
    docs = await repos.learning_records.recent(child["_id"], limit=limit)
    return {"items": serialize(docs), "total": len(docs)}


async def list_answer_records(
    repos: Repositories, account_id: ObjectId, child_id: str, *, limit: int = 2000
) -> dict:
    child = await child_controller.get_owned_child(repos, account_id, child_id)
    docs = await repos.answer_records.recent(child["_id"], limit=limit)
    return {"items": serialize(docs), "total": len(docs)}


# ---------------------------------------------------------------------------
# 数据可迁移性（导出源为服务端真源；导出/导入作为备份与迁移手段）
# ---------------------------------------------------------------------------
SCHEMA_VERSION = 1


async def export_bundle(repos: Repositories, account_id: ObjectId, child_id: str) -> dict:
    """导出该孩子的完整学习数据包（JSON 可直接落盘，也可再导入）。

    导出源为服务端真源。
    这让「数据可迁移」这条 P0 承诺在服务端存储下依然成立 ——
    用户的数据不因我们换了存储位置而变得更难带走。
    """
    child = await child_controller.get_owned_child(repos, account_id, child_id)
    child_oid = child["_id"]
    tasks = await repos.daily_tasks.find_many({"child_id": child_oid}, limit=500)
    return {
        "schema_version": SCHEMA_VERSION,
        "exported_at": serialize(_now()),
        "child": serialize(child),
        "review_states": (await list_review_states(repos, account_id, child_id))["items"],
        "wrong_questions": (await list_wrong_questions(repos, account_id, child_id))["items"],
        "learning_records": (await list_learning_records(repos, account_id, child_id, limit=500))["items"],
        "answer_records": (await list_answer_records(repos, account_id, child_id, limit=2000))["items"],
        "child_badges": (await list_child_badges(repos, account_id, child_id))["items"],
        "daily_tasks": serialize(tasks),
    }
