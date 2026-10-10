"""邀请码服务：归一化、哈希、可用性判定、文档构造。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core import security as S
from app.controllers import invite_controller as I


def test_normalize_code_strips_and_uppercases():
    assert I.normalize_code(" abcd-efgh-jkmn ") == "ABCDEFGHJKMN"
    assert I.normalize_code("ABCD EFGH JKMN") == "ABCDEFGHJKMN"


def test_hash_is_normalized_and_stable():
    assert I.hash_invite_code("abcd-efgh-jkmn") == I.hash_invite_code("ABCDEFGHJKMN")
    assert I.hash_invite_code("ABCDEFGHJKMN") == S.sha256_hex("ABCDEFGHJKMN")


def test_make_invite_document_fields():
    now = datetime.now(timezone.utc)
    doc = I.make_invite_document(
        raw_code="ABCDEFGHJKMN",
        batch_id="b1",
        channel="test",
        max_uses=2,
        expires_at=now + timedelta(days=1),
        note=None,
        created_by=None,
    )
    assert doc["code_hash"] == S.sha256_hex("ABCDEFGHJKMN")
    assert doc["code_hint"] == "ABCD-****-****"
    assert doc["used_count"] == 0
    assert doc["bound_account_ids"] == []
    assert doc["revoked_at"] is None
    assert "ABCDEFGHJKMN" not in str(doc.values())


def test_is_usable_happy_path():
    doc = {"used_count": 0, "max_uses": 1, "revoked_at": None, "expires_at": None}
    assert I.is_usable(doc) is True


def test_is_usable_revoked():
    doc = {"used_count": 0, "max_uses": 1, "revoked_at": datetime.now(timezone.utc), "expires_at": None}
    assert I.is_usable(doc) is False


def test_is_usable_expired():
    past = datetime.now(timezone.utc) - timedelta(days=1)
    doc = {"used_count": 0, "max_uses": 1, "revoked_at": None, "expires_at": past}
    assert I.is_usable(doc) is False


def test_is_usable_exhausted():
    doc = {"used_count": 1, "max_uses": 1, "revoked_at": None, "expires_at": None}
    assert I.is_usable(doc) is False


def test_generate_raw_codes_unique():
    codes = I.generate_raw_codes(20)
    assert len(codes) == 20
    assert len(set(codes)) == 20
    assert all(len(c) == 12 for c in codes)
