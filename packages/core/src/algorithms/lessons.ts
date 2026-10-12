/**
 * 关卡自动生成 —— 把「内容 + 人工干预」合成关卡序列。
 *
 * ## 为什么要自动生成
 * 手写 `lessons.json` 有两个必然的痛点：
 *   ① **内容一变，关卡就得重排** —— 加 10 个字要手工插关、调顺序、挪解锁链；
 *   ② **教学顺序被内容包的物理顺序绑架** —— 编辑在 JSON 里的排列顺序
 *      悄悄变成了孩子的学习顺序，而没有人真正设计过它。
 *
 * ## 为什么还要留人工干预点
 * 自动生成只能保证「稳定且合理」，保证不了「运营想要」。
 * 因此保留两个 override（见 `LessonOverride`）：
 *   - `order`：强制某关的排序位置（其余关自动让位）；
 *   - `tag_label`：给关卡起一个运营自定义的名字（「数字宝宝」而不是「第 1 关」）。
 * 这让运营能微调，而**不需要回头改生成算法**。
 *
 * ## 纪律：同样的输入必须得到同样的输出
 * 生成结果被持久化（写回 lessons），若同一天两次生成得到不同顺序，
 * 就会出现「内容没改，关卡却变了」—— 已完成的孩子进度会错位。
 * 因此这里的排序**全部使用确定性比较**（难度 → 显式 order → _id 兜底），
 * 绝不使用随机或依赖对象键顺序。
 *
 * 本模块是纯函数、零平台依赖（core 纪律），可被服务端与客户端共用。
 */

import type { Character, Lesson, Poem, Story } from '../types/content';
import type { LevelType } from '../constants';

/** 一关默认几个字。 */
export const DEFAULT_CHARS_PER_LESSON = 6;

/**
 * 生成关卡的年级上限默认值。
 *
 * 取 30 —— 与后端 `runtime_config.GRADE_MAX` 对齐，语义是「不限」：
 * 内容有多少年级就生成多少。后台把年级扩到 7/8/9 后无需改代码。
 */
export const DEFAULT_TARGET_GRADE = 30;

/** 关卡默认标签名（运营可用 override 改）。 */
export const DEFAULT_LESSON_TAG_LABEL = '综合';

/** 内容的三条线 —— 与客户端学习地图的首屏三选一对应。 */
export const TRACKS = ['literacy', 'story', 'poem'] as const;
export type Track = (typeof TRACKS)[number];

export const TRACK_LABEL: Record<Track, string> = {
  literacy: '识字',
  story: '识字短文',
  poem: '古诗',
};

/**
 * 人工干预项。
 *
 * `lesson_id` 用**生成前的稳定身份**（`{track}:{grade}:{序号}`）而不是关卡 `_id`，
 * 因为 `_id` 里含序号，一旦重排就变了 —— 用序号做键会让 override 在重排后失效。
 */
export interface LessonOverride {
  /** 强制排序位置（1 起）。冲突时按 id 字典序取第一个，其余顺延。 */
  order?: number;
  /** 关卡显示名。 */
  tag_label?: string;
  /** 停用该关（不下发）。 */
  disabled?: boolean;
}

/** 生成结果里附带的信息：客户端地图要按 track 分组渲染。 */
export interface GeneratedLesson extends Lesson {
  track: Track;
  /** 运营自定义的关卡名（override.tag_label），无覆盖时等于自动标签名。 */
  tag_label: string;
  /** 所属年级的分组键（同一 track 下按它切段）。 */
  grade: number;
}

interface GenerateOptions {
  /** 每关几个字（默认 6）。太大会一关十几分钟，太小则频繁切页。 */
  charsPerLesson?: number;
  /** 人工干预。 */
  overrides?: Record<string, LessonOverride>;
  /** 起点时间戳：新关卡的 created_at。缺省用固定值以保证可重现。 */
  createdAt?: string;
}

/** 生成用的最小来源结构（字 / 诗 / 故事都可以塞进来）。 */
interface SourceItem {
  _id: string;
  title: string;
  difficulty?: number;
  tags?: string[];
}

const DEFAULT_CREATED_AT = '1970-01-01T00:00:00.000Z';

/** 稳定的关卡身份：不受重排影响。 */
function stableKey(track: Track, grade: number, index: number): string {
  return `${track}:${grade}:${index}`;
}

