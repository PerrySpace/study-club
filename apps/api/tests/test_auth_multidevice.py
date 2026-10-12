"""多地同时登入（每设备独立会话）的回归测试。

被测的是一条**真实存在的缺陷**：前端登录时从不带 `client_id`，服务端
`upsert_session` 只好退化成按「客户端形态指纹」认设备。于是同一账号下
两台形态相同的设备（家里两台手机 / 两台 iPad）会算成**同一台**，
后登录的一方覆盖先登录一方的 Refresh Token，先登录的那台在 Access Token
过期后刷不回来 —— 表现就是「家里 iPad 一登，妈妈手机被踢下线」。

修法有两半，两边都必须成立，缺一个缺陷就会回来：
  ① **客户端**上报一个持久化的随机设备 id（`sc.deviceId` → `body.client.client_id`）；
  ② **服务端**用它当会话归属键（`(account_id, client_id)`）。

这里只覆盖服务端这一半（客户端那一半靠 platform/storage.ts 的 `ensureDeviceId`）。

另外顺带钉住一条**安全约束**：`client_id` 是客户端完全可控的字段，
**绝不能进限流键** —— 否则爆破登录时每试一次换个 id 就能无限重试。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.controllers import auth_controller as A
from app.core.client_headers import ClientContext

PASSCODE = "srtest123456"


class _FakeAccounts:
    """只实现 `_finish_login` 真正走到的方法。"""

    def __init__(self) -> None:
        self.marked_login = False

    async def find_by_identifier(self, identifier: str) -> dict | None:
        return {
            "_id": "acc-1",
            "passcode_hash": "irrelevant（校验已被 monkeypatch 掉）",
            "status": "active",
            "role": "learner",
            "e2e_enabled": True,
        }

    async def mark_login(self, account_id, *, now) -> None:
        self.marked_login = True


class _FakeDevices:
    """记录每次建会话时用的「设备键」。"""

    def __init__(self) -> None:
        self.keys: list[str] = []

    async def upsert_session(self, *, account_id, client, refresh_token_hash: str, now) -> None:
        self.keys.append(client.device_key)


def _repos() -> SimpleNamespace:
    return SimpleNamespace(accounts=_FakeAccounts(), devices=_FakeDevices())


def _req():
    return SimpleNamespace(resolved_identifier="srparent", resolved_passcode=PASSCODE, client=None)


def _client(client_id: str | None) -> ClientContext:
    return ClientContext(client="web", platform="web", device_form="desktop", client_id=client_id)


@pytest.fixture(autouse=True)
def _skip_passcode_check(monkeypatch):
    """密码校验走真实 Argon2 会很慢，且与本用例无关 —— 直接放行。"""
    monkeypatch.setattr(A, "verify_passcode", lambda *args, **kwargs: True)


# ---------------------------------------------------------------------------
# ① 两台设备 → 两条互不覆盖的会话
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_two_devices_get_separate_device_keys():
    repos = _repos()
    await A.login_by_account(repos, _req(), _client("dev-ipad"))
    await A.login_by_account(repos, _req(), _client("dev-phone"))

    assert repos.devices.keys == ["dev-ipad", "dev-phone"]
    # 关键断言：两次登录落在**不同**的设备键上。
    # 若相等，第二次登录会覆盖第一次的 Refresh Token，iPad 就会掉线。
    assert repos.devices.keys[0] != repos.devices.keys[1]


@pytest.mark.asyncio
async def test_same_device_relogin_reuses_one_session():
    """同一台设备重复登录应落回同一个键（否则每次登录都留一条僵尸会话）。"""
    repos = _repos()
    await A.login_by_account(repos, _req(), _client("dev-ipad"))
    await A.login_by_account(repos, _req(), _client("dev-ipad"))
    assert repos.devices.keys == ["dev-ipad", "dev-ipad"]


# ---------------------------------------------------------------------------
# ② 老客户端不带 client_id 时，退回形态指纹（保持旧行为，不报错）
# ---------------------------------------------------------------------------
def test_device_key_falls_back_to_form_fingerprint():
    a = _client(None)
    b = _client(None)
    assert a.device_key == b.device_key  # 同形态 → 认作同一台（旧行为，可接受）
    assert a.device_key != _client("dev-ipad").device_key


# ---------------------------------------------------------------------------
# ③ 安全约束：client_id 不得进入限流键
# ---------------------------------------------------------------------------
def test_rate_limit_key_ignores_client_supplied_id():
    """换个 client_id 不能换到新的限流桶 —— 否则限流等于不存在。"""
    a = _client("dev-a")
    b = _client("dev-b")
    assert a.rate_limit_key == b.rate_limit_key
    assert _client(None).rate_limit_key == a.rate_limit_key


def test_rate_limit_key_differs_across_device_forms():
    """形态不同（手机 / 桌面）仍应分开计数，避免一端把另一端刷满。"""
    phone = ClientContext(client="web", platform="web", device_form="phone")
    desktop = ClientContext(client="web", platform="web", device_form="desktop")
    assert phone.rate_limit_key != desktop.rate_limit_key
