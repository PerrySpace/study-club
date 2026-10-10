"""反馈路由（04-1 §十）。允许匿名提交（无 Token 时 account_id 为 null）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..core.deps import get_optional_account, get_repos
from ..core.response import ok
from ..models.feedback import FeedbackCreate
from ..repositories import Repositories
from ..controllers import feedback_controller

router = APIRouter(prefix="/feedbacks", tags=["feedbacks"])


@router.post("")
async def create_feedback(
    body: FeedbackCreate,
    account: dict | None = Depends(get_optional_account),
    repos: Repositories = Depends(get_repos),
):
    account_id = account["_id"] if account else None
    return ok(await feedback_controller.create(repos, account_id, body), http_status=201)
