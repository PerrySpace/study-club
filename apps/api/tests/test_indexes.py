"""索引定义与「同名不同定义要重建」的回归测试。

为什么专门测这一段 —— 这里出过一次很难查的事故：

`answer_records.uq_client_record` 原本声明为 `unique + sparse`，本意是
「只对带幂等键 `client_record_id` 的记录去重」。但 MongoDB 的**复合索引**上，
`sparse` 只在「所有索引键都缺失」时才跳过文档；`child_id` 永远有值，
所以没带 `client_record_id` 的记录照样以 `(child_id, null)` 进索引
（官方 Sparse Indexes 文档：*Only indexes documents that contain a value for
at least one of the keys*）。后果是「同一孩子下只能存下 1 条不带幂等键的答题记录」，
第 2 条起 E11000 → `POST /learning/answer` 500 —— 而网页端**从来不传**
`client_record_id`（那是离线补报专用），于是每个孩子从第 2 题起全部失败：
答题明细、错题本、复习状态、正确率统计一起哑掉。

更糟的是它**无法自愈**：`createIndex` 遇到同名但定义不同的索引只会报
`IndexOptionsConflict`，不会替换旧定义；旧代码把这个异常 print 一行就过去了，
线上就一直留着那条错索引。所以现在除了修正定义，`init_indexes` 还会
「同名不同定义 → 删除重建」。这两件事都必须被测试钉住。
"""

from __future__ import annotations

import pytest

from app.db import collections as C
from app.db.mongo import _index_specs, index_needs_rebuild, index_signature


def _all_specs() -> list[tuple[str, list[tuple[str, int]], dict]]:
    out = []
    for coll_name, specs in _index_specs().items():
        for keys, options in specs:
            out.append((coll_name, keys, options))
    return out


def _as_stored(keys, options) -> dict:
    """按 MongoDB `list_indexes()` 的回读形态造一个「已存在」的索引文档。

    除了定义里的字段，还刻意带上 MongoDB 自己会填的 `v` / `ns`，
    用来验证这些无关字段不会导致误判「定义变了」而反复重建。
    """
    doc = {"v": 2, "ns": "study_club.x", "key": {k: v for k, v in keys}}
    for key in ("unique", "sparse", "partialFilterExpression", "expireAfterSeconds"):
        if key in options:
            doc[key] = options[key]
    doc["name"] = options.get("name")
    return doc


# ---------------------------------------------------------------------------
# 定义本身
# ---------------------------------------------------------------------------
def test_every_index_has_a_name() -> None:
    """没有 name 就无法排查、也无法做「同名重建」的判定。"""
    for coll_name, _, options in _all_specs():
        assert options.get("name"), f"{coll_name} 有索引没写 name"


def test_index_names_are_unique_per_collection() -> None:
    """同名索引在重建逻辑里是「同一个索引」的标识，重名会互相顶掉。"""
    seen: dict[str, set[str]] = {}
    for coll_name, _, options in _all_specs():
        names = seen.setdefault(coll_name, set())
        name = options["name"]
        assert name not in names, f"{coll_name} 索引名重复：{name}"
        names.add(name)


def test_unique_compound_indexes_never_rely_on_sparse() -> None:
    """⛔ 复合唯一索引写 `sparse` 是**无效**的（见模块 docstring），必须用 partial。

    这条就是本次事故的护栏：谁再写出 `[多个键] + {"unique": True, "sparse": True}`，
    直接红。
    """
    offenders = [
        f"{coll_name}.{options['name']}"
        for coll_name, keys, options in _all_specs()
        if options.get("unique") and len(keys) > 1 and options.get("sparse")
    ]
    assert offenders == [], (
        "复合唯一索引不能用 sparse（只会在「所有键都缺失」时跳过文档）——"
        f"请改成 partialFilterExpression：{offenders}"
    )


def test_uq_client_record_is_partial_and_excludes_missing() -> None:
    """`uq_client_record` 只约束「带幂等键」的文档。"""
    spec = next(o for _, keys, o in _all_specs() if o.get("name") == "uq_client_record")
    assert spec.get("unique") is True
    assert "sparse" not in spec
    # `$type: "string"` 同时排除「字段缺失」和「显式 null」——
    # 只写 $exists 会把显式 null 收进来，同样会撞唯一键。
    assert spec["partialFilterExpression"] == {"client_record_id": {"$type": "string"}}


