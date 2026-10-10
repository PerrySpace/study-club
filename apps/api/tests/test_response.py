"""统一响应信封（04-1 §1.2 / §1.3）。"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone

from bson import ObjectId

from app.core import response as R


def _body(resp) -> dict:
    return json.loads(resp.body.decode("utf-8"))


def test_ok_envelope_shape():
    resp = R.ok({"a": 1})
    body = _body(resp)
    assert resp.status_code == 200
    assert body["code"] == 0
    assert body["message"] == "ok"
    assert body["data"] == {"a": 1}
    assert "request_id" in body and body["request_id"]


def test_fail_envelope_has_no_data_and_has_errors():
    resp = R.fail(40001, "参数校验失败", errors=[{"field": "grade", "reason": "必须是 1-6"}])
    body = _body(resp)
    assert resp.status_code == 400
    assert body["code"] == 40001
    assert "data" not in body
    assert body["errors"][0]["field"] == "grade"


def test_fail_http_status_follows_code():
    assert R.fail(40103, "x").status_code == 401
    assert R.fail(40301, "x").status_code == 403
    assert R.fail(40401, "x").status_code == 404
    assert R.fail(42901, "x").status_code == 429


def test_paged_envelope():
    resp = R.paged([1, 2], page=1, page_size=2, total=5)
    body = _body(resp)
    assert body["data"]["items"] == [1, 2]
    assert body["data"]["pagination"] == {
        "page": 1,
        "page_size": 2,
        "total": 5,
        "total_pages": 3,
    }


def test_paged_total_zero():
    body = _body(R.paged([], page=1, page_size=20, total=0))
    assert body["data"]["pagination"]["total_pages"] == 0


# ---------------------------------------------------------------------------
# 回归：出口兜底序列化
#
# 起因：`GET /content/lessons` 直接返回 Mongo 完整文档（含 created_at），
# 而 JSONResponse 内部是 json.dumps —— 一个 datetime 就让整个接口 500。
# 下面几条把「信封必须能吃下 BSON 带出来的类型」钉住。
# ---------------------------------------------------------------------------


def test_ok_serializes_mongo_types_instead_of_500():
    oid = ObjectId("6ac8bae077ba38e3d0c5c258")
    resp = R.ok(
        {
            "created_at": datetime(2026, 10, 9, 1, 2, 3, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 10, 9, 1, 2, 3),  # naive 按 UTC 处理
            "birth_date": date(2019, 5, 6),
            "_id": oid,
            "nested": {"ids": [ObjectId("6ac8bae077ba38e3d0c5c259")]},
        }
    )
    body = _body(resp)
    assert resp.status_code == 200
    assert body["data"]["created_at"] == "2026-10-09T01:02:03Z"
    assert body["data"]["updated_at"] == "2026-10-09T01:02:03Z"
    assert body["data"]["birth_date"] == "2019-05-06"
    assert body["data"]["_id"] == "6ac8bae077ba38e3d0c5c258"
    assert body["data"]["nested"]["ids"] == ["6ac8bae077ba38e3d0c5c259"]


def test_fail_envelope_also_serializes_errors():
    resp = R.fail(
        40001,
        "参数校验失败",
        errors=[{"field": "created_at", "value": datetime(2026, 1, 2, 3, 4, 5)}],
    )
    assert _body(resp)["errors"][0]["value"] == "2026-01-02T03:04:05Z"


def test_paged_items_serialized():
    body = _body(R.paged([{"_id": ObjectId("6ac8bae077ba38e3d0c5c25a")}], page=1, page_size=1, total=1))
    assert body["data"]["items"][0]["_id"] == "6ac8bae077ba38e3d0c5c25a"
