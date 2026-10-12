"""安全原语 —— 密码哈希、JWT、邀请码哈希/编码、Ed25519 验签、限流。

设计依据 02-5 §四 安全设计：
- 密码：Argon2id（argon2-cffi），明文不落日志、不入库
- 邀请码：只存 SHA-256 哈希；码为 12 位 Crockford Base32（60 bit 熵）
- 会话：短期 Access Token（JWT）+ 可吊销的 Refresh Token（只存哈希）
- 防护：恒定时间比较、限流、失败锁定
- 掩藏能力（手机号/微信/支付/推送）不在此实现，路由也不注册
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .config import settings
from .errors import TOKEN_EXPIRED, TOKEN_INVALID, BizException

# ---------------------------------------------------------------------------
# 密码（Argon2id）
# ---------------------------------------------------------------------------
# 参数取 OWASP 建议的「平衡档」，单次哈希约几十毫秒，适合登录频率。
_ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)


def hash_passcode(plain: str) -> str:
    """生成 Argon2id 哈希（含盐）。明文用完即弃。"""
    return _ph.hash(plain)


def verify_passcode(plain: str, hashed: str) -> bool:
    """校验密码。任何异常都视为不匹配，绝不把哈希细节泄漏出去。"""
    if not hashed:
        return False
    try:
        return _ph.verify(hashed, plain)
    except (VerifyMismatchError, InvalidHashError, ValueError):
        return False


# ---------------------------------------------------------------------------
# 哈希（邀请码 / 恢复码 / Refresh Token）
# ---------------------------------------------------------------------------
def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def constant_time_equal(a: str, b: str) -> bool:
    """恒定时间比较，防时序侧信道（02-5 §4.4）。"""
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


# ---------------------------------------------------------------------------
# 邀请码 / 恢复码编码
# ---------------------------------------------------------------------------
# Crockford Base32：去掉易混的 I / L / O / U，便于家长手抄与口述。
CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def random_code(num_chars: int = 12) -> str:
    """密码学随机生成 num_chars 位 Base32 码（禁止自增/时间戳派生）。"""
    return "".join(secrets.choice(CROCKFORD_ALPHABET) for _ in range(num_chars))


def format_invite_code(raw: str) -> str:
    """12 位分 3 组：XXXX-XXXX-XXXX（02-5 §4.2）。"""
    return "-".join(raw[i : i + 4] for i in range(0, len(raw), 4))


def invite_code_hint(raw: str) -> str:
    """展示用掩码：只露首组，其余打码，后台可辨认但不含完整码。"""
    groups = format_invite_code(raw).split("-")
    if len(groups) <= 1:
        return groups[0][:4] + "****"
    return groups[0] + "-" + "-".join("****" for _ in groups[1:])


def generate_recovery_code() -> str:
    """一次性恢复码：24 位 Base32（约 120 bit），仅显示一次，服务端只存哈希。"""
    return random_code(24)


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------
def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(account_id: str, role: str = "learner") -> tuple[str, int]:
    """返回 (token, expires_in_seconds)。"""
    ttl_sec = settings.access_token_ttl_min * 60
    now = _now()
    payload = {
        "sub": account_id,
        "role": role,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_sec)).timestamp()),
        "jti": uuid.uuid4().hex,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, ttl_sec


def create_refresh_token(account_id: str) -> tuple[str, str]:
    """返回 (token, token_hash)。服务端只存哈希，用于登出吊销。"""
    now = _now()
    payload = {
        "sub": account_id,
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=settings.refresh_token_ttl_days)).timestamp()),
        "jti": uuid.uuid4().hex,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, sha256_hex(token)


def decode_token(token: str) -> dict:
    """解析并校验 JWT。过期与无效分别映射 40101 / 40102。"""
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise BizException(TOKEN_EXPIRED, "Token 已过期") from exc
    except jwt.InvalidTokenError as exc:
        raise BizException(TOKEN_INVALID, "Token 无效") from exc


# ---------------------------------------------------------------------------
# Ed25519 离线签名邀请码验签（公钥随开源代码公开）
# ---------------------------------------------------------------------------
def verify_ed25519(public_key_str: str, payload: bytes, signature: bytes) -> bool:
    """支持 raw 32 字节（hex / base64）与 PEM 公钥。无法解析一律返回 False。"""
    if not public_key_str:
        return False
    key = _load_ed25519_public_key(public_key_str)
    if key is None:
        return False
    try:
        key.verify(signature, payload)
        return True
    except Exception:  # noqa: BLE001 - 签名格式错误或校验失败一律视为不通过
        return False


def _load_ed25519_public_key(value: str) -> Ed25519PublicKey | None:
    value = value.strip()
    if "BEGIN PUBLIC KEY" in value:
        try:
            from cryptography.hazmat.primitives import serialization

            return serialization.load_pem_public_key(value.encode("utf-8"))  # type: ignore[return-value]
        except Exception:  # noqa: BLE001 - 任何解析失败都视为不可用
            return None
    raw: bytes | None = None
    try:
        raw = bytes.fromhex(value)
    except ValueError:
        try:
            raw = base64.b64decode(value)
        except Exception:  # noqa: BLE001
            return None
    if raw and len(raw) == 32:
        try:
            return Ed25519PublicKey.from_public_bytes(raw)
        except Exception:  # noqa: BLE001
            return None
    return None


# ---------------------------------------------------------------------------
# 登录限流（进程内滑动窗口）
# ---------------------------------------------------------------------------
class SlidingWindowLimiter:
    """按 key 的滑动窗口限流。

    为什么放进程内：单实例 Docker 部署、无 Redis（03-1 §一 明确不引入缓存）。
    多实例水平扩展时应替换为共享存储——此处显式标注，避免被误认为分布式限流。
    """

    def __init__(self, max_events: int, window_sec: int) -> None:
        self._max = max_events
        self._window = window_sec
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            dq = self._events.setdefault(key, deque())
            while dq and now - dq[0] > self._window:
                dq.popleft()
            if len(dq) >= self._max:
                return False
            dq.append(now)
            return True

    def reset(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)


login_limiter = SlidingWindowLimiter(
    max_events=settings.login_rate_limit_max,
    window_sec=settings.login_rate_limit_window_sec,
)
