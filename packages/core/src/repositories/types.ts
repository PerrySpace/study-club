/**
 * 仓储接口 —— **业务代码只依赖接口**，实现由外壳注入（见 06-1 §2.8.2）。
 *
 * ⚠️ 契约已从「本地为主存储」改为「**服务端唯一真源**」：
 *   浏览器不再保存任何学习数据，IndexedDB 实现已整体移除（见 02-4 的修订）。
 *   因此接口里不再有「把本地算式结果写回去」的方法（saveReviewStates / saveDailyTask
 *   这类），取而代之的是「提交一次作答，服务端算完把结果返回来」——
 *   调度参数（ease/interval/next_review_at）由服务端拥有，客户端不再自行推导。
 *
 * 禁止在 store / 组件 / 组合式函数中直接调用 fetch / axios；一切走本接口。
 */

import type { Child } from '../types/identity';
import type {
  AnswerRecord,
  AnswerResult,
  AnswerSubmission,
  ChildBadge,
  DailyTask,
  LearningRecord,
  LearningState,
  LessonCompletion,
  ReviewState,
  WrongQuestion,
} from '../types/learning';

/** 儿童档案 + 学习数据仓储。服务端唯一真源。 */
export interface ProgressRepository {
  // ---- 档案 ----
  listChildren(): Promise<Child[]>;
  getChild(id: string): Promise<Child | null>;
  createChild(input: CreateChildInput): Promise<Child>;
  updateChild(id: string, patch: Partial<Child>): Promise<Child>;
  /** 软删除：服务端置 status=archived，不物理删除学习数据（03-2 §一）。 */
  deleteChild(id: string): Promise<void>;

  // ---- 学习状态读取 ----
  /**
   * 一次拿全：进度 + 今日任务 + 到期复习 + 徽章（客户端首屏唯一依赖）。
   * `includeDaily=false` 时不生成今日任务 —— 只读场景（复习页、报告页）用得到，
   * 避免「家长打开报告页」顺带替孩子生成了今天的任务。
   */
  getState(childId: string, includeDaily?: boolean): Promise<LearningState>;
  listReviewStates(childId: string): Promise<ReviewState[]>;
  getReviewState(childId: string, characterId: string): Promise<ReviewState | null>;
  listWrongQuestions(childId: string): Promise<WrongQuestion[]>;
  resolveWrongQuestion(childId: string, wrongId: string): Promise<void>;
  listAnswerRecords(childId: string, limit?: number): Promise<AnswerRecord[]>;
  listLearningRecords(childId: string, limit?: number): Promise<LearningRecord[]>;
  listChildBadges(childId: string): Promise<ChildBadge[]>;

  // ---- 写入（服务端计算并返回结果） ----
  submitAnswer(input: AnswerSubmission): Promise<AnswerResult>;
  /** 离线补偿：批量补交，服务端按 client_record_id 去重。 */
  submitAnswersBatch(
    childId: string,
    records: AnswerSubmission[],
  ): Promise<{ accepted: number; skipped_duplicate: number }>;
  completeLesson(input: LessonCompletion): Promise<{ record_id: string; newly_earned_badges: string[] }>;

  // ---- 每日任务 ----
  getDailyTask(childId: string, date?: string): Promise<DailyTask>;

  // ---- 数据可迁移性（P0：用户的退出自由） ----
  exportAll(childId: string): Promise<ExportBundle>;
}

export interface CreateChildInput {
  nickname: string;
  grade: number;
  avatar_key?: string;
  birth_year?: number | null;
  daily_new_char_target?: number;
  daily_review_target?: number;
  daily_time_limit_min?: number;
}

/** 导出包（源为服务端真源，含 schema_version，可长期留存）。 */
export interface ExportBundle {
  schema_version: number;
  exported_at: string;
  child: Child;
  review_states: ReviewState[];
  wrong_questions: WrongQuestion[];
  learning_records: LearningRecord[];
  answer_records: AnswerRecord[];
  child_badges: ChildBadge[];
  daily_tasks: DailyTask[];
}

/** 仓储集合（注入给业务代码的唯一入口）。 */
export interface Repositories {
  progress: ProgressRepository;
}
