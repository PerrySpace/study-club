"""站点配置：年级表（`grades`）—— 任意年级与脏数据边界。

背景：年级原本写死 1–6（core 的 `GRADE_LABELS`、各处 `Field(le=6)`），
现改为后台可配置。这份配置决定**客户端所有年级下拉**与**内容的 grade 校验上界**，
一条坏数据会同时污染界面与「该年级及以下」的内容池筛选，因此边界必须钉住。
"""

from __future__ import annotations

import pytest

from app.core import runtime_config as rc


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