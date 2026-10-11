/**
 * 学习域类型 —— 与 03-2 §五 对应。
 *
 * ⚠️ **服务端唯一真源**：这些类型是接口出参的形状，数据以服务端为唯一真源。
 * 调度参数（ease_factor / interval_days / next_review_at）由服务端拥有并计算，
 * 客户端只做展示与提交。
 */

import type { DailyTaskStatus, QuestionType, ReviewStatus } from '../constants';

export interface ReviewState {
  /** 出参形态为 `${child_id}:${character_id}`，便于前端做 key */
  _id: string;
  child_id: string;
  character_id: string;
  ease_factor: number;
  interval_days: number;
  repetitions: number;
  /** ISO 8601 UTC */
  next_review_at: string;
  last_result: 'correct' | 'wrong';
  last_reviewed_at: string | null;
  total_correct: number;
  total_wrong: number;
  status: ReviewStatus;
}

export interface WrongQuestion {
  /** 服务端 ObjectId 字符串；解答（resolve）时要用 */
  _id: string;
  child_id: string;
  character_id: string;
  char: string;
  wrong_count: number;
  question_types: QuestionType[];
  first_wrong_at: string;
  last_wrong_at: string;
  resolved: boolean;
  resolved_at: string | null;
}

export interface LearningRecord {
  _id: string;
  child_id: string;
  event_type:
    | 'lesson_start'
    | 'lesson_complete'
    | 'poem_read'
    | 'review_session'
    | 'daily_task_complete';
  lesson_id: string | null;
  poem_id: string | null;
  character_ids: string[];
  score: number | null;
  total: number | null;
  accuracy: number | null;
  stars: number | null;
  duration_ms: number;
  client: string;
  platform: string;
  device_form: string;
  client_version: string;
  occurred_at: string;
  created_at: string;
}

export interface AnswerRecord {
  _id: string;
  child_id: string;
  character_id: string;
  char: string;
  question_type: QuestionType;
  answer: string;
  correct_answer: string;
  is_correct: boolean;
  response_ms: number;
  session_id: string;
  occurred_at: string;
}

/**
 * 今日任务里的一个字（服务端**已经把字形一起下发**）。
 *
 * ⚠️ 为什么不是裸 id 数组：`/learning/state` 与 `/learning/daily-task` 的出参刻意做成
 * 「增肥」形态（见 04-1 §`GET /learning/daily-task`），把 `char` 一并带下来，
 * 客户端因此不必为了显示一个「水」字再打一次 `/content/characters/batch`。
 *
 * ⚠️ 表里（`daily_tasks` 集合）存的仍然是 `new_char_ids` 这类 id 数组（见 03-2 §五），
 * 由服务端在这一层转成带字形的对象。**两侧字段名不同是刻意的，不是笔误** ——
 * 早先前端按表字段名读，导致首页整块「今日任务」恒为 0 并在控制台抛
 * `task.new_char_ids is not iterable`。
 */
export interface DailyTaskChar {
  /** 与 `_id` 同值，保留两个名字是为了与后端出参逐字一致 */
  id: string;
  _id: string;
  char: string | null;
}

/**
 * 今日任务（`/learning/state` 的 `daily_task`，以及 `/learning/daily-task` 的出参）。
 *
 * 注意这是**接口出参形态**，不是 `daily_tasks` 集合的文档形态：没有 `_id` / `child_id` /
 * `generated_at`，但多了 `completed_count` 与 `total_count` ——
 * `total_count` 已经由服务端**去重**（同一个字可能同时出现在复习与错题里），
 * 客户端直接拿来当进度分母即可，不要再自己 Set 去重（重复一次只会让两边口径漂移）。
 */
export interface DailyTask {
  /** YYYY-MM-DD */
  date: string;
  status: DailyTaskStatus;
  new_chars: DailyTaskChar[];
  review_chars: DailyTaskChar[];
  wrong_chars: DailyTaskChar[];
  /** 已完成字数（服务端 `completed_char_ids` 的长度） */
  completed_count: number;
  /** 去重后的任务总字数 */
  total_count: number;
}

