"""应用配置 —— 全部来自环境变量（见根 .env.example）。

为什么用 pydantic-settings：配置即类型，缺失或格式错误在启动时就报错，
而不是在运行到某个分支时才炸。仓库内只提交 .env.example，真实密钥绝不入库。
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---------------- 通用 ----------------
    app_env: str = Field(default="development", alias="APP_ENV")
    public_site_url: str = Field(default="http://localhost:8080", alias="PUBLIC_SITE_URL")

    # ---------------- 数据库 ----------------
    mongodb_uri: str = Field(default="mongodb://localhost:27017/study_club", alias="MONGODB_URI")
    mongodb_db: str = Field(default="study_club", alias="MONGODB_DB")

    # ---------------- 服务 ----------------
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    api_prefix: str = Field(default="/api/v1", alias="API_PREFIX")

    # ---------------- 会话与安全 ----------------
    # 会话签名密钥：部署时必须替换（openssl rand -hex 32）
    jwt_secret: str = Field(default="dev-only-change-me", alias="JWT_SECRET")
    jwt_algorithm: str = "HS256"
    access_token_ttl_min: int = Field(default=30, alias="ACCESS_TOKEN_TTL_MIN")
    refresh_token_ttl_days: int = Field(default=30, alias="REFRESH_TOKEN_TTL_DAYS")

    # 邀请码通过 Ed25519 离线签名时可校验；公钥随开源代码公开，私钥仅签发方持有
    invite_signing_private_key: str = Field(default="", alias="INVITE_SIGNING_PRIVATE_KEY")
    invite_signing_public_key: str = Field(default="", alias="INVITE_SIGNING_PUBLIC_KEY")

    # 单管理员后台口令哈希（Argon2id，见 scripts/api/hash-password.sh）
    admin_password_hash: str = Field(default="", alias="ADMIN_PASSWORD_HASH")

    # 邀请码是否必填（注册准入开关）。
    # 默认 False = 免码开放（与既有行为一致，开源克隆后即可注册体验）；
    # 置 True 时**服务端强制**校验邀请码，前端 `VITE_ENABLE_INVITE_REQUIRED` 是同一开关的构建期侧。
    # 运行期可被「配置中心」（app_settings 集合）覆盖，见 repositories/ops / services/settings。
    require_invite: bool = Field(default=False, alias="REQUIRE_INVITE")

    # CORS 允许来源（逗号分隔）
    cors_origins: str = Field(
        default="http://localhost:8080,http://localhost:5173", alias="CORS_ORIGINS"
    )

    # ---------------- 素材存储（图片 / 音频 / 笔顺数据） ----------------
    # 内容改为「全部后台管理」后，素材不能再随前端包分发，必须由服务端托管。
    # 文件落磁盘（ASSET_DIR），元数据落 MongoDB（assets 集合）。
    asset_dir: str = Field(default="./data/assets", alias="ASSET_DIR")
    # 留空 → 出参用相对路径 `/api/v1/assets/<id>`，前端按 API 源拼接；
    # 这样换局域网 IP 不需要重建素材链接（比写死绝对地址稳）。
    asset_base_url: str = Field(default="", alias="ASSET_BASE_URL")
    asset_max_bytes: int = Field(default=10 * 1024 * 1024, alias="ASSET_MAX_BYTES")
    # 允许上传的 MIME 白名单（逗号分隔；`type/*` 形式亦可用）
    asset_allowed_mimes: str = Field(
        default=(
            "image/svg+xml,image/png,image/jpeg,image/webp,image/gif,"
            "audio/mpeg,audio/mp4,audio/wav,audio/ogg,audio/webm,"
            "application/json"
        ),
        alias="ASSET_ALLOWED_MIMES",
    )

    # ---------------- 登录防护参数（见 02-5 §4.4） ----------------
    login_rate_limit_max: int = 10  # 每窗口最大尝试次数
    login_rate_limit_window_sec: int = 600  # 窗口 10 分钟
    login_lock_threshold: int = 5  # 连续失败阈值
    login_lock_minutes: int = 15  # 锁定时长

    @field_validator("api_prefix")
    @classmethod
    def _normalize_prefix(cls, v: str) -> str:
        if not v.startswith("/"):
            v = "/" + v
        return v.rstrip("/") or ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def asset_allowed_mime_list(self) -> list[str]:
        return [m.strip().lower() for m in self.asset_allowed_mimes.split(",") if m.strip()]

    @property
    def asset_path_prefix(self) -> str:
        """素材出参的路径前缀（相对）。"""
        return f"{self.api_prefix}/assets"

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}


@lru_cache
def get_settings() -> Settings:
    """进程内单例：开关值只读一次（对齐 06-1 §2.8.1 纪律 ①）。"""
    return Settings()


settings = get_settings()