# ---------------------------------------------------------------------------
# 重建判定
# ---------------------------------------------------------------------------
def test_existing_matching_indexes_are_left_alone() -> None:
    """定义没变就不该重建：否则每次启动都 drop+create，白白抖动线上。"""
    for coll_name, keys, options in _all_specs():
        stored = _as_stored(keys, options)
        assert not index_needs_rebuild(stored, keys, options), f"{coll_name}.{options.get('name')} 被误判为需要重建"


def test_missing_index_is_not_treated_as_rebuild() -> None:
    """索引不存在 ⇒ 走正常 create 分支，不走重建分支。"""
    for _, keys, options in _all_specs():
        assert index_needs_rebuild(None, keys, options) is False


def test_detects_the_legacy_live_definition() -> None:
    """线上那条「非 partial 的唯一索引」必须被判为需要重建。

    这是本次事故的直接复现：库里存的是旧定义，代码里是新定义，
    必须能被识别出来并替换掉。
    """
    keys, options = next(
        (keys, o) for _, keys, o in _all_specs() if o.get("name") == "uq_client_record"
    )
    legacy = {"v": 2, "key": {"child_id": 1, "client_record_id": 1}, "unique": True, "name": "uq_client_record"}
    assert index_needs_rebuild(legacy, keys, options) is True


def test_detects_changed_option_and_key_order() -> None:
    keys, options = next(
        (keys, o) for _, keys, o in _all_specs() if o.get("name") == "uq_client_record"
    )
    # 唯一性被摘掉 → 必须重建
    assert index_needs_rebuild(_as_stored(keys, options) | {"unique": False}, keys, options) is True
    # 键序有语义，反了就是另一个索引
    reversed_doc = _as_stored(keys, options) | {"key": {k: v for k, v in reversed(keys)}}
    assert index_needs_rebuild(reversed_doc, keys, options) is True
    # 过滤表达式变了 → 必须重建
    changed = _as_stored(keys, options) | {"partialFilterExpression": {"client_record_id": {"$exists": True}}}
    assert index_needs_rebuild(changed, keys, options) is True


def test_signature_ignores_bookkeeping_fields() -> None:
    """`v` / `ns` / `background` 之类是 MongoDB 自己填的，不该参与比较。"""
    keys, options = next(
        (keys, o) for _, keys, o in _all_specs() if o.get("name") == "uq_client_record"
    )
    a = _as_stored(keys, options)
    b = dict(a) | {"v": 3, "ns": "other.db", "background": True}
    assert index_signature(a["key"], a) == index_signature(b["key"], b)


def test_text_index_is_exempt_from_rebuild_check() -> None:
    """文本索引不做重建判定 —— 否则每次启动都白白 drop+create 一遍。

    MongoDB 回读文本索引时 key 是 `{_fts: "text", _ftsx: 1}`（字段名挪进 `weights`），
    与定义里的 `char` / `meaning` / `words` 根本对不上，签名比对必然判为「已变更」。
    """
    text_keys, text_opts = next(
        (keys, o) for _, keys, o in _all_specs() if o.get("name") == "text_search"
    )
    assert any(v == "text" for _, v in text_keys), "前提：text_search 确实是文本索引"
    # 即便回读形态与定义完全对不上，也不允许把它判成「需要重建」——
    # 因为 init_indexes 会先走 _is_text_index 豁免，这条测试钉住豁免的依据。
    rewritten = {"v": 2, "key": {"_fts": "text", "_ftsx": 1}, "name": "text_search",
                 "weights": {k: 1 for k, _ in text_keys}, "textIndexVersion": 3,
                 "default_language": "english", "language_override": "language"}
    assert index_signature(rewritten["key"], rewritten) != index_signature(text_keys, text_opts)


@pytest.mark.parametrize("keys", [[("a", 1)], []])
def test_signature_accepts_plain_and_empty_keys(keys) -> None:
    """`keys` 既可能是定义里的 list，也可能是回读的 SON/dict；空键序列不能炸。"""
    assert index_signature(keys, {"name": "x"})[0] == tuple((k, int(v)) for k, v in keys)


def test_answer_records_indexes_cover_the_query_paths() -> None:
    """答题明细的查询路径（按孩子 / 按对错）必须有索引，否则统计会全表扫。"""
    names = {o["name"] for coll, _, o in _all_specs() if coll == C.ANSWER_RECORDS}
    assert {"child_char_occurred", "child_correct_occurred", "uq_client_record"} <= names
