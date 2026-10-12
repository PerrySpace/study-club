"""单管理员后台控制器（MVC —— Controller 层）。

不做 RBAC：只有「是/不是管理员」两种身份（见 05-1）。所有写操作记入 audit_logs。
审计不记录明文邀请码/密码/密文载荷——`diff` 只记元数据（03-1 §7.1）。

**一套通用 CRUD 覆盖 6 类内容**：差异（集合名 / id 规则 / 必填字段 / 可搜索字段）
全部来自 `repositories/content_registry.py` 的**数据**，因此新增一类内容不需要改本文件。
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId

from ..core import errors as E
from ..repositories import Repositories
from ..repositories.content_registry import REGISTRY, all_specs, spec_for
from . import content_import_controller, invite_controller, srs
from .serializers import serialize

# 单字符汉字 id：与内容包既有命名一致（ch_<codepoint hex>）
_CHAR_ID = re.compile(r"^ch_[0-9a-f]+$")
_SLUG_KEEP = re.compile(r"[^0-9A-Za-z_-]")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _slug(value: str, *, fallback: str) -> str:
    """把标题一类的中文/任意文本转成可作为 `_id` 后缀的 ASCII 串。

    纯中文会得到空串，此时退化为随机后缀 —— `_id` 只求稳定且唯一，
    可读性靠 title 字段，不靠 id。
    """
    ascii_part = _SLUG_KEEP.sub("", value.strip().lower().replace(" ", "-"))
    if len(ascii_part) >= 2:
        return ascii_part[:48]
    return fallback


# ---------------------------------------------------------------------------
# 审计
# ---------------------------------------------------------------------------
async def log_audit(
    repos: Repositories,
    *,
    actor: dict,
    action: str,
    target_collection: str,
    target_id: Any = None,
    diff: dict | None = None,
    ip: str = "unknown",
) -> None:
    await repos.audit_logs.record(
        {
            "actor_id": actor.get("_id"),
            "actor_role": actor.get("role", "admin"),
            "action": action,
            "target_collection": target_collection,
            "target_id": target_id,
            "diff": diff,
            "ip": ip,
            "created_at": _now(),
        }
    )


async def list_audit_logs(
    repos: Repositories, *, skip: int, limit: int, action: str | None = None, collection: str | None = None
) -> tuple[list[dict], int]:
    items, total = await repos.audit_logs.list_page(
        skip=skip, limit=limit, action=action, target_collection=collection
    )
    return serialize(items), total


# ---------------------------------------------------------------------------
# 后台首页：内容完整度概览（05-1 §八 / §九）
# ---------------------------------------------------------------------------
async def overview(repos: Repositories) -> dict:
    """只读聚合，供后台首页看板使用。

    设计约束（05-1 §1.3 / §六）：**只统计聚合计数，不返回任何用户内容**；
    儿童数据即使已服务端化，概览也只呈现体量，不下钻到个体明细。
    """
    char_total = await repos.characters.count()
    invite_total = await repos.invites.count()
    invite_revoked = await repos.invites.revoked_count()
    usage = await repos.invites.usage_totals()

    return {
        "characters": {
            "total": char_total,
            "by_status": await repos.characters.count_by("status"),
            "by_grade": await repos.characters.count_by("grade"),
            # 素材完备率（05-1 §八）：上架前应绑定配图 / 音频 / 笔顺数据
            "assets": await repos.characters.asset_completeness(),
        },
        "content": await repos.content_counts(),
        "assets": await repos.assets.stats(),
        "invites": {
            "total": invite_total,
            "active": invite_total - invite_revoked,
            "revoked": invite_revoked,
            "used_count": usage["used_count"],
            "capacity": usage["capacity"],
            "batches": await repos.invites.batch_count(),
        },
        "accounts": await repos.accounts.count(),
        "children": await repos.children.count({"status": {"$ne": "archived"}}),
        "audit_logs": await repos.audit_logs.count_all(),
    }


def registry_descriptor() -> list[dict]:
    """把注册表下发给后台，让「内容管理」页能按 schema 渲染表格与表单。

    这是「后台由数据驱动」的关键：后台前端不需要为每类内容硬编码列与字段。
    """
    return [
        {
            "key": spec.key,
            "collection": spec.collection,
            "label": spec.label,
            "id_prefix": spec.id_prefix,
            "id_source": spec.id_source,
            "required_on_create": list(spec.required_on_create),
            "searchable": list(spec.searchable),
            "filters": list(spec.filters),
            "default_sort": [list(pair) for pair in spec.default_sort],
            "unique_fields": list(spec.unique_fields),
            # 是否有可下载的模板：没有 field_docs 的类型（如徽章）不给「下载模板」按钮
            "has_template": bool(spec.field_docs),
        }
        for spec in all_specs()
    ]


# ---------------------------------------------------------------------------
# 邀请码管理
# ---------------------------------------------------------------------------
async def create_invites(
    repos: Repositories,
    req,
    actor: dict,
    ip: str,
) -> dict:
    batch_id = req.batch_id or f"batch-{_now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"
    expires_at = _now() + timedelta(days=req.expires_in_days) if req.expires_in_days else None
    raw_codes = invite_controller.generate_raw_codes(req.count)
    # 恒为 1：邀请码即账号的登录标识（02-5 §2.2 / 03-1 §3.1），
    # 一个码只能激活一个账号。请求模型已把 max_uses 限成 le=1，这里再钉一次是
    # **双保险**——绕过 pydantic（内部调用 / 将来改模型）也不会写出一个骗人的码。
    max_uses = 1
    docs = [
        invite_controller.make_invite_document(
            raw_code=raw,
            batch_id=batch_id,
            channel=req.channel,
            max_uses=max_uses,
            expires_at=expires_at,
            note=req.note,
            created_by=actor.get("_id"),
        )
        for raw in raw_codes
    ]
    if docs:
        await repos.invites.insert_batch(docs)
    await log_audit(
        repos,
        actor=actor,
        action="invite.batch_create",
        target_collection="invites",
        diff={"batch_id": batch_id, "count": req.count, "max_uses": max_uses, "channel": req.channel},
        ip=ip,
    )
    # ⚠️ 明文码只在创建时返回这一次
    return {
        "batch_id": batch_id,
        "count": len(docs),
        "expires_at": serialize(expires_at),
        "codes": [
            {"code": invite_controller.format_for_delivery(raw), "code_hint": invite_controller.invite_code_hint(raw)}
            for raw in raw_codes
        ],
    }


async def list_invites(
    repos: Repositories,
    skip: int,
    limit: int,
    batch_id: str | None = None,
    channel: str | None = None,
) -> tuple[list[dict], int]:
    items, total = await repos.invites.list_page(skip=skip, limit=limit, batch_id=batch_id, channel=channel)
    return serialize(items), total


async def revoke_invite(repos: Repositories, invite_id: str, actor: dict, ip: str) -> dict:
    oid = _object_id(invite_id, missing=E.CONTENT_NOT_FOUND, message="邀请码不存在")
    revoked = await repos.invites.revoke(oid, now=_now())
    if not revoked and not await repos.invites.exists({"_id": oid}):
        raise E.BizException(E.CONTENT_NOT_FOUND, "邀请码不存在")
    await log_audit(
        repos,
        actor=actor,
        action="invite.revoke",
        target_collection="invites",
        target_id=oid,
        ip=ip,
    )
    return {"revoked": True, "id": invite_id}


# ---------------------------------------------------------------------------
# 用户管理（账号级 —— 只下钻到账号，不含学习明细）
# ---------------------------------------------------------------------------
def _mask_phone(phone: str | None) -> str | None:
    """手机号掩码：只露前 3 位与后 4 位（后台最小可见，见 05-1 §1.3）。"""
    if not phone:
        return None
    if len(phone) < 7:
        return phone[:1] + "****"
    return phone[:3] + "****" + phone[-4:]


def _user_row(doc: dict) -> dict:
    return {
        "_id": doc["_id"],
        "username": doc.get("username"),
        "phone_masked": _mask_phone(doc.get("phone")),
        "has_phone": bool(doc.get("phone")),
        "display_name": doc.get("display_name"),
        "avatar_key": doc.get("avatar_key"),
        "role": doc.get("role", "learner"),
        "status": doc.get("status", "active"),
        "access_tier": doc.get("access_tier", "open"),
        "last_login_at": doc.get("last_login_at"),
        "created_at": doc.get("created_at"),
    }


async def list_users(
    repos: Repositories,
    *,
    skip: int,
    limit: int,
    keyword: str | None = None,
    status: str | None = None,
    role: str | None = None,
    has_children: bool | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
) -> tuple[list[dict], int]:
    items, total = await repos.accounts.list_page(
        skip=skip,
        limit=limit,
        keyword=keyword,
        status=status,
        role=role,
        has_children=has_children,
        created_from=created_from,
        created_to=created_to,
    )
    # children_count 在列表里一并给出：前端要显示「档案数」，
    # 若逐行再查一次就是 N+1 次查询。
    counts = await _children_counts(repos, [d["_id"] for d in items])
    rows = []
    for doc in items:
        row = _user_row(doc)
        row["children_count"] = counts.get(doc["_id"], 0)
        rows.append(serialize(row))
    return rows, total


async def _children_counts(repos: Repositories, account_ids: list[Any]) -> dict[Any, int]:
    """一次聚合统计多个账号的孩子档案数（避免 N+1）。"""
    if not account_ids:
        return {}
    rows = await repos.children.aggregate(
        [
            {"$match": {"account_id": {"$in": account_ids}, "status": {"$ne": "archived"}}},
            {"$group": {"_id": "$account_id", "n": {"$sum": 1}}},
        ]
    )
    return {r["_id"]: r["n"] for r in rows}


async def get_user(repos: Repositories, account_id: str) -> dict:
    oid = _object_id(account_id, missing=E.CONTENT_NOT_FOUND, message="账号不存在")
    doc = await repos.accounts.find_one({"_id": oid}, {"passcode_hash": 0, "sync_key_salt": 0})
    if doc is None:
        raise E.BizException(E.CONTENT_NOT_FOUND, "账号不存在")
    row = _user_row(doc)
    row["children_count"] = await repos.accounts.count_active_children(oid)
    return serialize(row)


# ---------------------------------------------------------------------------
# 用户编辑 / 注销 / 批量
# ---------------------------------------------------------------------------
# 可编辑字段白名单。刻意**不含**：
#   - `passcode_hash` / `invite_code_hash`：改登录凭据必须走各自专用方法，
#     否则会绕过密码哈希校验与登录锁定；
#   - `sync_key_salt`：端到端加密密钥盐，一改就再也解不开历史密文；
#   - `role`：单管理员后台没有多角色体系（05-1 §1.3），开放它等于凭空造 RBAC。
_USER_EDITABLE_FIELDS = ("display_name", "avatar_key", "access_tier")


async def update_user(
    repos: Repositories,
    account_id: str,
    payload: dict[str, Any],
    actor: dict,
    ip: str,
) -> dict:
    oid = _object_id(account_id, missing=E.CONTENT_NOT_FOUND, message="账号不存在")

    patch: dict[str, Any] = {}
    for field in _USER_EDITABLE_FIELDS:
        if field not in payload:
            continue
        value = payload[field]
        if field == "display_name":
            value = (str(value).strip() or None) if value is not None else None
            if value and len(value) > 24:
                raise E.BizException(
                    E.PARAM_INVALID,
                    "参数校验失败",
                    errors=[{"field": "display_name", "reason": "昵称不超过 24 字"}],
                )
        else:
            value = str(value).strip() or None if value is not None else None
        patch[field] = value

    if not patch:
        raise E.BizException(
            E.PARAM_INVALID,
            "没有可修改的字段",
            errors=[{"field": "fields", "reason": f"仅支持修改：{'、'.join(_USER_EDITABLE_FIELDS)}"}],
        )

    ok = await repos.accounts.update_profile(oid, patch=patch, now=_now())
    if not ok:
        raise E.BizException(E.CONTENT_NOT_FOUND, "账号不存在")

    await log_audit(
        repos,
        actor=actor,
        action="account.update",
        target_collection="accounts",
        target_id=oid,
        diff={"fields": sorted(patch.keys())},
        ip=ip,
    )
    return await get_user(repos, account_id)


async def delete_user(
    repos: Repositories, account_id: str, actor: dict, ip: str
) -> dict:
    """注销账号（软删）。

    与「禁用」的区别：禁用可恢复，注销不可 —— 会释放邀请码占用并使所有会话失效。
    **儿童学习数据保留**：这是儿童数据最小化的底线，注销的是「登录资格」不是「学习记录」。
    """
    oid = _object_id(account_id, missing=E.CONTENT_NOT_FOUND, message="账号不存在")
    doc = await repos.accounts.find_one({"_id": oid})
    if doc is None:
        raise E.BizException(E.CONTENT_NOT_FOUND, "账号不存在")
    if doc.get("status") == "deleted":
        raise E.BizException(E.PARAM_INVALID, "该账号已注销")

    await repos.accounts.soft_delete(oid, now=_now())
    # 会话全部失效：否则已登录的设备在凭证到期前仍能继续写学习数据
    await repos.devices.revoke_all(oid)
    await log_audit(
        repos,
        actor=actor,
        action="account.delete",
        target_collection="accounts",
        target_id=oid,
        diff={"children_preserved": await repos.accounts.count_active_children(oid)},
        ip=ip,
    )
    return {"deleted": True, "id": account_id, "children_preserved": True}


async def bulk_user_status(
    repos: Repositories,
    account_ids: list[str],
    status: str,
    actor: dict,
    ip: str,
) -> dict:
    """批量启用 / 禁用。逐个走同一套校验与审计，不做「一把梭」。

    部分成功是可以接受的：返回成功与失败的 id，让操作者知道哪几个没成、
    原因是什么 —— 静默吞掉失败比报错更危险。
    """
    if status not in ("active", "disabled"):
        raise E.BizException(E.PARAM_INVALID, "状态只能是 active 或 disabled")
    if not account_ids:
        raise E.BizException(E.PARAM_INVALID, "请选择至少一个账号")

    succeeded: list[str] = []
    failed: list[dict] = []
    for raw_id in account_ids[:100]:
        try:
            oid = _object_id(raw_id, missing=E.CONTENT_NOT_FOUND, message="账号不存在")
        except E.BizException as exc:
            failed.append({"id": raw_id, "reason": exc.message})
            continue
        ok = await repos.accounts.set_status(oid, status=status, now=_now())
        if ok:
            succeeded.append(raw_id)
        else:
            failed.append({"id": raw_id, "reason": "账号不存在"})

    await log_audit(
        repos,
        actor=actor,
        action=f"account.bulk_{status}",
        target_collection="accounts",
        diff={"count": len(succeeded), "failed": len(failed)},
        ip=ip,
    )
    return {"succeeded": succeeded, "failed": failed, "status": status}


async def set_user_status(
    repos: Repositories, account_id: str, status: str, actor: dict, ip: str
) -> dict:
    """启用 / 禁用账号。禁用后该账号无法登入（登录侧已校验 status）。"""
    oid = _object_id(account_id, missing=E.CONTENT_NOT_FOUND, message="账号不存在")
    ok = await repos.accounts.set_status(oid, status=status, now=_now())
    if not ok:
        raise E.BizException(E.CONTENT_NOT_FOUND, "账号不存在")
    await log_audit(
        repos,
        actor=actor,
        action=f"account.{status}",
        target_collection="accounts",
        target_id=oid,
        diff={"status": status},
        ip=ip,
    )
    return {"id": account_id, "status": status}


async def user_stats(repos: Repositories) -> dict:
    """用户体量聚合（后台用户页顶部卡片）。只计数，不含个体明细。"""
    by_status = await repos.accounts.count_by_status()
    return {
        "total": sum(v for k, v in by_status.items() if k != "deleted"),
        "by_status": by_status,
        "with_phone": await repos.accounts.count({"phone": {"$exists": True}, "status": {"$ne": "deleted"}}),
        "with_username": await repos.accounts.count(
            {"username": {"$exists": True}, "status": {"$ne": "deleted"}}
        ),
        "children": await repos.children.count({"status": {"$ne": "archived"}}),
    }


async def user_report(repos: Repositories, account_id: str, *, days: int = 7) -> dict:
    """账号级学习报告（后台点开某个用户时看）。

    对标主流识字产品家长端的「识字报告」：家长要看的是
    **识字总进度 / 已认汉字 / 掌握汉字 / 识字天数 / 最近一周的掌握量**，
    而不是一堆原始答题明细。故这里只给聚合值，且刻意把
    「已认（learned）」与「掌握（mastered）」**分开列** ——
    家长据此能分辨「这字只是见过一面」和「这字已经稳了」，
    复习该往哪儿使劲才有依据（这是竞品报告里最有用的一列）。
    """
    oid = _object_id(account_id, missing=E.CONTENT_NOT_FOUND, message="账号不存在")
    doc = await repos.accounts.find_one({"_id": oid}, {"passcode_hash": 0, "sync_key_salt": 0})
    if doc is None:
        raise E.BizException(E.CONTENT_NOT_FOUND, "账号不存在")

    since = _now() - timedelta(days=max(1, days))
    children = await repos.children.list_by_account(oid, include_archived=True)

    child_rows: list[dict] = []
    totals = {
        "learned": 0,
        "mastered": 0,
        "reviewing": 0,
        "learning": 0,
        "wrong": 0,
        "lessons": 0,
        "poems": 0,
        "badges": 0,
    }
    trend_map: dict[str, dict] = {}

    for child in children:
        cid = child["_id"]
        by_status = await repos.review_states.count_by_status(cid)
        learned = sum(by_status.values())
        mastered = by_status.get(srs.MASTERED, 0)
        lessons = await repos.learning_records.count_by_event(cid, "lesson_complete")
        poems = await repos.learning_records.count_by_event(cid, "poem_read")
        badges = len(await repos.child_badges.list_items(cid))
        wrong = await repos.wrong_questions.count_unresolved(cid)
        stats = child.get("stats") or {}

        child_rows.append(
            {
                "_id": str(cid),
                "nickname": child.get("nickname"),
                "grade": child.get("grade"),
                "status": child.get("status", "active"),
                "learned": learned,
                "mastered": mastered,
                "reviewing": by_status.get(srs.REVIEWING, 0),
                "learning": by_status.get(srs.LEARNING, 0),
                "mastery_rate": round(mastered / learned, 4) if learned else 0.0,
                "accuracy": await repos.answer_records.accuracy(cid),
                "wrong_count": wrong,
                "lesson_count": lessons,
                "poem_count": poems,
                "badge_count": badges,
                "streak_days": stats.get("streak_days", 0),
                "last_study_at": serialize(stats.get("last_study_at")),
            }
        )

        totals["learned"] += learned
        totals["mastered"] += mastered
        totals["reviewing"] += by_status.get(srs.REVIEWING, 0)
        totals["learning"] += by_status.get(srs.LEARNING, 0)
        totals["wrong"] += wrong
        totals["lessons"] += lessons
        totals["poems"] += poems
        totals["badges"] += badges

        # 趋势：答对率与题量按天合并（同一账号多档案相加，家长关心的是"这家今天练了多少"）
        for day, bucket in (await repos.answer_records.daily_buckets(cid, since)).items():
            slot = trend_map.setdefault(day, {"date": day, "total": 0, "correct": 0})
            slot["total"] += bucket.get("total", 0)
            slot["correct"] += bucket.get("correct", 0)

    for slot in trend_map.values():
        total = slot["total"]
        slot["accuracy"] = round(slot["correct"] / total, 4) if total else 0.0

    row = _user_row(doc)
    row["children_count"] = await repos.accounts.count_active_children(oid)
    return serialize(
        {
            "account": row,
            "children": child_rows,
            "totals": {
                **totals,
                "children": len(children),
                "mastery_rate": round(totals["mastered"] / totals["learned"], 4)
                if totals["learned"]
                else 0.0,
            },
            "trend": [trend_map[k] for k in sorted(trend_map)],
            "window_days": days,
        }
    )


# ---------------------------------------------------------------------------
# 内容通用 CRUD（6 类内容共用一套实现）
# ---------------------------------------------------------------------------
def _object_id(value: str, *, missing: int, message: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError) as exc:
        raise E.BizException(missing, message) from exc


def _repo_and_spec(repos: Repositories, collection: str):
    spec = spec_for(collection)
    if spec is None:
        raise E.BizException(
            E.PARAM_INVALID,
            "不支持的内容类型",
            errors=[{"field": "collection", "reason": f"未知集合 {collection}"}],
        )
    return getattr(repos, spec.key), spec


def _build_content_filter(spec, *, status: str | None, keyword: str | None, extra: dict[str, Any]) -> dict:
    flt: dict[str, Any] = {}
    if status:
        flt["status"] = status
    if keyword:
        kw = re.escape(keyword.strip())
        fields = list(spec.searchable) or ["_id"]
        flt["$or"] = [{f: {"$regex": kw, "$options": "i"}} for f in fields]
    for field in spec.filters:
        value = extra.get(field)
        if value not in (None, ""):
            flt[field] = value
    return flt


async def list_content(
    repos: Repositories,
    collection: str,
    *,
    skip: int,
    limit: int,
    status: str | None = None,
    keyword: str | None = None,
    extra: dict[str, Any] | None = None,
) -> tuple[list[dict], int]:
    repo, spec = _repo_and_spec(repos, collection)
    flt = _build_content_filter(spec, status=status, keyword=keyword, extra=extra or {})
    items, total = await repo.paginate(
        flt, sort=[("updated_at", -1), ("_id", 1)], skip=skip, limit=limit
    )
    return serialize(items), total


# 导出时剔除的只读内部字段（与 _strip_internal 对称）
_EXPORT_DROP = {"created_at", "updated_at", "created_by", "reviewed_by", "reviewed_at"}


async def export_content(
    repos: Repositories,
    collection: str,
    *,
    status: str | None = None,
    keyword: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict:
    """导出某类内容为**可回写仓库的 JSON**（幂等：导入时按 `_id` upsert 回同一文档）。

    返回文档原样（保留 `_id`），但剔除服务端维护的时间戳 / 审阅字段，
    让导出文件适合进 git、也适合再次导入。
    """
    repo, spec = _repo_and_spec(repos, collection)
    flt = _build_content_filter(spec, status=status, keyword=keyword, extra=extra or {})
    docs = await repo.find_many(flt, sort=list(spec.default_sort) or [("_id", 1)], limit=100000)
    items = [{k: v for k, v in serialize(d).items() if k not in _EXPORT_DROP} for d in docs]
    return {"collection": spec.collection, "label": spec.label, "count": len(items), "documents": items}


async def character_grade_counts(repos: Repositories) -> dict:
    """字库按年级的计数（后台「按年级分类」用）。

    grade 缺失的归入「未分级」，前端据此展示年级 Tab 与数量徽标。
    """
    by_grade = await repos.characters.count_by("grade")
    by_status = await repos.characters.count_by("status")
    return {
        "total": sum(v for k, v in by_grade.items()),
        "by_grade": by_grade,
        "by_status": by_status,
    }


def _derive_id(spec, payload: dict[str, Any], char: str | None) -> str:
    if spec.collection == "characters":
        if not char:
            raise E.BizException(
                E.PARAM_INVALID, "参数校验失败", errors=[{"field": "char", "reason": "创建时必须提供汉字本体"}]
            )
        if len(char) != 1:
            raise E.BizException(
                E.PARAM_INVALID, "参数校验失败", errors=[{"field": "char", "reason": "汉字必须是单个字符"}]
            )
        return "ch_" + format(ord(char), "x")

    source_value = str(payload.get(spec.id_source) or "") if spec.id_source else ""
    if not source_value:
        raise E.BizException(
            E.PARAM_INVALID,
            "参数校验失败",
            errors=[{"field": spec.id_source or "_id", "reason": f"创建{spec.label}时必须提供"}],
        )
    return spec.id_prefix + _slug(source_value, fallback=uuid.uuid4().hex[:10])


async def _assert_required(spec, payload: dict[str, Any]) -> None:
    missing = [f for f in spec.required_on_create if not str(payload.get(f) or "").strip()]
    if missing:
        raise E.BizException(
            E.PARAM_INVALID,
            "参数校验失败",
            errors=[{"field": f, "reason": f"{spec.label}的该字段为必填"} for f in missing],
        )


def _strip_internal(payload: dict[str, Any]) -> dict[str, Any]:
    """写库前剔掉只读内部字段：`_id` 由服务端派生，时间戳由服务端维护。"""
    return {k: v for k, v in payload.items() if k not in ("_id", "created_at", "updated_at", "created_by", "reviewed_by", "reviewed_at")}


async def _after_content_write(repos: Repositories, collection: str) -> None:
    """单条内容写入（新增 / 编辑 / 下架 / 删除）之后的**两件必做事**。

    两件都是「改完能立刻被看见」的前提，缺一个就会出现「改了没反应」：

    1. **重算关卡** —— 关卡是派生数据（由字库 / 古诗 / 识字短文算出），
       孩子端地图读的也是关卡而不是内容本身。不重算，改了内容等于没改。
    2. **刷新清单版本** —— `/health` 与客户端看到的 `content_version` 不变，
       客户端就不会重拉内容，于是「库里改了、客户端还是旧的」会伪装成缓存问题。
    """
    await content_import_controller.rebuild_lessons_for(repos, [collection])
    await content_import_controller.refresh_manifest(repos)


async def create_content(
    repos: Repositories, collection: str, payload: dict[str, Any], actor: dict, ip: str
) -> dict:
    repo, spec = _repo_and_spec(repos, collection)
    await _assert_required(spec, payload)

    char = payload.get("char") if spec.collection == "characters" else None
    doc_id = _derive_id(spec, payload, char)

    if await repo.exists({"_id": doc_id}):
        raise E.BizException(E.CONTENT_EXISTS, f"{spec.label}已存在")

    for field in spec.unique_fields:
        value = payload.get(field)
        if value and await repo.exists({field: value}):
            raise E.BizException(
                E.CONTENT_EXISTS,
                f"{spec.label}已存在",
                errors=[{"field": field, "reason": "该值已被占用"}],
            )

    now = _now()
    data = _strip_internal(payload)
    doc = {
        "_id": doc_id,
        **data,
        "status": data.get("status") or ("active" if spec.collection == "badges" else "draft"),
        "version": int(data.get("version") or 1),
        "created_by": actor.get("_id"),
        "created_at": now,
        "updated_at": now,
    }
    await repo.insert_one(doc)
    await log_audit(
        repos,
        actor=actor,
        action=f"{spec.collection}.create",
        target_collection=spec.collection,
        target_id=doc_id,
        diff={"id": doc_id},
        ip=ip,
    )
    await _after_content_write(repos, spec.collection)
    return serialize(doc)


async def update_content(
    repos: Repositories, collection: str, doc_id: str, payload: dict[str, Any], actor: dict, ip: str
) -> dict:
    repo, spec = _repo_and_spec(repos, collection)
    existing = await repo.find_one({"_id": doc_id})
    if existing is None:
        raise E.BizException(E.CONTENT_NOT_FOUND, f"{spec.label}不存在")

    for field in spec.unique_fields:
        value = payload.get(field)
        if value and value != existing.get(field) and await repo.exists({field: value}):
            raise E.BizException(
                E.CONTENT_EXISTS,
                f"{spec.label}已存在",
                errors=[{"field": field, "reason": "该值已被占用"}],
            )

    patch = _strip_internal(dict(payload))
    patch["version"] = int(existing.get("version", 1)) + 1
    patch["updated_at"] = _now()
    saved = await repo.save(doc_id, patch)
    await log_audit(
        repos,
        actor=actor,
        action=f"{spec.collection}.update",
        target_collection=spec.collection,
        target_id=doc_id,
        diff={"fields": sorted(patch.keys())},
        ip=ip,
    )
    await _after_content_write(repos, spec.collection)
    return serialize(saved or {**existing, **patch})


# 谁可能「指向」一条内容：这些集合的 `character_ids` 装的是别的内容 id
# （识字关装字 id、古诗关装诗 id、故事关装故事 id；单元装字 id）。
# ⚠️ 三元组是（Repositories 属性名, 集合名, 字段）——**这两个名字不一样**：
#    单元在 Repositories 上是 `units`，集合名却叫 `curriculum_units`，
#    混用会在查引用时直接 AttributeError（测试已钉住）。
_REFERENCE_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("lessons", "lessons", "character_ids"),
    ("units", "curriculum_units", "character_ids"),
)


async def references_for(repos: Repositories, collection: str, doc_id: str) -> list[dict[str, Any]]:
    """列出「谁在引用这条内容」（空列表 = 没人引用，可放心删）。

    为什么非要查：物理删除会留下**悬空引用**，而且它不报错 ——
    表现只是关卡点进去空空如也，或解锁链指向一扇不存在的门（孩子被卡住）。
    这类故障在界面上看不出原因，所以必须在删之前拦住。
    """
    counts: dict[str, dict[str, Any]] = {}

    if collection in ("characters", "poems", "stories"):
        for repo_key, coll_name, field in _REFERENCE_FIELDS:
            n = await getattr(repos, repo_key).count({field: doc_id})
            if n:
                entry = counts.setdefault(repo_key, {"collection": coll_name, "count": 0})
                entry["count"] += n

    # 关卡之间靠 `required_lesson_id` 串成解锁链：删一个关卡会让后继关卡指向空。
    if collection == "lessons":
        n = await repos.lessons.count({"required_lesson_id": doc_id})
        if n:
            entry = counts.setdefault("lessons", {"collection": "lessons", "count": 0})
            entry["count"] += n

    out: list[dict[str, Any]] = []
    for repo_key, entry in sorted(counts.items()):
        spec = spec_for(entry["collection"])
        out.append(
            {
                "collection": entry["collection"],
                "label": spec.label if spec else repo_key,
                "count": entry["count"],
            }
        )
    return out


async def delete_content(
    repos: Repositories,
    collection: str,
    doc_id: str,
    actor: dict,
    ip: str,
    *,
    hard: bool = False,
    force: bool = False,
) -> dict:
    """删除一条内容。**两种语义刻意分开，默认不改变既有行为。**

    - `hard=False`（默认）＝ **下架**：只把 status 置为 offline，随时能改回来。
      这是内容运营的常规动作，也是推荐做法（客户端立刻不再下发，数据还在）。
    - `hard=True` ＝ **物理删除**：从库里真的移除，**不可恢复**。
      用于「导入了一批错数据、要清掉重来」这类场景。

    `hard=True` 时先查引用：仍被关卡 / 单元 / 短文引用则**拒绝**（40903），
    并把引用明细回给调用方，由前端提示「这个字被 3 个关卡用着」。
    确实要删就显式 `force=True`，此时悬空引用的后果由操作者自行承担。
    """
    repo, spec = _repo_and_spec(repos, collection)
    if await repo.find_one({"_id": doc_id}) is None:
        raise E.BizException(E.CONTENT_NOT_FOUND, f"{spec.label}不存在")

    if not hard:
        ok = await repo.soft_delete(doc_id, now=_now())
        if not ok:
            raise E.BizException(E.CONTENT_NOT_FOUND, f"{spec.label}不存在")
        await log_audit(
            repos,
            actor=actor,
            action=f"{spec.collection}.offline",
            target_collection=spec.collection,
            target_id=doc_id,
            ip=ip,
        )
        # ⚠️ 下架也要重算关卡 + 刷版本：它同样改变了「哪些内容参与生成」，
        #    漏掉这一步的症状是「下架了但孩子端还在练」。
        await _after_content_write(repos, spec.collection)
        return {"deleted": True, "id": doc_id, "hard": False, "references": []}

    references = await references_for(repos, collection, doc_id)
    if references and not force:
        raise E.BizException(
            E.CONTENT_IN_USE,
            f"「{spec.label}」仍被引用，删除会让它们指向不存在的内容",
            errors=[
                {"field": r["collection"], "reason": f"{r['label']} 引用 {r['count']} 处"}
                for r in references
            ],
        )

    removed = await repo.delete_one({"_id": doc_id})
    if not removed:
        raise E.BizException(E.CONTENT_NOT_FOUND, f"{spec.label}不存在")

    await log_audit(
        repos,
        actor=actor,
        action=f"{spec.collection}.delete",
        target_collection=spec.collection,
        target_id=doc_id,
        diff={"hard": True, "force": force, "references": references},
        ip=ip,
    )
    # ⚠️ 清单计数与 content_version 必须跟着变：否则 `/health` 停在旧版本、
    #    客户端不重拉，「库里删了、客户端还显示着」会伪装成缓存问题。
    #    同理，删了内容还得重算关卡 —— 悬空引用正是靠这一步收敛的。
    await _after_content_write(repos, spec.collection)
    return {"deleted": True, "id": doc_id, "hard": True, "references": references}


def known_collections() -> list[str]:
    return list(REGISTRY.keys())


# ---------------------------------------------------------------------------
# 内容模板下载
# ---------------------------------------------------------------------------
def content_template(collection: str) -> dict:
    """生成「下载模板」用的 JSON：字段说明 + 一条可直接照抄的示例。

    为什么给模板而不是让用户自己看 schema：
      - `content/schema/*.json` 在仓库里，但**不会进产物**（前端容器里没有仓库），
        运营同学拿不到；
      - 导入是**宽松**的（`extra="allow"`，只对必填字段做校验），
        所以真正需要告知的就是「每个字段什么意思、哪些必填、哪些是派生字段（改了没用）」。

    派生字段（如 `new_character_chars` / `word_count`）在模板里明确标为
    「导入时自动生成」，避免运营反复手改后与正文不一致。
    """
    spec = spec_for(collection)
    if spec is None:
        raise E.BizException(E.PARAM_INVALID, f"不支持的内容类型：{collection}")

    required = set(spec.required_on_create)
    fields = [
        {
            "name": name,
            "required": name in required,
            "desc": desc,
            "derived": name in _DERIVED_FIELDS,
        }
        for name, desc in spec.field_docs
    ]

    return {
        "collection": spec.collection,
        "label": spec.label,
        "_comment": (
            f"{spec.label}导入模板。把 items 数组替换成真实内容后上传到后台「导入 JSON」；"
            f"导入按 _id 幂等 upsert，可重复导入来更新已有内容。"
            f"必填字段：{'、'.join(sorted(required)) or '无'}。"
            f"⚠️ 导入只写数据库（不会写回仓库 content/）。"
            f"发布（deploy）时：仓库里**已有**的集合不会再被重新播种 "
            f"—— 数据库有数据就以数据库为准，只补缺、不覆盖、不删除，"
            f"所以导入的内容会保留下来。"
            f"若某次发布跑过 `seed --force`，才会以仓库为准并清理库内多余条目。"
            f"⚠️ 状态必须是 published、grade 必须填，否则客户看不到（详见 fields 里的说明）。"
        ),
        "fields": fields,
        "items": [dict(spec.template_sample)] if spec.template_sample else [],
    }


# 导入时**自动重算**、手改无效的字段。在模板里显式标注，避免运营对着它反复改。
# 只列**当前仍有模板可下载的类型**（字库 / 古诗）会命中的字段名：
# 标错一个名字不会报错，只会让运营对着一个「改了没反应」的字段空试（已踩过）。
_DERIVED_FIELDS = frozenset(
    {
        "pinyin_plain",  # 汉字：由 pinyin 推导
        "full_text",  # 古诗：由 lines 拼接
        "version",  # 任何内容：更新时自增
    }
)
