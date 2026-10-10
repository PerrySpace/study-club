"""健康检查 —— 客户端启动时静默探测（超时即提示无法连接，见 04-1 §1.8）。

不要求登录：登录页本身要先探测「服务端在不在」。
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from ..core.deps import get_repos
from ..core.response import ok
from ..repositories import Repositories
from ..controllers import content_controller

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(repos: Repositories = Depends(get_repos)):
    manifest = await content_controller.get_manifest(repos)
    return ok(
        {
            "status": "ok",
            "content_version": manifest.get("content_version"),
            "server_time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
    )
