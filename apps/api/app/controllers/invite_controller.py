"""邀请码服务 —— 生成、哈希、可用性校验（02-5 §四 / 03-2 §3.2）。

硬约束：
- 只存 SHA-256 哈希，完整码只在签发时返回一次
- 校验失败用统一错误信息，绝不区分「不存在 / 已用尽 / 已吊销 / 已过期」（防枚举）
- 生成使用密码学随机（`secrets`），禁止自增或时间戳派生
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from ..core.security import (
    format_invite_code,
    invite_code_hint,
    random_code,
    sha256_hex,
)

_NON_ALNUM = re.compile(r"[^0-9A-Z]")


def normalize_code(code: str) -> str:
    """把用户输入的码归一化：大写、去分隔符。保证同一码不同书写形式哈希一致。"""
    return _NON_ALNUM.sub("", code.strip().upper())


def hash_invite_code(code: str) -> str:
    return sha256_hex(normalize_code(code))


def make_invite_document(
    *,
    raw_code: str,
    batch_id: str,
    channel: str,
    max_uses: int,
    expires_at: datetime | None,
    note: str | None,
    created_by=None,
) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "code_hash": sha256_hex(normalize_code(raw_code)),
        "code_hint": invite_code_hint(raw_code),
        "batch_id": batch_id,
        "channel": channel,
        "max_uses": max_uses,
        "used_count": 0,
        "bound_account_ids": [],
        "expires_at": expires_at,
        "revoked_at": None,
        "note": note,
        "created_by": created_by,
        "created_at": now,
    }


def generate_raw_codes(count: int) -> list[str]:
    """生成 count 个 12 位 Crockford Base32 原始码（未分组，便于哈希）。"""
    return [random_code(12) for _ in range(count)]


def format_for_delivery(raw_code: str) -> str:
    return format_invite_code(raw_code)


def is_usable(invite: dict, now: datetime | None = None) -> bool:
    """可用性判定（不含密码）：未吊销、未过期、未用尽。"""
    now = now or datetime.now(timezone.utc)
    if invite.get("revoked_at") is not None:
        return False
    expires_at = invite.get("expires_at")
    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < now:
            return False
    if int(invite.get("used_count", 0)) >= int(invite.get("max_uses", 1)):
        return False
    return True
