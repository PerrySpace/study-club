"""素材控制器 —— 上传 / 列表 / 删除 / 下发 / 绑定到内容。

存储模型：文件落 `ASSET_DIR`（命名卷，可写），元数据落 `assets` 集合。
内容文档只存 `*_ref`（素材 id），出参时展开为 `*_url` —— 于是「换配图不碰内容文档」。

安全要点（都不是可选项）：
- MIME 白名单 + 体积上限，避免把服务端变成任意文件托管
- `storage_key` 经过 `safe_storage_key()` 净化，杜绝 `../` 路径穿越
- 存储文件名用**服务端生成的 asset_id**，不采信客户端文件名
"""

from __future__ import annotations

import mimetypes
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..core import errors as E
from ..core.config import settings
from ..models.asset import AssetRefBind
from ..repositories import Repositories
from ..repositories.assets import safe_storage_key

# 浏览器不认的扩展名在此补齐（SVG 尤其中招，mimetypes 老库会漏）
_EXT_BY_MIME: dict[str, str] = {
    "image/svg+xml": ".svg",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/wav": ".wav",
    "audio/ogg": ".ogg",
    "audio/webm": ".webm",
    "application/json": ".json",
}
_TYPE_BY_MIME_PREFIX = (("image/", "image"), ("audio/", "audio"))

_ID_SAFE = re.compile(r"[^0-9A-Za-z_-]")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _asset_id() -> str:
    return "as_" + uuid.uuid4().hex[:16]


def _classify(mime: str) -> str:
    for prefix, kind in _TYPE_BY_MIME_PREFIX:
        if mime.startswith(prefix):
            return kind
    if mime == "application/json":
        return "stroke"
    return "other"


def _assert_mime_allowed(mime: str) -> None:
    allowed = settings.asset_allowed_mime_list
    if mime in allowed:
        return
    # 支持 `image/*` 形式
    for rule in allowed:
        if rule.endswith("/*") and mime.startswith(rule[:-1]):
            return
    raise E.BizException(
        E.UNSUPPORTED_MEDIA_TYPE,
        "不支持的素材类型",
        errors=[{"field": "file", "reason": f"{mime} 不在允许列表内"}],
    )


def _asset_dir() -> Path:
    path = Path(settings.asset_dir)
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise E.BizException(E.STORAGE_UNAVAILABLE, "素材存储不可用") from exc
    return path


def _public_url(asset_id: str) -> str:
    """相对路径优先：换局域网 IP 不用重建链接；配了 ASSET_BASE_URL 则用绝对地址（CDN）。"""
    base = settings.asset_base_url.rstrip("/")
    return f"{base}{settings.asset_path_prefix}/{asset_id}" if base else f"{settings.asset_path_prefix}/{asset_id}"


def _ext_for(mime: str, original_name: str | None) -> str:
    if mime in _EXT_BY_MIME:
        return _EXT_BY_MIME[mime]
    if original_name:
        suffix = Path(original_name).suffix.lower()
        if suffix and len(suffix) <= 6 and suffix.isprintable():
            return suffix
    guessed = mimetypes.guess_extension(mime) or ""
    return guessed if guessed else ".bin"


def _extract_dimensions(data: bytes, mime: str) -> tuple[int | None, int | None]:
    """只对 SVG 做轻量尺寸解析（PNG/JPEG 解析需要额外依赖，收益不大）。"""
    if mime != "image/svg+xml":
        return None, None
    head = data[:2048].decode("utf-8", errors="ignore")
    w = re.search(r'width="(\d+(?:\.\d+)?)"', head)
    h = re.search(r'height="(\d+(?:\.\d+)?)"', head)
    if w and h:
        try:
            return int(float(w.group(1))), int(float(h.group(1)))
        except ValueError:
            return None, None
    viewbox = re.search(r'viewBox="[\d.\-]+\s+[\d.\-]+\s+([\d.]+)\s+([\d.]+)"', head)
    if viewbox:
        try:
            return int(float(viewbox.group(1))), int(float(viewbox.group(2)))
        except ValueError:
            return None, None
    return None, None


