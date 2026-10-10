"""错误码与业务异常（04-1 §1.4）。错误码必须与前端 error-codes.ts 完全一致。"""

from __future__ import annotations

import pytest

from app.core import errors as E


def test_error_code_values_match_frontend():
    # 与 packages/core/src/constants/error-codes.ts 逐字对齐
    assert E.PARAM_INVALID == 40001
    assert E.TOKEN_EXPIRED == 40101
    assert E.TOKEN_INVALID == 40102
    assert E.INVITE_INVALID == 40103
    assert E.PASSCODE_INVALID == 40104
    assert E.ACCOUNT_LOCKED == 40105
    assert E.RECOVERY_INVALID == 40106
    assert E.FORBIDDEN == 40301
    assert E.FEATURE_DISABLED == 40302
    assert E.CHARACTER_NOT_FOUND == 40401
    assert E.POEM_NOT_FOUND == 40402
    assert E.CHILD_NOT_FOUND == 40403
    assert E.CONTENT_NOT_FOUND == 40404
    assert E.CONTENT_EXISTS == 40902
    assert E.RATE_LIMITED == 42901
    assert E.INTERNAL == 50001
    assert E.UPSTREAM_UNAVAILABLE == 50002


@pytest.mark.parametrize(
    ("code", "status"),
    [
        (40001, 400),
        (40101, 401),
        (40103, 401),
        (40105, 401),
        (40301, 403),
        (40302, 403),
        (40401, 404),
        (40902, 409),
        (42901, 429),
        (50001, 500),
        (50002, 502),
    ],
)
def test_http_status_mapping(code, status):
    assert E.http_status_for(code) == status


def test_unknown_code_defaults_to_400():
    assert E.http_status_for(40099) == 400


def test_biz_exception_defaults():
    exc = E.BizException(E.INVITE_INVALID, "邀请码或口令不正确")
    assert exc.code == 40103
    assert exc.http_status == 401
    assert exc.errors is None


def test_biz_exception_with_field_errors():
    exc = E.BizException(E.PARAM_INVALID, "参数校验失败", errors=[{"field": "a", "reason": "b"}])
    assert exc.http_status == 400
    assert exc.errors[0]["field"] == "a"


def test_unified_message_constant():
    assert E.UNIFIED_AUTH_MESSAGE == "邀请码或口令不正确"
