"""路由注册检查：确保掩藏能力「不注册」，关键接口齐全，前缀统一为 /api/v1。

实现说明：新版 FastAPI 把 `include_router` 的结果包成 `_IncludedRouter` 惰性节点，
`app.routes` 里不再直接是 `APIRoute`，因此断言改用 OpenAPI 路径表（也是客户端的真实契约）。
"""

from __future__ import annotations

import pytest

from app.main import app

PATHS = set(app.openapi()["paths"])


def test_api_prefix_applied():
    assert "/api/v1/health" in PATHS


@pytest.mark.parametrize(
    "path",
    [
        # 站点公开配置（无需登录）
        "/api/v1/config",
        # 内容（登录后可见）
        "/api/v1/content/bootstrap",
        "/api/v1/content/manifest",
        "/api/v1/content/characters",
        "/api/v1/content/characters/by-char/{char}",
        "/api/v1/content/characters/batch",
        "/api/v1/content/characters/{char_id}",
        "/api/v1/content/characters/{char_id}/similar",
        "/api/v1/content/poems",
        "/api/v1/content/poems/{poem_id}/quiz",
        "/api/v1/content/units",
        "/api/v1/content/lessons/{lesson_id}/questions",
        "/api/v1/content/stories",
        "/api/v1/content/badges",
        # 识字短文（阅读承接：用已学字编的读本）
        "/api/v1/content/readings",
        "/api/v1/content/readings/{reading_id}",
        # 素材下发（公开：<img>/<audio> 无法携带 Authorization）
        "/api/v1/assets/{asset_id}",
        # 认证
        "/api/v1/auth/invite/verify",
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/invite/register",
        "/api/v1/auth/invite/login",
        "/api/v1/auth/recovery/reset",
        "/api/v1/auth/refresh",
        "/api/v1/auth/logout",
        "/api/v1/auth/me",
        "/api/v1/auth/account",
        # 档案
        "/api/v1/children",
        "/api/v1/children/{child_id}",
        "/api/v1/children/{child_id}/stats",
        # 学习
        "/api/v1/learning/state",
        "/api/v1/learning/daily-task",
        "/api/v1/learning/answer",
        "/api/v1/learning/answer/batch",
        "/api/v1/learning/lesson/complete",
        "/api/v1/learning/review/due",
        "/api/v1/learning/review-states",
        "/api/v1/learning/badges",
        "/api/v1/learning/records",
        "/api/v1/learning/answers",
        "/api/v1/learning/export",
        "/api/v1/learning/wrong-questions",
        "/api/v1/learning/progress",
        # 报告
        "/api/v1/reports/child/{child_id}/overview",
        "/api/v1/reports/child/{child_id}/trend",
        "/api/v1/reports/child/{child_id}/mastery",
        "/api/v1/reports/child/{child_id}/weak-chars",
        "/api/v1/reports/child/{child_id}/weekly",
        # 匿名统计 / 反馈 / 同步
        "/api/v1/stats/events",
        "/api/v1/feedbacks",
        "/api/v1/sync/manifest",
        "/api/v1/sync/push",
        "/api/v1/sync/pull",
        "/api/v1/sync/salt",
        # 后台：单管理员 + 数据驱动通用 CRUD
        "/api/v1/admin/login",
        "/api/v1/admin/overview",
        "/api/v1/admin/registry",
        "/api/v1/admin/audit-logs",
        # 站点配置（配置中心）
        "/api/v1/admin/config",
        "/api/v1/admin/invites/batch",
        "/api/v1/admin/invites",
        "/api/v1/admin/invites/{invite_id}/revoke",
        # 用户（账号级列表；仅账号信息，不含学习明细）
        "/api/v1/admin/users",
        "/api/v1/admin/users/stats",
        "/api/v1/admin/users/{account_id}",
        "/api/v1/admin/users/{account_id}/report",
        "/api/v1/admin/users/{account_id}/status",
        "/api/v1/admin/assets",
        "/api/v1/admin/assets/stats",
        "/api/v1/admin/assets/bind",
        "/api/v1/admin/assets/{asset_id}",
        "/api/v1/admin/content/import",
        "/api/v1/admin/content/import/preview",
        "/api/v1/admin/content/{collection}/export",
        "/api/v1/admin/characters/grade-counts",
        "/api/v1/admin/content/{collection}",
        "/api/v1/admin/content/{collection}/{doc_id}",
    ],
)
def test_expected_route_registered(path):
    assert path in PATHS, f"缺少预期路由：{path}"


@pytest.mark.parametrize(
    "fragment",
    [
        "/otp",  # 短信验证码（需企业主体）
        "/wechat",  # 微信授权登录
        "/billing",  # 支付与订阅
        "/orders",  # 订单
        "/subscriptions",  # 订阅
        "/admin/roles",  # 多角色 RBAC
        # 注意：/admin/users 已按需求启用为「账号级用户列表」（仅账号信息，
        # 不下钻学习明细），故不再属于掩藏项；此处断言改为精确匹配角色/RBAC 路径。
        "/devices",  # 设备与推送（推送属掩藏；/devices 整体不注册）
        "/guardian",  # 监护人同意留痕
        "/push_subscriptions",  # 原生推送订阅
    ],
)
def test_masked_capabilities_not_registered(fragment):
    offenders = [p for p in PATHS if fragment in p]
    assert not offenders, f"掩藏能力不应注册路由：{offenders}"