export interface ChildBadge {
  _id: string;
  child_id: string;
  badge_code: string;
  /** 徽章定义（服务端 JOIN 下发的展示字段） */
  title?: string;
  description?: string | null;
  earned_at: string;
}

/**
 * 一道题。
 *
 * 服务端 `/content/lessons/{id}/questions` 会把**题面需要的一切**都塞进来
 * （拼音 / 释义 / 组词 / 例句 / 字理 / 配图 / 音频 / 笔顺），
 * 客户端因此不必为每道题再打一次接口。
 */
export interface Question {
  id: string;
  question_id?: string;
  question_type: QuestionType;
  character_id: string;
  char: string;
  prompt: string;
  stem?: string;
  options: QuestionOption[];
  answer: string;
  answer_character_id?: string;
  /* ---- 题面素材（服务端下发，可能为 null） ---- */
  pinyin?: string | null;
  meaning?: string | null;
  words?: string[];
  sentences?: string[];
  pictograph?: string | null;
  /** 字源图形（象形 emoji）—— 与 `image_url` 二选一即可展示，emoji 优先做兜底 */
  glyph?: string | null;
  image_url?: string | null;
  audio_url?: string | null;
  stroke_order_url?: string | null;
  /* ---- 兼容旧本地生成路径 ---- */
  audio_ref?: string | null;
}

/**
 * 选择题选项。
 *
 * ⚠️ `char` 承载的是**选项主文本**，不严格等于「汉字」：
 * 拼音题的选项是拼音、组词题的选项可能是词。
 * 之所以沿用 `char` 这个名字，是为了与后端 `/content/lessons/{id}/questions`
 * 下发的 `{ id, char }` 逐字一致 —— 前端擅自改名会让出参看起来「变了」，
 * 而两端口径不一致是最难排查的一类问题。
 *
 * `id` 通常是汉字本身（同题内选项文本已去重），服务端下发时也可能是 character_id。
 */
export interface QuestionOption {
  id: string;
  char: string;
  image_url?: string | null;
  pinyin?: string | null;
}

/** 提交一次作答（写入由服务端完成）。 */
export interface AnswerSubmission {
  child_id: string;
  character_id: string;
  char?: string | null;
  question_type: QuestionType;
  answer: string;
  correct_answer: string;
  is_correct: boolean;
  response_ms: number;
  session_id?: string | null;
  occurred_at?: string | null;
  /** 离线补偿上报的幂等键 */
  client_record_id?: string | null;
}

/** 服务端算完的结果（含下次复习时间与新解锁徽章）。 */
export interface AnswerResult {
  is_correct: boolean;
  next_review_at: string | null;
  interval_days: number;
  newly_earned_badges: Array<{ code: string; title: string }>;
}

export interface LessonCompletion {
  child_id: string;
  lesson_id?: string | null;
  event_type?: string;
  character_ids: string[];
  score?: number | null;
  total?: number | null;
  accuracy?: number | null;
  stars?: number | null;
  duration_ms?: number;
  occurred_at?: string | null;
  client_record_id?: string | null;
}

/** 服务端学习状态总览（`GET /learning/state` 的出参）。 */
export interface LearningState {
  child: {
    id: string;
    _id: string;
    nickname: string;
    grade: number;
    avatar_key: string;
    daily_new_char_target: number | null;
    daily_review_target: number | null;
    daily_time_limit_min: number | null;
  };
  progress: LearningProgress;
  daily_task: DailyTask | null;
  due_reviews: Array<{
    character_id: string;
    char: string | null;
    ease_factor: number;
    interval_days: number;
    next_review_at: string | null;
    status: ReviewStatus;
  }>;
  badges: string[];
  server_time: string;
}

export interface LearningProgress {
  total_learned: number;
  mastered: number;
  reviewing: number;
  learning: number;
  due_count: number;
  wrong_count: number;
  accuracy: number;
  streak_days: number;
}

/** 学情快照（报告页口径，服务端聚合）。 */
export interface LearningOverview extends LearningProgress {
  trend: Array<{ date: string; learned: number; correct: number; total: number }>;
}
