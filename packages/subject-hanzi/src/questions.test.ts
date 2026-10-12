import { describe, expect, it } from 'vitest';

import type { Character } from '@study-club/core';

import { generateQuestions } from './questions';

/**
 * 造一个「字段齐全」的最小汉字，便于按需删字段做边界测试。
 * 只需要出题用得到的字段，其余按 Character 的必填形状补齐。
 */
function mk(id: string, char: string, extra: Record<string, unknown> = {}): Character {
  return {
    _id: id,
    char,
    pinyin: `pinyin-${char}`,
    pinyin_plain: 'py',
    tone: 1,
    is_polyphone: false,
    polyphone_readings: [],
    radical: '一',
    stroke_count: 1,
    structure: '独体',
    stroke_order_ref: null,
    meaning: `意思-${char}`,
    words: [`词-${char}`],
    sentences: [],
    pictograph: null,
    glyph: null,
    image_ref: null,
    audio_ref: null,
    grade: 0,
    level: 'easy',
    difficulty: 1,
    tags: [],
    similar_chars: [],
    antonym: null,
    synonyms: [],
    unit_refs: [],
    status: 'published',
    version: 1,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...extra,
  } as Character;
}

function pool(): Character[] {
  return [
    mk('ch_4e00', '一'),
    mk('ch_4e8c', '二'),
    mk('ch_4e09', '三'),
    mk('ch_56db', '四'),
    mk('ch_4e94', '五'),
    mk('ch_516d', '六'),
  ];
}

describe('generateQuestions —— 缺字段容错', () => {
  /**
   * 回归（出题遇到缺字段的内容时不能崩）：
   * 后台导入的内容普遍缺 `similar_chars`（运营手工整理，不填这种派生字段），
   * 而 `db-first` 会保留库内版本。`pickDistractors` 里直接
   * `target.similar_chars.includes(...)` 会在 Array.filter 中抛 TypeError，
   * 调用链 `startQuiz → generateQuestions` 整体中断 —— 表现为点「开始闯关」
   * 毫无反应、**识字线全线的关卡都到不了结果页**。
   */
  it('目标字缺 similar_chars —— 不抛错，且仍能出题', () => {
    const target = mk('ch_4e00', '一');
    delete (target as unknown as Record<string, unknown>).similar_chars;

    let questions: ReturnType<typeof generateQuestions> = [];
    expect(() => {
      questions = generateQuestions([target], pool(), { optionCount: 4 });
    }).not.toThrow();

    expect(questions).toHaveLength(1);
    // 干扰项不足以凑满时也至少要「目标字 + 若干干扰」，不能变成没得选
    expect(questions[0].options.length).toBeGreaterThan(1);
    expect(questions[0].options.map((o) => o.char)).toContain('一');
  });

  it('整个池子都缺 similar_chars —— 不抛错', () => {
    const p = pool();
    for (const c of p) delete (c as unknown as Record<string, unknown>).similar_chars;

    expect(() => generateQuestions(p.slice(0, 3), p, { optionCount: 4 })).not.toThrow();
  });

  it('similar_chars 为空数组（正常空值）—— 不抛错，行为与缺失一致', () => {
    const target = mk('ch_4e00', '一', { similar_chars: [] });
    expect(() => generateQuestions([target], pool(), { optionCount: 4 })).not.toThrow();
  });

  it('有 similar_chars 时，形近字优先进入干扰项', () => {
    const target = mk('ch_4e00', '一', { similar_chars: ['二', '三'] });
    const questions = generateQuestions([target], pool(), { optionCount: 3 });
    // optionCount=3 → 2 个干扰项，理应优先取走两个形近字
    const others = questions[0].options.map((o) => o.char).filter((c) => c !== '一');
    expect(others.sort()).toEqual(['三', '二'].sort());
  });
});
