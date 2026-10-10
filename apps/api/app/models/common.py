"""通用请求模型 —— 分页参数（04-1 §1.3：page 默认 1，page_size 默认 20，最大 100）。"""

from __future__ import annotations

from fastapi import Query
from pydantic import BaseModel, Field


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @property
    def skip(self) -> int:
        return (self.page - 1) * self.page_size


def page_params(
    page: int = Query(default=1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数，最大 100"),
) -> PageParams:
    """作为 FastAPI 依赖使用：`params: PageParams = Depends(page_params)`。"""
    return PageParams(page=page, page_size=page_size)
