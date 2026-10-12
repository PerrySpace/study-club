"""单管理员后台路由（04-1 §九）。

不做 RBAC：只有「是/不是管理员」。写操作统一记入 audit_logs。
⛔ 本期不做（不注册）：/admin/roles（多角色 RBAC）。单管理员足够，与企业主体无关。
✅ /admin/users 现提供**账号级**用户列表（用户名/手机号掩码/状态），不含学习明细。

本模块把后台能力收敛为**数据驱动的通用接口**：
`/admin/content/{collection}` 一套覆盖汉字·古诗·单元·关卡·故事·徽章，
集合差异由 `GET /admin/registry` 下发的 schema 描述 —— 后台前端据此渲染表格与表单，
新增一类内容不需要动这里的代码。
"""

from __future__ import annotations

from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile

from ..core.client_headers import client_ip
from ..core.config import settings
from ..core.deps import get_current_admin, get_repos
from ..core.errors import FEATURE_DISABLED, FORBIDDEN, PARAM_INVALID, BizException
from ..core.response import ok, paged
from ..core.security import create_access_token, verify_passcode
from ..core import runtime_config
from ..models.admin import (
    InviteBatchRequest,
    SiteConfigUpdate,
    UserBulkStatusRequest,
    UserProfileUpdate,
    UserStatusRequest,
)
from ..models.asset import AssetRefBind
from ..models.auth import AdminLoginRequest
from ..models.common import PageParams, page_params
from ..models.content import ContentImportRequest
from ..repositories import Repositories
from ..controllers import admin_controller, asset_controller, content_import_controller

router = APIRouter(prefix="/admin", tags=["admin"])


def _parse_day(value: str | None, *, end_of_day: bool) -> datetime | None:
    """把 `2026-01-31` 这样的日期串解析成 UTC 边界时间。

    列表筛选用的是「注册时间」这个**日期**，用户选 1 月 31 日时显然
    要包含当天 23:59  registrations —— 所以上界要补到当天末尾，
    否则选同一天会返回空列表（看起来像功能坏了）。
    """
    if not value:
        return None
    try:
        day = date.fromisoformat(value[:10])
    except ValueError as exc:
        raise BizException(PARAM_INVALID, f"日期格式不正确：{value}（应为 YYYY-MM-DD）") from exc
    moment = datetime.combine(day, time.max if end_of_day else time.min, tzinfo=timezone.utc)
    return moment


@router.post("/login")
async def admin_login(body: AdminLoginRequest):
    """用 ADMIN_PASSWORD_HASH 换取管理员 JWT（密码哈希未配置时能力整体不可用）。"""
    if not settings.admin_password_hash:
        raise BizException(FEATURE_DISABLED, "管理员后台未配置")
    if not verify_passcode(body.password, settings.admin_password_hash):
        raise BizException(FORBIDDEN, "管理员密码不正确")
    token, expires_in = create_access_token("admin", role="admin")
    return ok({"access_token": token, "expires_in": expires_in, "token_type": "Bearer", "role": "admin"})


# ----------------------------- 概览 / 元信息 -----------------------------
@router.get("/overview")
async def overview(
    admin: dict = Depends(get_current_admin),
    repos: Repositories = Depends(get_repos),
):
    """后台首页看板：内容完整度 + 素材体量 + 邀请码体量（只读聚合，不含用户内容明细）。"""
    return ok(await admin_controller.overview(repos))


@router.get("/registry")
async def registry(admin: dict = Depends(get_current_admin)):
    """内容类型注册表：后台据此渲染「内容管理」的表格列与编辑表单。"""
    return ok({"items": admin_controller.registry_descriptor()})


@router.get("/audit-logs")
async def audit_logs(
    action: str | None = None,
    collection: str | None = None,
    page: PageParams = Depends(page_params),
    admin: dict = Depends(get_current_admin),
    repos: Repositories = Depends(get_repos),
):
    items, total = await admin_controller.list_audit_logs(
        repos, skip=page.skip, limit=page.page_size, action=action, collection=collection
    )
    return paged(items, page=page.page, page_size=page.page_size, total=total)


# ----------------------------- 邀请码 -----------------------------
@router.post("/invites/batch")
async def create_invites(
    body: InviteBatchRequest,
    request: Request,
    admin: dict = Depends(get_current_admin),
    repos: Repositories = Depends(get_repos),
):
    return ok(
        await admin_controller.create_invites(repos, body, admin, client_ip(request)), http_status=201
    )


