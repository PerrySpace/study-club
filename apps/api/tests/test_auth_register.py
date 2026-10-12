"""注册流程的身份模型回归测试（02-5 §2.2 / §3.4 / §4.4）。

被测的是一条**真实踩到过的缺陷**：邀请码是账号的登录标识，`accounts.invite_code_hash`
上有唯一索引，但 `register()` 起初没有做前置占用校验 —— 用同一个码第二次注册时，
pymongo 的 `DuplicateKeyError` 会被全局 handler 兜成 500「服务内部错误」。
后果有两层：
  ① 用户拿到一个无法理解的 5xx（正确行为是 401 + 统一文案「邀请码或密码不正确」）；
  ② 违反了 02-5 §4.4「绝不区分邀请码不存在 / 已用尽 / 已吊销 / 已过期」（防枚举）。

这里用最小假仓储覆盖三条路径：已被占用、并发撞唯一索引、免码开放。
不引入 mongo，测试毫秒级完成。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from pymongo.errors import DuplicateKeyError

from app.controllers import auth_controller as A
from app.core import errors as E
from app.core.client_headers import ClientContext

PASSCODE = "srtest123456"
RAW_CODE = "ABCDEFGHJKMN"


# ---------------------------------------------------------------------------
# 最小假仓储：只实现 register() 真正走到的方法
# ---------------------------------------------------------------------------
class _FakeAccounts:
    def __init__(
        self,
        *,
        bound: bool = False,
        raise_dup: bool = False,
        username_taken: bool = False,
        phone_taken: bool = False,
    ) -> None:
        self.bound = bound
        self.raise_dup = raise_dup
        self.username_taken = username_taken
        self.phone_taken = phone_taken
        self.inserted: list[dict] = []

    async def find_by_invite_hash(self, invite_code_hash: str) -> dict | None:
        return {"_id": "existing"} if self.bound else None

    async def find_by_username(self, username: str) -> dict | None:
        return {"_id": "existing"} if self.username_taken else None

    async def find_by_phone(self, phone: str) -> dict | None:
        return {"_id": "existing"} if self.phone_taken else None

    async def insert_one(self, doc: dict):
        if self.raise_dup:
            raise DuplicateKeyError("E11000 duplicate key error", 11000, {})
        self.inserted.append(doc)
        return "new-account-id"

    async def delete_one(self, flt: dict) -> None:  # pragma: no cover - 正常路径不触发
        return None


class _FakeInvites:
    def __init__(self, *, usable: bool = True) -> None:
        self.usable = usable
        self.consumed: list[str] = []

    async def find_by_code_hash(self, code_hash: str) -> dict | None:
        if not self.usable:
            return None
        return {"_id": "invite-1", "used_count": 0, "max_uses": 1}

    async def consume(self, invite_id, account_id) -> bool:
        self.consumed.append(invite_id)
        return True


class _FakeRecoveryCodes:
    def __init__(self) -> None:
        self.issued: list[dict] = []

    async def issue(self, *, account_id, code_hash: str, now) -> None:
        self.issued.append({"account_id": account_id, "code_hash": code_hash})


class _FakeDevices:
    async def upsert_session(self, **kwargs) -> None:
        return None


def _repos(
    *,
    bound: bool = False,
    raise_dup: bool = False,
    usable: bool = True,
    username_taken: bool = False,
    phone_taken: bool = False,
):
    return SimpleNamespace(
        accounts=_FakeAccounts(
            bound=bound,
            raise_dup=raise_dup,
            username_taken=username_taken,
            phone_taken=phone_taken,
        ),
        invites=_FakeInvites(usable=usable),
        recovery_codes=_FakeRecoveryCodes(),
        devices=_FakeDevices(),
    )


def _req(
    invite_code: str | None = RAW_CODE,
    *,
    username: str | None = "srtestuser",
    phone: str | None = None,
):
    return SimpleNamespace(
        username=username,
        phone=phone,
        invite_code=invite_code,
        display_name="小兔子家",
        avatar_key="rabbit",
        e2e_enabled=True,
        resolved_passcode=PASSCODE,
    )


CLIENT = ClientContext(client="web", platform="web", device_form="desktop", client_id="dev_test")


# ---------------------------------------------------------------------------
# ① 邀请码已被占用 → 业务错误，且**不写库**
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_register_rejects_invite_already_bound_to_another_account():
    repos = _repos(bound=True)
    with pytest.raises(E.BizException) as ei:
        await A.register(repos, _req(), CLIENT)

    assert ei.value.code == E.INVITE_INVALID
    assert ei.value.message == E.UNIFIED_AUTH_MESSAGE
    assert ei.value.http_status == 401
    # 关键：连账号都不该尝试插入
    assert repos.accounts.inserted == []
    # 也不该消耗邀请码
    assert repos.invites.consumed == []


# ---------------------------------------------------------------------------
# ② 并发窗口撞唯一索引 → 仍必须是业务错误，不能漏成 500
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_register_duplicate_key_race_is_translated_to_biz_error():
    repos = _repos(raise_dup=True)
    with pytest.raises(E.BizException) as ei:
        await A.register(repos, _req(), CLIENT)

    assert ei.value.code == E.INVITE_INVALID
    assert ei.value.message == E.UNIFIED_AUTH_MESSAGE
    # 绝不能被当成 500 内部错误
    assert ei.value.code != E.INTERNAL
    assert ei.value.http_status != 500


# ---------------------------------------------------------------------------
# ③ 免码开放（enableInviteRequired=false）不受影响
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_register_without_invite_code_creates_open_account():
    repos = _repos()
    result = await A.register(repos, _req(invite_code=None), CLIENT)

    assert len(repos.accounts.inserted) == 1
    doc = repos.accounts.inserted[0]
    assert doc["invite_code_hash"] is None
    assert doc["access_tier"] == "open"
    # 返回体仍带恢复码与账号摘要
    assert result["recovery_code"]
    assert result["account"]["display_name"] == "小兔子家"


# ---------------------------------------------------------------------------
# ④ 正常有码注册：落库时写入的是**哈希**，且消耗一次邀请码
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_register_with_valid_invite_code_hashes_code_and_consumes():
    repos = _repos()
    await A.register(repos, _req(), CLIENT)

    doc = repos.accounts.inserted[0]
    assert doc["invite_code_hash"] is not None
    assert RAW_CODE not in doc["invite_code_hash"]
    assert doc["access_tier"] == "invite_only"
    assert repos.invites.consumed == ["invite-1"]
    # 恢复码只存哈希
    assert repos.recovery_codes.issued
    assert len(repos.recovery_codes.issued[0]["code_hash"]) == 64


# ---------------------------------------------------------------------------
# ⑤ 无效邀请码（不存在/已用尽/已吊销/已过期）→ 统一文案
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_register_with_unusable_invite_code_uses_unified_message():
    repos = _repos(usable=False)
    with pytest.raises(E.BizException) as ei:
        await A.register(repos, _req(), CLIENT)
    assert ei.value.code == E.INVITE_INVALID
    assert ei.value.message == E.UNIFIED_AUTH_MESSAGE
    assert repos.accounts.inserted == []


# ---------------------------------------------------------------------------
# ⑥ 用户名 / 手机号：至少填一个 + 格式校验 + 唯一性（新增契约）
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_register_requires_at_least_one_identifier():
    repos = _repos()
    with pytest.raises(E.BizException) as ei:
        await A.register(repos, _req(username=None, phone=None), CLIENT)
    assert ei.value.code == E.PARAM_INVALID
    assert repos.accounts.inserted == []


@pytest.mark.asyncio
async def test_register_accepts_phone_only():
    repos = _repos()
    result = await A.register(repos, _req(username=None, phone="13800138000"), CLIENT)
    doc = repos.accounts.inserted[0]
    assert doc["phone"] == "13800138000"
    assert "username" not in doc  # 缺省而非 null（sparse 唯一索引前提）
    assert result["account"]["phone"] == "13800138000"


@pytest.mark.asyncio
async def test_register_rejects_malformed_username_and_phone():
    repos = _repos()
    with pytest.raises(E.BizException) as ei:
        await A.register(repos, _req(username="1ab", phone=None), CLIENT)
    assert ei.value.code == E.PARAM_INVALID
    assert ei.value.errors[0]["field"] == "username"

    with pytest.raises(E.BizException) as ei2:
        await A.register(repos, _req(username=None, phone="12345"), CLIENT)
    assert ei2.value.errors[0]["field"] == "phone"


@pytest.mark.asyncio
async def test_register_rejects_taken_username_and_phone():
    repos = _repos(username_taken=True)
    with pytest.raises(E.BizException) as ei:
        await A.register(repos, _req(username="takenuser"), CLIENT)
    assert ei.value.errors[0]["field"] == "username"

    repos2 = _repos(phone_taken=True)
    with pytest.raises(E.BizException) as ei2:
        await A.register(repos2, _req(username=None, phone="13800138000"), CLIENT)
    assert ei2.value.errors[0]["field"] == "phone"


@pytest.mark.asyncio
async def test_register_omits_identifier_keys_when_absent():
    """缺省字段而非写 null：sparse 唯一索引只跳过「没有该字段」的文档。"""
    repos = _repos()
    await A.register(repos, _req(username=None, phone="13800138000"), CLIENT)
    doc = repos.accounts.inserted[0]
    assert "username" not in doc
    assert doc["phone"] == "13800138000"


# ---------------------------------------------------------------------------
# ⑦ 邀请码开关：开启时必填（服务端强制，防绕过前端）
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_register_requires_invite_when_switch_on(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "require_invite", True)
    repos = _repos()
    with pytest.raises(E.BizException) as ei:
        await A.register(repos, _req(invite_code=None), CLIENT)
    assert ei.value.code == E.INVITE_INVALID
    assert repos.accounts.inserted == []


@pytest.mark.asyncio
async def test_register_allows_no_invite_when_switch_off(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "require_invite", False)
    repos = _repos()
    await A.register(repos, _req(invite_code=None), CLIENT)
    assert len(repos.accounts.inserted) == 1
