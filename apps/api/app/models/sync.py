"""端到端加密同步请求模型（04-1 §2.3 / 03-2 §7.4）。

⚠️ 服务端只存 `cipher_payload`，**不做任何解密**；密钥由用户口令在客户端派生。
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SyncObjectPush(BaseModel):
    model_config = ConfigDict(extra="ignore")

    object_type: str = Field(pattern="^(profile|learning_record|review_state|wrong_question|badge)$")
    object_key: str = Field(min_length=1, max_length=256)
    schema_version: int = Field(default=1, ge=1)
    cipher_payload: str = Field(min_length=1)
    cipher_algo: str = Field(default="xchacha20-poly1305@v1", max_length=64)
    nonce: str = Field(default="", max_length=128)
    revision: int = Field(default=1, ge=1)
    deleted: bool = False
    client_id: str = Field(default="unknown", max_length=128)


class SyncPushRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    objects: list[SyncObjectPush] = Field(default_factory=list, max_length=500)
