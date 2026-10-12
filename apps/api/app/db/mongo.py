"""MongoDB 连接与索引初始化（motor 异步）。

两条硬要求：
1. **幂等**：启动时重复执行不报错；集合不存在也能创建（MongoDB 会隐式建集合）。
2. **索引对齐文档**：每条索引对应 03-1 / 03-2 各节的「索引」行，不即兴发明。
"""

from __future__ import annotations

from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING as ASC
from pymongo import DESCENDING as DESC
from pymongo import TEXT

from ..core.config import settings
from . import collections as C

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongodb_uri, uuidRepresentation="standard")
    return _client


def get_database() -> AsyncIOMotorDatabase:
    return get_client()[settings.mongodb_db]


async def close_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


def _index_specs() -> dict[str, list[tuple[list[tuple[str, Any]], dict[str, Any]]]]:
    """返回 集合名 → [(keys, options)]。options 里的 name 便于幂等与排查。"""
    return {
        C.ACCOUNTS: [
            ([("invite_code_hash", ASC)], {"unique": True, "sparse": True, "name": "uq_invite_code_hash"}),
            # 用户名 / 手机号二选一，均为唯一；sparse 让未填的账号不参与唯一约束
            ([("username", ASC)], {"unique": True, "sparse": True, "name": "uq_username"}),
            ([("phone", ASC)], {"unique": True, "sparse": True, "name": "uq_phone"}),
            ([("status", ASC), ("created_at", DESC)], {"name": "status_created"}),
        ],
        C.INVITES: [
            ([("code_hash", ASC)], {"unique": True, "name": "uq_code_hash"}),
            ([("batch_id", ASC), ("revoked_at", ASC)], {"name": "batch_revoked"}),
            ([("expires_at", ASC)], {"sparse": True, "name": "expires_at"}),
        ],
        C.RECOVERY_CODES: [
            ([("account_id", ASC)], {"unique": True, "name": "uq_account"}),
            ([("code_hash", ASC)], {"name": "code_hash"}),
        ],
        C.CHILDREN: [
            ([("account_id", ASC)], {"name": "account"}),
            ([("account_id", ASC), ("status", ASC)], {"name": "account_status"}),
        ],
        C.DEVICES: [
            # 会话归属键：**(account_id, client_id)** —— 一台设备一条记录，多地可同时登入。
            #
            # ⛔ 原来写的是 `unique + sparse`，而 `sparse` 在**复合索引**上不生效
            #    （官方语义：复合 sparse 只在「所有索引键都缺失」时跳过文档，只要
            #    account_id 有值就会被索引进，client_id 缺失就存成 null）。
            #    之所以至今没炸，只是因为 `ClientContext.device_key` 永不返回空串
            #    （`client_id or rate_limit_key`，后者是 sha256 十六进制）⇒ 每条
            #    devices 文档都带 client_id。改成 partial 后语义与「实际生效的行为」
            #    完全一致，但不再依赖那个隐式前提 —— 这是 answer_records 踩过的同一个坑
            #    （见下面 uq_client_record 的注释）。
            (
                [("account_id", ASC), ("client_id", ASC)],
                {
                    "unique": True,
                    "partialFilterExpression": {"client_id": {"$type": "string"}},
                    "name": "uq_account_client_id",
                },
            ),
            ([("account_id", ASC), ("client", ASC)], {"name": "account_client"}),
            ([("refresh_token_hash", ASC)], {"sparse": True, "name": "refresh_token_hash"}),
            ([("last_active_at", DESC)], {"name": "last_active"}),
        ],
        C.CHARACTERS: [
            ([("char", ASC)], {"unique": True, "name": "uq_char"}),
            ([("grade", ASC), ("difficulty", ASC)], {"name": "grade_difficulty"}),
            ([("level", ASC), ("status", ASC)], {"name": "level_status"}),
            ([("tags", ASC)], {"name": "tags"}),
            ([("unit_refs.unit_id", ASC)], {"name": "unit_refs_unit_id"}),
            ([("status", ASC)], {"name": "status"}),
            ([("char", TEXT), ("meaning", TEXT), ("words", TEXT)], {"name": "text_search"}),
        ],
        C.POEMS: [
            ([("title", ASC)], {"name": "title"}),
            ([("grade", ASC), ("difficulty", ASC)], {"name": "grade_difficulty"}),
            ([("theme_tags", ASC)], {"name": "theme_tags"}),
            ([("source", ASC)], {"name": "source"}),
            ([("key_characters", ASC)], {"name": "key_characters"}),
        ],
        C.CURRICULUM_UNITS: [
            ([("unit_code", ASC)], {"unique": True, "name": "uq_unit_code"}),
            ([("grade_num", ASC), ("semester", ASC), ("order", ASC)], {"name": "grade_semester_order"}),
        ],
        C.LESSONS: [
            ([("level", ASC), ("order", ASC)], {"name": "level_order"}),
            ([("unit_id", ASC)], {"name": "unit_id"}),
        ],
        C.ASSETS: [
            ([("type", ASC), ("subtype", ASC)], {"name": "type_subtype"}),
            ([("storage_key", ASC)], {"unique": True, "sparse": True, "name": "uq_storage_key"}),
            ([("status", ASC)], {"name": "status"}),
        ],
        C.STORIES: [
            ([("level", ASC), ("grade", ASC)], {"name": "level_grade"}),
            ([("status", ASC)], {"name": "status"}),
        ],
        C.BADGES: [
            ([("code", ASC)], {"unique": True, "name": "uq_code"}),
        ],
        C.CHILD_BADGES: [
            ([("child_id", ASC), ("badge_code", ASC)], {"unique": True, "name": "uq_child_badge"}),
        ],
        C.LEARNING_RECORDS: [
            ([("child_id", ASC), ("occurred_at", DESC)], {"name": "child_occurred"}),
            ([("child_id", ASC), ("event_type", ASC), ("occurred_at", DESC)], {"name": "child_event_occurred"}),
            ([("client", ASC), ("occurred_at", DESC)], {"name": "client_occurred"}),
        ],
        C.ANSWER_RECORDS: [
            ([("child_id", ASC), ("character_id", ASC), ("occurred_at", DESC)], {"name": "child_char_occurred"}),
            ([("child_id", ASC), ("is_correct", ASC), ("occurred_at", DESC)], {"name": "child_correct_occurred"}),
            # 幂等去重（04-1 §1.5）：同一孩子下 client_record_id 唯一；离线补报可安全重放。
            #
            # ⛔ 必须是 partialFilterExpression，**不能写 sparse**。
            #    复合索引的 sparse 只在「所有索引键都缺失」时才跳过文档，而 child_id
            #    永远有值 ⇒ 没带幂等键的上报仍会被索引进 (child_id, null)，
            #    于是「同一孩子下只能存下 1 条不带 client_record_id 的答题记录」，
            #    第 2 条起必然 E11000 → POST /learning/answer 500。
            #    而网页端**从来不传** client_record_id（那是离线补报专用）⇒ 每个孩子
            #    从第 2 题起全部 500：答题明细、错题本、复习状态、正确率统计一起哑掉，
            #    结果页还会因为上报抛错而恒显示「答对 0/6、0%」（见 stores/learning.ts）。
            #    不加兜底时就会全线如此。
            #    partial 只索引「client_record_id 是字符串」的文档，正好等于我们要的语义。
            (
                [("child_id", ASC), ("client_record_id", ASC)],
                {
                    "unique": True,
                    "partialFilterExpression": {"client_record_id": {"$type": "string"}},
                    "name": "uq_client_record",
                },
            ),
        ],
        C.CHAR_REVIEW_STATES: [
            ([("child_id", ASC), ("next_review_at", ASC)], {"name": "child_next_review"}),
            ([("child_id", ASC), ("character_id", ASC)], {"unique": True, "name": "uq_child_char"}),
        ],
        C.WRONG_QUESTIONS: [
            ([("child_id", ASC), ("resolved", ASC), ("last_wrong_at", DESC)], {"name": "child_resolved_last"}),
        ],
        C.DAILY_TASKS: [
            ([("child_id", ASC), ("date", ASC)], {"unique": True, "name": "uq_child_date"}),
        ],
        C.SYNC_OBJECTS: [
            ([("account_id", ASC), ("object_type", ASC), ("object_key", ASC)], {"unique": True, "name": "uq_account_object"}),
            ([("updated_at", DESC)], {"name": "updated_at"}),
        ],
        C.STATS_EVENTS: [
            ([("bucket_date", ASC), ("event_name", ASC)], {"name": "bucket_event"}),
            ([("content_ref", ASC)], {"sparse": True, "name": "content_ref"}),
        ],
        C.FEEDBACKS: [
            ([("status", ASC), ("created_at", DESC)], {"name": "status_created"}),
            ([("category", ASC)], {"name": "category"}),
        ],
        C.AUDIT_LOGS: [
            ([("created_at", DESC)], {"name": "created_at"}),
            ([("action", ASC), ("created_at", DESC)], {"name": "action_created"}),
            ([("target_collection", ASC), ("target_id", ASC)], {"name": "target"}),
        ],
    }