@router.get("/invites")
async def list_invites(
    batch_id: str | None = None,
    channel: str | None = None,
    page: PageParams = Depends(page_params),
    admin: dict = Depends(get_current_admin),
    repos: Repositories = Depends(get_repos),
):
    items, total = await admin_controller.list_invites(
        repos, page.skip, page.page_size, batch_id, channel
    )
    return paged(items, page=page.page, page_size=page.page_size, total=total)


@router.post("/invites/{invite_id}/revoke")
async def revoke_invite(
    invite_id: str,
    request: Request,
    admin: dict = Depends(get_current_admin),
    repos: Repositories = Depends(get_repos),
):
    return ok(await admin_controller.revoke_invite(repos, invite_id, admin, client_ip(request)))


# ----------------------------- 站点配置（配置中心） -----------------------------
@router.get("/config")
async def get_site_config(
    admin: dict = Depends(get_current_admin),
):
    """读取当前站点运行配置（邀请码开关 / 是否开放注册 / 公告 / 默认学习目标）。"""
    return ok(runtime_config.get_config())


@router.put("/config")
async def update_site_config(
    body: SiteConfigUpdate,
    request: Request,
    admin: dict = Depends(get_current_admin),
    repos: Repositories = Depends(get_repos),
):
    """热更新站点配置：写 DB 并刷新进程缓存，**不需要重启**。"""
    patch = body.model_dump(exclude_none=True)
    try:
        cfg = await runtime_config.update_config(repos.settings, patch)
    except ValueError as exc:
        # 校验类失败（如 grades 含非法项）走 40001 而不是 500：这是**请求内容**的问题，
        # 运营能改；报 500 会让后台只看到一句「服务内部错误」，不知道错在哪个字段。
        # 细节由 `_normalize_grades_and_validate` 给出，直接透传给前端展示。
        raise BizException(PARAM_INVALID, str(exc)) from exc
    await admin_controller.log_audit(
        repos,
        actor=admin,
        action="config.update",
        target_collection="app_settings",
        target_id=repos.settings.DOC_ID,
        diff={"fields": sorted(patch.keys())},
        ip=client_ip(request),
    )
    return ok(cfg)


# ----------------------------- 用户管理 -----------------------------
@router.get("/users")
async def list_users(
    keyword: str | None = None,
    status: str | None = None,
    role: str | None = None,
    has_children: bool | None = None,
    registered_from: str | None = Query(
        default=None, description="注册时间下界（ISO 日期，如 2026-01-01）"
    ),
    registered_to: str | None = Query(
        default=None, description="注册时间上界（ISO 日期，如 2026-12-31，含当天）"
    ),
    page: PageParams = Depends(page_params),
    admin: dict = Depends(get_current_admin),
    repos: Repositories = Depends(get_repos),
):
    """账号列表（用户名 / 手机号掩码 / 状态 / 注册与登录时间）。不含学习明细。"""
    items, total = await admin_controller.list_users(
        repos,
        skip=page.skip,
        limit=page.page_size,
        keyword=keyword,
        status=status,
        role=role,
        has_children=has_children,
        created_from=_parse_day(registered_from, end_of_day=False),
        created_to=_parse_day(registered_to, end_of_day=True),
    )
    return paged(items, page=page.page, page_size=page.page_size, total=total)


@router.get("/users/stats")
async def user_stats(
    admin: dict = Depends(get_current_admin),
    repos: Repositories = Depends(get_repos),
):
    return ok(await admin_controller.user_stats(repos))


@router.get("/users/{account_id}")
async def user_detail(
    account_id: str,
    admin: dict = Depends(get_current_admin),
    repos: Repositories = Depends(get_repos),
):
    return ok(await admin_controller.get_user(repos, account_id))


@router.get("/users/{account_id}/report")
async def user_report(
    account_id: str,
    days: int = Query(default=7, ge=1, le=90),
    admin: dict = Depends(get_current_admin),
    repos: Repositories = Depends(get_repos),
):
    """账号级学习报告：已认 / 掌握 / 复习中 / 正确率 / 连续天数 / 最近趋势。

    刻意把「已认」与「掌握」分开列 —— 家长要能分辨「见过一面」和「已经稳住」。
    """
    return ok(await admin_controller.user_report(repos, account_id, days=days))


@router.post("/users/{account_id}/status")
async def set_user_status(
    account_id: str,
    body: UserStatusRequest,
    request: Request,
    admin: dict = Depends(get_current_admin),
    repos: Repositories = Depends(get_repos),
):
    return ok(
        await admin_controller.set_user_status(
            repos, account_id, body.status, admin, client_ip(request)
        )
    )


