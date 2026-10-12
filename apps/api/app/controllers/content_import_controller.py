"""内容导入控制器 —— 把 `content/*.json` 或上传的 JSON 灌进 MongoDB。

这是「内容即仓库 → 内容全部后台管理」的**过渡通道**：
仓库里的内容仍然是可版本管理、可 code review 的真源形态（写成 JSON、进 git），
但运行时真源是 MongoDB。导入是**幂等 upsert**，可以随时重跑。

导入的两类数据：
1. 内容文档（characters/poems/units/lessons/stories/badges）
2. 素材文件（content/assets/**）→ 复制进 ASSET_DIR 并登记 assets 集合
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from ..core import errors as E
from ..core.config import settings
from ..core.datetimes import normalize_dates
from ..models.content import ContentImportRequest
from ..repositories import Repositories
from ..repositories.content_registry import IMPORT_SOURCES, COUNT_KEYS, import_source_for
# ⛔ 关卡重算**刻意复用 seed 的实现**，而不是在请求路径里再写一套：
#    生成规则（分桶 / 每关字数 / overrides / 清理旧关）只允许有一处真源，
#    两份实现一定会漂移，而漂移的症状是「后台 14 关、客户端 13 关」这种极难定位的偏差。
from ..seed.importer import rebuild_lessons as _rebuild_lessons

#: 会改变**关卡编排**的内容集合 —— 动到它们就必须重算关卡。
#: 判断依据是 `lesson_generator.generate_lessons` 的入参：字库 / 古诗 / 识字短文。
LESSON_SOURCE_COLLECTIONS: frozenset[str] = frozenset({"characters", "poems", "stories"})


def _now() -> datetime:
    return datetime.now(timezone.utc)


def repo_root() -> Path:
    """定位仓库根（容器里 CWD=/app，且 /app/content 存在）。"""
    here = Path(__file__).resolve()
    for candidate in [Path.cwd(), *here.parents]:
        if (candidate / "content").is_dir():
            return candidate
    return Path.cwd()


async def rebuild_lessons_for(
    repos: Repositories, collections: Iterable[str]
) -> dict | None:
    """内容变了就**立刻重算关卡**；动的集合与关卡无关时什么都不做。

    为什么要挂在所有写入路径上：关卡是**派生数据**（孩子的学习地图读的就是它），
    而内容集合只是它的输入。只写内容不重算关卡，孩子端就等于什么都没变化 ——
    运营会以为「导入失败」，实际上数据早就进库了（2026-10-12 真实踩过）。

    传进来的 `collections` 用集合名（`characters`/`poems`/`stories`）。
    返回 `None` 表示「与关卡无关，没重算」，让调用方能区分「没做」与「做了但 0 条」。
    """
    if not (set(collections) & LESSON_SOURCE_COLLECTIONS):
        return None
    return await _rebuild_lessons(repos.db, repo_root())


def _read_items(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict) and "items" in data:
        return list(data["items"])
    if isinstance(data, list):
        return list(data)
    return [data]


def _prepare(doc: dict, *, publish: bool) -> dict:
    prepared = normalize_dates(dict(doc))
    if publish:
        prepared["status"] = "published"
    prepared.setdefault("created_at", _now())
    return prepared


def _repository_for(repos: Repositories, collection: str):
    spec_map = {
        "characters": repos.characters,
        "poems": repos.poems,
        "curriculum_units": repos.units,
        "lessons": repos.lessons,
        "stories": repos.stories,
        "badges": repos.badges,
    }
    repo = spec_map.get(collection)
    if repo is None:
        raise E.BizException(E.PARAM_INVALID, f"不支持导入该集合：{collection}")
    return repo


async def _import_collection(
    repos: Repositories, collection: str, docs: list[dict], *, publish: bool, dry_run: bool
) -> dict:
    repo = _repository_for(repos, collection)
    if dry_run:
        return {"collection": collection, "total": len(docs), "created": 0, "updated": 0, "dry_run": True}
    result = await repo.upsert_many([_prepare(d, publish=publish) for d in docs])
    return {"collection": collection, "total": len(docs), **result}


# ---------------------------------------------------------------------------
# 素材导入
# ---------------------------------------------------------------------------
def _iter_asset_files(root: Path) -> list[Path]:
    asset_root = root / "content" / "assets"
    if not asset_root.is_dir():
        return []
    return sorted(p for p in asset_root.rglob("*") if p.is_file() and not p.name.startswith("."))


def _asset_id_for(storage_key: str) -> str:
    """素材 id 由 storage_key 派生 → 同一份生成素材重复导入不会产生重复记录。"""
    import hashlib

    return "as_" + hashlib.sha1(storage_key.encode("utf-8")).hexdigest()[:16]


async def import_assets(repos: Repositories, root: Path, *, dry_run: bool = False) -> dict:
    """把仓库 content/assets 下的文件复制进 ASSET_DIR 并登记元数据。"""
    files = _iter_asset_files(root)
    if not files:
        return {"collection": "assets", "total": 0, "created": 0, "updated": 0}

    target_root = Path(settings.asset_dir)
    if not dry_run:
        target_root.mkdir(parents=True, exist_ok=True)

    created = updated = 0
    for src in files:
        storage_key = src.relative_to(root / "content" / "assets").as_posix()
        asset_id = _asset_id_for(storage_key)
        mime = {
            ".svg": "image/svg+xml",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif",
            ".mp3": "audio/mpeg",
            ".m4a": "audio/mp4",
            ".wav": "audio/wav",
            ".ogg": "audio/ogg",
            ".json": "application/json",
        }.get(src.suffix.lower(), "application/octet-stream")
        asset_type = "image" if mime.startswith("image/") else "audio" if mime.startswith("audio/") else "stroke"
        parts = storage_key.split("/")
        subtype = parts[1] if len(parts) > 2 else None

        exists = await repos.assets.exists({"_id": asset_id}) if not dry_run else False
        if dry_run:
            created += 1
            continue

        dest = target_root / storage_key
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())

        now = _now()
        doc: dict[str, Any] = {
            "_id": asset_id,
            "type": asset_type,
            "subtype": subtype,
            "mime": mime,
            "bytes": src.stat().st_size,
            "width": None,
            "height": None,
            "original_name": src.name,
            "storage_key": storage_key,
            "url": f"{settings.asset_path_prefix}/{asset_id}",
            "source": "generated",
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
        await repos.assets.replace_one({"_id": asset_id}, doc, upsert=True)
        if exists:
            updated += 1
        else:
            created += 1

    return {"collection": "assets", "total": len(files), "created": created, "updated": updated}


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
async def run_import(repos: Repositories, req: ContentImportRequest) -> dict:
    root = repo_root()
    wanted = set(req.collections) or {src.collection for src in IMPORT_SOURCES}
    wanted.discard("assets")

    results: list[dict] = []

    if req.source == "upload":
        payload = req.payload or {}
        if not payload:
            raise E.BizException(E.PARAM_INVALID, "选中的是上传导入，但没有提供 payload")
        for collection, docs in payload.items():
            if collection not in wanted:
                continue
            results.append(
                await _import_collection(
                    repos, collection, list(docs or []), publish=req.publish, dry_run=req.dry_run
                )
            )
    else:
        for src in IMPORT_SOURCES:
            if src.collection not in wanted:
                continue
            paths: list[str] = []
            if src.path:
                paths.append(src.path)
            paths.extend(src.extra_paths)
            docs: list[dict] = []
            for rel in paths:
                docs.extend(_read_items(root / rel))
            results.append(
                await _import_collection(
                    repos, src.collection, docs, publish=req.publish, dry_run=req.dry_run
                )
            )

    # 素材：只要导入了内容就顺带同步（配图缺失是内容质量问题的主要来源）
    want_assets = "assets" in set(req.collections) or not req.collections
    if want_assets:
        results.append(await import_assets(repos, root, dry_run=req.dry_run))

    if not req.dry_run:
        # ⭐ 关卡重算**必须紧跟内容写入**：孩子端地图读的是 `lessons`，
        #    而它是派生数据。以前这一步只存在于 `deploy`（seed）里，
        #    于是「后台导入完 → 孩子端毫无变化 → 以为导入失败」。
        #    重算会把「按当前库内内容应有哪些关卡」整份算出来（含清理旧关），
        #    并把结果并进返回体，让后台能直接显示「新增/更新/清理了几关」。
        lessons_result = await rebuild_lessons_for(repos, [r["collection"] for r in results])
        if lessons_result is not None:
            results.append(lessons_result)
        await refresh_manifest(repos)

    return {
        "results": results,
        "total": sum(r.get("total", 0) for r in results),
        "created": sum(r.get("created", 0) for r in results),
        "updated": sum(r.get("updated", 0) for r in results),
        "dry_run": req.dry_run,
    }


async def refresh_manifest(repos: Repositories) -> None:
    """重算清单计数并进一个内容小版本。

    公开给别的写入路径复用（如后台物理删除内容）：**只要内容的「published 条数」变了，
    就必须刷新清单**，否则 `/health` 与客户端看到的 `content_version` 会停在旧值，
    出现「库里已经删了、客户端还以为没变」。
    """
    counts = await repos.content_counts()
    counts.pop("assets", None)
    entries = {
        collection: await _repository_for(repos, collection).count({"status": "published"})
        for collection in COUNT_KEYS.values()
    }
    doc = await repos.manifest.get_current() or {"_id": "current"}
    doc["content_version"] = _bump_version(str(doc.get("content_version", "1.0.0")))
    doc["min_app_version"] = doc.get("min_app_version", "0.1.0")
    doc["updated_at"] = _now()
    doc["counts"] = {**counts, **entries}
    doc["files"] = []
    await repos.manifest.save_current(doc)


def _bump_version(version: str) -> str:
    """内容变更就自动进一个小版本 —— 客户端据此判断是否需要重拉。"""
    parts = (version or "1.0.0").split(".")
    try:
        parts = [int(p) for p in parts[:3]] + [0] * max(0, 3 - len(parts))
    except ValueError:
        return "1.0.0"
    parts[2] += 1
    return ".".join(str(p) for p in parts[:3])


async def preview_import_sources(repos: Repositories) -> list[dict]:
    """后台「内容导入」页：列出每个来源文件是否存在、有多少条。"""
    root = repo_root()
    out: list[dict] = []
    for src in IMPORT_SOURCES:
        paths = ([src.path] if src.path else []) + list(src.extra_paths)
        files = []
        total = 0
        for rel in paths:
            items = _read_items(root / rel)
            total += len(items)
            files.append({"path": rel, "exists": (root / rel).is_file(), "count": len(items)})
        spec = import_source_for(src.collection)
        out.append(
            {
                "collection": src.collection,
                "label": spec.collection if spec else src.collection,
                "count": total,
                "in_db": await _repository_for(repos, src.collection).count(),
                "files": files,
            }
        )
    asset_files = _iter_asset_files(root)
    out.append(
        {
            "collection": "assets",
            "label": "素材",
            "count": len(asset_files),
            "in_db": await repos.assets.count(),
            "files": [{"path": p.relative_to(root).as_posix(), "exists": True, "count": 1} for p in asset_files[:50]],
        }
    )
    return out
