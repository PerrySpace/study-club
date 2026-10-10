"""匿名统计请求模型（04-1 §九 / 03-2 §7.5）。

⚠️ 隐私红线：`stats_events` **禁止**出现 account_id / child_id / client_id 等任何个人标识。
这里用 `extra="forbid"` 把红线写进类型——客户端若误传这些字段，直接 40001 而不是静默落库。
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StatsEventItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_name: str = Field(min_length=1, max_length=64)
    content_ref: str | None = Field(default=None, max_length=128)
    client: str = Field(default="web", max_length=16)
    device_form: str = Field(default="desktop", max_length=16)
    client_version: str = Field(default="0.0.0", max_length=32)
    count: int = Field(default=1, ge=1)
    bucket_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


class StatsEventsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    events: list[StatsEventItem] = Field(default_factory=list, max_length=200)
