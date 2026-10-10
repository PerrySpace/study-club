"""徽章数据驱动判定（03-2 §6.1）。"""

from __future__ import annotations

from app.controllers.badges import evaluate_badges

DEFS = [
    {"code": "first_lesson", "title": "第一课", "condition": {"type": "lesson_count", "value": 1}, "status": "active"},
    {"code": "char_50", "title": "认识五十字", "condition": {"type": "char_count", "value": 50}, "status": "active"},
    {"code": "streak_7", "title": "坚持一周", "condition": {"type": "streak_days", "value": 7}, "status": "active"},
    {"code": "legacy", "title": "停用", "condition": {"type": "char_count", "value": 1}, "status": "inactive"},
]


def test_unlocks_eligible_badges_only():
    newly = evaluate_badges(badge_defs=DEFS, earned_codes=set(), metrics={"lesson_count": 1, "char_count": 10})
    codes = {b["code"] for b in newly}
    assert codes == {"first_lesson"}
    assert all("title" in b for b in newly)


def test_skips_already_earned():
    newly = evaluate_badges(badge_defs=DEFS, earned_codes={"first_lesson"}, metrics={"lesson_count": 5, "char_count": 60})
    codes = {b["code"] for b in newly}
    assert codes == {"char_50"}


def test_inactive_badge_never_unlocks():
    newly = evaluate_badges(badge_defs=DEFS, earned_codes=set(), metrics={"char_count": 999})
    assert "legacy" not in {b["code"] for b in newly}


def test_missing_metric_does_not_unlock():
    newly = evaluate_badges(badge_defs=DEFS, earned_codes=set(), metrics={"lesson_count": 1})
    assert {b["code"] for b in newly} == {"first_lesson"}
