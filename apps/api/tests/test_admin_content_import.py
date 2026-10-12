"""后台内容导入：导入完必须**立刻重算关卡**。

## 为什么专门钉这一条

关卡是**派生数据**（由字库 / 古诗 / 识字短文算出），而孩子端的学习地图读的正是关卡。
后台导入只写内容集合，若不同步重算关卡，运营看到的现象是
「导入成功了，孩子端一关都没变」—— 会直接怀疑导入失败（2026-10-12 真实发生）。
以前只有跑一次 `deploy`（seed）才重算，**导入与生效之间隔了一次发布**。

本文件只测**接线**（导入 → 重算 → 刷版本）；重算本身的实现由
`test_seed_importer.test_rebuild_lessons_uses_repo_spec` 用假 DB 覆盖。
"""

from __future__ import annotations

import pytest

from app.controllers import content_import_controller as cic
from app.models.content import ContentImportRequest


@pytest.mark.asyncio
async def test_import_triggers_lesson_rebuild_and_manifest_bump(monkeypatch):
    """导入字库 → 必须重算关卡、必须刷新清单版本，且两者都要出现在返回体里。"""
    rebuilt: list[list[str]] = []
    refreshed: list[bool] = []

    async def _fake_import(_repos, collection, docs, *, publish, dry_run):
        return {"collection": collection, "total": len(docs), "created": len(docs), "updated": 0}

    async def _fake_rebuild(_repos, collections):
        rebuilt.append(list(collections))
        return {"collection": "lessons", "created": 2, "updated": 0, "stale_removed": 0, "total": 2}

    async def _fake_refresh(_repos):
        refreshed.append(True)

    monkeypatch.setattr(cic, "_import_collection", _fake_import)
    monkeypatch.setattr(cic, "rebuild_lessons_for", _fake_rebuild)
    monkeypatch.setattr(cic, "refresh_manifest", _fake_refresh)

    req = ContentImportRequest(
        source="upload",
        collections=["characters"],
        payload={"characters": [{"_id": "ch_1"}, {"_id": "ch_2"}]},
        publish=True,
    )
    result = await cic.run_import(object(), req)  # type: ignore[arg-type]

    assert rebuilt == [["characters"]], "导入内容后必须重算关卡"
    assert refreshed == [True], "内容变了必须刷 content_version，否则客户端不重拉"
    lessons = [r for r in result["results"] if r["collection"] == "lessons"]
    assert lessons, "重算结果要回给后台，让运营能看见「新增了几关」"
    assert lessons[0]["created"] == 2


@pytest.mark.asyncio
async def test_dry_run_does_not_write_or_rebuild(monkeypatch):
    """试运行（dry_run）不落库、也就不该重算关卡 —— 否则「只是看一下」会改动线上。"""
    calls: list[str] = []

    async def _explode(*args, **kwargs):
        calls.append("called")
        raise AssertionError("dry_run 不应触发任何写入路径")

    async def _fake_import(_repos, collection, docs, *, publish, dry_run):
        return {"collection": collection, "total": len(docs), "dry_run": dry_run}

    monkeypatch.setattr(cic, "_import_collection", _fake_import)
    monkeypatch.setattr(cic, "rebuild_lessons_for", _explode)
    monkeypatch.setattr(cic, "refresh_manifest", _explode)

    req = ContentImportRequest(
        source="upload", collections=["characters"], payload={"characters": []}, dry_run=True
    )
    await cic.run_import(object(), req)  # type: ignore[arg-type]

    assert calls == []
