"""反馈控制器（MVC —— Controller 层，04-1 §十 / 03-2 §7.6）。

允许匿名（account_id 为 null）；联系方式自愿、可为空。这是免费模式下少数「知道用户遇到什么」的渠道。
"""

from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId

from ..repositories import Repositories
from .serializers import to_iso


async def create(repos: Repositories, account_id: ObjectId | None, req) -> dict:
    now = datetime.now(timezone.utc)
    feedback_id = await repos.feedbacks.create(
        {
            "account_id": account_id,
            "category": req.category,
            "content_ref": req.content_ref,
            "message": req.message,
            "contact": req.contact,
            "client": req.client,
            "status": "open",
            "created_at": now,
            "handled_at": None,
        }
    )
    return {"id": feedback_id, "status": "open", "created_at": to_iso(now)}
