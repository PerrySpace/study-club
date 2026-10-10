"""徽章判定（03-2 §6.1）：把写死在代码里的规则改为数据驱动的条件配置。

答题后立即判定并返回新解锁徽章，前端可即时弹窗（04-1 §五），避免额外请求。
"""

from __future__ import annotations


def evaluate_badges(
    *,
    badge_defs: list[dict],
    earned_codes: set[str],
    metrics: dict[str, float],
) -> list[dict]:
    """返回本次新解锁的徽章定义（含 code/title）。未达阈值或不满足条件不返回。"""
    newly: list[dict] = []
    for badge in badge_defs:
        code = badge.get("code")
        if not code or code in earned_codes:
            continue
        if badge.get("status") not in (None, "active"):
            continue
        condition = badge.get("condition") or {}
        ctype = condition.get("type")
        threshold = condition.get("value")
        if ctype is None or threshold is None:
            continue
        current = metrics.get(ctype)
        if current is None:
            continue
        if float(current) >= float(threshold):
            newly.append({"code": code, "title": badge.get("title", code)})
    return newly
