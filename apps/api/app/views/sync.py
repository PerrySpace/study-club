"""端到端加密同步路由（04-1 §2.3）。服务端只存密文，不做任何解密。"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request

from ..core.client_headers import parse_client_context
from ..core.deps import get_current_account, get_repos
from ..core.errors import PARAM_INVALID, BizException
from ..core.response import ok
from ..models.sync import SyncPushRequest
from ..repositories import Repositories
from ..controllers import sync_controller

router = APIRouter(prefix="/sync", tags=["sync"])


def _parse_since(since: str | None) -> datetime | None:
    if not since:
        return None
    try:
        return datetime.fromisoformat(since.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BizException(
            PARAM_INVALID, "参数校验失败", errors=[{"field": "since", "reason": "必须是 ISO 8601 时间"}]
        ) from exc


@router.get("/manifest")
async def manifest(
    object_type: str | None = Query(default=None),
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok(await sync_controller.manifest(repos, account["_id"], object_type))


@router.post("/push")
async def push(
    body: SyncPushRequest,
    request: Request,
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    client = parse_client_context(request)
    return ok(await sync_controller.push(repos, account["_id"], body.objects, client))


@router.get("/pull")
async def pull(
    since: str | None = Query(default=None, description="ISO 8601 UTC"),
    object_type: str | None = Query(default=None),
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok(await sync_controller.pull(repos, account["_id"], _parse_since(since), object_type))


@router.get("/salt")
async def salt(
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok(await sync_controller.get_or_create_salt(repos, account["_id"]))