# ---------------------------------------------------------------------------
# 上传
# ---------------------------------------------------------------------------
async def save_upload(
    repos: Repositories,
    *,
    filename: str | None,
    mime: str | None,
    data: bytes,
    subtype: str | None = None,
    actor: dict | None = None,
) -> dict:
    if not data:
        raise E.BizException(E.PARAM_INVALID, "文件为空")
    if len(data) > settings.asset_max_bytes:
        raise E.BizException(
            E.ASSET_TOO_LARGE,
            "文件超过大小上限",
            errors=[{"field": "file", "reason": f"最大 {settings.asset_max_bytes // 1024 // 1024} MB"}],
        )

    resolved_mime = (mime or mimetypes.guess_type(filename or "")[0] or "application/octet-stream").lower()
    resolved_mime = resolved_mime.split(";")[0].strip()
    _assert_mime_allowed(resolved_mime)

    asset_type = _classify(resolved_mime)
    asset_id = _asset_id()
    ext = _ext_for(resolved_mime, filename)
    variant = safe_storage_key(subtype or "misc") or "misc"
    storage_key = f"{asset_type}/{variant}/{asset_id}{ext}"

    target = _asset_dir() / storage_key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)

    width, height = _extract_dimensions(data, resolved_mime)
    now = _now()
    doc: dict[str, Any] = {
        "_id": asset_id,
        "type": asset_type,
        "subtype": subtype,
        "mime": resolved_mime,
        "bytes": len(data),
        "width": width,
        "height": height,
        "original_name": (filename or "")[:200] or None,
        "storage_key": storage_key,
        "url": _public_url(asset_id),
        "source": "uploaded",
        "status": "active",
        "created_by": (actor or {}).get("_id"),
        "created_at": now,
        "updated_at": now,
    }
    await repos.assets.insert_one(doc)
    return doc


# ---------------------------------------------------------------------------
# 查询 / 删除
# ---------------------------------------------------------------------------
async def list_assets(
    repos: Repositories,
    *,
    skip: int,
    limit: int,
    asset_type: str | None = None,
    keyword: str | None = None,
    include_deleted: bool = False,
) -> tuple[list[dict], int]:
    return await repos.assets.list_page(
        skip=skip,
        limit=limit,
        asset_type=asset_type,
        keyword=keyword,
        include_deleted=include_deleted,
    )


async def delete_asset(repos: Repositories, asset_id: str) -> dict:
    """软删除 + 引用检查。仍被内容引用时提示，但不阻断（后台可强行下架）。"""
    asset = await repos.assets.find_one({"_id": asset_id, "status": "active"})
    if asset is None:
        raise E.BizException(E.ASSET_NOT_FOUND, "素材不存在")
    refs = await repos.assets.ref_counts([asset_id])
    await repos.assets.soft_delete(asset_id, now=_now())
    return {"deleted": True, "id": asset_id, "referenced_by": refs.get(asset_id, 0)}


async def stats(repos: Repositories) -> dict:
    return await repos.assets.stats()


async def detail(repos: Repositories, asset_id: str) -> dict:
    asset = await repos.assets.find_one({"_id": asset_id})
    if asset is None:
        raise E.BizException(E.ASSET_NOT_FOUND, "素材不存在")
    asset["referenced_by"] = (await repos.assets.ref_counts([asset_id])).get(asset_id, 0)
    return asset


# ---------------------------------------------------------------------------
# 文件下发
# ---------------------------------------------------------------------------
async def resolve_file(repos: Repositories, asset_id: str) -> tuple[Path, str, str]:
    """返回 (磁盘路径, MIME, ETag)。路径一定落在 ASSET_DIR 内（防穿越）。"""
    asset = await repos.assets.find_one({"_id": asset_id})
    if asset is None or asset.get("status") != "active":
        raise E.BizException(E.ASSET_NOT_FOUND, "素材不存在")

    root = _asset_dir().resolve()
    path = (root / str(asset.get("storage_key", ""))).resolve()
    # 双保险：即便元数据被污染，也不允许读到 ASSET_DIR 之外
    if not str(path).startswith(str(root)) or not path.is_file():
        raise E.BizException(E.ASSET_NOT_FOUND, "素材文件缺失")

    mime = asset.get("mime") or mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    etag = f'W/"{asset_id}-{asset.get("bytes", 0)}"'
    return path, mime, etag


# ---------------------------------------------------------------------------
# 绑定到内容
# ---------------------------------------------------------------------------
async def bind_ref(repos: Repositories, payload: AssetRefBind) -> dict:
    """把素材绑到某条内容上（后台「替换配图」）。`asset_id=null` 即解绑。"""
    if payload.asset_id:
        exists = await repos.assets.exists({"_id": payload.asset_id, "status": "active"})
        if not exists:
            raise E.BizException(E.ASSET_NOT_FOUND, "素材不存在")

    collection = repos.db[payload.collection]
    doc_id = payload.doc_id
    if payload.collection == "characters" and not doc_id.startswith("ch_"):
        raise E.BizException(E.CHARACTER_NOT_FOUND, "汉字不存在")

    result = await collection.update_one(
        {"_id": doc_id},
        {"$set": {payload.field: payload.asset_id, "updated_at": _now()}},
    )
    if result.matched_count == 0:
        raise E.BizException(E.CONTENT_NOT_FOUND, "目标内容不存在")
    return {"bound": True, "collection": payload.collection, "doc_id": doc_id, "field": payload.field, "asset_id": payload.asset_id}
