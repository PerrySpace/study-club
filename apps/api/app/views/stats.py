"""匿名统计路由（04-1 §九）。无认证——统计必须能在未注册状态下静默上报。

隐私红线：body 模型 `extra="forbid"`，出现 account_id/child_id/client_id 直接 40001。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..core.deps import get_repos
from ..core.response import ok
from ..models.stats import StatsEventsRequest
from ..repositories import Repositories
from ..controllers import stats_controller

router = APIRouter(prefix="/stats", tags=["stats"])


@router.post("/events")
async def ingest_events(body: StatsEventsRequest, repos: Repositories = Depends(get_repos)):
    return ok(await stats_controller.ingest(repos, body.events))
