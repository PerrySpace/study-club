"""`/content/bootstrap` 的 grade 筛选语义 —— 客户端「一首都拉不到」的那类 bug。

背景（真实缺陷）：客户端固定传 `grade=6` 意图是「一次拉全量」
（见 core 的 `CONTENT_FETCH_MAX_GRADE`）。若服务端照搬 `build_filter` 的**等值**
语义，就只会取 `grade == 6` 的内容 —— 而内容包里古诗全是 `grade=1`，
于是客户端一首都拿不到，首页「古诗学习」永远显示「暂无古诗内容」。

这类缺陷不会报错、不会 500，只会让界面安静地空着，极难发现。
所以这里钉住的是**语义**：grade 必须是「该年级及以下」。
"""

from __future__ import annotations

import inspect

import pytest

from app.controllers import content_controller
from app.core import errors as E


class _FakeRepo:
    """只记录收到的 filter，不真查库。"""

    def __init__(self) -> None:
        self.filters: list[dict] = []

    def build_filter(self, **kwargs) -> dict:
        # 与真实实现同构：grade 是等值
        flt: dict = {}
        for key, value in kwargs.items():
            if value is not None:
                flt[key] = value
        return flt

    async def list_published(self, flt=None, *, limit=1000):
        self.filters.append({"kind": "published", "flt": flt})
        return []

    async def list_page(self, flt, *, skip=0, limit=50):
        self.filters.append({"kind": "page", "flt": flt})
        return [], 0

    async def paginate(self, flt, *, sort=None, skip=0, limit=50):
        self.filters.append({"kind": "paginate", "flt": flt})
        return [], 0

    async def list_active(self, *, limit=200):
        self.filters.append({"kind": "active", "flt": None})
        return []

    async def count(self, flt=None):
        return 0


class _FakeChars(_FakeRepo):
    def build_filter(self, **kwargs):
        # 汉字仓储的 build_filter 忽略 grade（学习池在控制器里显式给 $lte）
        flt: dict = {}
        for key, value in kwargs.items():
            if value is not None:
                flt[key] = value
        return flt


class _FakeManifest(_FakeRepo):
    async def get_current(self):
        return {"_id": "current", "content_version": "1.1.0", "counts": {}}


class _FakeRepos:
    """最小 Repositories 替身：只提供 bootstrap 用到的那几个仓储。"""

    def __init__(self) -> None:
        self.manifest = _FakeManifest()
        self.poems = _FakeRepo()
        self.characters = _FakeChars()
        self.units = _FakeRepo()
        self.lessons = _FakeRepo()
        self.badges = _FakeRepo()
        self.stories = _FakeRepo()
        self.readings = _FakeRepo()


@pytest.fixture
def repos() -> _FakeRepos:
    return _FakeRepos()


def _poem_filter(repos: _FakeRepos) -> dict:
    for record in repos.poems.filters:
        if record["kind"] == "page":
            return record["flt"]
    raise AssertionError("bootstrap 没有查询古诗")


def _char_filter(repos: _FakeRepos) -> dict:
    for record in repos.characters.filters:
        if record["kind"] == "paginate":
            return record["flt"]
    raise AssertionError("bootstrap 没有查询字库")


@pytest.mark.asyncio
async def test_bootstrap_poems_grade_is_lte_not_equals(repos: _FakeRepos):
    """古诗 grade 必须是「该年级及以下」，不是等值。"""
    await content_controller.bootstrap(repos, grade=6)
    grade_clause = _poem_filter(repos)["grade"]
    assert grade_clause == {"$lte": 6}, (
        f"古诗 grade 应为 $lte，实际 {grade_clause} —— "
        "等值会让客户端拉不到低年级的诗（首页「暂无古诗内容」）"
    )


@pytest.mark.asyncio
async def test_bootstrap_characters_grade_is_lte(repos: _FakeRepos):
    """字库同理，且与古诗保持同一语义（修一处不能坏另一处）。"""
    await content_controller.bootstrap(repos, grade=6)
    assert _char_filter(repos)["grade"] == {"$lte": 6}


@pytest.mark.asyncio
async def test_bootstrap_poems_and_chars_share_grade_semantics(repos: _FakeRepos):
    """两个集合的 grade 语义必须一致 —— 这是本 bug 的真正教训。

    同一个接口里一处 `$lte`、一处等值，看起来只是「忘了改」，
    但它只在客户端传 6 时才暴露，且表现为「界面安静地空着」。
    """
    await content_controller.bootstrap(repos, grade=6)
    assert _poem_filter(repos)["grade"] == _char_filter(repos)["grade"]


@pytest.mark.asyncio
async def test_bootstrap_higher_grade_narrows_pool(repos: _FakeRepos):
    """给 1 年级时只取 grade <= 1：上界必须真的生效，不能永远返回全量。"""
    await content_controller.bootstrap(repos, grade=1)
    assert _poem_filter(repos)["grade"] == {"$lte": 1}


@pytest.mark.asyncio
async def test_bootstrap_poems_not_filtered_by_equality(repos: _FakeRepos):
    """防回归：`build_filter(grade=...)` 的等值语义不得直接出现在 bootstrap 里。"""
    source = inspect.getsource(content_controller.bootstrap)
    assert "build_filter(grade=grade)" not in source, (
        "bootstrap 不得把 grade 直接透传给 build_filter（那是等值语义）"
    )


@pytest.mark.asyncio
async def test_bootstrap_readings_not_grade_limited(repos: _FakeRepos):
    """短文不做年级过滤（客户端本地按覆盖率再筛），保持现状不被误改。"""
    await content_controller.bootstrap(repos, grade=6)
    assert not any(r["kind"] == "page" and r["flt"].get("grade") for r in repos.readings.filters)