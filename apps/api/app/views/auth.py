"""认证路由（04-1 §二）。

⛔ 掩藏（不注册）：短信 OTP、微信授权登录、账号绑定、账号实名（需企业主体）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ..core.client_headers import ClientContext, parse_client_context
from ..core.deps import get_current_account, get_repos
from ..core.response import ok
from ..models.auth import (
    AccountLoginRequest,
    InviteLoginRequest,
    InviteRegisterRequest,
    InviteVerifyRequest,
    LogoutRequest,
    RecoveryResetRequest,
    RefreshRequest,
)
from ..repositories import Repositories
from ..controllers import auth_controller

router = APIRouter(prefix="/auth", tags=["auth"])


def _client(request: Request, client_id: str | None = None) -> ClientContext:
    return parse_client_context(request, client_id=client_id)


@router.post("/invite/verify")
async def verify_invite(body: InviteVerifyRequest, repos: Repositories = Depends(get_repos)):
    return ok(await auth_controller.verify_invite(repos, body.invite_code))


@router.post("/register")
async def register(
    body: InviteRegisterRequest,
    request: Request,
    repos: Repositories = Depends(get_repos),
):
    """统一注册：用户名/手机号二选一 + 密码（邀请码按开关可选）。"""
    client_id = body.client.client_id if body.client else None
    data = await auth_controller.register(repos, body, _client(request, client_id))
    return ok(data, http_status=201)


@router.post("/login")
async def login(
    body: AccountLoginRequest,
    request: Request,
    repos: Repositories = Depends(get_repos),
):
    """统一账号登录：`identifier` 可填用户名或手机号。"""
    client_id = body.client.client_id if body.client else None
    data = await auth_controller.login_by_account(repos, body, _client(request, client_id))
    return ok(data)


# ---------------- 兼容旧路径（邀请码口径） ----------------
@router.post("/invite/register")
async def register_legacy(
    body: InviteRegisterRequest,
    request: Request,
    repos: Repositories = Depends(get_repos),
):
    client_id = body.client.client_id if body.client else None
    data = await auth_controller.register(repos, body, _client(request, client_id))
    return ok(data, http_status=201)


@router.post("/invite/login")
async def login_legacy(
    body: InviteLoginRequest,
    request: Request,
    repos: Repositories = Depends(get_repos),
):
    client_id = body.client.client_id if body.client else None
    data = await auth_controller.login(repos, body, _client(request, client_id))
    return ok(data)


@router.post("/recovery/reset")
async def recovery_reset(body: RecoveryResetRequest, repos: Repositories = Depends(get_repos)):
    return ok(await auth_controller.reset_passcode(repos, body))


@router.post("/refresh")
async def refresh(body: RefreshRequest, repos: Repositories = Depends(get_repos)):
    return ok(await auth_controller.refresh(repos, body.refresh_token))


@router.post("/logout")
async def logout(
    body: LogoutRequest,
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok(await auth_controller.logout(repos, account, body.refresh_token))


@router.get("/me")
async def me(
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok(await auth_controller.me(repos, account))


@router.delete("/account")
async def delete_account(
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok(await auth_controller.delete_account(repos, account))
