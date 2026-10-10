"""站点公开配置路由（无需登录）。

客户端启动时要读的**非敏感**运行配置：邀请码是否必填、是否开放注册、公告、
默认学习目标、**玩法配置**（题型开关 / 阶段检测节奏 / 跟读开关 / 朗读语速）、
**年级表**。敏感项（密钥、DB 地址等）一律不下发。

`gameplay` 是「后台控制与客户端玩法同步」的下发口：客户端每次启动读一次，
据此渲染玩法 —— 后台改玩法不需要发版。

`grades` 同理：年级是后台可配置的（不再是写死的 1–6），后台加年级后
客户端的年级下拉自动跟着变，不需要发版。它必须在这里（免登录）下发，
因为注册页与引导页在**登录前**就要让用户选年级。

写入侧在 `/admin/config`（需管理员鉴权）。
"""

from __future__ import annotations

from fastapi import APIRouter

from ..core import runtime_config
from ..core.response import ok

router = APIRouter(tags=["config"])


@router.get("/config")
async def public_config():
    cfg = runtime_config.get_config()
    return ok(
        {
            "require_invite": cfg["require_invite"],
            "registration_open": cfg["registration_open"],
            "announcement": cfg["announcement"],
            "defaults": cfg["defaults"],
            "gameplay": runtime_config.gameplay_config(),
            # 年级表必须**免登录下发**：注册页与引导页在登录前就要让用户选年级，
            # 那时还没有任何账号能带 token。客户端据此渲染年级下拉，
            # 所以后台加年级后前端无需发版。
            "grades": cfg["grades"],
        }
    )
