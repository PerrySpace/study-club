"""⭐ 跨语言一致性门禁：Python 生成器必须与 core 的 TS 实现结果相同。

## 为什么这道门禁不可省
关卡在**服务端**落库（seed 导入时算好写进 `lessons` 集合）、在**客户端**消费。
两侧各有一份生成逻辑（`apps/api/app/seed/lesson_generator.py` 与
`packages/core/src/algorithms/lessons.ts`），因为关卡要先落库、客户端又需要即时重算。

一旦漂移，症状是「后台看到 14 关、客户端渲染 13 关」——
**两侧单测都通过，但合起来对不上**，根因极难定位。

## 实测已抓到过的两个真实漂移
1. TS 的填空循环条件多了 `cursor < rest.length`：钉住的位排在后面时会提前退出，
   后面的钉住位被 `filter` 挤掉 → 「override 写了没生效」。
2. `generateLessons` 的 `overrides` 在 `options` 里，传到顶层会**静默失效**
   （不报错、不抛异常，只是全部用自动标签名）。

## 环境依赖
需要 node（跑 TS 侧）。**node 不可用时跳过而不是失败** ——
这条门禁是加分项，不该在没装 node 的机器上把整条流水线搞挂。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# tests/ → apps/api/ → apps/ → 仓库根
REPO_ROOT = Path(__file__).resolve().parents[3]
PARITY_SCRIPT = REPO_ROOT / "scripts" / "test-lessons-parity.mts"
FIXTURE = REPO_ROOT / "scripts" / "test-fixture-content.json"
PY_OUT = REPO_ROOT / "scripts" / "test-generated-py.json"

NODE = shutil.which("node") or shutil.which("node.exe")

pytestmark = pytest.mark.skipif(NODE is None, reason="未安装 node，无法跑 TS 侧生成器")


@pytest.fixture(scope="module")
def parity_result() -> None:
    """跑一次一致性检查；失败时 pytest 直接报出来。"""
    from app.seed.lesson_generator import generate_lessons

    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    generated = generate_lessons(
        characters=fixture["characters"],
        poems=fixture["poems"],
        stories=fixture["stories"],
        target_grade=fixture["targetGrade"],
        chars_per_lesson=fixture["charsPerLesson"],
        overrides=fixture["overrides"],
    )
    PY_OUT.write_text(json.dumps(generated, ensure_ascii=False), encoding="utf-8")

    proc = subprocess.run(
        [NODE, "--experimental-strip-types", str(PARITY_SCRIPT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc.returncode == 0, (
        "生成器跨语言不一致（TS vs Python）：\n"
        f"{proc.stdout}\n{proc.stderr}\n"
        "两侧规则已漂移，必须同步修改 algorithms/lessons.ts 与 lesson_generator.py。"
    )


def test_generators_match(parity_result: None):
    """两侧在相同输入下必须产出**完全相同**的关卡序列。"""
