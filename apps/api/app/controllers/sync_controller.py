"""端到端加密同步控制器（MVC —— Controller 层，04-1 §2.3 / 03-2 §7.4）。

⚠️ 服务端**只存密文**，不做任何解密；密钥由用户口令在客户端派生（服务端没有任何解密密钥）。
冲突以客户端合并为准：服务端只保存 `revision` 更大的版本。
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from bson import ObjectId

from ..core.client_headers import ClientContext
from ..repositories import Repositories
from .serializers import serialize


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def get_or_create_salt(repos: Repositories, account_id: ObjectId) -> dict:
    salt = await repos.accounts.get_sync_salt(account_id)
    if not salt:
        salt = secrets.token_hex(16)
        await repos.accounts.set_sync_salt(account_id, salt)
    # 盐本身不是秘密，可下发；密钥永不出服务端
    return {"sync_key_salt": salt}


async def manifest(
    repos: Repositories, account_id: ObjectId, object_type: str | None = None
) -> dict:
    objects = await repos.sync_objects.manifest(account_id, object_type)
    return {
        "objects": [
            {
                "object_type": o.get("object_type"),
                "object_key": o.get("object_key"),
                "schema_version": o.get("schema_version"),
                "revision": o.get("revision"),
                "deleted": o.get("deleted", False),
                "updated_at": serialize(o.get("updated_at")),
            }
            for o in objects
        ],
        "total": len(objects),
        "server_time": serialize(_now()),
    }


async def push(
    repos: Repositories,
    account_id: ObjectId,
    objects: list,
    client: ClientContext,
) -> dict:
    now = _now()
    applied = 0
    skipped = 0
    for obj in objects:
        revision = await repos.sync_objects.revision_of(
            account_id=account_id, object_type=obj.object_type, object_key=obj.object_key
        )
        if revision is not None and revision > obj.revision:
            # 远端更新，客户端应先 pull 合并（服务端不做业务合并）
            skipped += 1
            continue
        await repos.sync_objects.put(
            account_id=account_id,
            obj=obj,
            client_id=obj.client_id or (client.client_id or "unknown"),
            now=now,
        )
        applied += 1
    return {"applied": applied, "skipped": skipped}


async def pull(
    repos: Repositories,
    account_id: ObjectId,
    since: datetime | None = None,
    object_type: str | None = None,
) -> dict:
    objects = await repos.sync_objects.pull(account_id=account_id, since=since, object_type=object_type)
    if not objects:
        return {"objects": [], "total": 0}
    return {
        "objects": serialize(objects),
        "total": len(objects),
        "server_time": serialize(_now()),
    }
