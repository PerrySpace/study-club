"""站点配置：年级表（`grades`）—— 任意年级与脏数据边界。

背景：年级原本写死 1–6（core 的 `GRADE_LABELS`、各处 `Field(le=6)`），
现改为后台可配置。这份配置决定**客户端所有年级下拉**与**内容的 grade 校验上界**，
一条坏数据会同时污染界面与「该年级及以下」的内容池筛选，因此边界必须钉住。
"""

from __future__ import annotations

import pytest

from app.core import runtime_config as rc
from app.models.admin import SiteConfigUpdate


def test_grade_max_is_wide_enough():
    """上界要够用（支持任意年级），又不能大到失去意义。

    太大时 `grade=999999` 这类脏数据会让「该年级及以下」的内容池查询
    退化成全表扫，界面上也会出现荒谬文案。
    """
    assert rc.GRADE_MAX >= 7, "至少要支持到七年级"
    assert rc.GRADE_MAX <= 30, "上界过大就失去了防脏数据的作用"


def test_default_grades_are_valid():
    ids = [g["id"] for g in rc.DEFAULT_GRADES]
    assert ids == sorted(ids), "默认年级应按 id 升序"
    assert len(ids) == len(set(ids)), "默认年级不应有重复 id"
    for g in rc.DEFAULT_GRADES:
        assert 0 <= g["id"] <= rc.GRADE_MAX
        assert g["label"].strip(), "年级名称不可为空"


def test_normalize_keeps_legacy_defaults_when_absent():
    """旧站点文档没有 grades 键时，必须回落到默认年级表。

    不回落的话升级后年级下拉会变成空的，注册引导直接卡死。
    """
    out = rc._normalize_grades(None)
    assert [g["id"] for g in out] == [g["id"] for g in rc.DEFAULT_GRADES]


def test_normalize_supports_arbitrary_grades():
    """支持七年级、跨学段档位等**非默认**年级 —— 这是本需求的核心。"""
    out = rc._normalize_grades(
        [
            {"id": 7, "label": "七年级", "enabled": True},
            {"id": 0, "label": "幼小衔接", "enabled": True},
        ]
    )
    labels = {g["id"]: g["label"] for g in out}
    assert labels[7] == "七年级"
    assert labels[0] == "幼小衔接"


def test_normalize_drops_out_of_range():
    out = rc._normalize_grades([{"id": 999, "label": "越界"}, {"id": 1, "label": "一年级"}])
    assert [g["id"] for g in out] == [1]


def test_normalize_drops_negative():
    out = rc._normalize_grades([{"id": -1, "label": "负数"}, {"id": 2, "label": "二年级"}])
    assert [g["id"] for g in out] == [2]


def test_normalize_drops_duplicate_id_keeping_first():
    """重复 id 保留**首次出现**的（连同它的位置），后者丢弃。

    位置也要稳定：客户端年级下拉的顺序由配置顺序决定，
    静默改顺序会让运营看到「顺序被系统调整了」。
    """
    out = rc._normalize_grades(
        [
            {"id": 1, "label": "一年级"},
            {"id": 2, "label": "二年级"},
            {"id": 1, "label": "重复项"},
        ]
    )
    assert [(g["id"], g["label"]) for g in out] == [(1, "一年级"), (2, "二年级")]


def test_normalize_drops_blank_label():
    out = rc._normalize_grades([{"id": 1, "label": "   "}, {"id": 2, "label": "二年级"}])
    assert [g["id"] for g in out] == [2]


def test_normalize_falls_back_when_all_invalid():
    """整张表全非法时回落到默认 —— 空年级表会让注册引导卡死。"""
    out = rc._normalize_grades([{"id": 999, "label": "越界"}])
    assert [g["id"] for g in out] == [g["id"] for g in rc.DEFAULT_GRADES]


def test_normalize_empty_list_falls_back():
    assert rc._normalize_grades([]) == [dict(g) for g in rc.DEFAULT_GRADES]


def test_normalize_non_list_falls_back():
    assert rc._normalize_grades("不是列表") == [dict(g) for g in rc.DEFAULT_GRADES]


def test_strict_validation_rejects_bad_input():
    """写入侧**不静默回落** —— 运营传非法值要报错，而不是悄悄变成默认年级表。

    否则运营会遇到「我明明保存了怎么又变回一年级」。
    """
    with pytest.raises(ValueError):
        rc._normalize_grades_and_validate([{"id": 999, "label": "越界"}])
    with pytest.raises(ValueError):
        rc._normalize_grades_and_validate([{"id": 1, "label": "  "}])
    with pytest.raises(ValueError):
        rc._normalize_grades_and_validate([])


def test_strict_validation_accepts_valid():
    out = rc._normalize_grades_and_validate([{"id": 7, "label": "七年级"}])
    assert out == [{"id": 7, "label": "七年级", "enabled": True}]


def test_enabled_grade_labels_sorted_by_id():
    """启用的年级按 id 升序 —— 避免「七年级排在一年级前面」。"""
    rc._cache = rc._normalize(
        {
            **rc.default_config(),
            "grades": [
                {"id": 7, "label": "七年级", "enabled": True},
                {"id": 1, "label": "一年级", "enabled": True},
                {"id": 2, "label": "二年级", "enabled": False},
            ],
        }
    )
    try:
        labels = rc.enabled_grade_labels()
        assert list(labels.keys()) == [1, 7], "应按 id 升序且不含停用项"
    finally:
        rc._cache = None


