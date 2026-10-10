"""隐私红线：统计禁止个人标识、儿童档案拒收敏感字段、口令强度。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core import errors as E
from app.models.child import ChildCreate
from app.models.stats import StatsEventItem
from app.controllers.auth_controller import validate_passcode


# --------------------------- 统计：禁止个人标识 ---------------------------
def test_stats_event_rejects_account_id():
    with pytest.raises(ValidationError):
        StatsEventItem(
            event_name="lesson_complete",
            bucket_date="2026-10-08",
            account_id="acc_1",  # type: ignore[call-arg]
        )


def test_stats_event_rejects_child_id_and_client_id():
    with pytest.raises(ValidationError):
        StatsEventItem(event_name="x", bucket_date="2026-10-08", child_id="c1")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        StatsEventItem(event_name="x", bucket_date="2026-10-08", client_id="dev")  # type: ignore[call-arg]


def test_stats_event_valid():
    e = StatsEventItem(event_name="lesson_complete", content_ref="u-g1-01", count=3, bucket_date="2026-10-08")
    assert e.count == 3


# --------------------------- 儿童档案：拒收敏感字段 ---------------------------
@pytest.mark.parametrize("field", ["real_name", "photo", "birthday", "school", "phone"])
def test_child_create_rejects_sensitive_fields(field):
    with pytest.raises(ValidationError):
        ChildCreate(nickname="小明", grade=2, **{field: "x"})


def test_child_create_ok_minimal():
    child = ChildCreate(nickname="小明", grade=2)
    assert child.avatar_key == "rabbit"
    assert child.daily_time_limit_min == 20


# --------------------------- 口令强度 ---------------------------
def test_passcode_too_short():
    with pytest.raises(E.BizException) as exc:
        validate_passcode("1234")
    assert exc.value.code == E.PARAM_INVALID


@pytest.mark.parametrize("weak", ["123456", "654321", "111111"])
def test_passcode_rejects_weak_digits(weak):
    with pytest.raises(E.BizException):
        validate_passcode(weak)


def test_passcode_accepts_mixed():
    validate_passcode("abc12345")
    validate_passcode("135792")  # 非连续
