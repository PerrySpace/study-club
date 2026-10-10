"""SRS 复习调度 —— 纯函数，便于单测（06-1 §3.2）。

采用 SM-2 变体：
- 答对：repetitions+1；第 1 次间隔 1 天，第 2 次 6 天，之后按 interval × ease 递增
- 答错：repetitions 归零，间隔回到 1 天，ease 下调（下限 1.3）
- 状态：`learning` / `reviewing` / `mastered`

「掌握」的双条件（对标主流识字产品的「已认 vs 掌握」两态）：

家长要能分清「这字只是见过一面」和「这字已经稳了」——
只按 `interval_days > 60` 判掌握，孩子要熬两个月才能看到"掌握"涨一个；
只按「答对次数」判掌握，又会让连续蒙对的长间隔字提前变成"掌握"。
故**任一条件成立**即判掌握：

1. `consecutive_correct >= MASTERY_STREAK`（默认 3）—— 连续 3 次答对，
   且因为走的是 SRS 节奏，这 3 次天然跨天（1 天 → 6 天），不是同一场连点。
2. `interval_days > MASTERED_INTERVAL_DAYS`（默认 60）—— 长间隔兜底。

`consecutive_correct` 归零的门是**答错**。因此"掌握"是可撤销的：
错一次即退回 `reviewing`，符合「掌握 = 当前还稳」而不是「曾经稳过」。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

EASE_MIN = 1.3
EASE_DEFAULT = 2.5
EASE_MAX = 3.0
MASTERED_INTERVAL_DAYS = 60
# 连续答对达到该次数即判「掌握」
MASTERY_STREAK = 3

LEARNING = "learning"
REVIEWING = "reviewing"
MASTERED = "mastered"


def status_for(interval_days: int, consecutive_correct: int = 0) -> str:
    if consecutive_correct >= MASTERY_STREAK or interval_days > MASTERED_INTERVAL_DAYS:
        return MASTERED
    if interval_days > 0:
        return REVIEWING
    return LEARNING


def compute_next(
    *,
    ease_factor: float,
    interval_days: int,
    repetitions: int,
    total_correct: int,
    total_wrong: int,
    is_correct: bool,
    consecutive_correct: int = 0,
    now: datetime | None = None,
) -> dict:
    """返回更新后的复习状态字段（不包含 child_id / character_id）。"""
    now = now or datetime.now(timezone.utc)

    if is_correct:
        repetitions += 1
        if repetitions == 1:
            interval_days = 1
        elif repetitions == 2:
            interval_days = 6
        else:
            interval_days = max(1, round(interval_days * ease_factor))
        ease_factor = min(EASE_MAX, ease_factor + 0.1)
        total_correct += 1
        consecutive_correct += 1
        last_result = "correct"
    else:
        repetitions = 0
        interval_days = 1
        ease_factor = max(EASE_MIN, ease_factor - 0.2)
        total_wrong += 1
        # 答错即撤销"掌握"：掌握的是「当前还稳」，不是「曾经稳过」
        consecutive_correct = 0
        last_result = "wrong"

    return {
        "ease_factor": round(ease_factor, 3),
        "interval_days": interval_days,
        "repetitions": repetitions,
        "next_review_at": now + timedelta(days=interval_days),
        "last_result": last_result,
        "last_reviewed_at": now,
        "total_correct": total_correct,
        "total_wrong": total_wrong,
        "consecutive_correct": consecutive_correct,
        "status": status_for(interval_days, consecutive_correct),
    }


def initial_state() -> dict:
    return {
        "ease_factor": EASE_DEFAULT,
        "interval_days": 0,
        "repetitions": 0,
        "total_correct": 0,
        "total_wrong": 0,
        "consecutive_correct": 0,
        "status": LEARNING,
    }
