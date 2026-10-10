"""MongoDB 连接（motor 异步）—— core 层对外的连接入口。

实现细节（连接串、连接池、索引初始化）在 `app/db/mongo.py`：
按 06-1 §3.1，`db/` 负责「MongoDB 连接、索引初始化、聚合查询」，本模块只做薄转发，
使 core 层与依赖注入有一个稳定的入口（见 core/deps.py）。
"""

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from ..db.mongo import close_client, get_client, get_database, init_indexes

__all__ = [
    "AsyncIOMotorClient",
    "AsyncIOMotorDatabase",
    "close_client",
    "get_client",
    "get_database",
    "init_indexes",
]
