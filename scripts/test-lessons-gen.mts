/**
 * 关卡自动生成的单元测试（core 是纯 JS 模块，这里用 node 直接跑）。
 *
 * 两条最要紧的性质，任何改动都不能破坏：
 *   ① **确定性** —— 同样的内容必须生成同样的关卡。否则「内容没改、关卡却变了」，
 *      已完成的孩子进度会错位（他们点的第 3 关变成了别的内容）。
 *   ② **override 不破坏解锁链** —— 运营挪动关卡后，解锁关系必须指向
 *      「实际的前一关」，否则某个孩子可能被一扇指向已移走位置的门卡住。
 */
import assert from 'node:assert/strict';

import { generateLessons, DEFAULT_CHARS_PER_LESSON } from '../packages/core/src/algorithms/lessons.ts';
import type { Character } from '../packages/core/src/types/content.ts';

function char(id: string, grade: number, difficulty: number, tags: string[] = [], order = 0): Character {
  return {
    _id: id,
    char: id.replace('ch_', ''),
    pinyin: '',
    pinyin_plain: '',
    tone: 1,
    is_polyphone: false,
    polyphone_readings: [],
    radical: '',
    stroke_count: 1,
    structure: '',
    stroke_order_ref: null,
    meaning: '',
    words: [],
    sentences: [],
    pictograph: null,
    glyph: null,
    image_ref: null,
    audio_ref: null,
    grade,
    level: `grade${grade}`,
    difficulty,
    tags,
    similar_chars: [],
    antonym: null,
    synonyms: [],
    unit_refs: [],
    status: 'published',
    version: 1,
    created_at: '2026-01-01T00:00:00.000Z',
    updated_at: '2026-01-01T00:00:00.000Z',
  } as unknown as Character;
}

function makeChars(n: number, grade = 1) {
  const tags = ['数字', '自然', '动物'];
  return Array.from({ length: n }, (_, i) =>
    char(`ch_${String(i).padStart(4, '0')}`, grade, (i % 3) + 1, [tags[i % tags.length]], i),
  );
}

// ---------------------------------------------------------------- 确定性

{
  const a = generateLessons({ characters: makeChars(18), targetGrade: 1 });
  const b = generateLessons({ characters: makeChars(18), targetGrade: 1 });
  assert.deepEqual(a, b, '同样输入必须得到同样输出');
  console.log('✅ 确定性：两次生成完全一致');
}

{
  // 输入顺序变了（编辑在 JSON 里挪了位置），生成结果不应跟着变
  const chars = makeChars(18);
  const shuffled = [chars[10], ...chars.slice(0, 10), ...chars.slice(11)];
  const a = generateLessons({ characters: chars, targetGrade: 1 });
  const b = generateLessons({ characters: shuffled, targetGrade: 1 });
  assert.deepEqual(
    a.map((l) => l._id),
    b.map((l) => l._id),
    '生成结果不得依赖输入数组的物理顺序',
  );
  console.log('✅ 确定性：打乱输入顺序不影响生成结果');
}

// ---------------------------------------------------------------- 切分

{
  const lessons = generateLessons({ characters: makeChars(18), targetGrade: 1 });
  const literacy = lessons.filter((l) => l.track === 'literacy');
  assert.equal(literacy.length, 3, '18 字 / 每关 6 字 = 3 关');
  assert.ok(literacy.every((l) => l.character_ids.length === DEFAULT_CHARS_PER_LESSON));
  console.log(`✅ 切分：18 字 → ${literacy.length} 关，每关 ${DEFAULT_CHARS_PER_LESSON} 字`);
}

{
  // 不足一关的字也要成关，不能被丢弃
  const lessons = generateLessons({ characters: makeChars(4), targetGrade: 1 });
  const literacy = lessons.filter((l) => l.track === 'literacy');
  assert.equal(literacy.length, 1, '尾数也要成关');
  assert.equal(literacy[0].character_ids.length, 4);
  assert.ok(lessons.every((l) => l.character_ids.length > 0), '不允许空关卡');
  console.log('✅ 切分：不足一关的字不会被丢弃');
}

{
  const lessons = generateLessons({ characters: makeChars(18), targetGrade: 3 });
  const literacy = lessons.filter((l) => l.track === 'literacy');
  assert.ok(literacy.every((l) => l.grade === 3), '关卡应记录目标年级');
  console.log('✅ 年级：关卡记录目标年级');
}

// ---------------------------------------------------------------- 年级过滤

{
  const chars = [...makeChars(6, 1), ...makeChars(6, 3)];
  const forGrade1 = generateLessons({ characters: chars, targetGrade: 1 });
  const ids1 = forGrade1.flatMap((l) => l.character_ids);
  assert.equal(ids1.length, 6, '一年级只应看到一年级的字');
  assert.ok(
    ids1.every((id) => id < "ch_0006"),
    '不该混入三年级内容',
  );
  console.log('✅ 年级过滤：一年级孩子看不到三年级的字');
}

{
  const chars = [...makeChars(6, 1), ...makeChars(6, 3)];
  const forGrade3 = generateLessons({ characters: chars, targetGrade: 3 });
  assert.equal(forGrade3.flatMap((l) => l.character_ids).length, 12, '三年级应看到两个年级的字');
  console.log('✅ 年级过滤：三年级看到该年级及以下');
}

// ---------------------------------------------------------------- 解锁链

