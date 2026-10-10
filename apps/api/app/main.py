"""应用装配（06-1 §3.1）。

职责：创建 app、挂载 `/api/v1`、CORS、统一异常处理、请求 id、启动时幂等建索引。
⛔ 掩藏能力的路由不在此导入、不注册（账号/短信/微信/支付/推送/RBAC）。
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from .core import errors as E
from .core import runtime_config
from .core.config import settings
from .core.response import envelope, set_request_id
from .db.mongo import close_client, get_database, init_indexes
from .repositories.ops import SettingsRepository
from .views import (
    admin,
    assets,
    auth,
    children,
    config as config_view,
    content,
    feedbacks,
    health,
    learning,
    reports,
    stats,
    sync,
)

# HTTP 状态码 → 业务错误码（仅用于兜底，业务错误码由 BizException 显式给出）
_STATUS_TO_CODE = {
    400: E.PARAM_INVALID,
    401: E.TOKEN_INVALID,
    403: E.FORBIDDEN,
    404: E.CONTENT_NOT_FOUND,
    405: E.PARAM_INVALID,
    409: E.CONTENT_EXISTS,
    429: E.RATE_LIMITED,
    500: E.INTERNAL,
    502: E.UPSTREAM_UNAVAILABLE,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动：幂等创建索引（集合不存在也能创建）
    try:
        db = get_database()
        await init_indexes(db)
        # 运行配置：DB 有值读 DB，没有则写默认值（需求：配置启动检查 DB）
        await runtime_config.load_config(SettingsRepository(db))
    except Exception as exc:  # noqa: BLE001 - 数据库暂不可用不应阻断进程（前端可降级）
        print(f"[startup] 索引/配置初始化失败（MongoDB 可能未就绪）：{exc}")
    yield
    await close_client()


def create_app() -> FastAPI:
    app = FastAPI(
        title="study-club API",
        version="1.0.0",
        description="小学课内识字 + 古诗文的云端后台（本地优先，非必需依赖）。",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-Id"],
    )

    @app.middleware("http")
    async def _request_id_middleware(request: Request, call_next):
        rid = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        set_request_id(rid)
        response = await call_next(request)
        response.headers["X-Request-Id"] = rid
        return response

    # ---------------- 异常处理 ----------------
    @app.exception_handler(E.BizException)
    async def _biz_handler(request: Request, exc: E.BizException):
        return envelope(
            code=exc.code,
            message=exc.message,
            errors=exc.errors,
            http_status=exc.http_status,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError):
        errors = []
        for err in exc.errors():
            loc = [str(x) for x in err.get("loc", []) if x not in ("body", "query", "path")]
            errors.append({"field": ".".join(loc) or "body", "reason": err.get("msg", "校验失败")})
        return envelope(code=E.PARAM_INVALID, message="参数校验失败", errors=errors, http_status=400)

    @app.exception_handler(StarletteHTTPException)
    async def _http_handler(request: Request, exc: StarletteHTTPException):
        code = _STATUS_TO_CODE.get(exc.status_code, E.INTERNAL if exc.status_code >= 500 else E.PARAM_INVALID)
        return envelope(code=code, message=str(exc.detail), http_status=exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled_handler(request: Request, exc: Exception):
        # 不把内部堆栈泄漏给客户端
        print(f"[error] {request.method} {request.url.path}: {exc!r}")
        return envelope(code=E.INTERNAL, message="服务内部错误", http_status=500)

    # ---------------- 路由（统一挂载 /api/v1） ----------------
    prefix = settings.api_prefix
    for module in (
        health,
        # 站点公开配置（启动即读，无需登录）
        config_view,
        # 素材文件下发：必须早于 content（同样是 GET，且 /assets/{id} 是扁平路径）
        assets,
        content,
        auth,
        children,
        learning,
        reports,
        stats,
        feedbacks,
        sync,
        admin,
    ):
        app.include_router(module.router, prefix=prefix)

    return app


app = create_app()
