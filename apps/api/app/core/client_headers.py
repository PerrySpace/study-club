"""客户端标识请求头解析（04-1 §1.6）。

`X-Client-Client / Platform / Form / Version / Capabilities` 由各端 HttpAdapter 统一注入。
服务端据此把 client / platform / device_form / client_version 落进 learning_records，
并可按版本做兼容降级。

取舍：契约标「必填」，但解析失败时**回落默认值**，不阻塞请求
而不是 400——把兼容性放在服务端比逼客户端升级更划算（04-1 §1.7 硬要求）。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import Request

from .security import sha256_hex

DEFAULT_CLIENT = "web"
DEFAULT_PLATFORM = "web"
DEFAULT_DEVICE_FORM = "desktop"
DEFAULT_VERSION = "0.0.0"


@dataclass(frozen=True)
class ClientContext:
    client: str = DEFAULT_CLIENT
    platform: str = DEFAULT_PLATFORM
    device_form: str = DEFAULT_DEVICE_FORM
    client_version: str = DEFAULT_VERSION
    capabilities: list[str] = field(default_factory=list)
    # 设备标识：客户端自报的**稳定随机 id**，用于把同一账号的不同设备分成独立会话
    # （见 repositories/identity.py 的 upsert_session）
    client_id: str | None = None

    @property
    def device_key(self) -> str:
        """会话归属键：有 client_id 就用它，否则退化为「客户端形态指纹」。

        这条键决定 `devices` 集合里一条会话记录属于哪台设备 —— 也就是
        「多地登入能不能同时在线」。前端不报 client_id 时，同形态的两台设备
        （例如两台手机）会被算成同一台，后登录者覆盖先登录者的 Refresh Token，
        表现为一台登录另一台被踢下线。
        """
        return self.client_id or self.rate_limit_key

    @property
    def rate_limit_key(self) -> str:
        """限流键：**只用客户端形态指纹，刻意不含 client_id**（见 02-5 §4.4）。

        为什么不把 `client_id` 拼进来：它是**客户端完全可控**的字段，
        拼进来等于把限流开关交给攻击者 —— 换个 id 就是一个全新的计数桶，
        爆破登录时每试一次都换个 id 即可无限重试，限流形同不存在。
        形态指纹虽然不是逐用户的，但攻击者改不动它，作为粗粒度的突发/DoS 闸门是有效的；
        真正的逐账号防线是 `accounts.failed_attempts` + `locked_until`（5 次失败锁 15 分钟）。

        ⚠️ 局限性（已知）：真实来源 IP 在当前的部署形态下不可靠 ——
        Cloudflare Tunnel 进来时 `$remote_addr` 是 127.0.0.1，而 `X-Forwarded-For`
        的首段是客户端可伪造的，所以这里不敢用 IP 做键。
        若将来有了可信的客户端 IP 来源，应改为「指纹 + IP」组合键。
        """
        return sha256_hex(f"{self.client}|{self.platform}|{self.device_form}|{self.client_version}")


def parse_client_context(request: Request, client_id: str | None = None) -> ClientContext:
    h = request.headers
    raw_caps = h.get("X-Client-Capabilities", "") or ""
    caps = [c.strip() for c in raw_caps.split(",") if c.strip()]
    return ClientContext(
        client=h.get("X-Client-Client") or DEFAULT_CLIENT,
        platform=h.get("X-Client-Platform") or DEFAULT_PLATFORM,
        device_form=h.get("X-Client-Form") or DEFAULT_DEVICE_FORM,
        client_version=h.get("X-Client-Version") or DEFAULT_VERSION,
        capabilities=caps,
        client_id=client_id,
    )


def client_ip(request: Request) -> str:
    """取真实来源 IP：优先 X-Forwarded-For 首个（反代场景），否则连接地址。"""
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
