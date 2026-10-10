"""统一响应信封 —— 成功 `{code:0,message,data,request_id}`，失败 `{code,message,errors?,request_id}`（04-1 §1.2）。

request_id 由中间件写入 contextvar，业务代码无需感知；即使异常发生在 handler 之外也能带上同一 id。

⚠️ 出口处统一做一次 `serialize()` 兜底。理由（真实踩过）：
`JSONResponse` 内部就是 `json.dumps`，遇到 `datetime` / `ObjectId` 直接抛 TypeError ——
控制器里少写一句序列化，表现却是整个接口 500（`GET /content/lessons` 就是这么挂的）。
在每个端点上各补一句的话，漏一个就再炸一次；这里是所有响应的唯一出口，兜一次就够。
代价是多一趟递归遍历，对一个内容量级在千条内的接口可以忽略。
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from typing import Any

from fastapi.responses import JSONResponse

from .serializers import serialize

# 当前请求 id（中间件设置；未设置时回退为新生成，保证任何响应都有 id）
_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)


def set_request_id(request_id: str) -> None:
    _request_id_ctx.set(request_id)


def get_request_id() -> str:
    return _request_id_ctx.get() or str(uuid.uuid4())


def envelope(
    data: Any = None,
    *,
    code: int = 0,
    message: str = "ok",
    errors: list[dict[str, Any]] | None = None,
    http_status: int = 200,
) -> JSONResponse:
    """构造 JSONResponse。失败响应不返回 data，只返回 errors（对齐 04-1 §1.2 失败示例）。"""
    body: dict[str, Any] = {
        "code": code,
        "message": message,
        "request_id": get_request_id(),
    }
    if code == 0:
        body["data"] = data
    elif errors:
        body["errors"] = errors
    return JSONResponse(status_code=http_status, content=serialize(body))


def ok(data: Any = None, *, message: str = "ok", http_status: int = 200) -> JSONResponse:
    return envelope(data=data, code=0, message=message, http_status=http_status)


def fail(
    code: int,
    message: str,
    *,
    errors: list[dict[str, Any]] | None = None,
    http_status: int | None = None,
) -> JSONResponse:
    from .errors import http_status_for

    return envelope(
        code=code,
        message=message,
        errors=errors,
        http_status=http_status if http_status is not None else http_status_for(code),
    )


def paged(
    items: list[Any],
    *,
    page: int,
    page_size: int,
    total: int,
    http_status: int = 200,
) -> JSONResponse:
    """分页响应（04-1 §1.3）。total_pages 向上取整，total=0 时为 0。"""
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    return ok(
        {
            "items": items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": total_pages,
            },
        },
        http_status=http_status,
    )
