"""学习模块路由（04-1 §五）。

**全部服务端存储**后，这些接口从「接收上报增量」变为**唯一数据通道**：
客户端读状态、写答题都只能走这里。因此新增 `GET /learning/state`
作为首页/进度页的单一数据源，避免客户端用 5 个并发请求拼装状态。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from ..core.client_headers import parse_client_context
from ..core.deps import get_current_account, get_repos
from ..core.response import ok
from ..models.learning import AnswerBatchRequest, AnswerSubmit, LessonCompleteRequest
from ..repositories import Repositories
from ..controllers import learning_controller

router = APIRouter(prefix="/learning", tags=["learning"])


@router.get("/state")
async def state(
    child_id: str,
    include_daily: bool = Query(default=True, description="是否包含今日任务"),
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    """首页/进度页的一次性状态聚合：进度 + 今日任务 + 到期复习 + 已获徽章。"""
    return ok(await learning_controller.state(repos, account["_id"], child_id, include_daily=include_daily))


@router.get("/daily-task")
async def daily_task(
    child_id: str,
    date: str | None = Query(default=None, description="YYYY-MM-DD，缺省为服务端当天"),
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok(await learning_controller.daily_task(repos, account["_id"], child_id, date))


@router.post("/answer")
async def submit_answer(
    body: AnswerSubmit,
    request: Request,
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    client = parse_client_context(request)
    return ok(await learning_controller.submit_answer(repos, account["_id"], body, client))


@router.post("/answer/batch")
async def submit_answer_batch(
    body: AnswerBatchRequest,
    request: Request,
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    client = parse_client_context(request)
    return ok(
        await learning_controller.submit_answers_batch(repos, account["_id"], body.child_id, body.records, client)
    )


@router.post("/lesson/complete")
async def complete_lesson(
    body: LessonCompleteRequest,
    request: Request,
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    client = parse_client_context(request)
    return ok(await learning_controller.complete_lesson(repos, account["_id"], body, client))


@router.get("/review/due")
async def review_due(
    child_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok(await learning_controller.review_due(repos, account["_id"], child_id, limit))


@router.get("/wrong-questions")
async def list_wrong_questions(
    child_id: str,
    resolved: bool | None = Query(default=None),
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok(await learning_controller.list_wrong_questions(repos, account["_id"], child_id, resolved))


@router.post("/wrong-questions/{wrong_id}/resolve")
async def resolve_wrong_question(
    wrong_id: str,
    child_id: str,
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok(await learning_controller.resolve_wrong_question(repos, account["_id"], child_id, wrong_id))


@router.get("/progress")
async def progress(
    child_id: str,
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok(await learning_controller.progress(repos, account["_id"], child_id))


# ---------------------------------------------------------------------------
# 客户端「全量同步 / 数据迁移」
# ---------------------------------------------------------------------------
@router.get("/review-states")
async def list_review_states(
    child_id: str,
    character_id: str | None = Query(default=None, description="只取某字的复习状态"),
    limit: int = Query(default=3000, ge=1, le=5000),
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok(
        await learning_controller.list_review_states(
            repos, account["_id"], child_id, character_id=character_id, limit=limit
        )
    )


@router.get("/badges")
async def list_child_badges(
    child_id: str,
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok(await learning_controller.list_child_badges(repos, account["_id"], child_id))


@router.get("/records")
async def list_learning_records(
    child_id: str,
    limit: int = Query(default=200, ge=1, le=1000),
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok(await learning_controller.list_learning_records(repos, account["_id"], child_id, limit=limit))


@router.get("/answers")
async def list_answer_records(
    child_id: str,
    limit: int = Query(default=2000, ge=1, le=5000),
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    return ok(await learning_controller.list_answer_records(repos, account["_id"], child_id, limit=limit))


@router.get("/export")
async def export_bundle(
    child_id: str,
    account: dict = Depends(get_current_account),
    repos: Repositories = Depends(get_repos),
):
    """导出该孩子的完整学习数据包（P0 数据可迁移性）。"""
    return ok(await learning_controller.export_bundle(repos, account["_id"], child_id))
