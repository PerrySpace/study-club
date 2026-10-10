"""认证控制器（MVC —— Controller 层）—— 邀请码 + 自设口令的注册/登入/刷新/恢复/注销（02-5 §三、§四）。

安全要点：
- 口令 Argon2id；邀请码只存 SHA-256 哈希
- 失败信息统一（防枚举）；限流 + 失败锁定
- Refresh Token 只存哈希，可吊销
- 恢复码仅返回一次，服务端只存哈希
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from ..core import errors as E
from ..core import runtime_config
from ..core.client_headers import ClientContext
from ..core.config import settings
from ..core.security import (
    create_access_token,
    create_refresh_token,
    generate_recovery_code,
    hash_passcode,
    login_limiter,
    sha256_hex,
    verify_passcode,
)
from ..repositories import Repositories
from . import invite_controller
from .serializers import serialize, to_iso


def _now() -> datetime:
    return datetime.now(timezone.utc)


# 用户名：4–20 位，字母开头，允许字母 / 数字 / 下划线（ASCII，避免全角与易混字符）
_USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{3,19}$")
# 手机号：中国大陆手机号（11 位，1 开头，第二位 3–9）
_PHONE_RE = re.compile(r"^1[3-9]\d{9}$")


# ---------------------------------------------------------------------------
# 口令强度
# ---------------------------------------------------------------------------
def validate_passcode(pin: str | None) -> None:
    """≥6 位，不接受纯连续/纯重复数字（家长易用与安全的折中，见 02-5 §3.1）。"""
    if not pin or len(pin) < 6:
        raise E.BizException(
            E.PARAM_INVALID,
            "口令不合规",
            errors=[{"field": "pin", "reason": "口令至少 6 位"}],
        )
    if pin.isdigit():
        digits = [int(c) for c in pin]
        ascending = all(digits[i + 1] - digits[i] == 1 for i in range(len(digits) - 1))
        descending = all(digits[i + 1] - digits[i] == -1 for i in range(len(digits) - 1))
        same = len(set(digits)) == 1
        if ascending or descending or same:
            raise E.BizException(
                E.PARAM_INVALID,
                "口令不合规",
                errors=[{"field": "pin", "reason": "口令不能是连续或重复的数字"}],
            )


# ---------------------------------------------------------------------------
# 账号标识（用户名 / 手机号）格式与归一化
# ---------------------------------------------------------------------------
def normalize_username(username: str | None) -> str | None:
    value = (username or "").strip()
    return value or None


def normalize_phone(phone: str | None) -> str | None:
    """去掉空格 / 连字符 / 括号后返回纯数字串。"""
    value = re.sub(r"[\s\-()]", "", phone or "")
    return value or None


def validate_username(username: str) -> None:
    if not _USERNAME_RE.match(username):
        raise E.BizException(
            E.PARAM_INVALID,
            "参数校验失败",
            errors=[
                {
                    "field": "username",
                    "reason": "用户名为 4–20 位，字母开头，仅含字母 / 数字 / 下划线",
                }
            ],
        )


def validate_phone(phone: str) -> None:
    if not _PHONE_RE.match(phone):
        raise E.BizException(
            E.PARAM_INVALID,
            "参数校验失败",
            errors=[{"field": "phone", "reason": "请输入有效的 11 位手机号"}],
        )


def validate_identifiers(username: str | None, phone: str | None) -> None:
    """用户名与手机号**至少填一个**；填了就要格式正确。"""
    if not username and not phone:
        raise E.BizException(
            E.PARAM_INVALID,
            "参数校验失败",
            errors=[{"field": "username", "reason": "用户名与手机号至少填写一个"}],
        )
    if username:
        validate_username(username)
    if phone:
        validate_phone(phone)


# ---------------------------------------------------------------------------
# 账号摘要
# ---------------------------------------------------------------------------
def account_summary(account: dict) -> dict:
    return serialize(
        {
            "_id": account["_id"],
            "account_id": account["_id"],
            "username": account.get("username"),
            "phone": account.get("phone"),
            "display_name": account.get("display_name"),
            "avatar_key": account.get("avatar_key"),
            "e2e_enabled": account.get("e2e_enabled", True),
            "role": account.get("role", "learner"),
            "status": account.get("status", "active"),
            "access_tier": account.get("access_tier", "invite_only"),
            "last_login_at": account.get("last_login_at"),
            "created_at": account.get("created_at"),
            "updated_at": account.get("updated_at"),
        }
    )


# ---------------------------------------------------------------------------
# 邀请码校验（预检，不消耗次数）
# ---------------------------------------------------------------------------
async def verify_invite(repos: Repositories, code: str) -> dict:
    invite = await repos.invites.find_by_code_hash(invite_controller.hash_invite_code(code))
    valid = bool(invite and invite_controller.is_usable(invite))
    return {"valid": valid, "access_tier": "invite_only"}


# ---------------------------------------------------------------------------
# 注册
# ---------------------------------------------------------------------------
async def register(repos: Repositories, req, client: ClientContext) -> dict:
    validate_passcode(req.resolved_passcode)

    username = normalize_username(getattr(req, "username", None))
    phone = normalize_phone(getattr(req, "phone", None))
    invite_code = getattr(req, "invite_code", None)
    validate_identifiers(username, phone)

    now = _now()
    invite_doc = None

    # 注册开关（运行时可改，见 core/runtime_config.py）
    if not runtime_config.is_registration_open():
        raise E.BizException(E.FEATURE_DISABLED, "当前已关闭注册")

    # 邀请码开关（服务端强制，防绕过前端）：开启时必填，关闭时可选。
    if runtime_config.is_invite_required() and not invite_code:
        raise E.BizException(
            E.INVITE_INVALID,
            "本次注册需要邀请码",
            errors=[{"field": "invite_code", "reason": "请填写邀请码"}],
        )
    # 有码 → 必须有效；无码 → 免码开放（放量期 / 开源默认），access_tier=open
    if invite_code:
        invite_doc = await repos.invites.find_by_code_hash(invite_controller.hash_invite_code(invite_code))
        if not invite_doc or not invite_controller.is_usable(invite_doc, now):
            raise E.BizException(E.INVITE_INVALID, E.UNIFIED_AUTH_MESSAGE)

    # 用户名 / 手机号唯一性前置校验（显式 check，避免撞唯一索引被兜成 500）
    if username and await repos.accounts.find_by_username(username):
        raise E.BizException(
            E.PARAM_INVALID,
            "参数校验失败",
            errors=[{"field": "username", "reason": "该用户名已被占用"}],
        )
    if phone and await repos.accounts.find_by_phone(phone):
        raise E.BizException(
            E.PARAM_INVALID,
            "参数校验失败",
            errors=[{"field": "phone", "reason": "该手机号已被占用"}],
        )

    display_name = (req.display_name or "我的家").strip()[:20] or "我的家"
    invite_hash = (
        sha256_hex(invite_controller.normalize_code(invite_code)) if invite_code else None
    )

    # ⚠️ 「一码一账号」是刻意的身份模型（02-5 §2.2 / §3.4）：邀请码即账号的登录标识，
    #    家庭内部共用「同一码 + 同一口令」进同一个档案空间；需要隔离就再发一个码。
    #    因此 accounts.invite_code_hash 上有唯一索引。这里必须先做一次**显式前置校验**——
    #    否则重复注册会撞唯一索引，把 pymongo.DuplicateKeyError 抛成 500「服务内部错误」，
    #    既泄漏了数据库约束、又让用户看到一个无法理解的错误（02-5 §4.4 要求统一文案防枚举）。
    if invite_hash is not None:
        bound = await repos.accounts.find_by_invite_hash(invite_hash)
        if bound is not None:
            raise E.BizException(E.INVITE_INVALID, E.UNIFIED_AUTH_MESSAGE)

    account_doc = {
        "display_name": display_name,
        "avatar_key": req.avatar_key or "rabbit",
        "passcode_hash": hash_passcode(req.resolved_passcode or ""),
        "invite_code_hash": invite_hash,
        "sync_key_salt": None,
        "e2e_enabled": bool(req.e2e_enabled),
        "role": "learner",
        "status": "active",
        "access_tier": "invite_only" if invite_code else "open",
        "last_login_at": now,
        "failed_attempts": 0,
        "locked_until": None,
        "created_at": now,
        "updated_at": now,
    }
    # ⚠️ username / phone 用**缺省字段**而非 null：唯一索引是 sparse，
    #    稀疏只跳过「没有该字段」的文档 —— 显式写 null 仍会被索引，
    #    多个「没填用户名」的账号就会互相撞唯一键。
    if username is not None:
        account_doc["username"] = username
    if phone is not None:
        account_doc["phone"] = phone

    try:
        account_id = await repos.accounts.insert_one(account_doc)
    except DuplicateKeyError as exc:
        # 并发窗口：两个请求同时通过了上面的前置校验，唯一索引兜住了第二个。
        # 按撞到的键回不同的文案 —— 撞用户名/手机号给字段级提示；撞邀请码仍用统一文案。
        raise _translate_duplicate(exc) from None
    account_doc["_id"] = account_id

    # 消耗邀请码（原子：仅当仍有剩余次数时 +1）
    if invite_doc is not None:
        consumed = await repos.invites.consume(invite_doc["_id"], account_id)
        if not consumed:  # 并发下被抢空
            await repos.accounts.delete_one({"_id": account_id})
            raise E.BizException(E.INVITE_INVALID, E.UNIFIED_AUTH_MESSAGE)

    # 恢复码：明文只返回一次
    raw_recovery = generate_recovery_code()
    await repos.recovery_codes.issue(
        account_id=account_id, code_hash=sha256_hex(raw_recovery), now=now
    )

    tokens = await _issue_session(repos, account_id, client, account_doc["role"])
    return {
        **_flat_tokens(account_id, tokens),
        "recovery_code": raw_recovery,
        "e2e_enabled": account_doc["e2e_enabled"],
        # 附加字段（字段只增不改不删，便于前端 client.ts 直接消费）
        "account": account_summary(account_doc),
        "tokens": tokens,
    }


# ---------------------------------------------------------------------------
# 登入
# ---------------------------------------------------------------------------
async def login(repos: Repositories, req, client: ClientContext) -> dict:
    """旧版邀请码登入（保留向后兼容）。"""
    _rate_limit(client)
    account = await repos.accounts.find_by_invite_hash(
        invite_controller.hash_invite_code(req.invite_code)
    )
    return await _finish_login(repos, account, req, client, unified=E.UNIFIED_AUTH_MESSAGE,
                               error_code=E.INVITE_INVALID)


async def login_by_account(repos: Repositories, req, client: ClientContext) -> dict:
    """统一账号登入：`identifier` 可填**用户名或手机号**。"""
    _rate_limit(client)
    identifier = req.resolved_identifier
    account = await repos.accounts.find_by_identifier(identifier) if identifier else None
    return await _finish_login(repos, account, req, client, unified=E.UNIFIED_ACCOUNT_MESSAGE,
                               error_code=E.ACCOUNT_INVALID)


def _rate_limit(client: ClientContext) -> None:
    """登录限流：按 client_id + IP（02-5 §4.4）。"""
    if not login_limiter.allow(client.rate_limit_key):
        raise E.BizException(E.RATE_LIMITED, "请求过于频繁，请稍后再试")


async def _finish_login(
    repos: Repositories,
    account: dict | None,
    req,
    client: ClientContext,
    *,
    unified: str,
    error_code: int,
) -> dict:
    """登录共用后半程：锁定检查 → 口令校验 → 失败计数 → 签发会话。

    两条登录通道（邀请码 / 账号）共用它，保证安全语义完全一致：
    统一文案防枚举、失败锁定、成功清零。
    """
    if account is None or account.get("status") == "deleted":
        # 统一错误信息，不暴露「账号不存在」
        raise E.BizException(error_code, unified)

    _check_locked(account)

    if not verify_passcode(req.resolved_passcode or "", account.get("passcode_hash", "")):
        await _register_failure(repos, account)
        raise E.BizException(error_code, unified)

    if account.get("status") == "disabled":
        raise E.BizException(E.FORBIDDEN, "账号已被禁用")

    now = _now()
    await repos.accounts.mark_login(account["_id"], now=now)
    login_limiter.reset(client.rate_limit_key)
    account["last_login_at"] = now
    account["failed_attempts"] = 0
    account["locked_until"] = None

    tokens = await _issue_session(repos, account["_id"], client, account.get("role", "learner"))
    return {
        **_flat_tokens(account["_id"], tokens),
        "e2e_enabled": account.get("e2e_enabled", True),
        "account": account_summary(account),
        "tokens": tokens,
    }


# ---------------------------------------------------------------------------
# 恢复码重置口令
# ---------------------------------------------------------------------------
async def reset_passcode(repos: Repositories, req) -> dict:
    validate_passcode(req.resolved_passcode)
    recovery = await repos.recovery_codes.find_by_hash(sha256_hex(req.recovery_code))
    if recovery is None or recovery.get("used_at") is not None:
        raise E.BizException(E.RECOVERY_INVALID, "恢复码无效或已使用")

    now = _now()
    await repos.accounts.set_passcode(
        recovery["account_id"], passcode_hash=hash_passcode(req.resolved_passcode or ""), now=now
    )
    await repos.recovery_codes.mark_used(recovery["_id"], now=now)
    # 重置口令会改变端到端加密密钥派生结果，客户端须重新派生（服务端不持有密钥）
    return {"account_id": str(recovery["account_id"]), "reset_at": to_iso(now)}


# ---------------------------------------------------------------------------
# 刷新
# ---------------------------------------------------------------------------
async def refresh(repos: Repositories, refresh_token: str) -> dict:
    device = await repos.devices.find_by_refresh_hash(sha256_hex(refresh_token))
    if device is None or device.get("revoked"):
        raise E.BizException(E.TOKEN_INVALID, "Token 无效")
    account = await repos.accounts.find_one({"_id": device["account_id"]})
    if account is None or account.get("status") != "active":
        raise E.BizException(E.TOKEN_INVALID, "Token 无效")

    # 轮换 Refresh Token（旧哈希立即失效）
    new_refresh, new_refresh_hash = create_refresh_token(str(account["_id"]))
    await repos.devices.rotate_refresh(device["_id"], refresh_token_hash=new_refresh_hash, now=_now())
    access, expires_in = create_access_token(str(account["_id"]), account.get("role", "learner"))
    tokens = {
        "access_token": access,
        "refresh_token": new_refresh,
        "expires_in": expires_in,
        "token_type": "Bearer",
    }
    return {**tokens, "tokens": tokens}


# ---------------------------------------------------------------------------
# 登出（吊销该设备 Refresh Token）
# ---------------------------------------------------------------------------
async def logout(repos: Repositories, account: dict, refresh_token: str | None) -> dict:
    if refresh_token:
        await repos.devices.revoke_by_refresh_hash(
            account_id=account["_id"], refresh_token_hash=sha256_hex(refresh_token)
        )
    else:
        await repos.devices.revoke_all(account["_id"])
    return {"revoked": True}


# ---------------------------------------------------------------------------
# 注销并删除云端数据（合规必需，04-1 §二）
# ---------------------------------------------------------------------------
async def delete_account(repos: Repositories, account: dict) -> dict:
    account_id = account["_id"]
    # 软删除账号（保留审计线索，但不再可登录）
    await repos.accounts.soft_delete(account_id, now=_now())
    # 物理删除云端个人数据：同步密文、档案、学习数据、设备会话、恢复码
    child_ids = await repos.children.ids_for_account(account_id)
    await repos.sync_objects.purge_account(account_id)
    await repos.devices.purge_account(account_id)
    await repos.recovery_codes.delete_many({"account_id": account_id})
    await repos.purge_child_data(child_ids)
    return {"deleted": True, "account_id": str(account_id)}


# ---------------------------------------------------------------------------
# 「我」摘要
# ---------------------------------------------------------------------------
async def me(repos: Repositories, account: dict) -> dict:
    summary = account_summary(account)
    summary["children_count"] = await repos.accounts.count_active_children(account["_id"])
    return summary


# ---------------------------------------------------------------------------
# 内部：会话与锁定
# ---------------------------------------------------------------------------
def _translate_duplicate(exc: DuplicateKeyError) -> E.BizException:
    """把唯一索引冲突翻译成**字段级**业务错误。

    并发窗口下前置校验可能同时通过，最终由唯一索引兜住第二个请求。
    按撞到的键给不同文案：用户名/手机号 → 字段级提示；邀请码 → 统一文案（防枚举）。
    """
    details = getattr(exc, "details", None) or {}
    key_pattern = details.get("keyPattern") or {}
    if "username" in key_pattern:
        return E.BizException(
            E.PARAM_INVALID, "参数校验失败", errors=[{"field": "username", "reason": "该用户名已被占用"}]
        )
    if "phone" in key_pattern:
        return E.BizException(
            E.PARAM_INVALID, "参数校验失败", errors=[{"field": "phone", "reason": "该手机号已被占用"}]
        )
    return E.BizException(E.INVITE_INVALID, E.UNIFIED_AUTH_MESSAGE)


def _flat_tokens(account_id: ObjectId, tokens: dict) -> dict:
    """04-1 §2.1 的扁平出参 + 附加 token_type。"""
    return {
        "account_id": str(account_id),
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "expires_in": tokens["expires_in"],
        "token_type": tokens.get("token_type", "Bearer"),
    }


async def _issue_session(
    repos: Repositories, account_id: ObjectId, client: ClientContext, role: str
) -> dict:
    access, expires_in = create_access_token(str(account_id), role)
    refresh, refresh_hash = create_refresh_token(str(account_id))
    await repos.devices.upsert_session(
        account_id=account_id, client=client, refresh_token_hash=refresh_hash, now=_now()
    )
    return {
        "access_token": access,
        "refresh_token": refresh,
        "expires_in": expires_in,
        "token_type": "Bearer",
    }


def _check_locked(account: dict) -> None:
    locked_until = account.get("locked_until")
    if locked_until is None:
        return
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    if locked_until > _now():
        raise E.BizException(E.ACCOUNT_LOCKED, "账号已锁定，请稍后再试")


async def _register_failure(repos: Repositories, account: dict) -> None:
    attempts = int(account.get("failed_attempts", 0)) + 1
    lock_until = None
    if attempts >= settings.login_lock_threshold:
        lock_until = _now() + timedelta(minutes=settings.login_lock_minutes)
    await repos.accounts.register_failure(
        account["_id"], attempts=attempts, lock_until=lock_until, now=_now()
    )
