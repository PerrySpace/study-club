"""儿童档案路由（04-1 §三）。全部需要登录，且按账号归属鉴权。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..core.deps import get_current_account, get_repos
from ..core.response import ok
from ..models.child import ChildCreate, ChildUpdate
from ..repositories import Repositories
from ..controllers import child_controller

router = APIRouter(prefix="/children", tags=["children"])


@router.get("")
async def list_children(
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok({"items": await child_controller.list_children(repos, account["_id"])})


@router.post("")
async def create_child(
    body: ChildCreate,
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok(await child_controller.create_child(repos, account["_id"], body), http_status=201)


@router.get("/{child_id}")
async def get_child(
    child_id: str,
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok(await child_controller.get_child(repos, account["_id"], child_id))


@router.patch("/{child_id}")
async def update_child(
    child_id: str,
    body: ChildUpdate,
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok(await child_controller.update_child(repos, account["_id"], child_id, body))


@router.delete("/{child_id}")
async def delete_child(
    child_id: str,
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok(await child_controller.delete_child(repos, account["_id"], child_id))


@router.get("/{child_id}/stats")
async def child_stats(
    child_id: str,
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok(await child_controller.child_stats(repos, account["_id"], child_id))
