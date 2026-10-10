"""序列化与内容筛选：出参 snake_case、ObjectId/时间转换、内容筛选构造。"""

from __future__ import annotations

from datetime import date, datetime, timezone

from bson import ObjectId

from app.models.content import CharacterListQuery
from app.controllers.serializers import serialize, to_iso
from app.repositories.content import CharacterRepository


def test_to_iso_aware_and_naive():
    aware = datetime(2026, 10, 8, 9, 12, tzinfo=timezone.utc)
    assert to_iso(aware) == "2026-10-08T09:12:00Z"
    naive = datetime(2026, 10, 8, 9, 12)
    assert to_iso(naive) == "2026-10-08T09:12:00Z"
    assert to_iso(None) is None


def test_serialize_nested():
    oid = ObjectId()
    doc = {
        "_id": oid,
        "child_id": oid,
        "when": datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        "day": date(2026, 1, 2),
        "items": [{"id": oid}],
    }
    out = serialize(doc)
    assert out["_id"] == str(oid)
    assert out["child_id"] == str(oid)
    assert out["when"] == "2026-01-02T03:04:05Z"
    assert out["day"] == "2026-01-02"
    assert out["items"][0]["id"] == str(oid)


def test_character_filter_defaults_to_published():
    # 前台默认只读 published；后台通过 all_status 放开
    flt = CharacterRepository.build_filter()
    assert flt["status"] == "published"


def test_character_filter_all_conditions():
    query = CharacterListQuery(
        grade=1, level="grade1", tags="自然,生活", unit_id="u-g1-01", keyword="水", status="draft"
    )
    flt = CharacterRepository.build_filter(
        status=query.status,
        grade=query.grade,
        level=query.level,
        unit_id=query.unit_id,
        tags=query.tag_list,
        keyword=query.keyword,
    )
    assert flt["status"] == "draft"
    assert flt["grade"] == 1
    assert flt["level"] == "grade1"
    assert flt["unit_refs.unit_id"] == "u-g1-01"
    assert flt["tags"] == {"$all": ["自然", "生活"]}
    assert "$or" in flt


def test_character_filter_admin_can_list_all_statuses():
    flt = CharacterRepository.build_filter(all_status=True)
    assert "status" not in flt