# 参与「定义是否一致」比对的索引选项。其余字段（`v`、`background` 等）由 MongoDB
# 自行填写，不参与比较，否则每次启动都会误判成「定义变了」而反复重建。
_INDEX_COMPARED_OPTIONS = ("unique", "sparse", "partialFilterExpression", "expireAfterSeconds")

# 布尔型选项：显式 false 与缺省等价（MongoDB 一般不回填 false），必须归一化
_INDEX_BOOL_OPTIONS = ("unique", "sparse")


def _freeze(value: Any) -> Any:
    """把嵌套结构变成可比较的不可变形态（dict/list 本身不能直接比）。"""
    if isinstance(value, dict):
        return tuple(sorted((str(k), _freeze(v)) for k, v in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(v) for v in value)
    return value


def index_signature(keys: Any, options: dict[str, Any]) -> tuple:
    """索引的「可比签名」：键序 + 影响语义的选项。

    `keys` 既接受定义里的 `[("child_id", 1), ...]`，也接受 MongoDB 回读的 SON/dict。
    键序参与比较 —— 复合索引的字段顺序有语义，不能排序后比较。
    """
    pairs = keys.items() if isinstance(keys, dict) else keys
    # 索引值不只有 1/-1：文本索引是 "text"，还能是 "2dsphere" / "hashed" 等字符串
    key_sig = tuple((str(k), v if isinstance(v, str) else int(v)) for k, v in pairs)
    opt_sig = []
    for key in _INDEX_COMPARED_OPTIONS:
        if key not in options:
            if key in _INDEX_BOOL_OPTIONS:
                opt_sig.append((key, False))
            continue
        if key in _INDEX_BOOL_OPTIONS:
            opt_sig.append((key, bool(options[key])))
        elif options[key] is not None:
            opt_sig.append((key, _freeze(options[key])))
    return (key_sig, tuple(opt_sig))


def index_needs_rebuild(existing: dict[str, Any] | None, keys: Any, options: dict[str, Any]) -> bool:
    """同名索引是否与期望定义不一致（不一致就必须删掉重建）。

    为什么必须显式处理：MongoDB 的 `createIndex` 遇到**同名但定义不同**的索引会直接
    报 `IndexOptionsConflict` 而**不会**去改它，旧的错误定义会一直留着、永不自愈。
    踩过这个坑：`uq_client_record` 定为 sparse 后，库里那条旧的非 sparse 索引一直没被替换，
    导致答题接口从第 2 题起全部 500，而启动日志只有一行容易被忽略的 `[index] 创建失败`。
    """
    if existing is None:
        return False
    return index_signature(existing.get("key") or {}, existing) != index_signature(keys, options)


def _is_text_index(keys: Any) -> bool:
    """文本索引（`TEXT` / "text"）不能走签名比对，原因见 init_indexes 里的注释。"""
    pairs = keys.items() if isinstance(keys, dict) else keys
    return any(v == TEXT for _, v in pairs)


async def init_indexes(db: AsyncIOMotorDatabase) -> None:
    """幂等创建全部索引；同名但定义已变的索引会被**删掉重建**。集合不存在时由 MongoDB 隐式创建。

    ⚠️ 文本索引（`characters.text_search`）是例外，**只 create、不做重建判定**：
    MongoDB 回读文本索引时会把 key 改写成 `{_fts: "text", _ftsx: 1}`（权重挪进
    `weights`），与定义里的字段名根本对不上 ⇒ 签名比对必然判为「已变更」，
    于是每次启动都白白 drop+create 一遍。
    文本索引定义极少变，退回「直接 create、冲突则记日志」即可；哪天真要改字段，
    手动 `drop_index("text_search")` 一次就行。
    """
    for coll_name, specs in _index_specs().items():
        coll = db[coll_name]
        existing: dict[str, dict[str, Any]] = {}
        try:
            async for idx in coll.list_indexes():
                name = idx.get("name")
                if name:
                    existing[name] = dict(idx)
        except Exception as exc:  # noqa: BLE001 - 集合可能还不存在 / 权限不足
            print(f"[index] 读取现有索引失败 {coll_name}: {exc}")

        for keys, options in specs:
            name = options.get("name")
            current = existing.get(name) if name else None
            if _is_text_index(keys):
                current = None
            elif index_needs_rebuild(current, keys, options):
                # 先删后建。风险由调用方兜住（整个循环对每个索引单独 try），
                # 且绝大多数情况下新定义都比旧定义**更宽松**（如 non-sparse → partial），
                # 因此重建不会因为既有数据不满足约束而失败。
                print(f"[index] {coll_name}.{name} 定义已变更，删除旧索引后重建")
                try:
                    await coll.drop_index(name)
                    current = None
                except Exception as exc:  # noqa: BLE001 - 删不掉就保持原样，不影响启动
                    print(f"[index] 删除旧索引失败 {coll_name}.{name}: {exc}")
            if current is not None:
                continue
            try:
                await coll.create_index(keys, **options)
            except Exception as exc:  # noqa: BLE001
                # 索引冲突（如既有索引同名但定义不同）不应阻断启动，但要能看见
                print(f"[index] 创建失败 {coll_name} {name}: {exc}")
