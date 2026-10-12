/**
 * 题目生成 —— 识字学科专属逻辑。
 *
 * 同一批到期字，用**不同题型**轮换（看图选字 / 听音选字 / 拼音匹配 / 组词 / 跟读），
 * 避免机械记忆；题型选择依据历史表现——一直答对的字换更难的题型（见 01-3 §4.3）。
 *
 * ⚠️ 题型取值必须与后端 `content_controller.QUESTION_STEMS` 的 key 逐字一致。
 * 客户端自己造一个后端不认识的 key，会出现「前端能出题、后台配不出」的静默失效。
 */

import { QUESTION_TYPE } from '@study-club/core';
import type { Character, Question, QuestionOption, QuestionType } from '@study-club/core';

/**
 * 把一串选项文本包成结构化选项。
 * id 直接用文本本身：同一题内的选项文本已去重（`pickDistractors` 保证），因此天然唯一。
 * 用文本而非下标做 id，是为了让「选中了哪个」在题目重排后仍然稳定。
 */
function toOptions(values: string[]): QuestionOption[] {
  return values.map((value) => ({ id: value, char: value }));
}

function shuffle<T>(arr: T[]): T[] {
  const out = [...arr];
  for (let i = out.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

function pickDistractors(
  target: Character,
  pool: Character[],
  field: 'char' | 'pinyin' | 'meaning',
  count: number,
): string[] {
  const same = pool.filter((c) => c._id !== target._id);
  // 优先形近字 / 同难度字，避免「一眼就能排除」的假题。
  //
  // ⛔ 必须 `?? []`：`similar_chars` 在**后台导入的内容**里经常整片缺失
  //    （那是运营手工整理的表格，不会填「形近字」这种派生字段），而
  //    `db-first` 会保留库内版本、不会用仓库内容覆盖它。一旦直接读
  //    `target.similar_chars.includes(...)`，本函数就在 Array.filter 里抛
  //    TypeError，调用链 `startQuiz → generateQuestions` 整个中断 ——
  //    表现为「点『开始闯关』毫无反应、永远到不了结果页」，且**识字线全线
  //    如此**（运营从表格导入的内容常常整片缺该字段）。
  //    形近字只是「干扰项优先用谁」的优化，缺了退化成随机取字，完全可接受。
  const targetSimilar = target.similar_chars ?? [];
  const similar = same.filter((c) => targetSimilar.includes(c.char));
  const rest = same.filter((c) => !targetSimilar.includes(c.char));
  const ordered = [...shuffle(similar), ...shuffle(rest)];
  const values: string[] = [];
  for (const c of ordered) {
    const v = c[field];
    if (!values.includes(v) && v !== target[field]) values.push(v);
    if (values.length >= count) break;
  }
  return values;
}

/** 题型兜底顺序：偏好的题型被后台关掉时，按此顺序往后找。 */
const FALLBACK_ORDER: QuestionType[] = [
  QUESTION_TYPE.imageChoice,
  QUESTION_TYPE.meaningChoice,
  QUESTION_TYPE.audioChoice,
  QUESTION_TYPE.speak,
  QUESTION_TYPE.wordBuild,
  QUESTION_TYPE.pinyinMatch,
];

/**
 * 从「偏好顺序」里挑第一个**后台允许**的题型。
 *
 * 为什么需要它：题型开关是后台可改的运营参数（`gameplay.enabled_question_types`）。
 * 若客户端只按难度挑题型、不看开关，就会出现「后台关掉了跟读，孩子还是被要求跟读」
 * —— 麦克风权限、隐私说明、家长预期全都对不上。
 */
function firstAllowed(preferred: QuestionType[], allowed?: readonly QuestionType[]): QuestionType {
  if (!allowed || !allowed.length) return preferred[0];
  const set = new Set<string>(allowed);
  for (const type of preferred) if (set.has(type)) return type;
  for (const type of FALLBACK_ORDER) if (set.has(type)) return type;
  // 一个都不认识：服务端已做过一次过滤，走到这里说明开关值与客户端版本不匹配，
  // 用首选题型保证「至少能出题」，不让孩子卡在空题上。
  return preferred[0];
}

/**
 * 按历史表现挑题型：越熟练，题型越「难」。
 *
 * 入门档在 `image-choice` / `meaning-choice` 之间二选一 —— 二者是**同一种考法**，
 * 区别只在题干素材：有字源图（`pictograph` / `glyph`）才用看图选字，
 * 没图就老实降级成「给意思选字」。
 *
 * @param allowed 后台允许的题型（来自 `gameplay.enabled_question_types`）；
 *                不传表示不限制（古诗模块等固定题型的场景）。
 */
export function pickQuestionType(
  history: { correct: number; wrong: number },
  target?: Pick<Character, 'pictograph' | 'glyph'>,
  allowed?: readonly QuestionType[],
): QuestionType {
  const hasPicture = Boolean(target?.pictograph || target?.glyph);
  const entry: QuestionType[] = hasPicture
    ? [QUESTION_TYPE.imageChoice, QUESTION_TYPE.meaningChoice]
    : [QUESTION_TYPE.meaningChoice, QUESTION_TYPE.imageChoice];

  const total = history.correct + history.wrong;
  if (total < 2) return firstAllowed(entry, allowed);

  const accuracy = history.correct / Math.max(1, total);
  if (accuracy < 0.6) return firstAllowed(entry, allowed);

  // 中档：跟读与听音选字交替 —— 跟读能为后续「听写」打底
  if (accuracy < 0.8) {
    const preferred =
      total % 3 === 1
        ? [QUESTION_TYPE.speak, QUESTION_TYPE.audioChoice, ...entry]
        : [QUESTION_TYPE.audioChoice, QUESTION_TYPE.speak, ...entry];
    return firstAllowed(preferred, allowed);
  }

  // 熟练档：读一读 / 组词 / 拼音 三选一，避免长期只练同一种
  const cycle = total % 3;
  const advanced =
    cycle === 0
      ? [QUESTION_TYPE.speak, QUESTION_TYPE.audioChoice]
      : cycle === 1
        ? [QUESTION_TYPE.wordBuild, QUESTION_TYPE.meaningChoice]
        : [QUESTION_TYPE.pinyinMatch, QUESTION_TYPE.meaningChoice];
  return firstAllowed([...advanced, ...entry], allowed);
}

export interface GenerateOptions {
  /** 该字的答题历史（用于题型轮换） */
  history?: Map<string, { correct: number; wrong: number }>;
  /** 每题选项数（含答案） */
  optionCount?: number;
  /** 限定题型（古诗模块等场景） */
  forceType?: QuestionType;
  /**
   * 后台允许的题型白名单（`gameplay.enabled_question_types`）。
   * `forceType` 优先于它 —— 调用方显式指定的题型不该被开关悄悄换掉。
   */
  allowedTypes?: readonly QuestionType[];
}

/**
 * 题目随身带的字素材。
 *
 * ⚠️ 这些字段**必须一起下发**，哪怕当前题型用不上：
 *   ① 「给点提示」要按需展开字源 / 组词 / 拼音，没有素材就等于没有提示；
 *   ② 题面朗读要读**释义**（读字会直接把答案说出去），缺了释义只能退回读整句题干；
 *   ③ 服务端的 `/content/lessons/{id}/questions` 本来就把这些一起给，
 *      客户端自生成的题目少这些字段，会让「切到服务端出题」时界面表现**变好**——
 *      这类「越改越不对」的差异最难查，宁可在本地生成时也对齐。
 */
function materialsOf(target: Character): Pick<
  Question,
  'pinyin' | 'meaning' | 'words' | 'sentences' | 'pictograph' | 'glyph'
> {
  return {
    pinyin: target.pinyin,
    meaning: target.meaning,
    words: target.words,
    sentences: target.sentences,
    pictograph: target.pictograph,
    glyph: target.glyph,
  };
}

export function generateQuestion(
  target: Character,
  pool: Character[],
  opts: GenerateOptions = {},
): Question {
  const optionCount = Math.max(2, opts.optionCount ?? 4);
  const history = opts.history?.get(target._id);
  const type =
    opts.forceType ?? pickQuestionType(history ?? { correct: 0, wrong: 0 }, target, opts.allowedTypes);
  const id = `q_${target._id}_${type}`;
  const materials = materialsOf(target);

  switch (type) {
    case QUESTION_TYPE.audioChoice: {
      const distractors = pickDistractors(target, pool, 'char', optionCount - 1);
      return {
        id,
        question_type: type,
        character_id: target._id,
        char: target.char,
        prompt: '听一听，选出正确的字',
        options: toOptions(shuffle([target.char, ...distractors])),
        answer: target.char,
        audio_ref: target.audio_ref,
        ...materials,
      };
    }
    case QUESTION_TYPE.speak: {
      // 跟读题：没有选项。判定来自语音识别（见 reading.ts 的 readingMatches），
      // 平台不支持识别时由视图降级为「我听过了」，仍按「读到」处理 —— 但会在界面上说明。
      return {
        id,
        question_type: type,
        character_id: target._id,
        char: target.char,
        prompt: `大声读一读：${target.char}`,
        options: [],
        answer: target.char,
        audio_ref: target.audio_ref,
        ...materials,
      };
    }
    case QUESTION_TYPE.pinyinMatch: {
      const distractors = pickDistractors(target, pool, 'pinyin', optionCount - 1);
      return {
        id,
        question_type: type,
        character_id: target._id,
        char: target.char,
        prompt: `「${target.char}」读作什么？`,
        options: toOptions(shuffle([target.pinyin, ...distractors])),
        answer: target.pinyin,
        audio_ref: null,
        ...materials,
      };
    }
    case QUESTION_TYPE.meaningChoice: {
      const distractors = pickDistractors(target, pool, 'char', optionCount - 1);
      return {
        id,
        question_type: type,
        character_id: target._id,
        char: target.char,
        prompt: `「${target.meaning}」说的是哪个字？`,
        options: toOptions(shuffle([target.char, ...distractors])),
        answer: target.char,
        audio_ref: null,
        ...materials,
      };
    }
    case QUESTION_TYPE.wordBuild: {
      const word = target.words[0] ?? target.char;
      const blanked = word.replace(target.char, '◻');
      const others = pool
        .filter((c) => c._id !== target._id)
        .map((c) => c.char)
        .filter((ch) => !word.includes(ch));
      return {
        id,
        question_type: type,
        character_id: target._id,
        char: target.char,
        prompt: `补全词语：${blanked}`,
        options: toOptions(shuffle([target.char, ...shuffle(others).slice(0, optionCount - 1)])),
        answer: target.char,
        audio_ref: null,
        ...materials,
      };
    }
    case QUESTION_TYPE.imageChoice:
    default: {
      const distractors = pickDistractors(target, pool, 'char', optionCount - 1);
      return {
        id,
        question_type: QUESTION_TYPE.imageChoice,
        character_id: target._id,
        char: target.char,
        prompt: `哪个字是「${target.meaning}」？`,
        options: toOptions(shuffle([target.char, ...distractors])),
        answer: target.char,
        audio_ref: target.audio_ref,
        ...materials,
      };
    }
  }
}

export function generateQuestions(
  targets: Character[],
  pool: Character[],
  opts: GenerateOptions = {},
): Question[] {
  return targets.map((t) => generateQuestion(t, pool, opts));
}

/** 古诗填字题（S-07）。 */
export function generatePoemFillQuestion(params: {
  poemId: string;
  lineText: string;
  keyChar: string;
  pool: string[];
}): Question {
  const blanked = params.lineText.replace(params.keyChar, '◻');
  const distractors = params.pool.filter((c) => c !== params.keyChar).slice(0, 3);
  return {
    id: `qp_${params.poemId}_${params.keyChar}`,
    question_type: QUESTION_TYPE.poemFill,
    character_id: params.keyChar,
    char: params.keyChar,
    prompt: `补全诗句：${blanked}`,
    options: toOptions(shuffle([params.keyChar, ...distractors])),
    answer: params.keyChar,
    audio_ref: null,
  };
}

/**
 * 「这道题该读什么给孩子听」。
 *
 * 启蒙人群**未必识字**，题面只写在屏幕上等于没出题：孩子看不懂
 * 「听一听，选出正确的字」，只会照着选项瞎点。所以每道题都要能被朗读出来。
 *
 * 分型规则（关键是**别把答案直接读出来**）：
 *   - `audio-choice` / `speak`：本来就要听这个字的读音 → 读 `char`
 *   - `pinyin-match`：读 `char`（题干是「这个字读什么」，读字正合适）
 *   - `image-choice` / `meaning-choice`：读**释义**（读字就把答案说了）
 *   - `word-build`：读提示语 + 挖空后的词语；挖空位读作「什么」
 *   - `poem-fill`：读挖空后的诗句
 *
 * 返回 `null` 表示「这道题不适合朗读」，此时视图**不要**渲染朗读按钮。
 */
export function speechTextForQuestion(question: Pick<
  Question,
  'question_type' | 'char' | 'prompt' | 'meaning' | 'pinyin'
>): string | null {
  switch (question.question_type) {
    case QUESTION_TYPE.audioChoice:
    case QUESTION_TYPE.speak:
    case QUESTION_TYPE.pinyinMatch:
      return question.char || null;
    case QUESTION_TYPE.imageChoice:
    case QUESTION_TYPE.meaningChoice:
      // ⚠️ 必须读释义而不是读字，否则直接泄露答案
      return question.meaning ?? question.prompt ?? null;
    case QUESTION_TYPE.wordBuild:
    case QUESTION_TYPE.poemFill:
      return question.prompt.replace(/◻/g, '什么') || null;
    default:
      return question.prompt || null;
  }
}

/** 题型是否需要语音识别（跟读）来作答。 */
export function isSpeakQuestion(questionType: QuestionType): boolean {
  return questionType === QUESTION_TYPE.speak;
}

/** 题型是否是「选项式」的（跟读题没有选项，不能走选项渲染分支）。 */
export function isChoiceQuestion(questionType: QuestionType): boolean {
  return questionType !== QUESTION_TYPE.speak && questionType !== QUESTION_TYPE.stroke;
}