/**
 * 内容**自身**年级。
 *
 * ⛔ 只能对「字段缺失」回落 1 —— `??` 正是这个语义（`0` = 学龄前必须保留）。
 * 服务端 Python 侧曾写成 `item.get("grade") or 1`，`0` 被 falsy 吞掉、
 * 学龄前内容静默升成一年级；两边因此生成出不同的关卡。必须逐字对齐。
 */
function gradeOf(item: { grade?: number | null }): number {
  return item.grade ?? 1;
}

/**
 * 年级 → 难度档位。学龄前（≤0）是 `sprout`，7 年级及以上跨到 `bridge`。
 *
 * ⛔ 不要写成 `('grade' + Math.max(1, grade))`：那会把学龄前摊成 `grade1`。
 * 与后端 `lesson_generator._level_for_grade` 逐条对应。
 */
function levelOf(grade: number): LevelType {
  if (grade <= 0) return 'sprout';
  if (grade <= 6) return `grade${grade}` as LevelType;
  return 'bridge';
}

/**
 * 确定性排序：难度升序 → `_id`。
 *
 * ⛔ 曾在这里读过 `Character.order`，但**内容包里根本没有这个字段**
 * （`char.schema.json` 也没声明）—— 加进类型只会让 TS 编译通过、运行时恒为
 * `undefined`，排序退化成「只按难度 + id」，与预期不符。
 * 因此只保留真实存在的两个键。教学顺序要调整，走 override 文件。
 *
 * `_id` 兜底**不可省**：两个字 difficulty 相同时，它们的相对顺序若取决于
 * 输入数组顺序，就会「内容没改、关卡却变了」。
 */
function sortCharacters(a: SourceItem, b: SourceItem): number {
  const d = (a.difficulty ?? 0) - (b.difficulty ?? 0);
  if (d !== 0) return d;
  return a._id.localeCompare(b._id);
}

function gameTypesFor(track: Track): string[] {
  // 故事关不做「看图选字」：故事的图是插画，不是字义，题型语义不匹配
  if (track === 'story') return ['meaning-choice', 'pinyin-match', 'speak'];
  return ['image-choice', 'audio-choice', 'pinyin-match', 'word-build', 'meaning-choice'];
}

function chunk<T>(items: T[], size: number): T[][] {
  const out: T[][] = [];
  for (let i = 0; i < items.length; i += size) out.push(items.slice(i, i + size));
  return out;
}

/**
 * 应用排序 override。
 *
 * 做法：先按 override.order 把关卡**抽出来放到指定位置**，其余保持原相对顺序填空。
 * 这样运营钉住「第 3 关是数字宝宝」后，其余关自动顺延，
 * 而不是互相挤掉导致关卡总数变化。
 *
 * ⚠️ 两个必须保证的性质，缺一个就会让地图出现重复节点或空位：
 *   ① **关卡顺序不重复、总数不变**（`order` 是链式解锁的依据，重复会让
 *      「下一关」指向自己）；
 *   ② 完成后**重排 `order` 字段**，否则 `order=1` 可能出现在第 3 位 ——
 *      界面若按 `order` 排序就会与实际位置矛盾。
 */
function applyOrderOverrides(
  lessons: GeneratedLesson[],
  overrides: Record<string, LessonOverride>,
): GeneratedLesson[] {
  const pinnedIndexes: Array<{ index: number; order: number }> = [];
  const takenSlots = new Set<number>();
  lessons.forEach((lesson, index) => {
    const want = overrides[lesson._id]?.order;
    if (typeof want !== 'number' || !Number.isInteger(want) || want < 1) return;
    // 越界（超出关卡总数）或两个 override 钉同一位置 → 跳过，
    // 不能互相覆盖：后者会被静默丢弃，这比报错更难排查
    if (want > lessons.length || takenSlots.has(want)) return;
    takenSlots.add(want);
    pinnedIndexes.push({ index, order: want });
  });

  if (!pinnedIndexes.length) return relinkUnlocks(lessons);

  // 先按目标位置铺好被钉住的关卡
  const slots: (GeneratedLesson | null)[] = new Array(lessons.length).fill(null);
  for (const p of pinnedIndexes) slots[p.order - 1] = lessons[p.index];

  // 其余按原顺序填空。
  // ⛔ 循环条件**不能**加 `cursor < rest.length`：钉住的位可能排在后面，
  // 一旦前面的 rest 先填完就提前退出，后面的钉住位会被 `filter` 挤掉 ——
  // 表现是「override 写了没生效」，且只在钉住位置靠后时才出现，极难查。
  const pinnedSourceIndexes = new Set(pinnedIndexes.map((p) => p.index));
  const rest = lessons.filter((_, i) => !pinnedSourceIndexes.has(i));
  let cursor = 0;
  for (let i = 0; i < slots.length; i += 1) {
    if (slots[i] === null && cursor < rest.length) slots[i] = rest[cursor++];
  }

  const filled = slots.filter((s): s is GeneratedLesson => s !== null);
  // 理论上不会走到这里（rest 数量恰好等于空位数）；真走到了说明 override
  // 有异常，宁可返回原序列也不要返回一个**长度变了**的结果。
  if (filled.length !== lessons.length) return lessons;

  // ⭐ 重排 order：解锁链与界面排序都以它为准，必须与实际位置一致
  const ordered = filled.map((lesson, i) => ({ ...lesson, order: i + 1 }));
  return relinkUnlocks(ordered);
}

