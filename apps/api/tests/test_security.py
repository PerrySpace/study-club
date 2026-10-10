"""安全原语测试：口令哈希、JWT、邀请码编码、Ed25519 验签、限流。"""

from __future__ import annotations

import base64
import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.core import errors as E
from app.core import security as S
from app.core.config import settings


# --------------------------- 口令 ---------------------------
def test_passcode_hash_and_verify():
    hashed = S.hash_passcode("abc123def")
    assert hashed != "abc123def"
    assert hashed.startswith("$argon2id$")
    assert S.verify_passcode("abc123def", hashed) is True
    assert S.verify_passcode("wrong", hashed) is False


def test_verify_passcode_handles_empty_hash():
    assert S.verify_passcode("x", "") is False
    assert S.verify_passcode("x", "not-a-hash") is False


# --------------------------- 哈希 ---------------------------
def test_sha256_and_constant_time_equal():
    assert S.sha256_hex("abc") == S.sha256_hex("abc")
    assert len(S.sha256_hex("abc")) == 64
    assert S.constant_time_equal("aa", "aa") is True
    assert S.constant_time_equal("aa", "ab") is False


# --------------------------- 邀请码编码 ---------------------------
def test_random_code_charset_and_length():
    code = S.random_code(12)
    assert len(code) == 12
    assert all(c in S.CROCKFORD_ALPHABET for c in code)
    # 不含易混字符
    assert not set(code) & set("ILOU")


def test_format_and_hint():
    assert S.format_invite_code("ABCDEFGHJKMN") == "ABCD-EFGH-JKMN"
    hint = S.invite_code_hint("ABCDEFGHJKMN")
    assert hint == "ABCD-****-****"
    assert "EFGH" not in hint


# --------------------------- JWT ---------------------------
def test_access_token_roundtrip():
    token, expires_in = S.create_access_token("507f1f77bcf86cd799439011", "learner")
    assert expires_in == settings.access_token_ttl_min * 60
    payload = S.decode_token(token)
    assert payload["sub"] == "507f1f77bcf86cd799439011"
    assert payload["type"] == "access"
    assert payload["role"] == "learner"


def test_refresh_token_hash_only():
    token, token_hash = S.create_refresh_token("507f1f77bcf86cd799439011")
    assert token_hash == S.sha256_hex(token)
    payload = S.decode_token(token)
    assert payload["type"] == "refresh"


def test_expired_token_maps_to_40101():
    expired = jwt.encode(
        {"sub": "x", "type": "access", "exp": int(time.time()) - 10},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(E.BizException) as exc:
        S.decode_token(expired)
    assert exc.value.code == E.TOKEN_EXPIRED
    assert exc.value.http_status == 401


def test_invalid_token_maps_to_40102():
    with pytest.raises(E.BizException) as exc:
        S.decode_token("not.a.jwt")
    assert exc.value.code == E.TOKEN_INVALID


# --------------------------- Ed25519 ---------------------------
def _keypair():
    """返回 (私钥对象, raw 32 字节公钥)。

    注意返回的是**私钥对象**而不是 raw 私钥字节 —— 测试要用它签名（`priv.sign`），
    raw 字节是 `bytes`，没有 `sign` 方法。
    """
    sk = Ed25519PrivateKey.generate()
    raw_pub = sk.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return sk, raw_pub


def test_ed25519_verify_hex_and_base64():
    priv, pub = _keypair()
    payload = b"tier=friend;expires=2026-12-31"
    sig = priv.sign(payload)
    assert S.verify_ed25519(pub.hex(), payload, sig) is True
    assert S.verify_ed25519(base64.b64encode(pub).decode(), payload, sig) is True
    assert S.verify_ed25519(pub.hex(), payload, b"tampered-signature-0000000000000000") is False
    assert S.verify_ed25519("", payload, sig) is False
    assert S.verify_ed25519("zzzz", payload, sig) is False


# --------------------------- 限流 ---------------------------
def test_sliding_window_limiter():
    limiter = S.SlidingWindowLimiter(max_events=3, window_sec=60)
    key = "1.2.3.4:dev"
    assert [limiter.allow(key) for _ in range(3)] == [True, True, True]
    assert limiter.allow(key) is False
    limiter.reset(key)
    assert limiter.allow(key) is True
