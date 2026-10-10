"""报告路由（04-1 §七）。学习数据已服务端化，报告即服务端聚合结果。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..core.deps import get_current_account, get_repos
from ..core.response import ok
from ..repositories import Repositories
from ..controllers import report_controller

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/child/{child_id}/overview")
async def overview(
    child_id: str,
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok(await report_controller.overview(repos, account["_id"], child_id))


@router.get("/child/{child_id}/trend")
async def trend(
    child_id: str,
    days: int = Query(default=30, ge=1, le=180),
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok(await report_controller.trend(repos, account["_id"], child_id, days))


@router.get("/child/{child_id}/mastery")
async def mastery(
    child_id: str,
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok(await report_controller.mastery(repos, account["_id"], child_id))


@router.get("/child/{child_id}/weak-chars")
async def weak_chars(
    child_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok(await report_controller.weak_chars(repos, account["_id"], child_id, limit))


@router.get("/child/{child_id}/weekly")
async def weekly(
    child_id: str,
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok(await report_controller.weekly(repos, account["_id"], child_id))
