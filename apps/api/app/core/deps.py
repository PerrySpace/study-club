"""依赖注入（06-1 §3.1）：数据库、当前账号、单管理员鉴权、客户端标识。"""

from __future__ import annotations

from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends, Header, Request
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..db import collections as C
from ..db.mongo import get_database
from ..repositories import Repositories
from . import errors as E
from .client_headers import ClientContext, parse_client_context
from .config import settings
from .security import decode_token, verify_passcode


async def get_db() -> AsyncIOMotorDatabase:
    return get_database()


async def get_repos(db: AsyncIOMotorDatabase = Depends(get_db)) -> "Repositories":
    """仓储容器依赖（MVC 的分层边界）。

    view 只声明 `repos: Repositories = Depends(get_repos)`，
    控制器只接受 `Repositories` —— 于是「业务代码碰不到 motor」成为**结构上**的保证，
    而不只是口头约定。
    """
    return Repositories(db)


def get_client_context(request: Request) -> ClientContext:
    return parse_client_context(request)


def _bearer(request: Request, authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


async def get_optional_account(
    request: Request,
    authorization: str | None = Header(default=None),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any] | None:
    """无 Token 时返回 None（用于 feedbacks 这类「允许匿名」的接口）。"""
    token = _bearer(request, authorization)
    if not token:
        return None
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise E.BizException(E.TOKEN_INVALID, "Token 无效")
    account = await _load_account(db, payload.get("sub"))
    if account is None or account.get("status") == "deleted":
        raise E.BizException(E.TOKEN_INVALID, "Token 无效")
    if account.get("status") == "disabled":
        raise E.BizException(E.FORBIDDEN, "账号已被禁用")
    return account


async def get_current_account(
    account: dict[str, Any] | None = Depends(get_optional_account),
) -> dict[str, Any]:
    if account is None:
        raise E.BizException(E.TOKEN_INVALID, "需要登录")
    return account


async def get_current_admin(
    request: Request,
    authorization: str | None = Header(default=None),
    x_admin_password: str | None = Header(default=None, alias="X-Admin-Password"),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """单管理员鉴权（不做 RBAC，见 05-1）。

    两种等价入口：
    1. 携带 admin 身份 JWT（管理员账号经 /admin/login 获取，role=admin）
    2. 携带 `X-Admin-Password` 头，与 ADMIN_PASSWORD_HASH 做 Argon2 校验

    第二种让「只有口令哈希、没有管理员账号」的部署也能用后台。
    """
    token = _bearer(request, authorization)
    if token:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise E.BizException(E.TOKEN_INVALID, "Token 无效")
        # 管理员登录令牌（sub=admin）无对应 accounts 记录，直接放行
        if payload.get("role") == "admin":
            sub = payload.get("sub")
            account = None
            if sub:
                try:
                    ObjectId(sub)
                    account = await _load_account(db, sub)
                except (InvalidId, TypeError):
                    account = None
            return account or {"_id": None, "role": "admin", "display_name": "admin", "access_tier": "open"}

    if x_admin_password and settings.admin_password_hash:
        if verify_passcode(x_admin_password, settings.admin_password_hash):
            # 返回一个最小化管理员主体，供 audit_logs 记录 actor
            return {"_id": None, "role": "admin", "display_name": "admin", "access_tier": "open"}

    raise E.BizException(E.FORBIDDEN, "需要管理员身份")


async def _load_account(db: AsyncIOMotorDatabase, account_id: str | None) -> dict[str, Any] | None:
    if not account_id:
        return None
    try:
        oid = ObjectId(account_id)
    except (InvalidId, TypeError):
        raise E.BizException(E.TOKEN_INVALID, "Token 无效") from None
    return await db[C.ACCOUNTS].find_one({"_id": oid})
