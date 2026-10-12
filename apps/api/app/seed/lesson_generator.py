"""关卡自动生成（服务端侧）—— 与 core 的 `algorithms/lessons.ts` **保持同一套规则**。

## 为什么服务端也要一份
关卡在**服务端**被持久化（`lessons` 集合），客户端只消费生成结果。
若让服务端手写一份 TS 逻辑、客户端再写一份 JS，两边会慢慢漂移 ——
表现为「后台看到 14 关、客户端渲染出 13 关」这类找不到源头的问题。

因此这里的规则与 TS 版**逐条对应**，改动必须同步：

| 规则 | 说明 |
| --- | --- |
| 排序 | `difficulty → order → _id` 三级升序。`_id` 兜底不可省：两个字的 difficulty 与 order 都相同时，数组顺序由编辑随手决定，不保证稳定 |
| 切分 | 识字线每 `chars_per_lesson` 字一关；古诗/故事一关一条内容 |
| `_id` | `{track}:{grade}:{序号}`，**不用随机 id** —— 关卡要被解锁链稳定引用 |
| `order` | override 之后**必须重排**为连续无重复 |
| 解锁链 | override 之后**必须重算**为「实际的前一关」 |

⛔ **确定性是硬要求**：同一份内容两次生成必须得到完全一致的结果。
打破它的后果是「内容没改、关卡却变了」—— 已完成的孩子进度会错位
（他们点过的第 3 关变成了别的内容）。
"""

from __future__ import annotations

from typing import Any, Iterable

from ..core.runtime_config import GRADE_MAX

# 每关几个字。太大会一关十几分钟，太小则频繁切页。
DEFAULT_CHARS_PER_LESSON = 6

TRACKS = ("literacy", "story", "poem")
# 展示名与 core 的 `TRACK_LABEL` 必须逐字一致：两份实现会互相校验（test_lessons_parity）。
# `story` 这条线对孩子叫「识字短文」，但 key 仍是 story（数据与接口的一部分）。
TRACK_LABEL = {"literacy": "识字", "story": "识字短文", "poem": "古诗"}


def _grade_of(item: dict[str, Any]) -> int:
    """内容**自身**的年级。

    ⛔ 只能对「字段缺失」回落 1，**不能**写成 `int(item.get("grade") or 1)`。
    Python 里 `0` 是 falsy，而 `0` 正是**学龄前**的合法取值 —— 这样写会把
    学龄前的字静默升成一年级：导入过的内容「看起来进去了」，却出现在一年级的
    关卡里，界面上完全看不出异常（本仓真实踩过）。
    TS 侧对应写法是 `c.grade ?? 1`（`??` 只对 null/undefined 回落），两边必须一致。
    """
    raw = item.get("grade")
    return 1 if raw is None else int(raw)


def _level_for_grade(grade: int) -> str:
    """年级 → 难度档位。

    学龄前（≤0）是 `sprout`，7 年级及以上跨学段落到 `bridge`。
    ⛔ 不要写成 `f"grade{max(1, grade)}"`：那会把学龄前摊成 `grade1`，
    与客户端 `levelForGrade()` 的口径不一致（那里 `grade <= 0 → sprout`）。
    """
    if grade <= 0:
        return "sprout"
    if grade <= 6:
        return f"grade{grade}"
    return "bridge"


def _sort_key(item: dict[str, Any]) -> tuple[int, str]:
    """确定性排序：难度升序 → `_id`。

    ⛔ 曾把 `order` 放进排序键，但**内容包里根本没有这个字段**
    （`char.schema.json` 也没声明）—— 加进类型只会让编译通过、运行时恒为
    `None`，排序退化成「只按难度 + id」，与预期不符。因此只保留真实存在的键。
    教学顺序要调整，走 override 文件。

    ⛔ `_id` 兜底不可省。少了它，两个 difficulty 相同的字会按**输入数组顺序**排
    —— 而数组顺序是编辑在 JSON 里随手写的，同一份内容重跑一次可能就变了，
    进而让已完成孩子的进度错位。
    """
    return (int(item.get("difficulty") or 0), str(item.get("_id") or ""))


def _chunk(items: list[dict], size: int) -> list[list[dict]]:
    if size <= 0:
        return [[it] for it in items]
    return [items[i : i + size] for i in range(0, len(items), size)]


