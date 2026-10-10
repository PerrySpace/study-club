/**
 * ⭐ 跨语言一致性检查：TS 生成器（core）vs Python 生成器（api/seed）。
 *
 * 为什么要它：关卡在**服务端**落库、在**客户端**消费，两侧各有一份生成逻辑。
 * 一旦漂移，症状是「后台看到 14 关、客户端渲染 13 关」——
 * 这种问题的根因极难定位（两边单测都通过，但合起来对不上）。
 *
 * 用法：先跑 Python 侧把结果写成 JSON，再跑本脚本对比。
 *   cd apps/api && python -m pytest tests/test_lesson_generator.py
 *   python -m app.seed.dump_generated > /tmp/py.json   # 或用下方等价命令
 */
import { readFileSync } from 'node:fs';

import { generateLessons } from '../packages/core/src/algorithms/lessons.ts';

const FIXTURE = JSON.parse(readFileSync('scripts/test-fixture-content.json', 'utf8'));

const ts = generateLessons({
  characters: FIXTURE.characters,
  poems: FIXTURE.poems,
  stories: FIXTURE.stories,
  targetGrade: FIXTURE.targetGrade,
  // ⚠️ overrides 在 options 里（不是顶层）—— 这个位置约定本身就是一次
  // 「参数传错位置 → override 静默失效」的坑，故在此显式标注。
  options: { charsPerLesson: FIXTURE.charsPerLesson, overrides: FIXTURE.overrides },
});

const py = JSON.parse(readFileSync('scripts/test-generated-py.json', 'utf8'));

const norm = (l) => ({
  _id: l._id,
  title: l.title,
  order: l.order,
  track: l.track,
  tag_label: l.tag_label,
  grade: l.grade,
  status: l.status,
  character_ids: l.character_ids,
  game_types: l.game_types,
  required: l.unlock_rules?.required_lesson_id ?? null,
});

const a = ts.map(norm);
const b = py.map(norm);

if (a.length !== b.length) {
  console.log(`❌ 关卡数量不同：TS ${a.length} vs Python ${b.length}`);
  process.exit(1);
}

let bad = 0;
for (let i = 0; i < a.length; i += 1) {
  const x = JSON.stringify(a[i]);
  const y = JSON.stringify(b[i]);
  if (x !== y) {
    bad += 1;
    if (bad <= 3) {
      console.log(`\n❌ 第 ${i + 1} 关不一致：`);
      console.log('  TS     :', x);
      console.log('  Python :', y);
    }
  }
}

if (bad) {
  console.log(`\n共 ${bad} 关不一致 —— 两侧规则已漂移，必须同步修改后重跑`);
  process.exit(1);
}
console.log(`✅ 两侧生成结果完全一致（${a.length} 关）`);
