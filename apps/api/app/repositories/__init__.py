"""数据访问层（MVC —— Model 层）。

`Repositories` 是一次请求内的仓储容器：controller 只依赖它，不接触 motor。
容器自身还承载**跨集合**的编排（如注销时清理一个账号的全部学习数据），
这类操作放在单个仓储里会让职责边界变模糊。
"""

from __future__ import annotations

from typing import Any, Iterable

from motor.motor_asyncio import AsyncIOMotorDatabase

from .assets import AssetRepository
from .base import BaseRepository
from .content import (
    BadgeRepository,
    CharacterRepository,
    ContentManifestRepository,
    LessonRepository,
    PoemRepository,
    StoryRepository,
    UnitRepository,
)
from .identity import (
    AccountRepository,
    DeviceRepository,
    InviteRepository,
    RecoveryCodeRepository,
    SyncObjectRepository,
)
from .learning import (
    AnswerRecordRepository,
    ChildBadgeRepository,
    ChildRepository,
    DailyTaskRepository,
    LearningRecordRepository,
    ReviewStateRepository,
    WrongQuestionRepository,
)
from .ops import AuditLogRepository, FeedbackRepository, SettingsRepository, StatsEventRepository


class Repositories:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.db = db

        # 身份
        self.accounts = AccountRepository(db)
        self.invites = InviteRepository(db)
        self.recovery_codes = RecoveryCodeRepository(db)
        self.devices = DeviceRepository(db)
        self.sync_objects = SyncObjectRepository(db)

        # 内容
        self.characters = CharacterRepository(db)
        self.poems = PoemRepository(db)
        self.units = UnitRepository(db)
        self.lessons = LessonRepository(db)
        self.stories = StoryRepository(db)
        self.badges = BadgeRepository(db)
        self.assets = AssetRepository(db)
        self.manifest = ContentManifestRepository(db)

        # 学习
        self.children = ChildRepository(db)
        self.review_states = ReviewStateRepository(db)
        self.answer_records = AnswerRecordRepository(db)
        self.wrong_questions = WrongQuestionRepository(db)
        self.daily_tasks = DailyTaskRepository(db)
        self.learning_records = LearningRecordRepository(db)
        self.child_badges = ChildBadgeRepository(db)

        # 运维
        self.stats_events = StatsEventRepository(db)
        self.feedbacks = FeedbackRepository(db)
        self.audit_logs = AuditLogRepository(db)
        self.settings = SettingsRepository(db)

    # ------------------------------------------------------------------
    # 跨集合编排
    # ------------------------------------------------------------------
    async def purge_child_data(self, child_ids: Iterable[Any]) -> int:
        """注销账号时物理删除学习数据（合规必需）。返回删除的档案数。"""
        ids = list(child_ids)
        if not ids:
            return 0
        await self.learning_records.purge_by_children(ids)
        await self.answer_records.purge_by_children(ids)
        await self.review_states.purge_by_children(ids)
        await self.wrong_questions.purge_by_children(ids)
        await self.daily_tasks.purge_by_children(ids)
        await self.child_badges.purge_by_children(ids)
        return await self.children.delete_in("_id", ids)

    async def content_counts(self) -> dict[str, int]:
        """内容体量（清单 / 概览用）。一次聚合，避免多处各写一份。"""
        return {
            "characters": await self.characters.count(),
            "poems": await self.poems.count(),
            "units": await self.units.count(),
            "lessons": await self.lessons.count(),
            "stories": await self.stories.count(),
            "badges": await self.badges.count(),
            "assets": await self.assets.count({"status": "active"}),
        }


__all__ = [
    "Repositories",
    "BaseRepository",
    "AccountRepository",
    "InviteRepository",
    "RecoveryCodeRepository",
    "DeviceRepository",
    "SyncObjectRepository",
    "CharacterRepository",
    "PoemRepository",
    "UnitRepository",
    "LessonRepository",
    "StoryRepository",
    "BadgeRepository",
    "AssetRepository",
    "ContentManifestRepository",
    "ChildRepository",
    "ReviewStateRepository",
    "AnswerRecordRepository",
    "WrongQuestionRepository",
    "DailyTaskRepository",
    "LearningRecordRepository",
    "ChildBadgeRepository",
    "StatsEventRepository",
    "FeedbackRepository",
    "AuditLogRepository",
    "SettingsRepository",
]
