"""后台内容模板下载 + 用户 CRUD 的契约测试。

这两块是本轮新增的「后台补齐」能力，测试盯住的是**契约而非实现**：
  - 模板：每个可维护的内容类型都要有字段说明，且必填项与 `required_on_create` 一致；
    派生字段必须被标出来（手改它们无效，运营反复手改是真实发生过的问题）。
  - 用户：可编辑字段白名单不能漏出登录凭据；`extra="forbid"` 必须真的挡住越权字段。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.controllers import admin_controller
from app.models.admin import UserBulkStatusRequest, UserProfileUpdate
from app.repositories import content_registry as CR

# 已支持模板下载的内容类型。字库/古诗是本轮明确要求补模板的两类。
TEMPLATED = ("characters", "poems")


# ---------------------------------------------------------------------------
# 模板下载
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("collection", TEMPLATED)
def test_template_exposes_field_docs(collection: str):
    template = admin_controller.content_template(collection)
    assert template["collection"] == collection
    assert template["fields"], "模板必须给出字段说明"
    assert template["items"], "模板必须给一条可直接照抄的示例"


@pytest.mark.parametrize("collection", TEMPLATED)
def test_template_required_matches_registry(collection: str):
    """模板里标必填的字段，必须与注册表的 `required_on_create` 逐字一致。

    两处不一致的后果是「模板说必填、导入却不校验」或反之，
    运营会照着错的说明填，踩坑时还找不到是哪个环节的问题。
    """
    spec = CR.spec_for(collection)
    assert spec is not None
    template = admin_controller.content_template(collection)
    marked = {f["name"] for f in template["fields"] if f["required"]}
    assert marked == set(spec.required_on_create)


@pytest.mark.parametrize("collection", TEMPLATED)
def test_template_sample_satisfies_required(collection: str):
    """示例本身必须能被导入通过 —— 模板给错示例比不给示例更糟。"""
    spec = CR.spec_for(collection)
    assert spec is not None
    sample = admin_controller.content_template(collection)["items"][0]
    for field in spec.required_on_create:
        assert str(sample.get(field) or "").strip(), f"示例缺少必填字段 {field}"


@pytest.mark.parametrize("collection", TEMPLATED)
def test_template_sample_id_follows_prefix(collection: str):
    """示例 `_id` 必须符合该类型的 id 规则，否则照抄示例会被判成「已存在」或格式错。"""
    spec = CR.spec_for(collection)
    assert spec is not None
    sample = admin_controller.content_template(collection)["items"][0]
    assert sample["_id"].startswith(spec.id_prefix)


def test_template_marks_derived_fields():
    """派生字段（导入时自动重算）必须标 derived，否则运营会手动改这些字段。"""
    # 古诗的 full_text 由 lines 推导；汉字库里 pinyin_plain 由 pinyin 推导
    poems_derived = {
        f["name"] for f in admin_controller.content_template("poems")["fields"] if f["derived"]
    }
    assert "full_text" in poems_derived

    char_derived = {
        f["name"]
        for f in admin_controller.content_template("characters")["fields"]
        if f["derived"]
    }
    assert "pinyin_plain" in char_derived


def test_template_rejects_unknown_collection():
    from app.core.errors import BizException

    with pytest.raises(BizException):
        admin_controller.content_template("not_a_collection")


def test_registry_marks_has_template():
    """后台据此决定要不要显示「下载模板」按钮；无字段说明的类型应为 false。"""
    described = admin_controller.registry_descriptor()
    by_key = {d["collection"]: d for d in described}
    for collection in TEMPLATED:
        assert by_key[collection]["has_template"] is True
    # 徽章当前没有写字段说明 → 不给按钮，避免下载到一个空模板
    assert by_key["badges"]["has_template"] is False


# ---------------------------------------------------------------------------
# 用户编辑：可编辑字段白名单
# ---------------------------------------------------------------------------
def test_profile_update_allows_display_fields():
    payload = UserProfileUpdate(
        display_name="小明妈妈", avatar_key="fox", access_tier="invite_only"
    )
    assert payload.model_dump(exclude_unset=True) == {
        "display_name": "小明妈妈",
        "avatar_key": "fox",
        "access_tier": "invite_only",
    }


@pytest.mark.parametrize(
    "field", ["username", "phone", "passcode_hash", "role", "invite_code_hash", "sync_key_salt"]
)
def test_profile_update_rejects_credential_fields(field: str):
    """登录标识与加密密钥盐绝不能从后台改 —— 必须 422，而不是静默丢弃。"""
    with pytest.raises(ValidationError):
        UserProfileUpdate(**{field: "whatever"})


def test_user_editable_whitelist_matches_model():
    """控制器白名单与请求模型必须一致，否则会出现「模型收了但控制器丢」的静默失败。"""
    model_fields = set(UserProfileUpdate.model_fields)
    assert model_fields == set(admin_controller._USER_EDITABLE_FIELDS)


def test_bulk_status_caps_selection():
    """批量操作要设上限：一次改一万个账号既慢又无法撤销。"""
    with pytest.raises(ValidationError):
        UserBulkStatusRequest(account_ids=["a"] * 101, status="active")


def test_bulk_status_rejects_unknown_status():
    with pytest.raises(ValidationError):
        UserBulkStatusRequest(account_ids=["a"], status="deleted")


# ---------------------------------------------------------------------------
# 路由注册
# ---------------------------------------------------------------------------
def test_admin_routes_registered():
    from app.main import app

    paths = set(app.openapi()["paths"])
    for path in (
        "/api/v1/admin/content/{collection}/template",
        "/api/v1/admin/content/{collection}/export",
        "/api/v1/admin/users/{account_id}",
        "/api/v1/admin/users/bulk/status",
    ):
        assert path in paths, f"缺少路由：{path}"


def test_admin_patch_and_delete_users_exist():
    """用户编辑用 PATCH、注销用 DELETE —— 契约级钉住。"""
    from app.main import app

    users_item = app.openapi()["paths"]["/api/v1/admin/users/{account_id}"]
    assert "patch" in users_item and "delete" in users_item