{
  const lessons = generateLessons({ characters: makeChars(18), targetGrade: 1 });
  const literacy = lessons.filter((l) => l.track === 'literacy');
  assert.equal(literacy[0].unlock_rules.required_lesson_id, null, '首关永远可玩');
  for (let i = 1; i < literacy.length; i += 1) {
    assert.equal(
      literacy[i].unlock_rules.required_lesson_id,
      literacy[i - 1]._id,
      `第 ${i + 1} 关应依赖实际的前一关`,
    );
  }
  console.log('✅ 解锁链：线性且指向实际前一关');
}

{
  const ids = new Set(generateLessons({ characters: makeChars(18), targetGrade: 1 }).map((l) => l._id));
  const broken = generateLessons({ characters: makeChars(18), targetGrade: 1 }).filter(
    (l) => l.unlock_rules.required_lesson_id && !ids.has(l.unlock_rules.required_lesson_id),
  );
  assert.equal(broken.length, 0, '解锁链不得指向不存在的关卡');
  console.log('✅ 解锁链：不指向不存在的关卡');
}

// ---------------------------------------------------------------- override

{
  const base = generateLessons({ characters: makeChars(18), targetGrade: 1 });
  const target = base.find((l) => l.track === 'literacy')!;
  const after = generateLessons({
    characters: makeChars(18),
    targetGrade: 1,
    options: { overrides: { [target._id]: { order: 3, tag_label: '数字宝宝' } } },
  });
  const literacy = after.filter((l) => l.track === 'literacy');

  assert.equal(literacy[2].tag_label, '数字宝宝', 'override 应生效');
  assert.equal(literacy.length, base.filter((l) => l.track === 'literacy').length, '关卡数不应改变');

  const orders = literacy.map((l) => l.order);
  assert.deepEqual(orders, [1, 2, 3], 'order 必须重排为连续无重复');

  const idSet = new Set(literacy.map((l) => l._id));
  assert.equal(new Set(literacy.map((l) => l._id)).size, literacy.length, '不得出现重复关卡');
  for (let i = 1; i < literacy.length; i += 1) {
    assert.equal(
      literacy[i].unlock_rules.required_lesson_id,
      literacy[i - 1]._id,
      'override 后解锁链仍须指向实际前一关',
    );
  }
  for (const l of literacy) {
    if (l.unlock_rules.required_lesson_id) assert.ok(idSet.has(l.unlock_rules.required_lesson_id));
  }
  console.log('✅ override：排序 + 改名生效，且不破坏解锁链');
}

{
  // 越界的 order 不应把别的关卡挤掉
  const base = generateLessons({ characters: makeChars(12), targetGrade: 1 });
  const first = base.find((l) => l.track === 'literacy')!;
  const after = generateLessons({
    characters: makeChars(12),
    targetGrade: 1,
    options: { overrides: { [first._id]: { order: 99 } } },
  });
  const literacy = after.filter((l) => l.track === 'literacy');
  assert.equal(literacy.length, base.filter((l) => l.track === 'literacy').length);
  console.log('✅ override：越界 order 被忽略，关卡数不变');
}

{
  const base = generateLessons({ characters: makeChars(12), targetGrade: 1 });
  const lit = base.filter((l) => l.track === 'literacy');
  const after = generateLessons({
    characters: makeChars(12),
    targetGrade: 1,
    options: { overrides: { [lit[0]._id]: { disabled: true } } },
  });
  const off = after.find((l) => l._id === lit[0]._id)!;
  assert.equal(off.status, 'offline', 'disabled 的关卡应置为 offline');
  console.log('✅ override：disabled 关卡被下架');
}

// ---------------------------------------------------------------- 三条线

{
  const lessons = generateLessons({
    characters: makeChars(18),
    poems: [
      { _id: 'pm_1', title: '静夜思', difficulty: 1, grade: 1, status: 'published' },
      { _id: 'pm_2', title: '咏鹅', difficulty: 1, grade: 1, status: 'published' },
    ] as never,
    stories: [{ _id: 'st_1', title: '小兔子数星星', grade: 1, status: 'published' }] as never,
    targetGrade: 1,
  });

  const tracks = new Set(lessons.map((l) => l.track));
  assert.deepEqual([...tracks].sort(), ['literacy', 'poem', 'story'], '三条线都要有');

  const poem = lessons.find((l) => l.track === 'poem')!;
  assert.equal(poem.tag_label, '静夜思', '古诗关卡名用诗题');

  const story = lessons.find((l) => l.track === 'story')!;
  assert.equal(story.tag_label, '小兔子数星星', '故事关卡名用故事标题');

  // 故事线不做「看图选字」：故事的图是插画不是字义，题型语义不匹配
  const storyLesson = lessons.filter((l) => l.track === 'story')[0];
  assert.ok(!storyLesson.game_types.includes('image-choice'), '故事线不应有 image-choice');
  console.log('✅ 三条线：识字 / 古诗 / 故事各有关卡，命名与题型正确');
}

{
  const lessons = generateLessons({
    characters: makeChars(12),
    poems: [{ _id: 'pm_x', title: '草', difficulty: 1, grade: 1, status: 'draft' }] as never,
    targetGrade: 1,
  });
  assert.equal(lessons.filter((l) => l.track === 'poem').length, 0, 'draft 内容不应生成关卡');
  console.log('✅ 过滤：draft 内容不生成关卡');
}

console.log('\n全部通过');
