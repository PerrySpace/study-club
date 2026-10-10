"""内容包硬约束：识字短文（阅读承接）。

「用**学过的字**编读本」是这类内容存在的全部理由 —— 覆盖率掉下去，读本就成了满篇生字的
天书，孩子只会挫败。竞品普遍兑现了这一步（每本只用已学字编、十来个字一本），
所以这里不靠人眼，把覆盖率与「声明字段必须和正文一致」做成自动化断言。

同时钉住注册表与导入源：短文是**一类内容**，必须能被后台通用 CRUD 管起来，
不能只存在于 JSON 里。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.repositories import content_registry as CR

REPO_ROOT = Path(__file__).resolve().parents[3]
CONTENT = REPO_ROOT / "content"
READINGS_FILE = CONTENT / "readings" / "readings.json"
SCHEMA_FILE = CONTENT / "schema" / "reading.schema.json"
MANIFEST_FILE = CONTENT / "manifest.json"

# 单篇短文里「已学字」占比的下限。低于此值不推荐给刚学完这批字的孩子。
MIN_COVERAGE = 0.75


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _is_cjk(ch: str) -> bool:
    return "\u4e00" <= ch <= "\u9fff"


@pytest.fixture(scope="module")
def readings() -> list[dict]:
    assert READINGS_FILE.exists(), f"缺少内容文件：{READINGS_FILE}"
    payload = _load(READINGS_FILE)
    assert isinstance(payload.get("items"), list)
    return payload["items"]


@pytest.fixture(scope="module")
def lib_by_id() -> dict[str, str]:
    """全字库：`_id` → 汉字。短文里出现的 id 必须都能在这里找到。"""
    out: dict[str, str] = {}
    for path in sorted((CONTENT / "characters").glob("*.json")):
        for item in _load(path)["items"]:
            out[item["_id"]] = item["char"]
    return out


def test_readings_non_empty(readings):
    assert len(readings) >= 6, "一年级至少要有 6 篇可读的短文/短句"


def test_ids_use_reading_prefix(readings):
    for item in readings:
        assert item["_id"].startswith("rd_"), item["_id"]


def test_character_ids_are_real_library_ids(readings, lib_by_id):
    for item in readings:
        for cid in item["character_ids"]:
            assert cid.startswith("ch_"), f"{item['_id']} 非法 id：{cid}"
            assert cid in lib_by_id, f"{item['_id']} 引用了字库里不存在的 {cid}"


def test_declared_chars_match_text_exactly(readings):
    """`character_chars` 必须**恰好**等于正文里的去重汉字（按首次出现顺序）。

    这是防漂移的核心：改了正文却忘了重算字段，覆盖率就会变成一个假数字。
    """
    for item in readings:
        text_chars = [c for c in item["text"] if _is_cjk(c)]
        expected = list(dict.fromkeys(text_chars))
        assert item["character_chars"] == expected, f"{item['_id']} 的 character_chars 与正文不一致"


def test_new_character_chars_match_remainder(readings, lib_by_id):
    """`new_character_chars` 必须恰好是「正文出现过、但不在 character_ids 里」的那些字。"""
    for item in readings:
        covered = {lib_by_id[cid] for cid in item["character_ids"]}
        expected = [c for c in item["character_chars"] if c not in covered]
        assert item["new_character_chars"] == expected, f"{item['_id']} 的 new_character_chars 不一致"


@pytest.mark.parametrize("threshold", [MIN_COVERAGE])
def test_coverage_above_threshold(readings, threshold):
    for item in readings:
        total = len(item["character_chars"])
        assert total > 0, f"{item['_id']} 没有汉字"
        coverage = len(item["character_ids"]) / total
        assert coverage >= threshold, (
            f"{item['_id']}（{item['title']}）覆盖率 {coverage:.0%} < {threshold:.0%}，"
            f"生字：{item['new_character_chars']}"
        )


def test_sentence_text_joins_to_full_text(readings):
    """`text` 必须等于各句 `text` 的拼接 —— 客户端整篇朗读依赖它。"""
    for item in readings:
        assert item["text"] == "".join(s["text"] for s in item["sentences"]), item["_id"]


def test_every_sentence_has_reading_aids(readings):
    """启蒙阶段每句都要有拼音与释义，否则家长带读时无处下手。"""
    for item in readings:
        for sentence in item["sentences"]:
            assert sentence["pinyin"].strip(), f"{item['_id']} 缺拼音"
            assert sentence["meaning"].strip(), f"{item['_id']} 缺释义"


def test_both_sentence_and_passage_types_present(readings):
    """起步读本（单句）与多句短文都要有 —— 循序渐进是这个环节的全部意义。"""
    kinds = {item["type"] for item in readings}
    assert "sentence" in kinds
    assert "passage" in kinds


# ---------------------------------------------------------------------------
# 内容包 / 注册表契约
# ---------------------------------------------------------------------------
def test_manifest_counts_and_checksum():
    """清单里的读数与校验和必须对得上实际文件（构建脚本可重算，手改必被抓住）。"""
    import hashlib

    manifest = _load(MANIFEST_FILE)
    assert manifest["counts"]["readings"] == len(_load(READINGS_FILE)["items"])
    entry = next((f for f in manifest["files"] if f["path"] == "readings/readings.json"), None)
    assert entry is not None, "清单里缺少 readings/readings.json"
    buf = READINGS_FILE.read_bytes()
    assert entry["bytes"] == len(buf)
    assert entry["checksum"] == "sha256:" + hashlib.sha256(buf).hexdigest()


def test_manifest_keeps_units_and_lessons_separate():
    """`units` 与 `lessons` 是两个口径，清单脚本不能把同目录的两份文件加成一个数。"""
    counts = _load(MANIFEST_FILE)["counts"]
    assert counts["units"] == len(_load(CONTENT / "lessons" / "units.json")["items"])
    assert counts["lessons"] == len(_load(CONTENT / "lessons" / "lessons.json")["items"])
    assert counts["units"] != counts["lessons"] + counts["units"]


def test_schema_required_fields_present():
    schema = _load(SCHEMA_FILE)
    assert schema["additionalProperties"] is False, "内容 schema 必须禁止额外字段，否则导出会混入派生数据"
    required = set(schema["required"])
    assert {"_id", "title", "sentences", "text", "character_ids", "character_chars"} <= required
    assert "new_character_chars" in required
    assert schema["properties"]["_id"]["pattern"] == "^rd_"


def test_registered_in_content_registry():
    """短文必须进注册表，后台通用 CRUD 才管得到它。"""
    spec = CR.spec_for("readings")
    assert spec is not None
    assert spec.key == "readings"
    assert spec.collection == "readings"
    assert spec.id_prefix == "rd_"
    assert "title" in spec.required_on_create
    assert "text" in spec.required_on_create
    assert "grade" in spec.filters
    assert CR.COUNT_KEYS["readings"] == "readings"


def test_registered_as_import_source():
    """导入源登记：`content/readings/readings.json` 必须能被「内容导入」一键重灌。"""
    paths = {src.path for src in CR.IMPORT_SOURCES}
    assert "content/readings/readings.json" in paths
