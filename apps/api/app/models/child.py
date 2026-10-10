"""儿童档案请求模型（04-1 §三 / 03-2 §3.4）。

隐私约束是架构级的（不是可选项）：接口**不接受**真实姓名、照片、精确生日、学校名。
因此这里用 `extra="forbid"`——传入任何未声明字段（含上述敏感字段）直接 40001。
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ..core.runtime_config import GRADE_MAX


class ChildCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nickname: str = Field(min_length=1, max_length=20)
    avatar_key: str = Field(default="rabbit", max_length=32)
    grade: int = Field(ge=0, le=GRADE_MAX)
    birth_year: int | None = Field(default=None, ge=1990, le=2100)
    unit_preference: str = Field(default="self", pattern="^(self|custom)$")
    daily_new_char_target: int = Field(default=8, ge=3, le=30)
    daily_review_target: int = Field(default=12, ge=0, le=50)
    daily_time_limit_min: int = Field(default=20, ge=5, le=60)


class ChildUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nickname: str | None = Field(default=None, min_length=1, max_length=20)
    avatar_key: str | None = Field(default=None, max_length=32)
    grade: int | None = Field(default=None, ge=0, le=GRADE_MAX)
    birth_year: int | None = Field(default=None, ge=1990, le=2100)
    unit_preference: str | None = Field(default=None, pattern="^(self|custom)$")
    daily_new_char_target: int | None = Field(default=None, ge=3, le=30)
    daily_review_target: int | None = Field(default=None, ge=0, le=50)
    daily_time_limit_min: int | None = Field(default=None, ge=5, le=60)
