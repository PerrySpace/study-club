/**
 * 内容域实体类型 —— 与 docs/03-数据设计/02-数据字典.md §四 一一对应。
 *
 * ⚠️ 字段一律保持契约原样（snake_case）：
 *    内容包 JSON == `/content/*` 接口响应 == 本地缓存对象 == 本文件类型。
 *    这样「随包 → 远端静态 → 轻后端」三条路径共用同一套解析逻辑，
 *    且「纯本地」与「有后端」体验完全一致（见 02-4 §3.3）。
 */

import type { CharStructure, ContentStatus, LevelType, PoemSource, ThemeTag } from '../constants';

export interface PolyphoneReading {
  pinyin: string;
  tone: number;
  meaning: string;
  usage: string;
  note: string | null;
}

export interface UnitRef {
  unit_id: string;
  unit_name: string;
  group_name: string | null;
  order: number;
}

export interface Character {
  _id: string;
  char: string;
  pinyin: string;
  pinyin_plain: string;
  tone: number;
  is_polyphone: boolean;
  polyphone_readings: PolyphoneReading[];
  radical: string;
  stroke_count: number;
  structure: CharStructure;
  stroke_order_ref: string | null;
  meaning: string;
  words: string[];
  sentences: string[];
  pictograph: string | null;
  /**
   * 字源图形 —— 「看图选字」题干的**主图**。
   *
   * 三种形态混存，按优先级取图（图片 > emoji）：
   *   1. **图片链接**：`https://…`（客户端才会请求；后台预览不加载外链）
   *   2. **站内素材 id**：`as_…`，对应素材中心上传后的图片
   *   3. **emoji**：`💧`、`⛰️`
   *
   * 为什么保留 emoji：给 500 个字配插图是巨大的素材工作量，
   * 而 emoji 天生就是象形、零上传、零版权风险，是**兜底那一层**。
   * 需要更精细的配图时用链接或素材，此时图片表现力更强。
   *
   * ⚠️ 两种都必须是**字义联想**，不是装饰图 —— 孩子靠这张图建立字义，
   * 配错图比不配图更糟。
   */
  glyph: string | null;
  image_ref: string | null;
  audio_ref: string | null;
  grade: number;
  level: LevelType;
  difficulty: number;
  tags: string[];
  similar_chars: string[];
  antonym: string | null;
  synonyms: string[];
  unit_refs: UnitRef[];
  status: ContentStatus;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface PoemLine {
  text: string;
  pinyin: string;
  meaning: string;
}

export interface PoemUnitRef {
  unit_id: string;
  grade: number;
  unit_name: string;
}

export interface Poem {
  _id: string;
  title: string;
  dynasty: string;
  author: string;
  lines: PoemLine[];
  full_text: string;
  audio_ref: string | null;
  appreciation: string;
  background: string | null;
  key_characters: string[];
  grade: number;
  unit_ref: PoemUnitRef | null;
  theme_tags: ThemeTag[];
  difficulty: number;
  source: PoemSource;
  status: ContentStatus;
  created_at: string;
  updated_at: string;
}

export interface CurriculumUnit {
  _id: string;
  unit_code: string;
  title: string;
  theme: string;
  grade: string;
  grade_num: number;
  semester: '上' | '下';
  organize_by: 'theme' | 'difficulty' | 'radical' | 'custom';
  character_ids: string[];
  focus: string;
  unit_type: '识字' | '古诗' | '拓展';
  order: number;
  status: ContentStatus;
}

export interface LessonUnlockRules {
  required_lesson_id: string | null;
  min_stars: number;
}

/**
 * 关卡。
 *
 * ⚠️ 关卡**不再手写**（`content/lessons/lessons.json` 已退役）：
 * 现在由 `algorithms/lessons.ts` 从内容自动切分生成，运营只能通过
 * `order`（排序位置）与 `tag_label`（关卡名）两个 override 微调。
 *
 * `_id` 形如 `literacy:1:3`（`轨道:年级:序号`）：**不用随机 id**，
 * 因为关卡要能被稳定引用（解锁链 `required_lesson_id` 指向它），
 * 而「同样的内容生成同样的 id」才能让已完成的进度在下一次生成后仍然对得上。
 */
export interface Lesson {
  _id: string;
  title: string;
  level: LevelType;
  order: number;
  character_ids: string[];
  game_types: string[];
  unlock_rules: LessonUnlockRules;
  poem_id: string | null;
  unit_id: string | null;
  status: ContentStatus;
  created_at: string;
  /** 内容线：识字 / story（孩子端叫识字短文）/ 古诗 —— 客户端学习地图按它分三块。 */
  track?: 'literacy' | 'story' | 'poem';
  /** 运营自定义的关卡名（无覆盖时为自动标签名）。 */
  tag_label?: string;
  /** 所属年级（自动生成时写入，供地图按年级分段）。 */
  grade?: number;
}

export interface Story {
  _id: string;
  title: string;
  type: 'story' | 'rhyme';
  level: LevelType;
  grade: number;
  text: string;
  highlight_characters: string[];
  audio_ref: string | null;
  unlock_after_lesson_ids: string[];
  word_count: number;
  status: ContentStatus;
}

export interface Badge {
  _id: string;
  code: string;
  title: string;
  description: string;
  icon_ref: string | null;
  condition: {
    type: 'lesson_count' | 'char_count' | 'streak_days' | 'poem_count' | 'accuracy';
    value: number;
  };
  order: number;
  status: 'active' | 'inactive';
}

/** 内容包清单（见 04-1 §1.8）。 */
export interface ContentManifestFile {
  path: string;
  checksum: string;
  bytes: number;
  count: number;
}

export interface ContentManifest {
  content_version: string;
  min_app_version: string;
  updated_at: string;
  counts: Record<string, number>;
  files: ContentManifestFile[];
}

/** 客户端解析后的内容包（内存形态）。 */
export interface ContentBundle {
  manifest: ContentManifest;
  characters: Character[];
  poems: Poem[];
  units: CurriculumUnit[];
  lessons: Lesson[];
  stories: Story[];
  badges: Badge[];
}

export const EMPTY_BUNDLE: ContentBundle = {
  manifest: {
    content_version: '0.0.0',
    min_app_version: '0.0.0',
    updated_at: new Date(0).toISOString(),
    counts: {},
    files: [],
  },
  characters: [],
  poems: [],
  units: [],
  lessons: [],
  stories: [],
  badges: [],
};
