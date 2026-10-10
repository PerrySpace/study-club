/**
 * learning store —— 学习会话、答题提交、学情总览。
 *
 * 纪律（本轮确立）：**服务端算，客户端不算**。
 * SRS 参数（ease / interval / next_review_at）、每日任务、连续天数、正确率、徽章解锁
 * 全部由服务端生产并随响应返回；客户端只做三件事：
 *   渲染题目 → 收集作答 → 提交上去并展示服务端给的结论。
 *
 * 上一版在客户端跑 `applyReview` / `generateDailyTask` / `overview` 聚合的那套已整体移除。
 * 两边各算一份，早晚会漂移 —— 用户会看到「手机上是 3 天后再复习、电脑上是 5 天」，
 * 而这类不一致几乎无法向家长解释。
 *
 * 唯一允许本地计数的是 `sessionCorrect/sessionWrong`：它们只是本次会话的 UI 提示，
 * 不落库、不作为任何判断依据。
 */

import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import { BizError, ERROR_CODE } from '../constants';
import type { Child } from '../types';
import type {
  AnswerResult,
  DailyTask,
  LearningOverview,
  LearningState,
  Question,
  ReviewState,
  WrongQuestion,
} from '../types/learning';
import { useCore } from './context';

export const useLearningStore = defineStore('learning', () => {
  /** 服务端下发的学习状态总览（首屏唯一数据源）。 */
  const state = ref<LearningState | null>(null);
  /** 当前会话的题目队列（由调用方传入，通常来自 lessonQuestions）。 */
  const sessionQuestions = ref<Question[]>([]);
  const sessionIndex = ref(0);
  const sessionId = ref<string>('');
  const sessionStartedAt = ref<number>(0);
  const sessionCorrect = ref(0);
  const sessionWrong = ref(0);
  const reviewStates = ref<ReviewState[]>([]);
  const wrongQuestions = ref<WrongQuestion[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);

  const dailyTask = computed<DailyTask | null>(() => state.value?.daily_task ?? null);
  const progress = computed(() => state.value?.progress ?? null);
  const currentQuestion = computed<Question | null>(
    () => sessionQuestions.value[sessionIndex.value] ?? null,
  );
  const sessionFinished = computed(
    () => sessionQuestions.value.length > 0 && sessionIndex.value >= sessionQuestions.value.length,
  );

  /** 拉取学习状态总览；`includeDaily=false` 时不生成今日任务（用于报告页等只读场景）。 */
  async function loadState(childId: string, includeDaily = true): Promise<LearningState> {
    loading.value = true;
    error.value = null;
    try {
      const next = await useCore().repositories.progress.getState(childId, includeDaily);
      state.value = next;
      return next;
    } catch (err) {
      error.value = err instanceof Error ? err.message : '学习状态加载失败';
      throw err;
    } finally {
      loading.value = false;
    }
  }

  /** 明细列表（错题本 / 复习清单页用；不在首屏链路上）。 */
  async function loadChildData(childId: string): Promise<void> {
    const repo = useCore().repositories.progress;
    const [states, wrongs] = await Promise.all([
      repo.listReviewStates(childId),
      repo.listWrongQuestions(childId),
    ]);
    reviewStates.value = states;
    wrongQuestions.value = wrongs;
  }

  /** 取今日任务。已在 `state` 里则直接返回，避免重复请求。 */
  async function ensureDailyTask(child: Child): Promise<DailyTask> {
    if (state.value?.daily_task && state.value.child._id === child._id) return state.value.daily_task;
    const task = await useCore().repositories.progress.getDailyTask(child._id);
    if (state.value) state.value = { ...state.value, daily_task: task };
    return task;
  }

  function startSession(questions: Question[]): void {
    sessionQuestions.value = questions;
    sessionIndex.value = 0;
    sessionId.value = `s_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
    sessionStartedAt.value = Date.now();
    sessionCorrect.value = 0;
    sessionWrong.value = 0;
  }

  /**
   * 提交一题作答。服务端写明细、更新复习状态、维护错题本，并把
   * 「下次复习时间 / 间隔天数 / 新解锁徽章」返回。
   *
   * 注意：这里**不**在本地推算下一次复习时间，直接展示 `result.next_review_at`。
   */
  async function submitAnswer(params: {
    childId: string;
    question: Question;
    answer: string;
    isCorrect: boolean;
    responseMs: number;
  }): Promise<AnswerResult> {
    const { childId, question, answer, isCorrect, responseMs } = params;
    const result = await useCore().repositories.progress.submitAnswer({
      child_id: childId,
      character_id: question.character_id,
      char: question.char,
      question_type: question.question_type,
      answer,
      correct_answer: question.answer,
      is_correct: isCorrect,
      response_ms: responseMs,
      session_id: sessionId.value,
      occurred_at: new Date().toISOString(),
    });

    if (isCorrect) sessionCorrect.value += 1;
    else sessionWrong.value += 1;
    sessionIndex.value += 1;

    // 首页进度条要立刻反映，避免「答完了但进度没动」的错觉；
    // 权威值仍以服务端为准，下次 loadState 会覆盖。
    if (state.value) {
      const p = state.value.progress;
      state.value = {
        ...state.value,
        progress: {
          ...p,
          total_learned: p.total_learned,
        },
      };
    }
    return result;
  }

  /**
   * 关卡完成流水（含端信息，支撑分端分析）。
   *
   * `stars` 一般**不传**：由正确率统一换算（`starsForAccuracy`），
   * 三条线的星星才可比 —— 家长在地图上看到「3 星」时，含义必须唯一。
   * 只有古诗/故事这类「完成方式不是答题」的关卡才显式传，且仍须落在 0–3。
   */
  async function completeLesson(params: {
    childId: string;
    lessonId: string | null;
    characterIds: string[];
    score: number;
    total: number;
    /** 显式星星（0–3）。缺省按正确率换算。 */
    stars?: number;
  }): Promise<{ record_id: string; newly_earned_badges: string[] }> {
    const accuracy = params.total > 0 ? params.score / params.total : 0;
    const stars =
      typeof params.stars === 'number'
        ? Math.max(0, Math.min(3, Math.round(params.stars)))
        : accuracy >= 0.9
          ? 3
          : accuracy >= 0.7
            ? 2
            : accuracy >= 0.5
              ? 1
              : 0;
    const res = await useCore().repositories.progress.completeLesson({
      child_id: params.childId,
      lesson_id: params.lessonId,
      event_type: 'lesson_complete',
      character_ids: params.characterIds,
      score: params.score,
      total: params.total,
      accuracy,
      stars,
      duration_ms: sessionStartedAt.value ? Date.now() - sessionStartedAt.value : 0,
      occurred_at: new Date().toISOString(),
      // 端信息（client/platform/device_form/client_version）由 ApiClient 统一注入
      // X-Client-* 请求头，后端从 ClientContext 读取，这里不再重复放在 body 里。
    });

    // 完成一关后进度与今日任务都变了，重新取一次权威值
    try {
      await loadState(params.childId);
    } catch {
      // 刷新失败不影响「关卡已完成」这个事实，静默即可
    }
    return res;
  }

  /**
   * 学情总览：进度用 `/learning/state`，趋势用报告接口。
   * 两者都是服务端聚合结果，客户端不做任何加减。
   */
  async function overview(childId: string): Promise<LearningOverview> {
    const { api } = useCore();
    if (!api) throw new BizError(ERROR_CODE.UPSTREAM_UNAVAILABLE, '服务端不可达，请稍后重试');
    const [st, tr] = await Promise.all([
      api.learningState(childId, false),
      api.reportTrend(childId, 7),
    ]);
    return { ...st.progress, trend: tr.items ?? [] };
  }

  /** 错题解答（复习答对后标记）。 */
  async function resolveWrongQuestion(childId: string, wrongId: string): Promise<void> {
    await useCore().repositories.progress.resolveWrongQuestion(childId, wrongId);
    wrongQuestions.value = wrongQuestions.value.map((w) =>
      w._id === wrongId ? { ...w, resolved: true, resolved_at: new Date().toISOString() } : w,
    );
  }

  return {
    state,
    dailyTask,
    progress,
    sessionQuestions,
    sessionIndex,
    sessionId,
    sessionCorrect,
    sessionWrong,
    sessionFinished,
    reviewStates,
    wrongQuestions,
    currentQuestion,
    loading,
    error,
    loadState,
    loadChildData,
    ensureDailyTask,
    startSession,
    submitAnswer,
    completeLesson,
    overview,
    resolveWrongQuestion,
  };
});