@router.patch("/users/{account_id}")
async def update_user(
    account_id: str,
    body: UserProfileUpdate,
    request: Request,
    admin: dict = Depends(get_current_admin),
    repos: Repositories = Depends(get_repos),
):
    """编辑账号资料（昵称 / 头像 / 准入档位）。

    ⛔ **不接受**改 `username` / `phone` / `passcode_hash` / `role`：
    前两个是登录标识（带唯一索引，改动等于换账号），`role` 在单管理员体系里无意义。
    `UserProfileUpdate` 用 `extra="forbid"` 挡在门外 —— 返回 422 而不是静默丢弃，
    免得操作者以为改成功了。
    """
    return ok(
        await admin_controller.update_user(
            repos, account_id, body.model_dump(exclude_unset=True), admin, client_ip(request)
        )
    )


@router.delete("/users/{account_id}")
async def delete_user(
    account_id: str,
    request: Request,
    admin: dict = Depends(get_current_admin),
    repos: Repositories = Depends(get_repos),
):
    """注销账号（软删）：释放邀请码占用、使所有会话失效，但**保留学习数据**。"""
    return ok(
        await admin_controller.delete_user(repos, account_id, admin, client_ip(request))
    )


@router.post("/users/bulk/status")
async def bulk_user_status(
    body: UserBulkStatusRequest,
    request: Request,
    admin: dict = Depends(get_current_admin),
    repos: Repositories = Depends(get_repos),
):
    """批量启用 / 禁用。返回成功与失败的 id，不静默吞掉失败项。"""
    return ok(
        await admin_controller.bulk_user_status(
            repos, body.account_ids, body.status, admin, client_ip(request)
        )
    )


# ----------------------------- 素材中心 -----------------------------
# ⚠️ 具体路径（/assets/bind、/assets/stats）必须声明在 /assets/{asset_id} 之前，
#    否则会被路径参数吃掉。
@router.post("/assets")
async def upload_asset(
    request: Request,
    file: UploadFile = File(...),
    subtype: str | None = Form(default=None),
    admin: dict = Depends(get_current_admin),
    repos: Repositories = Depends(get_repos),
):
    """上传素材（图片 / 音频 / 笔顺 JSON）。返回素材元数据，供内容绑定。"""
    data = await file.read()
    doc = await asset_controller.save_upload(
        repos,
        filename=file.filename,
        mime=file.content_type,
        data=data,
        subtype=subtype,
        actor=admin,
    )
    await admin_controller.log_audit(
        repos,
        actor=admin,
        action="asset.upload",
        target_collection="assets",
        target_id=doc["_id"],
        diff={"mime": doc["mime"], "bytes": doc["bytes"]},
        ip=client_ip(request),
    )
    return ok(doc, http_status=201)


@router.get("/assets")
async def list_assets(
    type: str | None = None,
    keyword: str | None = None,
    include_deleted: bool = False,
    page: PageParams = Depends(page_params),
    admin: dict = Depends(get_current_admin),
    repos: Repositories = Depends(get_repos),
):
    items, total = await asset_controller.list_assets(
        repos,
        skip=page.skip,
        limit=page.page_size,
        asset_type=type,
        keyword=keyword,
        include_deleted=include_deleted,
    )
    return paged(items, page=page.page, page_size=page.page_size, total=total)


@router.get("/assets/stats")
async def asset_stats(
    admin: dict = Depends(get_current_admin),
    repos: Repositories = Depends(get_repos),
):
    return ok(await asset_controller.stats(repos))


@router.post("/assets/bind")
async def bind_asset(
    body: AssetRefBind,
    request: Request,
    admin: dict = Depends(get_current_admin),
    repos: Repositories = Depends(get_repos),
):
    """把素材绑定到内容上（后台「替换配图」）；`asset_id=null` 即解绑。"""
    result = await asset_controller.bind_ref(repos, body)
    await admin_controller.log_audit(
        repos,
        actor=admin,
        action="asset.bind",
        target_collection=body.collection,
        target_id=body.doc_id,
        diff={"field": body.field, "asset_id": body.asset_id},
        ip=client_ip(request),
    )
    return ok(result)


@router.get("/assets/{asset_id}")
async def asset_detail(
    asset_id: str,
    admin: dict = Depends(get_current_admin),
    repos: Repositories = Depends(get_repos),
):
    return ok(await asset_controller.detail(repos, asset_id))


@router.delete("/assets/{asset_id}")
async def delete_asset(
    asset_id: str,
    request: Request,
    admin: dict = Depends(get_current_admin),
    repos: Repositories = Depends(get_repos),
):
    result = await asset_controller.delete_asset(repos, asset_id)
    await admin_controller.log_audit(
        repos,
        actor=admin,
        action="asset.delete",
        target_collection="assets",
        target_id=asset_id,
        diff={"referenced_by": result.get("referenced_by")},
        ip=client_ip(request),
    )
    return ok(result)


