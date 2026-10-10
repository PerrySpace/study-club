/**
 * 拼音比对与声调 —— 识字学科专属逻辑（**不得写进 packages/core**）。
 * 判据：这段逻辑换成英语单词还成立吗？不成立 → 属学科包。
 */

const TONE_MARKS: Record<string, Record<string, string>> = {
  a: { 1: 'ā', 2: 'á', 3: 'ǎ', 4: 'à' },
  o: { 1: 'ō', 2: 'ó', 3: 'ǒ', 4: 'ò' },
  e: { 1: 'ē', 2: 'é', 3: 'ě', 4: 'è' },
  i: { 1: 'ī', 2: 'í', 3: 'ǐ', 4: 'ì' },
  u: { 1: 'ū', 2: 'ú', 3: 'ǔ', 4: 'ù' },
  v: { 1: 'ǖ', 2: 'ǘ', 3: 'ǚ', 4: 'ǜ' },
  ü: { 1: 'ǖ', 2: 'ǘ', 3: 'ǚ', 4: 'ǜ' },
};

/** 无声调化：去掉声调符号，ü→v 统一。 */
export function toPlainPinyin(pinyin: string): string {
  return pinyin
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/ü/g, 'v')
    .replace(/\s+/g, '')
    .toLowerCase();
}

/** 取声调数字（0 = 轻声）。 */
export function toneOf(pinyin: string): number {
  const normalized = pinyin.normalize('NFD');
  const marks: Record<string, number> = {
    '\u0304': 1,
    '\u0301': 2,
    '\u030c': 3,
    '\u0300': 4,
  };
  for (const ch of normalized) {
    if (marks[ch]) return marks[ch];
  }
  return 0;
}

/** 给无声调拼音加上声调符号（用于展示与题目生成）。 */
export function applyTone(plain: string, tone: number): string {
  if (tone < 1 || tone > 4) return plain;
  const lower = plain.toLowerCase();
  // 标调优先元音顺序 a > o > e > i/u/ü（iu / ui 标后者）
  const order = ['a', 'o', 'e'];
  for (const v of order) {
    const idx = lower.indexOf(v);
    if (idx >= 0) return replaceAt(plain, idx, TONE_MARKS[v][tone]);
  }
  if (lower.includes('iu')) {
    const idx = lower.lastIndexOf('u');
    return replaceAt(plain, idx, TONE_MARKS.u[tone]);
  }
  if (lower.includes('ui')) {
    const idx = lower.lastIndexOf('i');
    return replaceAt(plain, idx, TONE_MARKS.i[tone]);
  }
  for (const v of ['i', 'u', 'v', 'ü']) {
    const idx = lower.indexOf(v);
    if (idx >= 0) return replaceAt(plain, idx, TONE_MARKS[v][tone]);
  }
  return plain;
}

function replaceAt(s: string, index: number, ch: string): string {
  return s.slice(0, index) + ch + s.slice(index + 1);
}

/** 判定读音是否匹配（忽略声调时只比拼音主体）。 */
export function pinyinMatches(input: string, expected: string, ignoreTone = false): boolean {
  const a = toPlainPinyin(input);
  const b = toPlainPinyin(expected);
  return ignoreTone ? a === b : input.trim().toLowerCase() === expected.trim().toLowerCase();
}
