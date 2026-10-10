"""关卡自动生成（服务端）的单元测试。

与 `packages/core/src/algorithms/lessons.ts` 是**同一套规则的两份实现**
（关卡要落库，所以服务端必须能算一遍）。测试除保证自身正确外，
还钉住「确定性」「override 不破坏解锁链」这两条最要紧的性质。

⚠️ 两侧规则一旦漂移，症状是「后台看到 14 关、客户端渲染 13 关」——
这类问题的根因极难定位，所以改动 TS 版时**必须**同步这里并跑本文件。
"""

from __future__ import annotations

from app.seed.lesson_generator import generate_lessons


def _char(i: int, grade: int = 1, difficulty: int = 1, tags: list[str] | None = None, order: int = 0) -> dict:
    return {
        "_id": f"ch_{i:04d}",
        "char": str(i),
        "grade": grade,
        "difficulty": difficulty,
        "order": order,
        "tags": tags if tags is not None else ["数字", "自然", "动物"][i % 3],
        "status": "published",
    }


def _chars(n: int, grade: int = 1) -> list[dict]:
    return [_char(i, grade, (i % 3) + 1, order=i) for i in range(n)]


# ---------------------------------------------------------------- 确定性


def test_deterministic():
    """同样输入必须得到同样输出。

    打破它的后果：「内容没改、关卡却变了」—— 已完成的孩子进度会错位。
    """
    a = generate_lessons(characters=_chars(18), target_grade=1)
    b = generate_lessons(characters=_chars(18), target_grade=1)
    assert a == b


def test_deterministic_ignores_input_order():
    """打乱输入数组顺序不应影响生成结果。

    ⛔ 这条靠 `_sort_key` 里的 `_id` 兜底才成立。少那一项时，
    两个 difficulty/order 都相同的字会按数组顺序排 —— 而数组顺序是编辑
    随手写的，重跑一次可能就变了。
    """
    chars = _chars(18)
    shuffled = [chars[10], *chars[:10], *chars[11:]]
    a = generate_lessons(characters=chars, target_grade=1)
    b = generate_lessons(characters=shuffled, target_grade=1)
    assert [l["_id"] for l in a] == [l["_id"] for l in b]


# ---------------------------------------------------------------- 切分


def test_splits_into_six_char_lessons():
    lessons = generate_lessons(characters=_chars(18), target_grade=1)
    literacy = [l for l in lessons if l["track"] == "literacy"]
    assert len(literacy) == 3
    assert all(len(l["character_ids"]) == 6 for l in literacy)


def test_remainder_still_becomes_a_lesson():
    """不足一关的字也要成关，不能被丢弃。"""
    lessons = generate_lessons(characters=_chars(4), target_grade=1)
    literacy = [l for l in lessons if l["track"] == "literacy"]
    assert len(literacy) == 1
    assert len(literacy[0]["character_ids"]) == 4


def test_no_empty_lesson():
    lessons = generate_lessons(characters=_chars(13), target_grade=1)
    assert all(len(l["character_ids"]) > 0 for l in lessons)


# ---------------------------------------------------------------- 年级


def test_grade_pool_excludes_higher_grades():
    chars = [*_chars(6, 1), *_chars(6, 3)]
    lessons = generate_lessons(characters=chars, target_grade=1)
    ids = [i for l in lessons if l["track"] == "literacy" for i in l["character_ids"]]
    assert len(ids) == 6, "一年级只应看到一年级的字"


def test_grade_pool_includes_lower_grades():
    chars = [*_chars(6, 1), *_chars(6, 3)]
    lessons = generate_lessons(characters=chars, target_grade=3)
    ids = [i for l in lessons if l["track"] == "literacy" for i in l["character_ids"]]
    assert len(ids) == 12, "三年级应看到该年级及以下"


# ---------------------------------------------------------------- 解锁链


def test_unlock_chain_is_linear():
    lessons = generate_lessons(characters=_chars(18), target_grade=1)
    literacy = [l for l in lessons if l["track"] == "literacy"]
    assert literacy[0]["unlock_rules"]["required_lesson_id"] is None, "首关永远可玩"
    for i in range(1, len(literacy)):
        assert literacy[i]["unlock_rules"]["required_lesson_id"] == literacy[i - 1]["_id"]


def test_unlock_chain_never_points_at_missing_lesson():
    lessons = generate_lessons(characters=_chars(18), target_grade=1)
    ids = {l["_id"] for l in lessons}
    for l in lessons:
        req = l["unlock_rules"]["required_lesson_id"]
        assert req is None or req in ids


# ---------------------------------------------------------------- override


