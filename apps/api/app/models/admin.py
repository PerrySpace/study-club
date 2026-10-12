"""管理后台请求模型（04-1 §九 / 05-1）。

单管理员后台，不做 RBAC；写操作统一记入 audit_logs。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class InviteBatchRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    count: int = Field(default=1, ge=1, le=100)
    # ⚠️ 只允许 1。邀请码是**账号的登录标识**（02-5 §2.2 / 03-1 §3.1）：
    #    accounts.invite_code_hash 上有唯一索引，一个码只能激活一个账号，
    #    家庭内部共用「同一码 + 同一密码」进同一个档案空间，需要隔离就再发一个码。
    #    早先这里允许到 1000，后台于是摆出一个「可用次数」控件，但填 3 只会成功 1 个、
    #    第二次注册直接撞唯一索引。现在收成 le=1，让契约本身就说实话（越界返回 422）。
    max_uses: int = Field(default=1, ge=1, le=1)
    channel: str = Field(default="self", pattern="^(self|friend|community|test)$")
    expires_in_days: int | None = Field(default=None, ge=1, le=3650)
    batch_id: str | None = Field(default=None, max_length=64)
    note: str | None = Field(default=None, max_length=200)


class CharacterWrite(BaseModel):
    """汉字写入：以内容包字段为准，故 `extra="allow"` 让后台字段可原样导出回 JSON。

    `char` 在创建时必填（由 service 校验），更新时可选——便于 PATCH 局部修改。
    """

    model_config = ConfigDict(extra="allow")

    char: str | None = Field(default=None, max_length=1)
    status: str | None = None
    version: int | None = Field(default=None, ge=1)


class UserStatusRequest(BaseModel):
    """后台启用 / 禁用账号（02-5 §四：禁用后不可登录）。"""

    model_config = ConfigDict(extra="ignore")

    status: str = Field(pattern="^(active|disabled)$")


class UserProfileUpdate(BaseModel):
    """后台编辑账号资料 —— **只能改展示性字段**。

    ⛔ 不提供 `username` / `phone` / `passcode_hash` / `role`：
      - 用户名与手机号是**登录标识**，各自带唯一索引，改动等于换账号，
        且历史登录记录会对不上；
      - 密码哈希必须经 Argon2 重新计算，不能明文直传；
      - 单管理员后台没有多角色体系（05-1 §1.3），开放 `role` 等于凭空造 RBAC。

    越权字段被 `extra="forbid"` 直接挡在门外，而不是静默丢弃 —— 后者会让操作者
    以为改成功了。
    """

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, max_length=24)
    avatar_key: str | None = Field(default=None, max_length=64)
    access_tier: str | None = Field(default=None, pattern="^(open|invite_only)$")


class UserBulkStatusRequest(BaseModel):
    """批量启用 / 禁用。"""

    model_config = ConfigDict(extra="forbid")

    account_ids: list[str] = Field(min_length=1, max_length=100)
    status: str = Field(pattern="^(active|disabled)$")


class SiteConfigUpdate(BaseModel):
    """站点运行配置更新（配置中心）。全部可选，只改传入的字段。

    `gameplay` 用 `dict` 透传而不是逐字段声明：它的字段会随玩法迭代增减，
    逐字段声明等于每加一个玩法开关都要改三处（模型 / 控制器 / 前端类型）。
    取值合法性由 `core/runtime_config._normalize_gameplay` 统一收敛
    （越界 clamp、未知题型丢弃、空题型回落默认全集）—— 单一收口点，不散落校验。

    ⚠️ **这里的字段清单必须与 `runtime_config.update_config` 的 `allowed` 白名单对齐**。
    本模型是 `extra="ignore"`（刻意的：后台前端会把自己读到的整个配置对象回传，
    逐字段 forbid 会让任何新增前端字段都变成 422），代价是**漏声明 = 静默丢弃**：
    请求体带着该字段进来，Pydantic 直接扔掉，控制器 `model_dump(exclude_none=True)`
    也看不到它 —— 表现是「保存成功、页面刷新后一字未变」，且日志里毫无线索。

    这正是 `grades` 踩过的坑：`runtime_config` 支持、后台在传、客户端在读，
    唯独这里没声明，于是运营加完年级永远保存不上。新增配置项时，
    除了本模型还要同步 `runtime_config.allowed` 与前端 `SiteConfig` 类型。
    """

    model_config = ConfigDict(extra="ignore")

    require_invite: bool | None = None
    registration_open: bool | None = None
    announcement: str | None = Field(default=None, max_length=500)
    defaults: dict[str, int] | None = None
    # 年级表：**整表替换**（不是合并），因为「删掉一个年级」在合并语义下删不掉。
    # 具体校验在 `_normalize_grades_and_validate` —— 非法即报错，不静默回落默认表。
    grades: list[dict[str, Any]] | None = None
    gameplay: dict[str, Any] | None = None
