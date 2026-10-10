"""内容模块请求模型（04-1 §四）。

列表接口的筛选条件集中为模型便于复用与校验；返回体直接是内容包字段（snake_case），
不在此重复定义响应模型——内容的唯一字段定义源是 03-2 与 content/*.json。

写入模型统一 `extra="allow"`：后台要能把字段**原样导出回内容 JSON**，
因此不在服务端把字段冻死；必填字段由注册表（repositories/content_registry.py）声明并在控制器校验。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..core.runtime_config import GRADE_MAX


# ---------------------------------------------------------------------------
# 查询
# ---------------------------------------------------------------------------
class CharacterListQuery(BaseModel):
    model_config = ConfigDict(extra="ignore")

    grade: int | None = Field(default=None, ge=0, le=GRADE_MAX)
    level: str | None = None
    tags: str | None = None  # 逗号分隔
    unit_id: str | None = None
    status: str | None = Field(default=None, description="仅后台可用，默认 published")
    keyword: str | None = None

    @property
    def tag_list(self) -> list[str]:
        return [t.strip() for t in (self.tags or "").split(",") if t.strip()]


class PoemListQuery(BaseModel):
    model_config = ConfigDict(extra="ignore")

    grade: int | None = Field(default=None, ge=0, le=GRADE_MAX)
    theme_tags: str | None = None  # 逗号分隔
    source: str | None = None
    keyword: str | None = None

    @property
    def theme_tag_list(self) -> list[str]:
        return [t.strip() for t in (self.theme_tags or "").split(",") if t.strip()]


class ContentListQuery(BaseModel):
    """单元 / 关卡 / 故事 / 徽章的通用后台筛选。"""

    model_config = ConfigDict(extra="ignore")

    status: str | None = None
    keyword: str | None = None
    grade: int | None = Field(default=None, ge=0, le=GRADE_MAX)
    level: str | None = None


# ---------------------------------------------------------------------------
# 写入（后台 CRUD）
# ---------------------------------------------------------------------------
class CharacterWrite(BaseModel):
    """汉字写入：以内容包字段为准，故 `extra="allow"`。

    `char` 在创建时必填（由 controller 校验），更新时可选——便于 PATCH 局部修改。
    """

    model_config = ConfigDict(extra="allow")

    char: str | None = Field(default=None, max_length=1)
    status: str | None = None
    version: int | None = Field(default=None, ge=1)


class PoemWrite(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: str | None = Field(default=None, max_length=64)
    author: str | None = Field(default=None, max_length=32)
    dynasty: str | None = Field(default=None, max_length=16)
    status: str | None = None


class UnitWrite(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: str | None = Field(default=None, max_length=64)
    unit_code: str | None = Field(default=None, max_length=32)
    status: str | None = None


class LessonWrite(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: str | None = Field(default=None, max_length=64)
    level: str | None = None
    status: str | None = None


class StoryWrite(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: str | None = Field(default=None, max_length=64)
    text: str | None = None
    status: str | None = None


class BadgeWrite(BaseModel):
    model_config = ConfigDict(extra="allow")

    code: str | None = Field(default=None, max_length=48)
    title: str | None = Field(default=None, max_length=48)
    status: str | None = None


# ---------------------------------------------------------------------------
# 内容导入
# ---------------------------------------------------------------------------
class ContentImportRequest(BaseModel):
    """从仓库 `content/*.json` 或上传的 JSON 导入内容（幂等 upsert）。"""

    model_config = ConfigDict(extra="ignore")

    # repo = 读服务端仓库内的 content/（容器里已挂载）；
    # upload = 读 payload 里按集合分组的文档数组。
    source: str = Field(default="repo", pattern="^(repo|upload)$")
    # 空表示全部集合；键为集合名（characters/poems/curriculum_units/lessons/stories/badges）
    collections: list[str] = Field(default_factory=list)
    payload: dict[str, Any] | None = None
    dry_run: bool = Field(default=False, description="只统计不落库")
    publish: bool = Field(default=False, description="导入时把 status 置为 published")