# ----------------------------- 内容导入 -----------------------------
# ⚠️ 同样必须声明在 /content/{collection} 之前
@router.get("/content/import/preview")
async def import_preview(
    admin: dict = Depends(get_current_admin),
    repos: Repositories = Depends(get_repos),
):
    """列出每个内容来源文件是否存在、有多少条、库里现有多少条。"""
    return ok({"items": await content_import_controller.preview_import_sources(repos)})


@router.post("/content/import")
async def import_content(
    body: ContentImportRequest,
    request: Request,
    admin: dict = Depends(get_current_admin),
    repos: Repositories = Depends(get_repos),
):
    """从仓库 `content/*.json` 或上传载荷导入（幂等 upsert，可随时重跑）。"""
    result = await content_import_controller.run_import(repos, body)
    if not body.dry_run:
        await admin_controller.log_audit(
            repos,
            actor=admin,
            action="content.import",
            target_collection="content",
            diff={
                "source": body.source,
                "collections": body.collections or "all",
                "created": result.get("created"),
                "updated": result.get("updated"),
            },
            ip=client_ip(request),
        )
    return ok(result)


# ----------------------------- 导出 / 年级统计 -----------------------------
@router.get("/characters/grade-counts")
async def character_grade_counts(
    admin: dict = Depends(get_current_admin),
    repos: Repositories = Depends(get_repos),
):
    """字库按年级计数（后台年级分类 Tab 的徽标）。"""
    return ok(await admin_controller.character_grade_counts(repos))


@router.get("/content/{collection}/export")
async def export_content(
    collection: str,
    status: str | None = None,
    keyword: str | None = None,
    grade: int | None = None,
    level: str | None = None,
    admin: dict = Depends(get_current_admin),
    repos: Repositories = Depends(get_repos),
):
    """导出某类内容为可回写仓库的 JSON（按当前筛选）。"""
    extra = {"grade": grade, "level": level, "grade_num": grade}
    return ok(
        await admin_controller.export_content(
            repos, collection, status=status, keyword=keyword, extra=extra
        )
    )


@router.get("/content/{collection}/template")
async def content_template(
    collection: str,
    admin: dict = Depends(get_current_admin),
):
    """下载导入模板：字段说明 + 一条可直接照抄的示例。

    ⚠️ 必须声明在 `/content/{collection}` 之前，否则 `template` 会被
    路径参数当成集合名吃掉（与 `/content/import/preview` 同一类坑）。
    """
    return ok(admin_controller.content_template(collection))


# ----------------------------- 内容通用 CRUD -----------------------------
@router.get("/content/{collection}")
async def list_content(
    collection: str,
    status: str | None = None,
    keyword: str | None = None,
    grade: int | None = None,
    level: str | None = None,
    page: PageParams = Depends(page_params),
    admin: dict = Depends(get_current_admin),
    repos: Repositories = Depends(get_repos),
):
    extra = {"grade": grade, "level": level, "grade_num": grade}
    items, total = await admin_controller.list_content(
        repos,
        collection,
        skip=page.skip,
        limit=page.page_size,
        status=status,
        keyword=keyword,
        extra=extra,
    )
    return paged(items, page=page.page, page_size=page.page_size, total=total)


@router.post("/content/{collection}")
async def create_content(
    collection: str,
    body: dict,
    request: Request,
    admin: dict = Depends(get_current_admin),
    repos: Repositories = Depends(get_repos),
):
    return ok(
        await admin_controller.create_content(repos, collection, body, admin, client_ip(request)),
        http_status=201,
    )


@router.patch("/content/{collection}/{doc_id}")
async def update_content(
    collection: str,
    doc_id: str,
    body: dict,
    request: Request,
    admin: dict = Depends(get_current_admin),
    repos: Repositories = Depends(get_repos),
):
    return ok(
        await admin_controller.update_content(repos, collection, doc_id, body, admin, client_ip(request))
    )


@router.delete("/content/{collection}/{doc_id}")
async def delete_content(
    collection: str,
    doc_id: str,
    request: Request,
    hard: bool = Query(False, description="true = 物理删除，不可恢复；默认 false = 下架（软删）"),
    force: bool = Query(False, description="物理删除时忽略引用校验（会留下悬空引用）"),
    admin: dict = Depends(get_current_admin),
    repos: Repositories = Depends(get_repos),
):
    """删除内容。

    默认仍是**下架**（软删，`status → offline`），保持既有调用方行为不变；
    只有显式传 `hard=true` 才是不可恢复的物理删除。
    """
    return ok(
        await admin_controller.delete_content(
            repos, collection, doc_id, admin, client_ip(request), hard=hard, force=force
        )
    )
