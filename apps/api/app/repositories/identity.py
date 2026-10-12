"""身份域仓储：账号 / 邀请码 / 恢复码 / 设备会话。

「彻底服务端」之后这些集合承担全部身份状态，且**每一步都要能审计**。
密码与邀请码只以哈希形式出现在这里，明文一律不落库。
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from .base import BaseRepository


class AccountRepository(BaseRepository):
    collection = "accounts"

    async def find_by_invite_hash(self, invite_code_hash: str) -> dict | None:
        return await self.find_one({"invite_code_hash": invite_code_hash})

    async def find_by_username(self, username: str) -> dict | None:
        return await self.find_one({"username": username})

    async def find_by_phone(self, phone: str) -> dict | None:
        return await self.find_one({"phone": phone})

    async def find_by_identifier(self, identifier: str) -> dict | None:
        """按「用户名或手机号」查账号（统一登录入口用）。

        不做格式判断：分别按两个字段各查一次，命中即返回。
        两个唯一索引保证各自唯一，因此最多命中一个。
        """
        ident = (identifier or "").strip()
        if not ident:
            return None
        account = await self.find_by_username(ident)
        if account is None:
            account = await self.find_by_phone(ident)
        return account

    async def list_page(
        self,
        *,
        skip: int,
        limit: int,
        keyword: str | None = None,
        status: str | None = None,
        role: str | None = None,
        has_children: bool | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> tuple[list[dict], int]:
        """后台「用户列表」分页。

        ⚠️ 只暴露账号级信息，**不下钻学习明细**（儿童数据最小化，见 05-1 §1.3）。

        `has_children` 用 `$lookup` 子查询表达「至少有一个孩子档案」——
        不能先把 children 全查出来在内存里过滤，那是一次全表扫描。
        """
        flt: dict[str, Any] = {}
        if status:
            flt["status"] = status
        else:
            # 默认不含已注销（软删）账号
            flt["status"] = {"$ne": "deleted"}
        if role:
            flt["role"] = role
        if created_from or created_to:
            window: dict[str, Any] = {}
            if created_from:
                window["$gte"] = created_from
            if created_to:
                window["$lte"] = created_to
            flt["created_at"] = window
        if keyword:
            kw = re.escape(keyword.strip())
            flt["$or"] = [
                {"username": {"$regex": kw, "$options": "i"}},
                {"phone": {"$regex": kw, "$options": "i"}},
                {"display_name": {"$regex": kw, "$options": "i"}},
            ]

        pipeline: list[dict] = [{"$match": flt}]
        if has_children is not None:
            pipeline.append(
                {
                    "$lookup": {
                        "from": "children",
                        "let": {"aid": "$_id"},
                        "pipeline": [
                            {"$match": {"$expr": {"$eq": ["$account_id", "$$aid"]}}},
                            {"$limit": 1},
                        ],
                        "as": "_child_probe",
                    }
                }
            )
            pipeline.append(
                {"$addFields": {"_has_children": {"$gt": [{"$size": "$_child_probe"}, 0]}}}
            )
            pipeline.append({"$match": {"_has_children": has_children}})
            pipeline.append({"$unset": "_child_probe"})

        if has_children is None:
            total = await self.count(flt)
        else:
            counted = await self.db["accounts"].aggregate(
                pipeline + [{"$count": "n"}]
            ).to_list(length=1)
            total = int(counted[0]["n"]) if counted else 0

        pipeline.append({"$sort": {"created_at": -1}})
        pipeline.append({"$skip": skip})
        pipeline.append({"$limit": limit})
        pipeline.append({"$unset": "_has_children"})
        rows = await self.db["accounts"].aggregate(pipeline).to_list(length=limit)
        for row in rows:
            # 密码/密文相关字段一律不出口
            row.pop("passcode_hash", None)
            row.pop("sync_key_salt", None)
        return rows, total

    async def count_by_status(self) -> dict[str, int]:
        return await self.count_by("status")

    async def set_status(self, account_id, *, status: str, now: datetime) -> bool:
        res = await self.update_one(
            {"_id": account_id}, {"$set": {"status": status, "updated_at": now}}
        )
        return res.matched_count > 0

    async def find_by_id_str(self, account_id: str) -> dict | None:
        from bson import ObjectId
        from bson.errors import InvalidId

        try:
            oid = ObjectId(account_id)
        except (InvalidId, TypeError):
            return None
        return await self.find_one({"_id": oid})

    async def update_profile(
        self, account_id, *, patch: dict[str, Any], now: datetime
    ) -> bool:
        """后台编辑账号资料。

        ⚠️ **字段白名单在控制器层**（`admin_controller`）：这里只负责落库，
        不做业务判断。`passcode_hash` / `invite_code_hash` / `sync_key_salt`
        绝不能出现在 `patch` 里 —— 改登录凭据必须走各自的专用方法，
        否则会绕过密码哈希校验与登录锁定逻辑。
        """
        if not patch:
            return await self.exists({"_id": account_id})
        patch = {**patch, "updated_at": now}
        res = await self.update_one({"_id": account_id}, {"$set": patch})
        return res.matched_count > 0

    async def set_display_name(self, account_id, *, display_name: str | None, now: datetime) -> bool:
        return await self.update_profile(account_id, patch={"display_name": display_name}, now=now)

    async def set_avatar_key(self, account_id, *, avatar_key: str | None, now: datetime) -> bool:
        return await self.update_profile(account_id, patch={"avatar_key": avatar_key}, now=now)

    async def count_active_children(self, account_id) -> int:
        return await self.db["children"].count_documents({"account_id": account_id, "status": "active"})

    async def mark_login(self, account_id, *, now: datetime) -> None:
        await self.update_one(
            {"_id": account_id},
            {"$set": {"failed_attempts": 0, "locked_until": None, "last_login_at": now, "updated_at": now}},
        )

    async def register_failure(self, account_id, *, attempts: int, lock_until: datetime | None, now: datetime) -> None:
        patch: dict[str, Any] = {"failed_attempts": attempts, "updated_at": now}
        if lock_until is not None:
            patch["locked_until"] = lock_until
        await self.update_one({"_id": account_id}, {"$set": patch})

    async def set_passcode(self, account_id, *, passcode_hash: str, now: datetime) -> None:
        await self.update_one(
            {"_id": account_id},
            {
                "$set": {
                    "passcode_hash": passcode_hash,
                    "failed_attempts": 0,
                    "locked_until": None,
                    "updated_at": now,
                }
            },
        )

    async def set_sync_salt(self, account_id, salt: str) -> None:
        await self.update_one({"_id": account_id}, {"$set": {"sync_key_salt": salt}})

    async def get_sync_salt(self, account_id) -> str | None:
        doc = await self.find_one({"_id": account_id}, {"sync_key_salt": 1})
        return (doc or {}).get("sync_key_salt")

    async def soft_delete(self, account_id, *, now: datetime) -> None:
        """注销：软删账号 + 释放邀请码占用（保留审计线索，不再可登录）。"""
        await self.update_one(
            {"_id": account_id},
            {"$set": {"status": "deleted", "updated_at": now, "invite_code_hash": None}},
        )


class InviteRepository(BaseRepository):
    collection = "invites"

    async def find_by_code_hash(self, code_hash: str) -> dict | None:
        return await self.find_one({"code_hash": code_hash})

    async def consume(self, invite_id, account_id) -> bool:
        """原子消耗一次邀请码：仅当仍有剩余次数时才 +1（并发安全）。"""
        updated = await self.coll.find_one_and_update(
            {"_id": invite_id, "$expr": {"$lt": ["$used_count", "$max_uses"]}},
            {"$inc": {"used_count": 1}, "$push": {"bound_account_ids": account_id}},
        )
        return updated is not None

    async def insert_batch(self, docs: list[dict]) -> int:
        if not docs:
            return 0
        return await self.insert_many(docs)

    async def list_page(
        self,
        *,
        skip: int,
        limit: int,
        batch_id: str | None = None,
        channel: str | None = None,
    ) -> tuple[list[dict], int]:
        flt: dict[str, Any] = {}
        if batch_id:
            flt["batch_id"] = batch_id
        if channel:
            flt["channel"] = channel
        # 不返回完整哈希，只回 code_hint（防泄漏）
        total = await self.count(flt)
        items = await self.find_many(flt, sort=[("created_at", -1)], skip=skip, limit=limit, projection={"code_hash": 0})
        return items, total

    async def revoke(self, invite_id, *, now: datetime) -> bool:
        res = await self.update_one({"_id": invite_id, "revoked_at": None}, {"$set": {"revoked_at": now}})
        return res.matched_count > 0

    async def usage_totals(self) -> dict[str, int]:
        row = await self.aggregate_one(
            [
                {
                    "$group": {
                        "_id": None,
                        "used": {"$sum": {"$ifNull": ["$used_count", 0]}},
                        "capacity": {"$sum": {"$ifNull": ["$max_uses", 0]}},
                    }
                }
            ]
        )
        return {
            "used_count": int((row or {}).get("used", 0)),
            "capacity": int((row or {}).get("capacity", 0)),
        }

    async def batch_count(self) -> int:
        return len([b for b in await self.distinct("batch_id") if b])

    async def revoked_count(self) -> int:
        return await self.count({"revoked_at": {"$ne": None}})


class RecoveryCodeRepository(BaseRepository):
    collection = "recovery_codes"

    async def find_by_hash(self, code_hash: str) -> dict | None:
        return await self.find_one({"code_hash": code_hash})

    async def issue(self, *, account_id, code_hash: str, now: datetime) -> None:
        await self.insert_one(
            {"account_id": account_id, "code_hash": code_hash, "used_at": None, "created_at": now}
        )

    async def mark_used(self, doc_id, *, now: datetime) -> None:
        await self.update_one({"_id": doc_id}, {"$set": {"used_at": now}})


class DeviceRepository(BaseRepository):
    collection = "devices"

    async def find_by_refresh_hash(self, refresh_token_hash: str) -> dict | None:
        return await self.find_one({"refresh_token_hash": refresh_token_hash})

    async def upsert_session(self, *, account_id, client, refresh_token_hash: str, now: datetime) -> None:
        """按 **(account_id, client_id)** 落一条设备会话记录。

        ⚠️ 这条过滤条件是「多地同时登入」的关键：一台设备一条记录、各自持有自己的
        Refresh Token。若换成按账号 upsert（或不带 client_id），后登录的设备会覆盖
        先登录设备的 Refresh Token，先登录的那台在 Access Token 过期后就刷不回来，
        直接被踢回登录页 —— 也就是「一台登录、另一台掉线」。
        """
        client_key = client.device_key
        await self.update_one(
            {"account_id": account_id, "client_id": client_key},
            {
                "$set": {
                    "account_id": account_id,
                    "client_id": client_key,
                    "client": client.client,
                    "platform": client.platform,
                    "device_form": client.device_form,
                    "app_version": client.client_version,
                    "os_version": None,
                    "device_model": None,
                    "refresh_token_hash": refresh_token_hash,
                    "revoked": False,
                    "last_active_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )

    async def rotate_refresh(self, device_id, *, refresh_token_hash: str, now: datetime) -> None:
        await self.update_one(
            {"_id": device_id},
            {"$set": {"refresh_token_hash": refresh_token_hash, "last_active_at": now}},
        )

    async def revoke_by_refresh_hash(self, *, account_id, refresh_token_hash: str) -> None:
        await self.update_one(
            {"account_id": account_id, "refresh_token_hash": refresh_token_hash},
            {"$set": {"revoked": True}},
        )

    async def revoke_all(self, account_id) -> None:
        await self.coll.update_many({"account_id": account_id}, {"$set": {"revoked": True}})

    async def purge_account(self, account_id) -> int:
        return await self.delete_many({"account_id": account_id})


class SyncObjectRepository(BaseRepository):
    collection = "sync_objects"

    async def manifest(self, account_id, object_type: str | None = None) -> list[dict]:
        flt: dict[str, Any] = {"account_id": account_id}
        if object_type:
            flt["object_type"] = object_type
        return await self.find_many(
            flt,
            sort=[("updated_at", -1)],
            limit=2000,
            projection={"cipher_payload": 0},
        )

    async def revision_of(self, *, account_id, object_type: str, object_key: str) -> int | None:
        doc = await self.find_one(
            {"account_id": account_id, "object_type": object_type, "object_key": object_key},
            {"revision": 1},
        )
        return int(doc["revision"]) if doc else None

    async def put(self, *, account_id, obj, client_id: str, now: datetime) -> None:
        await self.update_one(
            {"account_id": account_id, "object_type": obj.object_type, "object_key": obj.object_key},
            {
                "$set": {
                    "account_id": account_id,
                    "object_type": obj.object_type,
                    "object_key": obj.object_key,
                    "schema_version": obj.schema_version,
                    "cipher_payload": obj.cipher_payload,
                    "cipher_algo": obj.cipher_algo,
                    "nonce": obj.nonce,
                    "revision": obj.revision,
                    "deleted": obj.deleted,
                    "client_id": client_id,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )

    async def pull(self, *, account_id, since: datetime | None, object_type: str | None) -> list[dict]:
        flt: dict[str, Any] = {"account_id": account_id}
        if object_type:
            flt["object_type"] = object_type
        if since is not None:
            flt["updated_at"] = {"$gt": since}
        return await self.find_many(flt, sort=[("updated_at", 1)], limit=2000)

    async def purge_account(self, account_id) -> int:
        return await self.delete_many({"account_id": account_id})