def test_disabled_grade_excluded_but_kept_in_all_grades():
    """停用项不进入下拉，但仍能在后台看到并重新启用。"""
    rc._cache = rc._normalize(
        {
            **rc.default_config(),
            "grades": [
                {"id": 1, "label": "一年级", "enabled": True},
                {"id": 2, "label": "二年级", "enabled": False},
            ],
        }
    )
    try:
        assert 2 not in rc.enabled_grade_labels()
        assert any(g["id"] == 2 for g in rc.grades_config()), "停用项不该从配置里消失"
    finally:
        rc._cache = None


def test_config_normalize_always_produces_grades_key():
    """`_normalize` 必须始终带上 grades —— 否则老文档升级后前端拿到 undefined。"""
    assert isinstance(rc._normalize({}).get("grades"), list)
    assert isinstance(rc._normalize({"grades": []}).get("grades"), list)


def test_public_config_includes_grades():
    """免登录 `/config` 必须带 grades：注册页在建账号之前就要选年级。"""
    assert "grades" in rc.default_config()


# ---------------------------------------------------------------------------
# 请求模型 ↔ runtime_config 白名单（真实事故的回归）
# ---------------------------------------------------------------------------
def test_request_model_declares_every_updatable_key():
    """`SiteConfigUpdate` 必须声明 `UPDATABLE_KEYS` 的**每一个**键。

    真实事故：`grades` 在 runtime_config 里已支持、后台前端在传、客户端在读，
    唯独请求模型没声明。模型是 `extra="ignore"`，于是 Pydantic 把 `grades`
    **静默丢弃** —— 运营在设置页加好年级、点保存、提示成功，刷新后配置一字未变，
    而且审计日志里的 `fields` 也不含它，排查时毫无线索。

    为什么上面那一堆单测抓不到：它们全都**直接调 runtime_config**，
    永远不会经过请求模型。只有把两层对起来才能暴露，所以在这里钉住。
    """
    declared = set(SiteConfigUpdate.model_fields)
    missing = rc.UPDATABLE_KEYS - declared
    assert not missing, (
        f"runtime_config 支持但请求模型未声明，会被 extra='ignore' 静默丢弃：{sorted(missing)}。"
        "新增配置项时请同时改 models/admin.py 与 runtime_config.UPDATABLE_KEYS。"
    )


def test_request_model_keeps_grades():
    """模型必须原样保留 `grades` —— 回归上面那次静默丢弃。"""
    payload = [{"id": 7, "label": "七年级", "enabled": True}]
    dump = SiteConfigUpdate(grades=payload).model_dump(exclude_none=True)
    assert dump.get("grades") == payload


def test_request_model_drops_unrelated_fields_but_not_grades():
    """`extra="ignore"` 的本意是「后台回传多余字段时不报错」，不是「丢配置项」。

    这条用例把两侧都钉住：陌生键要放行（否则前端加一个展示字段就 422），
    认识的键一个都不能丢。
    """
    dump = SiteConfigUpdate.model_validate(
        {"grades": [{"id": 1, "label": "一年级"}], "unknown_preview_field": True}
    ).model_dump(exclude_none=True)
    assert "unknown_preview_field" not in dump
    assert dump["grades"] == [{"id": 1, "label": "一年级"}]


@pytest.mark.asyncio
async def test_update_config_persists_grades_via_request_model():
    """完整链路（前端表单 → 请求模型 → update_config → 落库 + 刷缓存）。

    不含 HTTP 层，但这正是运营真实走的那条路；上面那次事故就断在第一跳。
    """

    class _FakeSettingsRepo:
        """最小假仓储：只实现 runtime_config 用到的那两个方法。"""

        def __init__(self) -> None:
            self.doc: dict | None = None

        async def get_site(self) -> dict | None:
            return self.doc

        async def save_site(self, doc: dict, *, now) -> None:  # noqa: ANN001 - 鸭子类型
            self.doc = dict(doc)

    rc._cache = None
    repo = _FakeSettingsRepo()
    await rc.load_config(repo)
    try:
        patch = SiteConfigUpdate(
            grades=[{"id": 0, "label": "学龄前"}, {"id": 7, "label": "七年级"}]
        ).model_dump(exclude_none=True)
        await rc.update_config(repo, patch)

        assert rc.enabled_grade_labels() == {0: "学龄前", 7: "七年级"}

        # 落库的那份也必须带上 —— 只刷进程缓存的话，重启又回到旧年级表
        saved = await repo.get_site()
        assert saved is not None
        assert [g["id"] for g in saved["grades"]] == [0, 7]
    finally:
        rc._cache = None


@pytest.mark.asyncio
async def test_update_config_rejects_invalid_grades_with_value_error():
    """写入侧非法值必须**报错**（由路由转成 40001），而不是静默回落默认年级表。

    静默回落的后果是「我明明保存了怎么又变回一年级」，且运营拿不到任何提示。
    """

    class _FakeSettingsRepo:
        def __init__(self) -> None:
            self.doc: dict | None = None

        async def get_site(self) -> dict | None:
            return self.doc

        async def save_site(self, doc: dict, *, now) -> None:  # noqa: ANN001 - 鸭子类型
            self.doc = dict(doc)

    rc._cache = None
    repo = _FakeSettingsRepo()
    await rc.load_config(repo)
    try:
        with pytest.raises(ValueError):
            await rc.update_config(repo, {"grades": [{"id": 999, "label": "越界"}]})
    finally:
        rc._cache = None