def _stable_key(track: str, grade: int, index: int) -> str:
    return f"{track}:{grade}:{index}"


def _default_tag_label(track: str, group: list[dict], index: int) -> str:
    """自动关卡名。

    - 识字：用本关字的**共同标签**（「数字」「自然」）+ 序号 —— 孩子看一眼就知道学什么；
    - 古诗 / 故事：直接用内容本身的标题（诗题 / 故事名）。
    """
    if track != "literacy":
        return str(group[0].get("title") or f"{TRACK_LABEL[track]} {index + 1}")

    counts: dict[str, int] = {}
    for item in group:
        for tag in item.get("tags") or []:
            counts[tag] = counts.get(tag, 0) + 1
    if not counts:
        return f"{TRACK_LABEL[track]} {index + 1}"
    # 出现最多者胜出；平手时按标签名排序，保证确定性
    top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    return f"{top} {index + 1}"


def _relink_unlocks(lessons: list[dict]) -> list[dict]:
    """按最终顺序重建线性解锁链。

    ⛔ 必须在 override **之后**执行。解锁链表达的是「实际的前一关」，
    而不是「序号的前一关」—— 旧实现里这个 bug 的后果是：
    某个孩子被要求先完成一个已不存在于该位置的关卡，界面表现为「第一关点不动」。
    """
    out: list[dict] = []
    for i, lesson in enumerate(lessons):
        item = dict(lesson)
        rules = dict(item.get("unlock_rules") or {})
        rules["required_lesson_id"] = lessons[i - 1]["_id"] if i > 0 else None
        rules.setdefault("min_stars", 0)
        item["unlock_rules"] = rules
        out.append(item)
    return out


def _apply_order_overrides(lessons: list[dict], overrides: dict[str, Any]) -> list[dict]:
    """按 override.order 钉位置；其余保持原相对顺序填空。

    保证两条性质，缺一个就会让地图出现重复节点或空位：
      ① 关卡顺序不重复、总数不变（`order` 是链式解锁的依据，重复会让「下一关」指向自己）；
      ② 完成后重排 `order` 字段 —— 否则 `order=1` 可能出现在第 3 位，
         界面若按 order 排序就与实际位置矛盾。

    边界：越界（超出关卡总数）或两个 override 钉同一位置 → 跳过，不互相覆盖。
    「填不满时」宁可返回原序列，也不返回一个**长度变了**的结果。
    """
    pinned: list[tuple[int, int]] = []  # (原索引, 目标位置-1)
    taken: set[int] = set()
    for i, lesson in enumerate(lessons):
        want = (overrides.get(lesson["_id"]) or {}).get("order")
        if not isinstance(want, int) or want < 1:
            continue
        pos = want - 1
        if pos >= len(lessons) or pos in taken:
            continue
        taken.add(pos)
        pinned.append((i, pos))

    if not pinned:
        return _relink_unlocks(lessons)

    slots: list[dict | None] = [None] * len(lessons)
    for src, pos in pinned:
        slots[pos] = lessons[src]
    rest = [l for i, l in enumerate(lessons) if i not in {s for s, _ in pinned}]
    cursor = 0
    for i in range(len(slots)):
        if slots[i] is None and cursor < len(rest):
            slots[i] = rest[cursor]
            cursor += 1
    filled = [s for s in slots if s is not None]
    if len(filled) != len(lessons):
        return _relink_unlocks(lessons)
    # ⭐ 重排 order，使字段值与实际位置一致
    return _relink_unlocks([{**l, "order": i + 1} for i, l in enumerate(filled)])


def _game_types(track: str) -> list[str]:
    # 故事线不做「看图选字」：故事的图是插画而非字义，题型语义不匹配
    if track == "story":
        return ["meaning-choice", "pinyin-match", "speak"]
    return ["image-choice", "audio-choice", "pinyin-match", "word-build", "meaning-choice"]


