"""通用导入器（scripts/seed/seed.py 的核心）。

支持三种规格（每个 data/*.json 一个文件）：

1. 直导（documents）：
   {"collection":"invites","feature":"邀请码","unique_key":"code_hash","documents":[...]}

2. 从内容包导入（source）：
   {"collection":"characters","source":"content/characters/grade-1.json",
    "unique_key":"char","strip_wrapper":true}

3. **运行时生成**（generated）：
   {"collection":"lessons","feature":"关卡","generated":"lessons"}
   —— 关卡不再手写文件，由内容自动切分（见 `lesson_generator.py`）。
   这种 spec 的 `depends_on` 列出它需要读取的其它集合。

约束：用 `unique_key`（或文档自带 `_id`）做 upsert，**幂等**；`--drop` 时先清集合。

分层说明：本模块是**离线 CLI 入口**（scripts/seed/seed.py），不在请求路径上，
因此直接用 motor 客户端是刻意的 —— 请求路径的分层纪律（view → controller → repository）
针对的是 HTTP 服务；把一次性导入也塞进仓储层只会让仓储多出一堆只被调用一次的写接口。
时间归一化复用 `core/datetimes.py`，避免与后台「内容导入」两处规则漂移。
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from ..core.config import settings
from ..core.datetimes import normalize_dates
from ..core.security import hash_passcode
from .lesson_generator import generate_lessons


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def load_spec(path: Path) -> dict:
    return _read_json(path)


#: `generated` 支持的生成器名 → 其依赖的集合。
#: 依赖顺序由 `import_dir` 的文件序号保证（字符在 04、故事在 07），
#: 但这里**显式声明**而不是靠文件名序号隐式保证 —— 后者一旦有人重命名文件就悄悄坏了。
GENERATED_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "lessons": ("characters", "poems", "stories"),
}

#: 允许「清掉不在本次导入里的旧文档」的集合 —— **显式白名单**。
#:
#: ⛔ 这些集合的库内内容应当与仓库**完全一致**（内容即仓库），
#:    多出来的即为废弃：内容包里删掉一篇故事，库里的旧篇不会自动消失，
#:    于是自动生成的关卡数会多出一个（实测 22 → 23），且不报错。
#:
#: ⛔ **绝不能**把 accounts / invites 放进来 —— 它们的内容来自**用户行为**
#:    （注册、领码），不是仓库的镜像。照抄「不在本次导入里就删」会删掉真实用户数据。
#:    用白名单而不是「除某些集合外都清」，就是为了让这个风险**显式可见**。
PRUNABLE_COLLECTIONS: frozenset[str] = frozenset(
    {
        "characters",
        "poems",
        "stories",
        "readings",
        "curriculum_units",
        "lessons",
        "badges",
    }
)


async def resolve_generated(spec: dict, db: AsyncIOMotorDatabase, repo_root: Path) -> list[dict]:
    """运行时生成待导入文档。

    目前只有关卡：`lessons` 不再手写文件，而是从内容自动切分
    （见 `lesson_generator.py`，与 core 的 `algorithms/lessons.ts` 同一套规则）。

    为什么关卡要「生成」而不是手写：
      - 内容一变就得手工插关、调顺序、挪解锁链；
      - 手写文件的排列顺序会**悄悄变成孩子的学习顺序**，而没有人真正设计过它。
    """
    kind = spec.get("generated")
    if kind != "lessons":
        raise ValueError(f"未知的生成器：{kind!r}")

    # ⛔ 这层必须是 `async def`：`async for` 异步推导式**只能**出现在异步函数里。
    #    写成同步函数 + `return [d async for d in ...]` 会在导入时抛
    #    SyntaxError: asynchronous comprehension outside of an asynchronous function
    #    —— 而 seed 失败不阻塞发布，于是「构建 SUCCESS 但关卡没导入」会被漏过去。
    async def _all(collection: str) -> list[dict]:
        return [d async for d in db[collection].find({})]

    overrides = _read_json(repo_root / spec["overrides"]) if spec.get("overrides") else {}
    # 先取好三份内容再生成：下面要按「实际参与生成的数量」打印诊断，
    # 而 generate_lessons 内部还会再按 grade/status 过滤，两处口径要能对上。
    characters_pool = await _all("characters")
    poems_pool = await _all("poems")
    stories_pool = await _all("stories")

    lessons = generate_lessons(
        characters=characters_pool,
        poems=poems_pool,
        stories=stories_pool,
        target_grade=int(spec.get("target_grade") or 1),
        chars_per_lesson=int(spec.get("chars_per_lesson") or 6),
        overrides=overrides,
    )

    # ⭐ 把**每条线的关卡数**与**实际参与生成的内容数**打出来。
    #
    # 为什么需要：出过一次「生成 23 关、预期 22 关」的偏差，而 `total=23` 本身
    # 看起来完全正常 —— 只有「哪条线多了一关」能指到具体原因（多出来的是识字
    # 关还是故事关）。仅看总数永远猜不出。
    def _eligible(docs: list[dict]) -> int:
        return sum(1 for d in docs if d.get("status") == "published")

    by_track: dict[str, int] = {}
    for lesson in lessons:
        t = str(lesson.get("track") or "?")
        by_track[t] = by_track.get(t, 0) + 1
    print(
        f"    · 关卡构成 {by_track}｜可用内容：字 {_eligible(characters_pool)}"
        f" / 诗 {_eligible(poems_pool)} / 故事 {_eligible(stories_pool)}"
        f"（库内 {len(characters_pool)}/{len(poems_pool)}/{len(stories_pool)}）"
    )

    return lessons


def resolve_documents(spec: dict, repo_root: Path) -> list[dict]:
    """从 spec 得到待导入文档列表。"""
    if spec.get("documents") is not None:
        return list(spec["documents"])
    if spec.get("source"):
        source = repo_root / spec["source"]
        data = _read_json(source)
        if spec.get("strip_wrapper"):
            # 内容包形如 {content_version, items:[...]}；取 items 并保留字段原样
            if isinstance(data, dict) and "items" in data:
                return list(data["items"])
        if spec.get("single_doc_id") is not None:
            doc = dict(data)
            doc["_id"] = spec["single_doc_id"]
            return [doc]
        if isinstance(data, list):
            return list(data)
        if isinstance(data, dict) and "items" in data:
            return list(data["items"])
        return [data]
    return []


def _upsert_filter(doc: dict, unique_key: str | None) -> dict | None:
    if "_id" in doc:
        return {"_id": doc["_id"]}
    if unique_key and unique_key in doc:
        return {unique_key: doc[unique_key]}
    return None


def _prepare_document(spec: dict, doc: dict) -> dict:
    """落库前的字段处理：账号口令占位由 seed 生成 Argon2 哈希，明文不入库。"""
    prepared = normalize_dates(dict(doc))
    if spec.get("collection") == "accounts":
        plain = prepared.pop("passcode", None)
        if plain and not prepared.get("passcode_hash"):
            prepared["passcode_hash"] = hash_passcode(plain)
    # 邀请码种子只允许哈希字段（防止误把明文码写进仓库）
    return prepared


async def import_spec(
    db: AsyncIOMotorDatabase, spec: dict, repo_root: Path, drop: bool = False
) -> dict:
    collection = spec["collection"]
    # 生成型 spec 从库里读依赖集合来算，不读文件
    raw_docs = (
        await resolve_generated(spec, db, repo_root)
        if spec.get("generated")
        else resolve_documents(spec, repo_root)
    )
    docs = [_prepare_document(spec, d) for d in raw_docs]

    if drop:
        await db[collection].delete_many({})
    created = 0
    updated = 0
    skipped = 0
    unique_key = spec.get("unique_key")

    # ⭐ 清理**本次没导入**的旧文档。
    #
    # 仅适用于「内容即仓库」的内容型集合（内容包 + 自动生成的关卡）：
    # 这些集合的库内内容应当与仓库**完全一致**，多出来的即为废弃。
    #
    # ⛔ **绝不能**对 accounts / invites 这类集合做同样处理 ——
    #    它们的内容来自用户行为（注册、领码），不是仓库的镜像。
    #    照抄「不在本次导入里就删」会**删掉真实用户数据**。
    #    因此这里用显式白名单，而不是「除了某些集合都清」。
    stale_removed = 0
    if collection in PRUNABLE_COLLECTIONS and spec.get("prune_stale", True):
        keep_ids = {str(d.get("_id")) for d in docs}
        stale_ids: list[str] = []
        async for old in db[collection].find({}):
            oid = str(old.get("_id") or "")
            if oid not in keep_ids:
                stale_ids.append(oid)
        for oid in stale_ids:
            await db[collection].delete_one({"_id": oid})
            stale_removed += 1

    for doc in docs:
        flt = _upsert_filter(doc, unique_key)
        if flt is None:
            # 无主键也无唯一键：无法幂等，按插入处理（重复执行会新增）
            await db[collection].insert_one(doc)
            created += 1
            continue
        exists = await db[collection].find_one(flt, {"_id": 1})
        if exists:
            await db[collection].replace_one(flt, doc, upsert=True)
            updated += 1
        else:
            await db[collection].insert_one(doc)
            created += 1
    # `stale_removed` 放进返回值：让部署日志能看到「清了几条历史残留」。
    # 不记的话，清理失败与「本来就没有残留」在日志里长得一模一样。
    return {
        "collection": collection,
        "feature": spec.get("feature", ""),
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "stale_removed": stale_removed,
        "total": len(docs),
    }


async def import_dir(
    db: AsyncIOMotorDatabase,
    data_dir: Path,
    repo_root: Path,
    only: str | None = None,
    drop: bool = False,
) -> list[dict]:
    results: list[dict] = []
    # 本次运行里**已经导入过**的集合名。用来判断生成型 spec 的依赖是否就绪 ——
    # 刻意不用「集合是否为空」：空集合可能是合法状态（真的没有古诗），
    # 而「没导入过」才是顺序错了。
    imported_collections: set[str] = set()
    for path in sorted(data_dir.glob("*.json")):
        # 支持 --only <表名>：匹配文件名（去扩展名）
        if only and only not in path.stem:
            continue
        spec = load_spec(path)
        # 00_meta.json 只做说明，不导入
        if not spec.get("collection"):
            continue
        # ⭐ 生成型 spec 必须等依赖集合**先被导入过**。
        #
        #    只检查「依赖集合非空」是不够的：poems / stories 完全可能是空的
        #    （「这个站点还没有古诗」是合法状态），那本来就该生成 0 条古诗关卡。
        #    真正要防的是「该集合根本没被导入过」—— 原 `07_lessons.json` 排在
        #    `08_stories.json` 之前正是这种情况，依赖不满足却一声不吭地生成 0 关。
        #
        #    因此用 `required_dependencies`（默认全部）做「已导入」检查：
        #    依赖里任一集合**从未被导入过**才报错。
        if spec.get("generated"):
            never_imported = [
                dep
                for dep in GENERATED_DEPENDENCIES.get(spec["generated"], ())
                if dep not in imported_collections
            ]
            if never_imported:
                raise RuntimeError(
                    f"{path.name} 要生成 {spec['collection']}，但这些依赖集合还没被导入："
                    f"{never_imported}。请去掉 --only 或调整 seed 文件顺序，"
                    f"让依赖先于它执行。"
                )
        result = await import_spec(db, spec, repo_root, drop=drop)
        result["file"] = path.name
        results.append(result)
        imported_collections.add(spec["collection"])
    return results


def _find_repo_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "content").is_dir():
            return candidate
    return start


async def run(
    mongo_uri: str | None = None,
    data_dir: str | None = None,
    repo_root: str | None = None,
    only: str | None = None,
    drop: bool = False,
) -> list[dict]:
    app_dir = Path(__file__).resolve()
    repo = Path(repo_root) if repo_root else _find_repo_root(app_dir)
    data = Path(data_dir) if data_dir else repo / "scripts" / "seed" / "data"

    client = AsyncIOMotorClient(mongo_uri or settings.mongodb_uri, uuidRepresentation="standard")
    try:
        db = client[settings.mongodb_db]
        return await import_dir(db, data, repo, only=only, drop=drop)
    finally:
        client.close()


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="study-club 种子数据导入器")
    parser.add_argument("--data-dir", default=None, help="种子数据目录（默认 scripts/seed/data）")
    parser.add_argument("--repo-root", default=None, help="仓库根（用于解析 content/ 相对路径）")
    parser.add_argument("--mongo-uri", default=None, help="MongoDB 连接串")
    parser.add_argument("--only", default=None, help="只导入文件名包含该子串的表")
    parser.add_argument("--drop", action="store_true", help="导入前清空目标集合")
    args = parser.parse_args(argv)

    results = asyncio.run(
        run(
            mongo_uri=args.mongo_uri,
            data_dir=args.data_dir,
            repo_root=args.repo_root,
            only=args.only,
            drop=args.drop,
        )
    )
    for r in results:
        line = (
            f"  [{r['collection']}] {r.get('feature', '')} "
            f"created={r['created']} updated={r['updated']} total={r['total']}"
        )
        # 清理掉的历史残留也要打出来：否则「清理失败」与「本来就没有残留」
        # 在日志里长得一模一样，看的人无从判断。
        if r.get("stale_removed"):
            line += f" stale_removed={r['stale_removed']}"
        print(line)
    print(f"完成：共 {len(results)} 个数据集。")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