def test_override_order_and_label():
    base = generate_lessons(characters=_chars(18), target_grade=1)
    target = [l for l in base if l["track"] == "literacy"][0]
    after = generate_lessons(
        characters=_chars(18),
        target_grade=1,
        overrides={target["_id"]: {"order": 3, "tag_label": "数字宝宝"}},
    )
    literacy = [l for l in after if l["track"] == "literacy"]

    assert literacy[2]["tag_label"] == "数字宝宝"
    assert len(literacy) == len([l for l in base if l["track"] == "literacy"]), "关卡数不应改变"
    assert [l["order"] for l in literacy] == [1, 2, 3], "order 必须重排为连续无重复"
    assert len({l["_id"] for l in literacy}) == len(literacy), "不得出现重复关卡"
    for i in range(1, len(literacy)):
        assert (
            literacy[i]["unlock_rules"]["required_lesson_id"] == literacy[i - 1]["_id"]
        ), "override 后解锁链仍须指向实际前一关"


def test_override_out_of_range_is_ignored():
    base = generate_lessons(characters=_chars(12), target_grade=1)
    first = [l for l in base if l["track"] == "literacy"][0]
    after = generate_lessons(
        characters=_chars(12), target_grade=1, overrides={first["_id"]: {"order": 99}}
    )
    assert len([l for l in after if l["track"] == "literacy"]) == len(
        [l for l in base if l["track"] == "literacy"]
    )


def test_override_conflicting_slot_does_not_overwrite():
    """两个 override 钉同一位置：后者跳过，不互相覆盖。"""
    base = generate_lessons(characters=_chars(18), target_grade=1)
    lit = [l for l in base if l["track"] == "literacy"]
    after = generate_lessons(
        characters=_chars(18),
        target_grade=1,
        overrides={lit[0]["_id"]: {"tag_label": "A"}, lit[1]["_id"]: {"order": 1, "tag_label": "B"}},
    )
    new_lit = [l for l in after if l["track"] == "literacy"]
    assert len(new_lit) == len(lit)
    assert len({l["_id"] for l in new_lit}) == len(new_lit), "不得出现重复关卡"


def test_override_disabled():
    base = generate_lessons(characters=_chars(12), target_grade=1)
    first = [l for l in base if l["track"] == "literacy"][0]
    after = generate_lessons(
        characters=_chars(12), target_grade=1, overrides={first["_id"]: {"disabled": True}}
    )
    assert next(l for l in after if l["_id"] == first["_id"])["status"] == "offline"


def test_comment_keys_are_ignored():
    """override 文件里的 `_comment` 之类注释键不能被当成关卡 id。"""
    after = generate_lessons(
        characters=_chars(12),
        target_grade=1,
        overrides={"_comment": "这是一段说明", "_note": {"order": 1}},
    )
    assert all(not l["_id"].startswith("_") for l in after)


# ---------------------------------------------------------------- 三条线


def test_three_tracks_generated():
    lessons = generate_lessons(
        characters=_chars(18),
        poems=[
            {"_id": "pm_1", "title": "静夜思", "difficulty": 1, "grade": 1, "status": "published"},
            {"_id": "pm_2", "title": "咏鹅", "difficulty": 1, "grade": 1, "status": "published"},
        ],
        stories=[{"_id": "st_1", "title": "小马喝水", "grade": 1, "status": "published"}],
        target_grade=1,
    )
    assert {l["track"] for l in lessons} == {"literacy", "poem", "story"}
    assert next(l for l in lessons if l["track"] == "poem")["tag_label"] == "静夜思"
    assert next(l for l in lessons if l["track"] == "story")["tag_label"] == "小马喝水"


def test_story_track_has_no_image_choice():
    """故事线不做「看图选字」：故事的图是插画不是字义，题型语义不匹配。"""
    lessons = generate_lessons(
        characters=_chars(12),
        stories=[{"_id": "st_1", "title": "故事", "grade": 1, "status": "published"}],
        target_grade=1,
    )
    story = [l for l in lessons if l["track"] == "story"][0]
    assert "image-choice" not in story["game_types"]


def test_draft_content_generates_nothing():
    lessons = generate_lessons(
        characters=_chars(12),
        poems=[{"_id": "pm_x", "title": "草", "difficulty": 1, "grade": 1, "status": "draft"}],
        target_grade=1,
    )
    assert [l for l in lessons if l["track"] == "poem"] == []


def test_lesson_ids_are_stable_format():
    """关卡 id 必须是 `{track}:{grade}:{序号}` —— 解锁链要稳定引用它。"""
    lessons = generate_lessons(characters=_chars(12), target_grade=1)
    for l in lessons:
        assert l["_id"].startswith(f"{l['track']}:{l['grade']}:")


def test_tag_label_uses_character_tag():
    """识字关卡名用本关字的共同标签，而不是「第 1 关」。"""
    chars = [
        _char(i, tags=["数字"]) for i in range(6)
    ]
    lessons = generate_lessons(characters=chars, target_grade=1)
    literacy = [l for l in lessons if l["track"] == "literacy"]
    assert literacy[0]["tag_label"].startswith("数字")