/**
 * 按最终顺序重建线性解锁链：第 N 关依赖第 N-1 关，首关无前置。
 *
 * 为什么必须**在 override 之后**重建：解锁链表达的是「实际的前一关」，
 * 而不是「序号的前一关」。override 挪动了关卡位置，两者就不一样了。
 * 旧实现里这个 bug 的后果是：某个孩子被要求先完成一个已经不存在于
 * 该位置的关卡，界面上表现为「第一关点不动」。
 */
function relinkUnlocks(lessons: GeneratedLesson[]): GeneratedLesson[] {
  return lessons.map((lesson, i) => ({
    ...lesson,
    unlock_rules: {
      ...lesson.unlock_rules,
      required_lesson_id: i === 0 ? null : (lessons[i - 1]?._id ?? null),
    },
  }));
}

/** 生成一条线（识字 / 识字短文 / 古诗）下的全部关卡。 */
function generateTrack(
  track: Track,
  grade: number,
  source: SourceItem[],
  overrides: Record<string, LessonOverride>,
  options: Required<Pick<GenerateOptions, 'charsPerLesson'>> & { createdAt: string },
): GeneratedLesson[] {
  const ordered = source.slice().sort(sortCharacters);

  const groups = track === 'poem' || track === 'story' ? chunk(ordered, 1) : chunk(ordered, options.charsPerLesson);

  const built: GeneratedLesson[] = groups.map((group, i) => {
    const key = stableKey(track, grade, i + 1);
    const ov = overrides[key] ?? {};
    return {
      _id: key,
      // title 保留内容原名（识字线是单字、古诗线是诗题），供后台与日志辨认
      title: group[0]?.title ?? `${TRACK_LABEL[track]} ${i + 1}`,
      level: levelOf(grade),
      order: i + 1,
      character_ids: group.map((g) => g._id),
      game_types: gameTypesFor(track),
      unlock_rules: {
        // 线性解锁：本关的前一关。首关 null（永远可玩）。
        // ⚠️ 这里先用**未 override 的序号**占位，稍后 `relinkUnlocks` 会按最终
        // 顺序重算 —— 否则运营钉住某关到第 3 位后，解锁链会指向「序号 2」
        // 那个已经被挪走的关卡，孩子可能被一扇不存在的门卡住。
        required_lesson_id: null,
        min_stars: 0,
      },
      poem_id: null,
      unit_id: null,
      status: ov.disabled ? 'offline' : 'published',
      created_at: options.createdAt,
      track,
      tag_label: ov.tag_label?.trim() || defaultTagLabel(track, group, i),
      grade,
    };
  });

  return applyOrderOverrides(built, overrides);
}

/**
 * 自动关卡名。
 *
 * 分三种情况：
 *   - **识字**：用本关字的**共同标签**（「数字」「自然」）+ 序号 —— 有信息量，
 *     孩子和家长看一眼就知道这关学什么；同一标签连续出现时靠序号区分。
 *   - **古诗**：用**诗题**（静夜思 / 咏鹅）—— 一关一首诗，诗题就是最好的名字。
 *   - **故事**：用**故事标题** —— 同上。
 *
 * 后两条线一关一条内容，名字直接取内容本身；只有识字线需要「归纳出这一组是什么」。
 */