def _generate_track(
    track: str,
    grade: int,
    source: list[dict],
    overrides: dict[str, Any],
    chars_per_lesson: int,
    created_at: str,
) -> list[dict]:
    ordered = sorted(source, key=_sort_key)
    groups = _chunk(ordered, 1 if track in ("poem", "story") else chars_per_lesson)

    built: list[dict] = []
    for i, group in enumerate(groups):
        key = _stable_key(track, grade, i + 1)
        ov = overrides.get(key) or {}
        title = str(group[0].get("title") or f"{TRACK_LABEL[track]} {i + 1}")
        custom = str(ov.get("tag_label") or "").strip()
        built.append(
            {
                "_id": key,
                "title": title,
                "level": _level_for_grade(grade),
                "order": i + 1,
                "character_ids": [g["_id"] for g in group],
                "game_types": _game_types(track),
                "unlock_rules": {"required_lesson_id": None, "min_stars": 0},
                "poem_id": None,
                "unit_id": None,
                "status": "offline" if ov.get("disabled") else "published",
                "created_at": created_at,
                "track": track,
                "tag_label": custom or _default_tag_label(track, group, i),
                "grade": grade,
            }
        )

    return _apply_order_overrides(built, overrides)


def generate_lessons(
    *,
    characters: Iterable[dict],
    poems: Iterable[dict] = (),
    stories: Iterable[dict] = (),
    target_grade: int = GRADE_MAX,
    chars_per_lesson: int = DEFAULT_CHARS_PER_LESSON,
    overrides: dict[str, Any] | None = None,
    created_at: str = "1970-01-01T00:00:00.000Z",
) -> list[dict]:
    """由内容生成全部关卡（三条线 × **每个年级各一条**）。

    ## 为什么按「内容自身年级」分桶，而不是一个池子只生成一套

    旧实现用单一 `target_grade` 取「该年级及以下」的池子、却只产出
    **grade = target_grade** 的关卡（`target_grade=1` ⇒ 全部关卡都是 grade 1）。
    两个后果都真实发生过：

      ① 学龄前（`grade=0`）的内容被 `int(x.get("grade") or 1)` 摊成一年级 ——
         「导入过的学龄前内容」在关卡里全成了一年级的字，界面看不出异常；
      ② 学龄前孩子（`grade=0`）在客户端按 `lesson.grade <= 孩子年级` 过滤后
         **一关都看不到**（因为关卡 grade 最小也是 1）。

    改成每个年级各自成线后：`grade=0` 的字只进 `grade=0` 的关卡；
    一年级孩子仍按「该年级及以下」看到 0 年级 + 1 年级两条线，语义不变、互不污染。

    `target_grade` 现在是**上限**（含）：只生成 `grade <= target_grade` 的桶。
    默认 `GRADE_MAX` —— 「内容有多少年级就生成多少」，让后台扩展年级后无需改代码。
    """
    ov = {k: v for k, v in (overrides or {}).items() if not k.startswith("_")}

    def _bucket(items: Iterable[dict]) -> dict[int, list[dict]]:
        """按自身年级分桶；只留已发布、且不超过上限的。"""
        out: dict[int, list[dict]] = {}
        for item in items:
            if item.get("status") != "published":
                continue
            grade = _grade_of(item)
            if grade > target_grade:
                continue
            out.setdefault(grade, []).append(item)
        return out

    char_buckets = _bucket(characters)
    poem_buckets = _bucket(poems)
    story_buckets = _bucket(stories)

    out: list[dict] = []

    # 输出顺序保持「按线分组」（识字 → 古诗 → 故事），线内按年级升序 ——
    # 与旧实现的顺序习惯一致，日志与快照更好读。
    for grade in sorted(char_buckets):
        pool = [
            {
                "_id": c["_id"],
                "title": c.get("char") or c["_id"],
                "difficulty": c.get("difficulty"),
                "tags": c.get("tags") or [],
            }
            for c in char_buckets[grade]
        ]
        out += _generate_track("literacy", grade, pool, ov, chars_per_lesson, created_at)

    for grade in sorted(poem_buckets):
        src = [
            {
                "_id": p["_id"],
                "title": p.get("title") or p["_id"],
                "difficulty": p.get("difficulty"),
                "tags": p.get("theme_tags") or [],
            }
            for p in poem_buckets[grade]
        ]
        out += _generate_track("poem", grade, src, ov, chars_per_lesson, created_at)

    for grade in sorted(story_buckets):
        src = [
            {
                "_id": s["_id"],
                "title": s.get("title") or s["_id"],
                # 故事统一难度 1：目的是「读得有趣」，不是考字认得准不准
                "difficulty": 1,
                "tags": [],
            }
            for s in story_buckets[grade]
        ]
        out += _generate_track("story", grade, src, ov, chars_per_lesson, created_at)

    return out
