"""站点运行配置 —— 玩法段（gameplay）的归一化与契约对齐。

为什么要专门测这一段：

1. **防漂移**：`GAMEPLAY_QUESTION_TYPES` 在 core 里独立声明（core 不能反向 import
   controllers），与 `content_controller.QUESTION_STEMS` 是两份数据，必须由测试钉住。
2. **防非法状态**：后台可以把题型全关掉 —— 那孩子进去就没题可答。归一化必须回落默认全集。
3. **防越界**：阶段检测间隔 / 语速都由后台输入，必须在服务端 clamp（前端校验可被绕过）。
"""

from __future__ import annotations

import pytest

from app.controllers.content_controller import QUESTION_STEMS
from app.core import runtime_config as rc


class _FakeSettingsRepo:
    """最小假仓储：只实现 runtime_config 用到的两个方法。"""

    def __init__(self) -> None:
        self.doc: dict | None = None
        self.save_calls = 0

    async def get_site(self) -> dict | None:
        return self.doc

    async def save_site(self, doc: dict, *, now) -> None:  # noqa: ANN001 - 鸭子类型
        self.doc = dict(doc)
        self.save_calls += 1


@pytest.fixture(autouse=True)
def _reset_config_cache():
    """进程内缓存是模块级全局量：每个用例前后都清掉，避免用例间互相污染。"""
    rc._cache = None
    yield
    rc._cache = None


# ---------------------------------------------------------------------------
# 契约对齐（防漂移）
# ---------------------------------------------------------------------------
def test_gameplay_types_subset_of_question_stems():
    """玩法可选题型必须都是真实题型，不能有客户端不认识的键。"""
    assert set(rc.GAMEPLAY_QUESTION_TYPES) <= set(QUESTION_STEMS)


def test_only_stroke_is_intentionally_excluded():
    """刻意少一个 `stroke`：笔顺素材尚未入库，先不开放这个开关（避免后台能开、客户端没得玩）。"""
    assert set(QUESTION_STEMS) - set(rc.GAMEPLAY_QUESTION_TYPES) == {"stroke"}


def test_default_gameplay_shape():
    g = rc.default_gameplay()
    assert g["stage_test_every"] == 5
    assert g["enabled_question_types"] == list(rc.GAMEPLAY_QUESTION_TYPES)
    assert g["enable_speak"] is True
    assert g["show_pictograph"] is True
    assert g["speak_rate"] == 0.8


# ---------------------------------------------------------------------------
# 归一化
# ---------------------------------------------------------------------------
def test_stage_test_every_clamped():
    base = rc.default_gameplay()
    assert rc._normalize_gameplay({"stage_test_every": 1}, base)["stage_test_every"] == rc.STAGE_TEST_EVERY_MIN
    assert rc._normalize_gameplay({"stage_test_every": 99}, base)["stage_test_every"] == rc.STAGE_TEST_EVERY_MAX
    assert rc._normalize_gameplay({"stage_test_every": "abc"}, base)["stage_test_every"] == 5


def test_empty_question_types_falls_back_to_all():
    """一个题型都不许 = 孩子进去没题可答，这不是合法状态。"""
    out = rc._normalize_gameplay({"enabled_question_types": []}, rc.default_gameplay())
    assert out["enabled_question_types"] == list(rc.GAMEPLAY_QUESTION_TYPES)


def test_unknown_question_types_dropped_and_deduped_in_contract_order():
    out = rc._normalize_gameplay(
        {"enabled_question_types": ["speak", "nope-not-a-type", "image-choice", "speak"]},
        rc.default_gameplay(),
    )
    # 不认识的丢掉、重复的去掉、顺序永远是契约顺序（不随输入顺序抖动）
    assert out["enabled_question_types"] == ["image-choice", "speak"]


def test_non_list_question_types_falls_back_to_all():
    out = rc._normalize_gameplay({"enabled_question_types": "image-choice"}, rc.default_gameplay())
    assert out["enabled_question_types"] == list(rc.GAMEPLAY_QUESTION_TYPES)


def test_speak_rate_clamped_and_nan_falls_back():
    base = rc.default_gameplay()
    assert rc._normalize_gameplay({"speak_rate": 5}, base)["speak_rate"] == rc.SPEAK_RATE_MAX
    assert rc._normalize_gameplay({"speak_rate": 0.1}, base)["speak_rate"] == rc.SPEAK_RATE_MIN
    assert rc._normalize_gameplay({"speak_rate": float("nan")}, base)["speak_rate"] == 0.8
    assert rc._normalize_gameplay({"speak_rate": None}, base)["speak_rate"] == 0.8


def test_switches_coerced_to_bool():
    out = rc._normalize_gameplay(
        {"enable_speak": 0, "show_pictograph": None}, rc.default_gameplay()
    )
    assert out["enable_speak"] is False
    # None 走默认值 True（而不是变成 False），口径是「缺键 = 用默认」
    assert out["show_pictograph"] is True


# ---------------------------------------------------------------------------
# 载入 / 更新
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_load_config_seeds_defaults_when_db_empty():
    repo = _FakeSettingsRepo()
    cfg = await rc.load_config(repo)
    assert repo.save_calls == 1
    assert cfg["gameplay"]["stage_test_every"] == 5
    # 缓存生效：再取一次拿到同一个对象
    assert rc.get_config() is cfg
    rc._cache = None  # 清理全局缓存，避免污染其它测试


@pytest.mark.asyncio
async def test_update_config_merges_gameplay_and_clamps():
    repo = _FakeSettingsRepo()
    await rc.load_config(repo)
    cfg = await rc.update_config(
        repo,
        {
            "gameplay": {"stage_test_every": 3, "enabled_question_types": ["image-choice"], "speak_rate": 0.6},
            "require_invite": True,
        },
    )
    assert cfg["gameplay"]["stage_test_every"] == 3
    assert cfg["gameplay"]["enabled_question_types"] == ["image-choice"]
    assert cfg["gameplay"]["speak_rate"] == 0.6
    # 未提到的玩法键保留旧值，不会被 dict 合并抹掉
    assert cfg["require_invite"] is True
    rc._cache = None


@pytest.mark.asyncio
async def test_update_config_ignores_unknown_keys():
    repo = _FakeSettingsRepo()
    await rc.load_config(repo)
    cfg = await rc.update_config(repo, {"not_a_key": 1, "gameplay": {"nope": 2}})
    assert "not_a_key" not in cfg
    assert "nope" not in cfg["gameplay"]
    rc._cache = None


@pytest.mark.asyncio
async def test_gameplay_config_returns_detached_copy():
    """返回副本：调用方就地改坏不会污染进程缓存。"""
    repo = _FakeSettingsRepo()
    await rc.load_config(repo)
    got = rc.gameplay_config()
    got["enabled_question_types"].append("hacked")
    got["stage_test_every"] = 999
    again = rc.gameplay_config()
    assert "hacked" not in again["enabled_question_types"]
    assert again["stage_test_every"] == 5
    rc._cache = None
