"""错误码与业务异常 —— 与 `packages/core/src/constants/error-codes.ts` 逐字对齐。

纪律（04-1 §1.4）：错误码不复用，同一码不得改变含义；不做自造码。
HTTP 状态码保持语义正确，由 ERR_CODE_HTTP 映射。
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# 错误码常量（唯一定义源是前端 error-codes.ts，此处镜像；禁止各写一份语义）
# ---------------------------------------------------------------------------
OK = 0

PARAM_INVALID = 40001

TOKEN_EXPIRED = 40101
TOKEN_INVALID = 40102
INVITE_INVALID = 40103  # 邀请码无效/已用尽/已吊销/已过期（统一错误信息，防枚举）
PASSCODE_INVALID = 40104
ACCOUNT_LOCKED = 40105
RECOVERY_INVALID = 40106
ACCOUNT_INVALID = 40107  # 账号（用户名/手机号）不存在或密码错误（统一错误信息，防枚举）

FORBIDDEN = 40301
FEATURE_DISABLED = 40302

PARTIAL_CONTENT = 40601  # 批量导入部分失败

CHARACTER_NOT_FOUND = 40401
POEM_NOT_FOUND = 40402
CHILD_NOT_FOUND = 40403
CONTENT_NOT_FOUND = 40404
ASSET_NOT_FOUND = 40405

CONTENT_EXISTS = 40902
CONTENT_IN_USE = 40903  # 内容仍被关卡 / 单元 / 短文引用，物理删除被拒绝（可 force 强制）

ASSET_TOO_LARGE = 41301
UNSUPPORTED_MEDIA_TYPE = 41501

RATE_LIMITED = 42901

INTERNAL = 50001
UPSTREAM_UNAVAILABLE = 50002
STORAGE_UNAVAILABLE = 50003


# 码段 → HTTP 状态码。500xx 之外的未知码一律按请求错误处理，避免把 4xx 误报成 5xx。
ERR_CODE_HTTP: dict[int, int] = {
    PARAM_INVALID: 400,
    TOKEN_EXPIRED: 401,
    TOKEN_INVALID: 401,
    INVITE_INVALID: 401,
    PASSCODE_INVALID: 401,
    ACCOUNT_LOCKED: 401,
    RECOVERY_INVALID: 401,
    ACCOUNT_INVALID: 401,
    FORBIDDEN: 403,
    FEATURE_DISABLED: 403,
    PARTIAL_CONTENT: 206,
    CHARACTER_NOT_FOUND: 404,
    POEM_NOT_FOUND: 404,
    CHILD_NOT_FOUND: 404,
    CONTENT_NOT_FOUND: 404,
    ASSET_NOT_FOUND: 404,
    CONTENT_EXISTS: 409,
    CONTENT_IN_USE: 409,
    ASSET_TOO_LARGE: 413,
    UNSUPPORTED_MEDIA_TYPE: 415,
    RATE_LIMITED: 429,
    INTERNAL: 500,
    UPSTREAM_UNAVAILABLE: 502,
    STORAGE_UNAVAILABLE: 500,
}

# 统一错误信息（防枚举）：邀请码无效 / 已用尽 / 密码错误一律用它。
UNIFIED_AUTH_MESSAGE = "邀请码或密码不正确"
# 账号登录统一文案（防枚举）：用户名/手机号不存在 与 密码错误 一律用它。
UNIFIED_ACCOUNT_MESSAGE = "账号或密码不正确"


def http_status_for(code: int) -> int:
    return ERR_CODE_HTTP.get(code, 400)


class BizException(Exception):
    """业务异常：由 service 层抛出，全局 handler 统一转换为响应信封。"""

    def __init__(
        self,
        code: int,
        message: str,
        errors: list[dict[str, Any]] | None = None,
        http_status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.errors = errors
        self.http_status = http_status or http_status_for(code)
