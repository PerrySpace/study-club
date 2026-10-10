"""种子导入器：`generated` 型 spec（关卡运行时生成）。

## 为什么这些测试非有不可
seed 导入失败**不阻塞发布** —— 构建照样 SUCCESS，只是日志里一行 WARN。
本轮就出现过一次：生成器里写了 `return [d async for d in ...]`（同步函数里用
异步推导式），导入直接抛 SyntaxError，而构建报「成功」。
「构建成功但数据没导进去」是最难发现的失败方式，只能靠测试钉住。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.seed import importer


class _FakeCollection:
    def __init__(self, docs: list[dict] | None = None):
        self._docs: list[dict] = list(docs or [])
        self.deleted = False

    def find(self, _flt):
        async def _gen():
            for d in self._docs:
                yield d

        return _gen()

    async def count_documents(self, _flt):
        return len(self._docs)

    def delete_many(self, _flt):
        async def _go():
            self.deleted = True
            self._docs.clear()

        return _go()

    async def delete_one(self, flt):
        for i, d in enumerate(self._docs):
            if all(d.get(k) == v for k, v in flt.items()):
                self._docs.pop(i)
                return True
        return False

    async def find_one(self, flt, _proj=None):
        # 模拟真实 upsert 语义：命中 _id 或唯一键就返回已存在的文档
        for d in self._docs:
            if all(d.get(k) == v for k, v in flt.items()):
                return d
        return None

    async def replace_one(self, flt, _doc, upsert=False):
        for i, d in enumerate(self._docs):
            if all(d.get(k) == v for k, v in flt.items()):
                self._docs[i] = _doc
                return True
        if upsert:
            self._docs.append(_doc)
        return True

    async def insert_one(self, _doc):
        self._docs.append(_doc)
        return _doc.get("_id")


class _FakeDB:
    """假 db：既能预置数据（模拟「上游集合已导入」），也能接收写入。"""

    def __init__(self, data: dict[str, list[dict]] | None = None):
        self._cols = {k: _FakeCollection(v) for k, v in (data or {}).items()}

    def __getitem__(self, name: str) -> _FakeCollection:
        return self._cols.setdefault(name, _FakeCollection())


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    (tmp_path / "scripts" / "seed" / "data").mkdir(parents=True)
    overrides = tmp_path / "scripts" / "seed" / "data" / "lesson_overrides.json"
    overrides.write_text(
        json.dumps({"literacy:1:1": {"tag_label": "数字宝宝"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    return tmp_path


def _chars(n: int) -> list[dict]:
    return [
        {
            "_id": f"ch_{i:04d}",
            "char": str(i),
            "grade": 1,
            "difficulty": 1,
            "tags": ["数字"],
            "status": "published",
        }
        for i in range(n)
    ]


# ---------------------------------------------------------------- 核心回归


@pytest.mark.asyncio
async def test_resolve_generated_is_async(repo_root: Path):
    """⭐ 回归：`async for` 推导式要求所在函数是 async。

    之前写成同步函数 + `return [d async for d in ...]`，导入时抛
    `SyntaxError: asynchronous comprehension outside of an asynchronous function`。
    因为 seed 失败不阻塞发布，构建报 SUCCESS 而关卡根本没导进去 ——
    这类失败只能靠测试拦住。
    """
    db = _FakeDB({"characters": _chars(12), "poems": [], "stories": []})
    spec = {
        "collection": "lessons",
        "generated": "lessons",
        "overrides": "scripts/seed/data/lesson_overrides.json",
    }
    # 若是同步函数，这里 await 会直接 TypeError
    result = await importer.resolve_generated(spec, db, repo_root)
    assert len(result) == 2, "12 字 / 每关 6 字 = 2 关"
    assert result[0]["tag_label"] == "数字宝宝", "override 应生效"
    assert result[0]["track"] == "literacy"


@pytest.mark.asyncio
async def test_import_spec_with_generated(repo_root: Path):
    """import_spec 要能吃下 generated 型 spec（并正确 await 生成器）。"""
    db = _FakeDB({"characters": _chars(12), "poems": [], "stories": []})
    spec = {
        "collection": "lessons",
        "generated": "lessons",
        "target_grade": 1,
        "chars_per_lesson": 6,
    }
    result = await importer.import_spec(db, spec, repo_root)
    assert result["collection"] == "lessons"
    assert result["total"] == 2
    assert len(db["lessons"]._docs) == 2


@pytest.mark.asyncio
async def test_unknown_generator_raises(repo_root: Path):
    """未知生成器名要**报错**而不是静默跳过。

    静默跳过会得到「关卡 0 条」的空集合，而构建照样成功。
    """
    db = _FakeDB({"characters": _chars(6)})
    with pytest.raises(ValueError, match="未知的生成器"):
        await importer.resolve_generated({"generated": "nope"}, db, repo_root)


# ---------------------------------------------------------------- 清理白名单


@pytest.mark.asyncio
async def test_prunable_collection_removes_stale(repo_root: Path):
    """⭐ 回归：内容型集合里「内容包已删掉的条目」必须从库里清掉。

    实测踩过：内容包从 5 篇故事删到 4 篇，库里的旧篇仍在 →
    自动生成的关卡数 22 变 23。这类偏差不报错、界面不异常，
    只有把「库内条数」与「内容包条数」对着看才发现。
    """
    db = _FakeDB({"characters": _chars(12), "poems": [], "stories": []})
    # 预置一篇内容包里已经没有的旧故事
    db["stories"]._docs.append({"_id": "st_old_removed", "title": "旧故事", "status": "published"})

    data_dir = repo_root / "scripts" / "seed" / "data"
    (data_dir / "07_stories.json").write_text(
        json.dumps({"collection": "stories", "documents": [{"_id": "st_new", "title": "新故事"}]}),
        encoding="utf-8",
    )
    results = await importer.import_dir(db, data_dir, repo_root)
    ids = [d["_id"] for d in db["stories"]._docs]
    assert "st_old_removed" not in ids, "内容包已删的条目必须从库中清掉"
    assert ids == ["st_new"]
    assert next(r for r in results if r["collection"] == "stories")["stale_removed"] == 1


@pytest.mark.asyncio
async def test_user_data_collections_are_never_pruned(repo_root: Path):
    """⭐ 安全红线：`accounts` / `invites` 绝不能被「不在本次导入里就删」清掉。

    它们的库内内容来自**用户行为**（注册、领码），不是仓库的镜像。
    一旦被清，用户当场无法登录 —— 且不可恢复。
    这个测试就是为了让「误加进白名单」立刻失败。
    """
    db = _FakeDB({})

    # 库里已有真实用户数据（不在本次 seed 里）
    db["accounts"]._docs.append({"_id": "acc_real_user", "username": "real_user"})
    db["invites"]._docs.append({"_id": "inv_used", "code_hash": "abc"})

    data_dir = repo_root / "scripts" / "seed" / "data"
    (data_dir / "02_accounts.json").write_text(
        json.dumps({"collection": "accounts", "documents": [{"_id": "acc_admin", "username": "admin"}]}),
        encoding="utf-8",
    )
    (data_dir / "01_invites.json").write_text(
        json.dumps({"collection": "invites", "documents": [{"_id": "inv_sample", "code_hash": "x"}]}),
        encoding="utf-8",
    )
    await importer.import_dir(db, data_dir, repo_root)

    acc_ids = [d["_id"] for d in db["accounts"]._docs]
    inv_ids = [d["_id"] for d in db["invites"]._docs]
    assert "acc_real_user" in acc_ids, "真实用户账号被误删了！"
    assert "inv_used" in inv_ids, "已使用的邀请码被误删了！"


def test_prunable_whitelist_excludes_user_data():
    """白名单本身要钉住：新增内容型集合可以，但账号类集合绝不能进。"""
    assert "characters" in importer.PRUNABLE_COLLECTIONS
    assert "lessons" in importer.PRUNABLE_COLLECTIONS
    for forbidden in ("accounts", "invites", "children", "devices", "learning_records"):
        assert forbidden not in importer.PRUNABLE_COLLECTIONS, (
            f"{forbidden} 是用户数据，绝不能进可清理白名单"
        )


# ---------------------------------------------------------------- 残留清理


@pytest.mark.asyncio
async def test_stale_generated_docs_are_removed(repo_root: Path):
    """⭐ 回归：本次没生成的旧文档必须被清掉。

    实测踩过两种：
      ① id 形态从 `ls_g1_01` 变成 `literacy:1:1`，旧批次原样留着；
      ② 关卡数从 23 变 22，少掉那一关的旧 id **形态完全合法**，
         于是「按形态判断」清不掉它 —— 必须按「不在本次结果里」判断。
    两种症状相同：发布日志不报错、界面不异常、健康检查全绿，
    只是孩子看到多出来的废弃关卡。
    """
    db = _FakeDB({"characters": _chars(12), "poems": [], "stories": []})
    # 预置两批旧数据：一批形态不合法、一批形态合法但本次不会再生成
    for i in range(1, 15):
        db["lessons"]._docs.append({"_id": f"ls_g1_{i:02d}", "title": f"旧关 {i}"})
    for i in range(1, 20):
        db["lessons"]._docs.append({"_id": f"literacy:1:{i}", "title": f"多余识字关 {i}"})

    spec = {"collection": "lessons", "generated": "lessons", "chars_per_lesson": 6}
    result = await importer.import_spec(db, spec, repo_root)

    ids = [d["_id"] for d in db["lessons"]._docs]
    assert not any(i.startswith("ls_g1_") for i in ids), f"形态不合法的未被清理：{ids}"
    assert len(ids) == 2, f"只应剩 2 个本次生成的关卡，实际 {len(ids)}：{ids}"
    assert set(ids) == {"literacy:1:1", "literacy:1:2"}
    # 预置 14 个形态不合法的 + 19 个形态合法但多余的 - 2 个本次会重新生成的
    assert result["stale_removed"] == 14 + 19 - 2, "清理数量要如实报出，便于部署日志核对"


@pytest.mark.asyncio
async def test_valid_generated_docs_survive(repo_root: Path):
    """清理只删形态不合法的，**不能**把已生成的合法关卡也删掉。"""
    db = _FakeDB({"characters": _chars(12), "poems": [], "stories": []})
    spec = {"collection": "lessons", "generated": "lessons", "chars_per_lesson": 6}

    await importer.import_spec(db, spec, repo_root)
    first = [d["_id"] for d in db["lessons"]._docs]
    # 再跑一次（幂等）：数量不应变
    await importer.import_spec(db, spec, repo_root)
    assert [d["_id"] for d in db["lessons"]._docs] == first, "重复导入后关卡不应减少"


# ---------------------------------------------------------------- 依赖检查


@pytest.mark.asyncio
async def test_import_dir_reports_not_yet_imported_dependency(tmp_path: Path, repo_root: Path):
    """依赖集合**从未被导入**时要报错并说清原因，而不是生成 0 关后「成功」。

    这正是重排 seed 文件序号的理由：原 07_lessons 排在 08_stories 之前，
    依赖不满足 → 生成出空关卡，而一切看起来都正常。

    ⛔ 注意语义是「有没有被导入过」，**不是**「集合是否为空」——
    「这个站点还没有古诗」是合法状态，不该报错。
    """
    data_dir = repo_root / "scripts" / "seed" / "data"
    (data_dir / "09_lessons.json").write_text(
        json.dumps({"collection": "lessons", "generated": "lessons"}), encoding="utf-8"
    )
    # 一个 spec 都不先导入 → 三个依赖都没被导入过
    db = _FakeDB({"characters": [], "poems": [], "stories": []})
    with pytest.raises(RuntimeError, match="还没被导入"):
        await importer.import_dir(db, data_dir, repo_root)


@pytest.mark.asyncio
async def test_import_dir_allows_empty_dependency_once_imported(tmp_path: Path, repo_root: Path):
    """依赖被导入过但内容为空 → 合法，生成 0 条对应关卡，不报错。"""
    data_dir = repo_root / "scripts" / "seed" / "data"
    (data_dir / "05_poems.json").write_text(
        json.dumps({"collection": "poems", "documents": []}), encoding="utf-8"
    )
    (data_dir / "07_stories.json").write_text(
        json.dumps({"collection": "stories", "documents": []}), encoding="utf-8"
    )
    (data_dir / "04_characters.json").write_text(
        json.dumps({"collection": "characters", "documents": _chars(12)}), encoding="utf-8"
    )
    (data_dir / "09_lessons.json").write_text(
        json.dumps({"collection": "lessons", "generated": "lessons", "chars_per_lesson": 6}),
        encoding="utf-8",
    )
    db = _FakeDB({"characters": [], "poems": [], "stories": []})
    results = await importer.import_dir(db, data_dir, repo_root)
    lessons = next(r for r in results if r["collection"] == "lessons")
    # 12 个字 / 每关 6 字 = 2 个识字关卡；无古诗无故事 → 0 条对应关卡
    assert lessons["total"] == 2


@pytest.mark.asyncio
async def test_import_dir_runs_generated_in_order(tmp_path: Path, repo_root: Path):
    """依赖满足时，生成型 spec 正常跑完。"""
    data_dir = repo_root / "scripts" / "seed" / "data"
    (data_dir / "04_characters.json").write_text(
        json.dumps({"collection": "characters", "documents": _chars(12)}), encoding="utf-8"
    )
    (data_dir / "05_poems.json").write_text(
        json.dumps({"collection": "poems", "documents": []}), encoding="utf-8"
    )
    (data_dir / "07_stories.json").write_text(
        json.dumps({"collection": "stories", "documents": []}), encoding="utf-8"
    )
    (data_dir / "09_lessons.json").write_text(
        json.dumps({"collection": "lessons", "generated": "lessons", "chars_per_lesson": 6}),
        encoding="utf-8",
    )
    db = _FakeDB({"characters": [], "poems": [], "stories": []})
    results = await importer.import_dir(db, data_dir, repo_root)
    assert len(results) == 4
    assert next(r for r in results if r["collection"] == "lessons")["total"] == 2
