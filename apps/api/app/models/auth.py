"""认证与身份请求模型（04-1 §二 / 02-5 §三）。

密码字段同时接受 `pin`（文档用词）与 `passcode`（前端 client.ts 用词）——
契约要求「字段只增不改不删」，用别名兼容比强制一端改名更稳妥。
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ClientInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")

    client_id: str | None = None
    platform: str | None = None
    app_version: str | None = None


class InviteVerifyRequest(BaseModel):
    invite_code: str = Field(min_length=4, max_length=64)


class _PasscodeMixin(BaseModel):
    """密码字段兼容：pin 与 passcode 二选一。"""

    pin: str | None = None
    passcode: str | None = None

    @model_validator(mode="after")
    def _resolve_passcode(self) -> "_PasscodeMixin":
        if self.pin is None:
            self.pin = self.passcode  # type: ignore[attr-defined]
        elif self.passcode is None:
            self.passcode = self.pin  # type: ignore[attr-defined]
        return self

    @property
    def resolved_passcode(self) -> str | None:
        return self.pin or self.passcode


class InviteRegisterRequest(_PasscodeMixin):
    """注册请求。

    身份标识改为「用户名 / 手机号二选一」：两者**至少填一个**，
    格式与唯一性由 controller 校验（见 auth_controller）。
    邀请码退为**可选**字段，是否必填由 `settings.require_invite` 开关决定。
    """

    model_config = ConfigDict(extra="ignore")

    username: str | None = Field(default=None, max_length=32)
    phone: str | None = Field(default=None, max_length=20)
    invite_code: str | None = Field(default=None, max_length=64)
    display_name: str | None = Field(default=None, max_length=20)
    avatar_key: str | None = Field(default=None, max_length=32)
    client: ClientInfo | None = None
    e2e_enabled: bool = True


class AccountLoginRequest(_PasscodeMixin):
    """统一账号登录：`identifier` 可填**用户名或手机号**。

    兼容旧字段：`account` 与 `invite_code` 也接受（后者用于保留邀请码登录通道）。
    解析优先级：identifier → account → invite_code。
    """

    model_config = ConfigDict(extra="ignore")

    identifier: str | None = Field(default=None, max_length=64)
    account: str | None = Field(default=None, max_length=64)
    invite_code: str | None = Field(default=None, max_length=64)
    client: ClientInfo | None = None

    @property
    def resolved_identifier(self) -> str | None:
        return self.identifier or self.account or self.invite_code


class InviteLoginRequest(_PasscodeMixin):
    """旧版邀请码登录（保留，向后兼容）。"""

    model_config = ConfigDict(extra="ignore")

    invite_code: str = Field(min_length=4, max_length=64)
    client: ClientInfo | None = None


class RecoveryResetRequest(_PasscodeMixin):
    model_config = ConfigDict(extra="ignore")

    recovery_code: str = Field(min_length=8, max_length=128)
    invite_code: str | None = Field(default=None, max_length=64)


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    refresh_token: str = Field(min_length=8)


class LogoutRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    refresh_token: str | None = None


class AdminLoginRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    password: str = Field(min_length=1)
