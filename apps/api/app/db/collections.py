"""集合名常量 —— 与 03-1 / 03-2 的集合名逐字对齐（snake_case 复数）。

集中命名避免拼写漂移；⛔ 掩藏集合（users/otp_codes/orders/...）不在此登记，
因为它们不启用、不建索引、不可达。
"""

from __future__ import annotations

ACCOUNTS = "accounts"
INVITES = "invites"
RECOVERY_CODES = "recovery_codes"
CHILDREN = "children"
DEVICES = "devices"

CHARACTERS = "characters"
POEMS = "poems"
CURRICULUM_UNITS = "curriculum_units"
LESSONS = "lessons"
ASSETS = "assets"
STORIES = "stories"
BADGES = "badges"
# 识字短文（阅读承接）：只用**已学字**编写的短句/短文，认完字就有东西可读
READINGS = "readings"

LEARNING_RECORDS = "learning_records"
ANSWER_RECORDS = "answer_records"
CHAR_REVIEW_STATES = "char_review_states"
WRONG_QUESTIONS = "wrong_questions"
DAILY_TASKS = "daily_tasks"
CHILD_BADGES = "child_badges"

AUDIT_LOGS = "audit_logs"
SYNC_OBJECTS = "sync_objects"
STATS_EVENTS = "stats_events"
FEEDBACKS = "feedbacks"

# 内容包清单（非数据字典集合，用于承接 content/manifest.json，见 04-1 §1.8）
CONTENT_MANIFEST = "content_manifest"

# 站点运行配置（单文档：_id = "site"）—— 启动时读取，后台可改（配置中心）
APP_SETTINGS = "app_settings"

# 内容集合名 → 内容包文件路径（供 seed 与 content router 复用）
CONTENT_PATHS: dict[str, str] = {
    CHARACTERS: "content/characters/grade-1.json",
    POEMS: "content/poems/required-75.json",
    CURRICULUM_UNITS: "content/lessons/units.json",
    LESSONS: "content/lessons/lessons.json",
    STORIES: "content/stories/stories.json",
    BADGES: "content/badges/badges.json",
    READINGS: "content/readings/readings.json",
}
