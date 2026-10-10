"""素材下发路由（04-1 §四 素材扩展）。

**为什么这条路由不要求登录**（这是刻意的、有记录的取舍）：
素材最终会被 `<img src>` / `<audio src>` 直接引用，而浏览器对这两类标签**不会**带
Authorization 头。若强制鉴权，图片与音频就只能在 JS 里 fetch 成 blob 再赋 src ——
既丧失 HTTP 缓存，也把首屏拖慢一个量级。

安全边界：素材是**教学内容**（程序生成插画 / 朗读音频），不是任何用户的私人数据；
素材 id 是 32 位随机的（`as_` + 16 hex），不可枚举。用户上传的数据仍全部走在鉴权路由下。

缓存策略：素材不可变（替换配图 = 换 id，见 asset_controller），因此可长缓存 + 强 ETag。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Response
from fastapi.responses import FileResponse

from ..core.deps import get_repos
from ..repositories import Repositories
from ..controllers import asset_controller

router = APIRouter(tags=["assets"])

_IMMUTABLE_CACHE = "public, max-age=31536000, immutable"


@router.get("/assets/{asset_id}")
async def serve_asset(
    asset_id: str,
    if_none_match: str | None = Header(default=None, alias="If-None-Match"),
    repos: Repositories = Depends(get_repos),
):
    path, mime, etag = await asset_controller.resolve_file(repos, asset_id)

    # 命中协商缓存：直接 304，不再读盘/回传
    if if_none_match and etag in if_none_match:
        return Response(status_code=304, headers={"ETag": etag, "Cache-Control": _IMMUTABLE_CACHE})

    return FileResponse(
        path,
        media_type=mime,
        headers={
            "ETag": etag,
            "Cache-Control": _IMMUTABLE_CACHE,
            "X-Content-Type-Options": "nosniff",
            # SVG 可内嵌脚本：内联展示时隔离掉脚本与同源权限
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox",
        },
    )
