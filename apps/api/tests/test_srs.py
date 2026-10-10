"""SRS 复习调度纯函数（03-2 §5.3）。"""

from __future__ import annotations

from datetime import datetime, timezone

from app.controllers import srs


def _base():
    return {"ease_factor": 2.5, "interval_days": 0, "repetitions": 0, "total_correct": 0, "total_wrong": 0}


def test_first_correct_gives_one_day():
    out = srs.compute_next(**_base(), is_correct=True)
    assert out["repetitions"] == 1
    assert out["interval_days"] == 1
    assert out["last_result"] == "correct"
    assert out["total_correct"] == 1
    assert out["status"] == srs.REVIEWING


def test_second_correct_gives_six_days():
    out = srs.compute_next(ease_factor=2.5, interval_days=1, repetitions=1, total_correct=1, total_wrong=0, is_correct=True)
    assert out["interval_days"] == 6
    assert out["repetitions"] == 2


def test_third_correct_multiplies_ease():
    out = srs.compute_next(ease_factor=2.5, interval_days=6, repetitions=2, total_correct=2, total_wrong=0, is_correct=True)
    # ceil(6 * 2.5) 取整后 >= 15
    assert out["interval_days"] >= 15
    assert out["repetitions"] == 3


def test_wrong_resets_repetitions_and_shortens_interval():
    out = srs.compute_next(ease_factor=2.5, interval_days=20, repetitions=5, total_correct=5, total_wrong=0, is_correct=False)
    assert out["repetitions"] == 0
    assert out["interval_days"] == 1
    assert out["ease_factor"] == 2.3
    assert out["last_result"] == "wrong"
    assert out["total_wrong"] == 1


def test_ease_factor_floor_is_1_3():
    out = srs.compute_next(ease_factor=1.3, interval_days=1, repetitions=0, total_correct=0, total_wrong=9, is_correct=False)
    assert out["ease_factor"] == 1.3


def test_status_mastered_over_60_days():
    assert srs.status_for(61) == srs.MASTERED
    assert srs.status_for(60) == srs.REVIEWING
    assert srs.status_for(0) == srs.LEARNING


# ---------------------------------------------------------------------------
# 「已认 vs 掌握」双条件（对标主流识字产品的家长报告口径）
# ---------------------------------------------------------------------------
def test_status_mastered_by_consecutive_streak():
    """连续答对达到 MASTERY_STREAK 即判掌握 —— 不必熬到 61 天。"""
    assert srs.status_for(1, srs.MASTERY_STREAK) == srs.MASTERED
    assert srs.status_for(1, srs.MASTERY_STREAK - 1) == srs.REVIEWING


def test_status_two_conditions_are_independent():
    """任一条件成立即掌握：短间隔但连对、或长间隔但刚错完，都算。"""
    assert srs.status_for(2, srs.MASTERY_STREAK) == srs.MASTERED  # 靠连对
    assert srs.status_for(90, 0) == srs.MASTERED  # 靠长间隔
    assert srs.status_for(0, 0) == srs.LEARNING


def test_consecutive_correct_accumulates_on_correct():
    out = srs.compute_next(
        ease_factor=2.5,
        interval_days=1,
        repetitions=1,
        total_correct=1,
        total_wrong=0,
        consecutive_correct=1,
        is_correct=True,
    )
    assert out["consecutive_correct"] == 2
    assert out["status"] == srs.REVIEWING  # 才 2 次，还没到 3 次


def test_mastery_is_revocable_on_wrong():
    """答错即撤销「掌握」：掌握的是「当前还稳」，不是「曾经稳过」。"""
    out = srs.compute_next(
        ease_factor=2.5,
        interval_days=40,
        repetitions=9,
        total_correct=9,
        total_wrong=0,
        consecutive_correct=5,  # 已掌握
        is_correct=False,
    )
    assert out["consecutive_correct"] == 0
    assert out["status"] == srs.REVIEWING


def test_three_in_a_row_reaches_mastered_through_compute_next():
    """走真实的三次连对：1 天 → 6 天 → 15 天，第 3 次即判掌握。"""
    state = srs.initial_state()
    for _ in range(3):
        state = {
            **state,
            **srs.compute_next(
                ease_factor=state["ease_factor"],
                interval_days=state["interval_days"],
                repetitions=state["repetitions"],
                total_correct=state["total_correct"],
                total_wrong=state["total_wrong"],
                consecutive_correct=state["consecutive_correct"],
                is_correct=True,
            ),
        }
    assert state["consecutive_correct"] == srs.MASTERY_STREAK
    assert state["status"] == srs.MASTERED


def test_next_review_at_uses_now():
    now = datetime(2026, 10, 8, tzinfo=timezone.utc)
    out = srs.compute_next(**_base(), is_correct=True, now=now)
    assert out["next_review_at"] == datetime(2026, 10, 9, tzinfo=timezone.utc)


def test_initial_state():
    state = srs.initial_state()
    assert state["ease_factor"] == 2.5
    assert state["interval_days"] == 0
    assert state["status"] == srs.LEARNING