function defaultTagLabel(
  track: Track,
  group: SourceItem[],
  index: number,
): string {
  if (track !== 'literacy') {
    return group[0]?.title || `${TRACK_LABEL[track]} ${index + 1}`;
  }
  const counts = new Map<string, number>();
  for (const item of group) {
    for (const t of item.tags ?? []) counts.set(t, (counts.get(t) ?? 0) + 1);
  }
  // 取本关出现最多的标签；平手时按标签名排序保证确定性
  const top = [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))[0];
  return top ? `${top[0]} ${index + 1}` : `${TRACK_LABEL[track]} ${index + 1}`;
}

/**
 * 主入口：由内容生成全部关卡（三条线 × **每个年级各一条**）。
 *
 * ## 为什么按「内容自身年级」分桶
 * 旧实现用单一 `targetGrade` 取「该年级及以下」的池子，却只产出 `grade = targetGrade`
 * 的关卡。两个后果都真实发生过：
 *   ① 学龄前（`grade=0`）的内容被摊进一年级 —— 导入过却「看不见」；
 *   ② 学龄前孩子（`grade=0`）在客户端按 `lesson.grade <= 孩子年级` 过滤后
 *      **一关都看不到**（关卡 grade 最小也是 1）。
 *
 * 改成每年级各自成线后：`grade=0` 的内容只进 `grade=0` 的关卡；一年级孩子仍按
 * 「该年级及以下」看到 0 年级 + 1 年级两条线 —— 语义不变、互不污染。
 *
 * 与后端 `lesson_generator.py::generate_lessons` **逐条对应**，改动必须同步。
 *
 * @param targetGrade 年级**上限**（含）。默认 `DEFAULT_TARGET_GRADE`，
 *                   即「内容有多少年级就生成多少」。
 */
export function generateLessons(params: {
  characters: Character[];
  poems?: Poem[];
  stories?: Story[];
  targetGrade?: number;
  options?: GenerateOptions;
}): GeneratedLesson[] {
  const options = {
    charsPerLesson: params.options?.charsPerLesson ?? DEFAULT_CHARS_PER_LESSON,
    createdAt: params.options?.createdAt ?? DEFAULT_CREATED_AT,
  };
  const overrides = params.options?.overrides ?? {};
  const ceiling = params.targetGrade ?? DEFAULT_TARGET_GRADE;

  /** 按自身年级分桶；只留已发布、且不超过上限的。 */
  function bucket<T extends { status?: string; grade?: number | null }>(items: T[]): Map<number, T[]> {
    const map = new Map<number, T[]>();
    for (const item of items) {
      if (item.status !== 'published') continue;
      const g = gradeOf(item);
      if (g > ceiling) continue;
      const list = map.get(g);
      if (list) list.push(item);
      else map.set(g, [item]);
    }
    return map;
  }

  const charBuckets = bucket(params.characters);
  const poemBuckets = bucket(params.poems ?? []);
  const storyBuckets = bucket(params.stories ?? []);
  const ascending = (a: number, b: number): number => a - b;

  // 输出顺序保持「按线分组」（识字 → 古诗 → 故事），线内按年级升序 ——
  // 与后端实现一致。
  const out: GeneratedLesson[] = [];

  for (const grade of [...charBuckets.keys()].sort(ascending)) {
    const pool: SourceItem[] = (charBuckets.get(grade) ?? []).map((c) => ({
      _id: c._id,
      title: c.char,
      difficulty: c.difficulty,
      tags: c.tags,
    }));
    out.push(...generateTrack('literacy', grade, pool, overrides, options));
  }

  for (const grade of [...poemBuckets.keys()].sort(ascending)) {
    const src: SourceItem[] = (poemBuckets.get(grade) ?? []).map((p) => ({
      _id: p._id,
      title: p.title,
      difficulty: p.difficulty,
      tags: p.theme_tags,
    }));
    out.push(...generateTrack('poem', grade, src, overrides, options));
  }

  for (const grade of [...storyBuckets.keys()].sort(ascending)) {
    const src: SourceItem[] = (storyBuckets.get(grade) ?? []).map((s) => ({
      _id: s._id,
      title: s.title,
      // 故事统一难度 1：故事的目的是「读得有趣」，不是考字认得准不准。
      difficulty: 1,
      tags: undefined,
    }));
    out.push(...generateTrack('story', grade, src, overrides, options));
  }

  return out;
}
