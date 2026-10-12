"""后台内容删除：**下架（软删）与物理删除必须语义分明**。

为什么值得专门钉住：
  1. 这两件事风险等级完全不同 —— 下架改回来即可，物理删除不可恢复。
     若哪天有人「顺手」把默认语义从软删改成硬删，运营的一次误点就是数据丢失。
  2. 物理删除会留下**悬空引用**：关卡 / 单元 / 短文的 `character_ids` 指向已删内容，
     界面不报错、只是关卡点进去空着，或解锁链指向一扇不存在的门（孩子被卡住）。
     这类故障从表现上完全看不出原因，所以必须在删之前拦住。
  3. 删完必须刷新清单：`content_version` 不动，客户端就不会重拉，
     「库里删了、客户端还显示着」会被误判成缓存问题。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.controllers import admin_controller
from app.core import errors as E

REPO_ROOT = Path(__file__).resolve().parents[3]
TS_ERROR_CODES = REPO_ROOT / "packages" / "core" / "src" / "constants" / "error-codes.ts"

ACTOR = {"_id": "admin_1", "role": "admin"}


# ---------------------------------------------------------------------------
# 替身仓储：内存文档 + 最小匹配器
# ---------------------------------------------------------------------------
def _matches(doc: dict, flt: dict) -> bool:
    """只实现本测试用到的三种条件：等值、数组包含、`$lte`。"""
    for key, want in flt.items():
        have = doc.get(key)
        if isinstance(want, dict):
            if "$lte" in want and not (isinstance(have, (int, float)) and have <= want["$lte"]):
                return False
        elif isinstance(have, list):
            if want not in have:
                return False
        elif have != want:
            return False
    return True


class _FakeRepo:
    def __init__(self, docs: list[dict] | None = None) -> None:
        self.docs: dict[str, dict] = {d["_id"]: dict(d) for d in (docs or [])}

    async def find_one(self, flt: dict):
        return self.docs.get(flt.get("_id"))

    async def count(self, flt: dict | None = None) -> int:
        if not flt:
            return len(self.docs)
        return sum(1 for d in self.docs.values() if _matches(d, flt))

    async def soft_delete(self, doc_id: str, *, now=None) -> bool:
        doc = self.docs.get(doc_id)
        if doc is None:
            return False
        doc["status"] = "offline"
        doc["updated_at"] = now
        return True

    async def delete_one(self, flt: dict) -> int:
        return 1 if self.docs.pop(flt.get("_id"), None) is not None else 0


class _FakeManifest:
    def __init__(self) -> None:
        self.doc = {"_id": "current", "content_version": "1.1.0", "min_app_version": "0.1.0"}

    async def get_current(self):
        return dict(self.doc)

    async def save_current(self, doc: dict) -> None:
        self.doc = dict(doc)


class _FakeAudit:
    def __init__(self) -> None:
        self.records: list[dict] = []

    async def record(self, doc: dict) -> None:
        self.records.append(doc)


class _FakeRepos:
    def __init__(self, **collections: list[dict]) -> None:
        for key in ("characters", "poems", "units", "lessons", "stories", "badges", "readings"):
            setattr(self, key, _FakeRepo(collections.get(key)))
        self.manifest = _FakeManifest()
        self.audit_logs = _FakeAudit()

    async def content_counts(self) -> dict:
        return {key: len(getattr(self, key).docs) for key in ("characters", "poems", "readings")}


@pytest.fixture
def repos() -> _FakeRepos:
    return _FakeRepos(
        characters=[
            {"_id": "ch_1", "char": "水", "status": "published", "grade": 1},
            {"_id": "ch_2", "char": "火", "status": "published", "grade": 1},
            # 没有任何关卡/单元/短文引用它 —— 用于验证「无人引用时不必 force」
            {"_id": "ch_3", "char": "山", "status": "published", "grade": 1},
        ],
        lessons=[
            {"_id": "literacy:1:1", "title": "第一关", "character_ids": ["ch_1"], "status": "published"},
            {"_id": "literacy:1:2", "title": "第二关", "character_ids": ["ch_2"],
             "required_lesson_id": "literacy:1:1", "status": "published"},
        ],
    )


# ---------------------------------------------------------------------------
# 默认语义：软删（下架）
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_default_delete_is_offline_and_keeps_doc(repos: _FakeRepos):
    """不带参数时**必须是下架** —— 既有调用方（后台「下架」按钮）语义不能被改掉。"""
    result = await admin_controller.delete_content(repos, "characters", "ch_1", ACTOR, "127.0.0.1")

    assert result["hard"] is False
    assert "ch_1" in repos.characters.docs, "软删不能把文档删掉"
    assert repos.characters.docs["ch_1"]["status"] == "offline"
    assert repos.audit_logs.records[-1]["action"] == "characters.offline"


@pytest.mark.asyncio
async def test_default_delete_does_not_bump_manifest(repos: _FakeRepos):
    """下架不改 published 计数，因此不该进版本号（否则客户端每次都白重拉）。"""
    before = repos.manifest.doc["content_version"]
    await admin_controller.delete_content(repos, "characters", "ch_1", ACTOR, "127.0.0.1")
    assert repos.manifest.doc["content_version"] == before


# ---------------------------------------------------------------------------
# 硬删：物理移除
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_hard_delete_removes_document(repos: _FakeRepos):
    # ch_2 被第二关引用，但第一关只引用 ch_1 —— 删 ch_1 会命中引用，需要 force
    result = await admin_controller.delete_content(
        repos, "characters", "ch_1", ACTOR, "127.0.0.1", hard=True, force=True
    )

    assert result["hard"] is True
    assert "ch_1" not in repos.characters.docs, "硬删必须真的从库里移除"
    assert repos.audit_logs.records[-1]["action"] == "characters.delete"


@pytest.mark.asyncio
async def test_hard_delete_bumps_content_version(repos: _FakeRepos):
    """删完必须刷新清单 —— 否则 `/health` 停在旧版本，客户端不重拉。"""
    await admin_controller.delete_content(
        repos, "characters", "ch_1", ACTOR, "127.0.0.1", hard=True, force=True
    )
    assert repos.manifest.doc["content_version"] == "1.1.1"


@pytest.mark.asyncio
async def test_hard_delete_missing_doc_is_404(repos: _FakeRepos):
    with pytest.raises(E.BizException) as exc:
        await admin_controller.delete_content(
            repos, "characters", "ch_nope", ACTOR, "127.0.0.1", hard=True
        )
    assert exc.value.code == E.CONTENT_NOT_FOUND


# ---------------------------------------------------------------------------
# 引用校验：拦住悬空引用
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_hard_delete_refused_when_referenced(repos: _FakeRepos):
    """ch_1 被第一关的 character_ids 指着 —— 必须拒绝，且把引用明细回给调用方。"""
    with pytest.raises(E.BizException) as exc:
        await admin_controller.delete_content(repos, "characters", "ch_1", ACTOR, "127.0.0.1", hard=True)

    assert exc.value.code == E.CONTENT_IN_USE
    reasons = " ".join(item["reason"] for item in (exc.value.errors or []))
    assert "关卡" in reasons and "1" in reasons, "报错必须说清被谁引用、几处"
    assert "ch_1" in repos.characters.docs, "被拒绝时不能已经删掉"


@pytest.mark.asyncio
async def test_hard_delete_force_is_recorded_in_audit(repos: _FakeRepos):
    """强制删除要留下「明知引用仍删」的痕迹，事后可追溯。"""
    await admin_controller.delete_content(
        repos, "characters", "ch_1", ACTOR, "127.0.0.1", hard=True, force=True
    )
    record = repos.audit_logs.records[-1]
    assert record["diff"]["force"] is True
    assert record["diff"]["references"], "引用明细要一并存档"


@pytest.mark.asyncio
async def test_lesson_unlock_chain_counts_as_reference(repos: _FakeRepos):
    """删关卡也要查：第二关 `required_lesson_id` 指向第一关。

    漏掉这一条的后果正是「孩子被一扇不存在的门卡住」——
    界面上看不出任何异常。
    """
    with pytest.raises(E.BizException) as exc:
        await admin_controller.delete_content(
            repos, "lessons", "literacy:1:1", ACTOR, "127.0.0.1", hard=True
        )
    assert exc.value.code == E.CONTENT_IN_USE


@pytest.mark.asyncio
async def test_unreferenced_content_deletes_without_force(repos: _FakeRepos):
    """没人引用的内容应当直接删掉，不该逼着使用者再点一次「强制」。"""
    result = await admin_controller.delete_content(
        repos, "characters", "ch_3", ACTOR, "127.0.0.1", hard=True
    )
    assert result["hard"] is True
    assert result["references"] == []
    assert "ch_3" not in repos.characters.docs


# ---------------------------------------------------------------------------
# 错误码镜像（纪律：唯一定义源是前端 error-codes.ts，后端为镜像）
# ---------------------------------------------------------------------------
def test_content_in_use_code_mirrored_in_frontend():
    text = TS_ERROR_CODES.read_text(encoding="utf-8")
    assert "CONTENT_IN_USE: 40903" in text, "前端 error-codes.ts 必须与后端 errors.py 同步"
    assert E.CONTENT_IN_USE == 40903
    assert E.http_status_for(E.CONTENT_IN_USE) == 409
