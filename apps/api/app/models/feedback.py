"""反馈请求模型（04-1 §十 / 03-2 §7.6）。

允许匿名提交（account_id 可为 null）；联系方式自愿，不强制。
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class FeedbackCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    category: str = Field(default="other", pattern="^(bug|content_error|suggestion|other)$")
    content_ref: str | None = Field(default=None, max_length=128)
    message: str = Field(min_length=1, max_length=2000)
    contact: str | None = Field(default=None, max_length=128)
    client: str = Field(default="web", max_length=16)
