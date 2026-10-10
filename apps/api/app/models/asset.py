"""素材模型（04-1 §四 素材扩展）。

内容改为「全部后台管理」后，图片 / 音频 / 笔顺数据统一走素材中心：
- 文件落磁盘（ASSET_DIR），元数据落 `assets` 集合
- 内容文档只存引用（`image_ref` / `audio_ref` / `stroke_order_ref`），出参时展开为 `*_url`
- 这样替换配图**不用改内容文档**，也不会把二进制塞进 MongoDB
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

ASSET_TYPE = ("image", "audio", "stroke", "other")


class AssetUpdate(BaseModel):
    """素材元数据局部更新（文件本身不可改，只能替换）。"""

    model_config = ConfigDict(extra="forbid")

    subtype: str | None = Field(default=None, max_length=64)
    original_name: str | None = Field(default=None, max_length=200)


class AssetQuery(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: str | None = Field(default=None, pattern="^(image|audio|stroke|other)$")
    keyword: str | None = Field(default=None, max_length=64)
    include_deleted: bool = False


class AssetRefBind(BaseModel):
    """把素材绑定到某条内容上（后台「替换配图」按钮用）。"""

    model_config = ConfigDict(extra="forbid")

    collection: str = Field(pattern="^(characters|poems|stories|lessons|curriculum_units|badges)$")
    doc_id: str = Field(min_length=1, max_length=64)
    field: str = Field(pattern="^(image_ref|audio_ref|stroke_order_ref|icon_ref)$")
    asset_id: str | None = Field(default=None, description="传 null 表示解绑")
