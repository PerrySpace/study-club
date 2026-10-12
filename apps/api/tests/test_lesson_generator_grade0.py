"""学龄前（grade=0）与「年级上限」—— 钉住两个真实踩过的坑。

## 坑 1：`or 1` 把学龄前吞成一年级
Python 里 `0` 是 falsy。旧实现写的是 `int(c.get("grade") or 1)`，
于是学龄前（`grade=0`）的内容被**静默升成 1**：导入过的内容「看起来进去了」，
却出现在一年级的关卡里，界面上完全看不出异常。
（TS 侧对应写法 `c.grade ?? 1` 只对 null/undefined 回落 —— 两边因此生成出
不同的关卡，正是 `test_lessons_parity.py` 要拦的那类漂移。）

## 坑 2：只生成一套关卡 ⇒ 学龄前孩子零关可玩
旧实现用单一 `target_grade` 取「该年级及以下」的池子、却只产出
`grade = target_grade` 的关卡。客户端按 `lesson.grade <= 孩子年级` 过滤 ⇒
学龄前孩子（`grade=0`）**一关都看不到**，而库里明明有学龄前内容。

修法：关卡按「内容自身年级」分桶，每个年级各成一条线。
`target_grade` 从「目标年级」变成「上限（含）」，默认 `GRADE_MAX`。
"""

from __future__ import annotations

from app.seed.lesson_generator import generate_lessons


def _char(i: int, grade: int | None = 1) -> dict:
    item: dict = {
        "_id": f"ch_{i:04d}",
        "char": str(i),
        "difficulty": 1,
        "tags": ["家人"],
        "status": "published",
    }
    if grade is not None:
        item["grade"] = grade
    return item


def _chars(n: int, grade: int | None = 1, offset: int = 0) -> list[dict]:
    return [_char(offset + i, grade) for i in range(n)]


def _literacy(lessons: list[dict]) -> list[dict]:
    return [l for l in lessons if l["track"] == "literacy"]


# ---------------------------------------------------------------- 坑 1：0 不被吞


def test_preschool_content_stays_grade_zero():
    """`grade=0` 的字必须产出 `grade=0` 的关卡，不能被升成 1。"""
    lessons = _literacy(generate_lessons(characters=_chars(6, 0)))

    assert lessons, "学龄前内容必须能成关（否则等于「导入没生效」）"
    assert {l["grade"] for l in lessons} == {0}
    assert all(l["_id"].startswith("literacy:0:") for l in lessons)


def test_missing_grade_still_defaults_to_one():
    """字段**缺失**才回落 1 —— 与 TS 的 `?? 1` 同义，但 `0` 不是「缺失」。"""
    lessons = _literacy(generate_lessons(characters=_chars(6, None)))

    assert {l["grade"] for l in lessons} == {1}


def test_preschool_and_grade1_do_not_mix():
    """学龄前与一年级各成一条线：字不能互相混进对方的关卡。"""
    chars = [*_chars(6, 0), *_chars(6, 1, offset=100)]
    lessons = _literacy(generate_lessons(characters=chars))

    by_grade: dict[int, list[dict]] = {}
    for lesson in lessons:
        by_grade.setdefault(lesson["grade"], []).append(lesson)

    assert set(by_grade) == {0, 1}, "两个年级应各成一条线"
    ids0 = {i for l in by_grade[0] for i in l["character_ids"]}
    ids1 = {i for l in by_grade[1] for i in l["character_ids"]}
    assert not (ids0 & ids1), "学龄前与一年级的字不得互相混入"
    assert ids0 == {f"ch_{i:04d}" for i in range(6)}


# ---------------------------------------------------------------- 坑 2：可见性


def test_preschool_lesson_visible_to_preschool_child():
    """客户端按 `lesson.grade <= 孩子年级` 过滤 —— 学龄前孩子（0）不能是零关。"""
    lessons = generate_lessons(characters=_chars(6, 0))

    visible = [l for l in lessons if l["grade"] <= 0]
    assert visible, "学龄前孩子过滤后必须还有关卡可玩"


def test_grades_get_their_own_lessons():
    """每个年级都能拿到自己年级（及以下）的关卡 —— 这是「年级可扩展」的前提。"""
    chars = [*_chars(6, 0), *_chars(6, 1, offset=100), *_chars(6, 2, offset=200)]
    lessons = generate_lessons(characters=chars)

    for grade in (0, 1, 2):
        visible = [l for l in lessons if l["grade"] <= grade]
        assert visible, f"{grade} 年级孩子应有可见关卡"


# ---------------------------------------------------------------- 上限与档位


def test_target_grade_is_a_ceiling():
    """`target_grade` 是**上限**：超过它的年级不生成。"""
    chars = [*_chars(6, 1), *_chars(6, 7, offset=100)]
    lessons = generate_lessons(characters=chars, target_grade=6)

    assert {l["grade"] for l in lessons} == {1}


def test_default_ceiling_covers_extended_grades():
    """默认上限是 `GRADE_MAX` —— 后台把年级扩到 7/8/9 后无需改代码。"""
    lessons = generate_lessons(characters=_chars(6, 9))

    assert {l["grade"] for l in lessons} == {9}


def test_level_of_preschool_is_sprout():
    """难度档位：学龄前是 `sprout`，不是 `grade1`。

    ⛔ 旧实现 `f"grade{max(1, grade)}"` 会把学龄前摊成 `grade1`，
    与客户端 `levelForGrade()`（`grade <= 0 → sprout`）的口径不一致。
    """
    lessons = generate_lessons(characters=_chars(6, 0))

    assert all(l["level"] == "sprout" for l in lessons)


def test_level_of_extended_grade_is_bridge():
    """7 年级及以上跨学段，落 `bridge`；1–6 仍是 `grade{n}`。"""
    high = generate_lessons(characters=_chars(6, 7))
    mid = generate_lessons(characters=_chars(6, 3, offset=100))

    assert all(l["level"] == "bridge" for l in high)
    assert all(l["level"] == "grade3" for l in mid)


# ---------------------------------------------------------------- 三条线一起


def test_preschool_buckets_apply_to_all_tracks():
    """古诗与故事同样按自身年级成线 —— 不能只有识字线生效。"""
    lessons = generate_lessons(
        characters=_chars(6, 0),
        poems=[{"_id": "pm_p0", "title": "咏鹅", "difficulty": 1, "grade": 0, "status": "published"}],
        stories=[{"_id": "st_p0", "title": "小手拍拍", "grade": 0, "status": "published"}],
    )

    assert {l["track"] for l in lessons} == {"literacy", "poem", "story"}
    assert all(l["grade"] == 0 for l in lessons)
    assert all(l["level"] == "sprout" for l in lessons)
