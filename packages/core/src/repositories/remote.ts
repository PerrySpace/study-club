/**
 * ApiRepository —— `ProgressRepository` 的服务端实现（**当前唯一实现**）。
 *
 * ApiRepository 是数据的服务端实现，数据落点为 MongoDB。
 * 业务代码（store / 视图 / 组件）只依赖仓储接口，注入的实现即决定数据来源。
 * 这正是「业务只依赖接口」这条纪律要换来的收益。
 *
 * 两条纪律：
 *   ① 服务端算，客户端不算 —— SRS 参数、每日任务、连续天数、正确率全部来自服务端；
 *      客户端只负责渲染与把作答提交上去（否则两边算法一定会漂移）。
 *   ② 读接口失败不静默兜底成「空数据」 —— 空数据会让用户以为「我的进度没了」，
 *      比报错更糟。因此这里让异常照常抛出，由 UI 展示可重试的错误态。
 */

import type { ApiClient } from '../api/client';
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
import type { CreateChildInput, ExportBundle, ProgressRepository } from './types';

export class ApiRepository implements ProgressRepository {
  constructor(private readonly api: ApiClient) {}

  // ------------------------------------------------------------------
  // 档案
  // ------------------------------------------------------------------
  async listChildren(): Promise<Child[]> {
    return (await this.api.listChildren()).items ?? [];
  }

  async getChild(id: string): Promise<Child | null> {
    try {
      return await this.api.getChild(id);
    } catch {
      // 不存在 / 不属于本账号统一按「没有」处理（服务端对两者都报 40301，防枚举）
      return null;
    }
  }

  async createChild(input: CreateChildInput): Promise<Child> {
    return this.api.createChild({
      nickname: input.nickname,
      grade: input.grade,
      avatar_key: input.avatar_key,
      ...(input.birth_year !== undefined ? { birth_year: input.birth_year } : {}),
      ...(input.daily_new_char_target !== undefined
        ? { daily_new_char_target: input.daily_new_char_target }
        : {}),
      ...(input.daily_review_target !== undefined
        ? { daily_review_target: input.daily_review_target }
        : {}),
      ...(input.daily_time_limit_min !== undefined
        ? { daily_time_limit_min: input.daily_time_limit_min }
        : {}),
    });
  }

  async updateChild(id: string, patch: Partial<Child>): Promise<Child> {
    return this.api.updateChild(id, patch);
  }

  async deleteChild(id: string): Promise<void> {
    await this.api.deleteChild(id);
  }

  // ------------------------------------------------------------------
  // 学习状态读取
  // ------------------------------------------------------------------
  async getState(childId: string, includeDaily = true): Promise<LearningState> {
    return this.api.learningState(childId, includeDaily);
  }

  async listReviewStates(childId: string): Promise<ReviewState[]> {
    return (await this.api.reviewStates(childId)).items ?? [];
  }

  async getReviewState(childId: string, characterId: string): Promise<ReviewState | null> {
    const res = await this.api.reviewStates(childId, characterId);
    return res.items?.[0] ?? null;
  }

  async listWrongQuestions(childId: string): Promise<WrongQuestion[]> {
    return (await this.api.wrongQuestions(childId)).items ?? [];
  }

  async resolveWrongQuestion(childId: string, wrongId: string): Promise<void> {
    await this.api.resolveWrongQuestion(childId, wrongId);
  }

  async listAnswerRecords(childId: string, limit = 2000): Promise<AnswerRecord[]> {
    return (await this.api.answerRecords(childId, limit)).items ?? [];
  }

  async listLearningRecords(childId: string, limit = 200): Promise<LearningRecord[]> {
    return (await this.api.learningRecords(childId, limit)).items ?? [];
  }

  async listChildBadges(childId: string): Promise<ChildBadge[]> {
    return (await this.api.childBadges(childId)).items ?? [];
  }

  // ------------------------------------------------------------------
  // 写入（服务端计算并返回）
  // ------------------------------------------------------------------
  async submitAnswer(input: AnswerSubmission): Promise<AnswerResult> {
    return this.api.submitAnswer(input);
  }

  async submitAnswersBatch(
    childId: string,
    records: AnswerSubmission[],
  ): Promise<{ accepted: number; skipped_duplicate: number }> {
    if (!records.length) return { accepted: 0, skipped_duplicate: 0 };
    return this.api.submitAnswersBatch(childId, records);
  }

  async completeLesson(
    input: LessonCompletion,
  ): Promise<{ record_id: string; newly_earned_badges: string[] }> {
    const res = await this.api.completeLesson(input);
    return {
      record_id: res.record_id,
      newly_earned_badges: (res.newly_earned_badges ?? []).map((b) => (b as { code: string }).code),
    };
  }

  // ------------------------------------------------------------------
  // 每日任务
  // ------------------------------------------------------------------
  async getDailyTask(childId: string, date?: string): Promise<DailyTask> {
    return this.api.dailyTask(childId, date);
  }

  // ------------------------------------------------------------------
  // 数据可迁移性
  // ------------------------------------------------------------------
  async exportAll(childId: string): Promise<ExportBundle> {
    return (await this.api.exportChildData(childId)) as unknown as ExportBundle;
  }
}
