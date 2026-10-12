"""站点运行配置 —— DB 驱动（`app_settings` 单文档）+ 进程内缓存。

为什么要有它（需求：配置启动检查 DB，有则读 DB 的值，后台可改）：

- **环境变量**（`core/config.py`）是**首次启动的默认值**，适合放"部署相关"的东西
  （端口、密钥、DB 地址）。
- **运营参数**（邀请码开关、默认学习目标、玩法配置）不该改一次就重启一次服务，
  因此落 DB、可在后台热改。启动时读一次进缓存；运行中只读缓存（对齐
  「开关值只读一次」纪律，见 06-1 §2.8.1）。

本模块**不导入 repositories**（保持 core 不反向依赖数据层）：仓储以鸭子类型传入。

两段配置的分工（不要混淆）：

- `defaults`：**新建孩子档案时**写入 child 文档的初值（每人可再单独改）。
- `gameplay`：**全体生效的玩法开关**，客户端每次启动读取并据此渲染（题型、跟读、
  阶段检测节奏、朗读语速、是否展示字源图）。改这里等于给所有孩子换一套玩法。
  这是「后台控制与客户端玩法同步」的唯一真源 —— 客户端不再自带一份写死的玩法表。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .config import settings

# 站点配置单文档主键
SITE_DOC_ID = "site"

# 玩法可选题型 —— 必须与 `controllers/content_controller.py` 的 QUESTION_STEMS 键集一致。
# core 不能反向导入 controllers，故此处独立声明，并由 tests 断言两者对齐（防漂移）。
GAMEPLAY_QUESTION_TYPES: tuple[str, ...] = (
    "image-choice",
    "audio-choice",
    "pinyin-match",
    "word-build",
    "meaning-choice",
    "speak",
)

# 阶段检测节奏的可选区间（每学 N 个字插入一次旧字抽查）
STAGE_TEST_EVERY_MIN = 3
STAGE_TEST_EVERY_MAX = 10
SPEAK_RATE_MIN = 0.6
SPEAK_RATE_MAX = 1.2

# 年级上限守卫。
#
# 年级现在是**后台可配置**的（见 `_normalize_grades`），不再写死 1–6；
# 但仍需要一个宽松的上界，否则脏数据能落进 `grade=999999`，进而让
# 「该年级及以下」的内容池查询退化成全表扫、且界面上出现荒谬文案。
# 30 足以覆盖到「研究生」这类极端需求，又不会成为真实负担。
GRADE_MAX = 30

# 默认年级表。后台可增删改；这里的值只在「从未配置过」时作为初值。
DEFAULT_GRADES: tuple[dict[str, Any], ...] = (
    {"id": 0, "label": "学龄前", "enabled": True},
    {"id": 1, "label": "一年级", "enabled": True},
    {"id": 2, "label": "二年级", "enabled": True},
    {"id": 3, "label": "三年级", "enabled": True},
    {"id": 4, "label": "四年级", "enabled": True},
    {"id": 5, "label": "五年级", "enabled": True},
    {"id": 6, "label": "六年级", "enabled": True},
)


def _normalize_grades(value: Any) -> list[dict[str, Any]]:
    """年级表归一化 —— 允许后台配置任意年级，但对脏数据设硬边界。

    为什么要归一化而不是直接信任配置：这份数据**决定客户端所有年级下拉、
    以及内容的 grade 校验上界**，一条坏数据（id 超界 / label 为空 / 重复 id）
    会同时污染界面与「该年级及以下」的内容池筛选。因此：
      - id 必须落在 `0..GRADE_MAX`
      - id 不重复（后者覆盖前者，保持首次出现的位置）
      - label 必须是非空字符串
      - 整条非法则**回落到默认年级表**，而不是让站点配置变成空年级
    """
    if not isinstance(value, list) or not value:
        return [dict(item) for item in DEFAULT_GRADES]

    seen: set[int] = set()
    out: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        try:
            gid = int(item.get("id"))
        except (TypeError, ValueError):
            continue
        if gid < 0 or gid > GRADE_MAX or gid in seen:
            continue
        label = str(item.get("label") or "").strip()
        if not label:
            continue
        seen.add(gid)
        out.append({"id": gid, "label": label[:16], "enabled": bool(item.get("enabled", True))})

    return out or [dict(item) for item in DEFAULT_GRADES]


def grades_config() -> list[dict[str, Any]]:
    """当前年级表（已归一化）。返回深拷贝，避免调用方就地改坏缓存。"""
    return _normalize_grades(get_config().get("grades"))


def enabled_grade_labels() -> dict[int, str]:
    """`{id: label}`，只含启用的年级 —— 客户端下拉与文案回退都用它。

    为什么按 id 升序返回：客户端新建档案时年级下拉的顺序应与配置顺序无关，
    而要和「年级本身的大小」一致 —— 否则运营把年级顺序打乱后，
    会出现「七年级排在一年级前面」。
    """
    items = [g for g in grades_config() if g["enabled"]]
    return {int(g["id"]): str(g["label"]) for g in sorted(items, key=lambda g: int(g["id"]))}


def _normalize_grades_and_validate(value: Any) -> list[dict[str, Any]]:
    """后台保存前的校验入口（复用归一化，但**不做静默回落**）。

    与 `_normalize_grades` 的区别：那一处用于「读」（脏数据要能兜住），
    这一处用于「写」（运营明确传了非法值就要报错，不能悄悄替换成默认值）。
    """
    if not isinstance(value, list) or not value:
        raise ValueError("grades 不能为空")
    cleaned = _normalize_grades(value)
    if len(cleaned) != len([x for x in value if isinstance(x, dict)]):
        raise ValueError("grades 含有非法项（id 需为 0–%d 的整数、id 不可重复、label 不可为空）" % GRADE_MAX)
    return cleaned


# 可写入的配置键白名单 —— **唯一真源**。
#
# 为什么要提到模块级：这份清单有两个消费方，必须同时对得上 ——
#   ① `update_config` 用它过滤补丁（不在表里的一律忽略）；
#   ② 后台请求模型 `models.admin.SiteConfigUpdate` 必须把每个键都声明成字段。
# ② 一旦漏声明，模型的 `extra="ignore"` 会把它**静默丢弃**：请求体里明明带着、
# 控制器 `model_dump()` 里却没有，表现是「保存成功、刷新后一字未变」，
# 而 runtime_config 自己的单测全绿（因为它是被直接调用的，从没经过模型）。
# `grades` 就这么丢过一次。提成常量后，测试可以直接比对两层，防止再次漏。
UPDATABLE_KEYS: frozenset[str] = frozenset(
    {"require_invite", "registration_open", "announcement", "defaults", "gameplay", "grades"}
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def default_config() -> dict[str, Any]:
    """默认配置。环境变量 `REQUIRE_INVITE` 作为 `require_invite` 的初值。"""
    return {
        "require_invite": bool(settings.require_invite),
        "registration_open": True,
        "announcement": "",
        "defaults": {
            "daily_new_char_target": 8,
            "daily_review_target": 20,
            "daily_time_limit_min": 20,
        },
        "grades": [dict(item) for item in DEFAULT_GRADES],
        "gameplay": default_gameplay(),
    }


def default_gameplay() -> dict[str, Any]:
    """玩法默认值 —— 客户端在不支持读服务端配置时也照此渲染（保证行为一致）。"""
    return {
        # 每学 N 个新字，插入一次"旧字抽查"（阶段检测）：只推新字不回头，是识字最大的坑
        "stage_test_every": 5,
        # 允许出现的题型；客户端据此过滤，后台可关掉某个玩法
        "enabled_question_types": list(GAMEPLAY_QUESTION_TYPES),
        # 跟读（浏览器原生语音识别）；关闭后跟读题型整块不出现
        "enable_speak": True,
        # 展示字源图（象形 emoji / 绑定图片）
        "show_pictograph": True,
        # 朗读语速（越小越慢，0.6 是"一个字一个字念"的档位）
        "speak_rate": 0.8,
    }


# 进程内缓存：启动时载入一次，运行中只读
_cache: dict[str, Any] | None = None


def _normalize(raw: dict[str, Any] | None) -> dict[str, Any]:
    """把 DB 文档补齐成完整结构（新增字段用默认值兜底，避免旧文档缺键）。"""
    base = default_config()
    doc = {**(raw or {})}
    defaults = {**base["defaults"], **(doc.get("defaults") or {})}
    gameplay = {**base["gameplay"], **(doc.get("gameplay") or {})}
    return {
        "require_invite": bool(doc.get("require_invite", base["require_invite"])),
        "registration_open": bool(doc.get("registration_open", base["registration_open"])),
        "announcement": str(doc.get("announcement") or ""),
        "defaults": {
            "daily_new_char_target": _clamp_int(defaults.get("daily_new_char_target"), 1, 50, 8),
            "daily_review_target": _clamp_int(defaults.get("daily_review_target"), 1, 100, 20),
            "daily_time_limit_min": _clamp_int(defaults.get("daily_time_limit_min"), 5, 240, 20),
        },
        "gameplay": _normalize_gameplay(gameplay, base["gameplay"]),
        "grades": _normalize_grades(doc.get("grades")),
    }


def _normalize_gameplay(raw: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
    types = _allowed_types(raw.get("enabled_question_types"))
    if not types:
        # 一个题型都不许 = 孩子进去没题可答，这不是合法状态，回落到默认全集
        types = list(base["enabled_question_types"])
    return {
        "stage_test_every": _clamp_int(
            raw.get("stage_test_every"), STAGE_TEST_EVERY_MIN, STAGE_TEST_EVERY_MAX, 5
        ),
        "enabled_question_types": types,
        "enable_speak": _as_bool(raw.get("enable_speak"), True),
        "show_pictograph": _as_bool(raw.get("show_pictograph"), True),
        "speak_rate": round(_clamp_float(raw.get("speak_rate"), SPEAK_RATE_MIN, SPEAK_RATE_MAX, 0.8), 2),
    }


def _allowed_types(value: Any) -> list[str]:
    """只保留认识的题型，并**按固定顺序**去重 —— 顺序影响客户端题型轮换的可预期性。"""
    if not isinstance(value, (list, tuple, set)):
        return list(GAMEPLAY_QUESTION_TYPES)
    picked = {str(v) for v in value}
    return [t for t in GAMEPLAY_QUESTION_TYPES if t in picked]


def _as_bool(value: Any, default: bool) -> bool:
    """`None` / 缺键一律走默认值。

    为什么不用 `bool(value)` 兜底：DB 里被写成 `null`（人工改库、或早先版本的
    写入路径）不该等于「把开关关掉」—— 那会让一次无关的写入静默改变全体孩子的玩法。
    """
    if value is None:
        return default
    return bool(value)


def _clamp_int(value: Any, low: int, high: int, fallback: int) -> int:
    try:
        ivalue = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(low, min(high, ivalue))


def _clamp_float(value: Any, low: float, high: float, fallback: float) -> float:
    try:
        fvalue = float(value)
    except (TypeError, ValueError):
        return fallback
    if fvalue != fvalue:  # NaN
        return fallback
    return max(low, min(high, fvalue))


async def load_config(repo: Any) -> dict[str, Any]:
    """启动时载入：DB 有值读 DB；没有则写入默认值。返回并缓存。"""
    global _cache
    doc = await repo.get_site()
    if doc is None:
        doc = {"_id": SITE_DOC_ID, **default_config(), "created_at": _now()}
        await repo.save_site(doc, now=_now())
    _cache = _normalize(doc)
    return _cache


def get_config() -> dict[str, Any]:
    """读取当前配置（未载入时回落到默认值，保证任何调用点都拿得到完整结构）。"""
    return _cache if _cache is not None else default_config()


def is_invite_required() -> bool:
    return bool(get_config().get("require_invite"))


def is_registration_open() -> bool:
    return bool(get_config().get("registration_open"))


def gameplay_config() -> dict[str, Any]:
    """玩法配置（客户端行为开关）。返回副本，避免调用方就地改坏缓存。"""
    return _normalize_gameplay(get_config().get("gameplay") or {}, default_gameplay())


async def update_config(repo: Any, patch: dict[str, Any]) -> dict[str, Any]:
    """合并并落库，随后刷新缓存。只接受白名单字段（`UPDATABLE_KEYS`），其余忽略。

    `None` 值一律跳过：调用方用 `model_dump(exclude_none=True)` 表达「这个字段没传」，
    真要写入 `null` 的场景（如清空公告）走空串，不走 `None`。
    """
    global _cache
    current = _normalize(get_config())
    merged = dict(current)
    for key, value in patch.items():
        if key not in UPDATABLE_KEYS or value is None:
            continue
        if key in ("defaults", "gameplay") and isinstance(value, dict):
            merged[key] = {**current[key], **value}
        elif key == "grades":
            # 年级表是**整表替换**而非合并：运营「删掉一个年级」时，
            # 合并语义会让被删的年级因为还在 current 里而删不掉。
            # 写入走严格校验（不静默回落），否则运营传了非法值会静默变成默认年级表
            # ——「我明明保存了怎么又变回一年级」。
            merged[key] = _normalize_grades_and_validate(value)
        else:
            merged[key] = value
    normalized = _normalize(merged)
    await repo.save_site({"_id": SITE_DOC_ID, **normalized}, now=_now())
    _cache = normalized
    return normalized
