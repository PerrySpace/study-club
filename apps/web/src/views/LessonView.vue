<script setup lang="ts">
/**
 * LessonView —— 字卡学习 + 闯关答题（S-02 / S-03，并串起 S-05 间隔重复）。
 *
 * 一道题的完整链路：
 *   生成题目（subject-hanzi）→ 本地即时判定 → `learning.submitAnswer()`
 *   → **服务端**写复习状态 + 答题明细 + 错题本，并把「下次复习时间」返回来。
 *
 * ⚠️ 题目目前在客户端生成（`generateQuestions`），判分也在客户端。
 * 服务端已提供 `/content/lessons/{id}/questions`（题面素材齐全），
 * 改造为消费该接口是下一步（内容补齐后再切，避免「切过去发现题目变少」）。
 * 在那之前，「哪些字到期」已经改用服务端口径，避免两边算得不一样。
 *
 * ---------------------------------------------------------------------------
 * 本轮针对**启蒙人群**的改造（原来的流程是「成人式」的：给字卡 → 直接考）：
 *   1. 学习阶段拆成 **看一看 → 听一听 → 读一读** 三个微步骤。
 *      一口气把拼音、部首、笔画、释义、组词全摊开，6 岁孩子抓不住重点；
 *      拆成三步后每一步只有一个动作，且每一步都有语音。
 *   2. 每个阶段都有**学习伙伴**说话（引导 + 鼓励），文案口语化。
 *   3. 答题有**连对**反馈（连对 3 题）与语音复述（答对读组词，答错读字）。
 *   4. 跟读题走麦克风（`speak` 题型），设备不支持时降级为「我听过了」。
 *   5. 结果页给**星星动画 + 新解锁徽章**，让「完成」这件事有奖励感。
 *
 * 路由参数 lessonId 支持四种取值：
 *   实际关卡 id | 'daily'（今日任务）| 'due'（到期复习）| 'wrong'（错题重练）
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useRoute, useRouter } from 'vue-router';

import {
  QUESTION_TYPE,
  useChildStore,
  useContentStore,
  useLearningStore,
  useSiteConfigStore,
} from '@study-club/core';
import type { Character, Lesson, Question, QuestionType } from '@study-club/core';
import {
  generateQuestion,
  generateQuestions,
  interleaveStageTests,
  pinyinMatches,
  readingPlanForChar,
  readingPlanForWord,
} from '@study-club/subject-hanzi';
import type { StageQueueItem } from '@study-club/subject-hanzi';

import { pickPraise } from '@/utils/feedback';

import BaseButton from '@/components/base/BaseButton.vue';
import BaseCard from '@/components/base/BaseCard.vue';
import BaseEmpty from '@/components/base/BaseEmpty.vue';
import BaseProgress from '@/components/base/BaseProgress.vue';
import CharCard from '@/components/biz/CharCard.vue';
import GlyphFigure from '@/components/biz/GlyphFigure.vue';
import GuideBubble from '@/components/biz/GuideBubble.vue';
import LevelResult from '@/components/biz/LevelResult.vue';
import QuestionCard from '@/components/biz/QuestionCard.vue';
import ReadAlongButton from '@/components/biz/ReadAlongButton.vue';
import SpeakButton from '@/components/biz/SpeakButton.vue';
import WritingPad from '@/components/biz/WritingPad.vue';
import { useBreakpoint } from '@/composables/useBreakpoint';
import { useCompanion } from '@/composables/useCompanion';
import { useSpeech } from '@/composables/useSpeech';
import { useToast } from '@/composables/useToast';
import { useTrackProgress } from '@/composables/useTrackProgress';
import { useViewportHeight } from '@/composables/useViewportHeight';
import {
  entryLessonOfTrack,
  nextLesson,
  routeForLesson,
  starsForAccuracy,
  type Track,
  trackOf,
} from '@/utils/levels';

const route = useRoute();
const router = useRouter();
const childStore = useChildStore();
const content = useContentStore();
const learning = useLearningStore();
const siteConfig = useSiteConfigStore();
const toast = useToast();
const { isDesktop } = useBreakpoint();
const { canSpeak, speak } = useSpeech();
const viewportHeight = useViewportHeight();
const companion = useCompanion();

const { current } = storeToRefs(childStore);

type Phase = 'loading' | 'study' | 'quiz' | 'result' | 'empty';
/**
 * 学习阶段的微步骤：看 → 听 → 读 → 写。
 *
 * 「写一写」是本轮新增的一步：认完字不写，等于没认 —— 识字产品的分水岭
 * 恰恰是「学过的字会不会在几天后再次出现、且孩子真的记住了」，
 * 而「写」是唯一能暴露字形错误的动作（看和听都发现不了「把水写成氷」）。
 * 关掉跟读就没有「读一读」这一步（而不是给一个点了没反应的麦克风）。
 */
type StudyStep = 'look' | 'listen' | 'read' | 'write';

const STEP_LABEL: Record<StudyStep, string> = {
  look: '看一看',
  listen: '听一听',
  read: '读一读',
  write: '写一写',
};
/** 全部题型枚举值 —— 用于把后台下发的题型字符串收敛成受类型检查的集合。 */
const ALL_QUESTION_TYPES = Object.values(QUESTION_TYPE) as QuestionType[];

/** 玩法配置（后台可热改）：题型白名单 / 阶段检测节奏 / 跟读开关 / 语速 / 字源图。 */
const gameplay = computed(() => siteConfig.gameplay);

/**
 * 允许出现的题型。
 *
 * 服务端在 `/content/lessons/{id}/questions` 已过滤过一次；这里是**第二道**：
 * 客户端自出题（当前主路径）必须自己看开关，否则「后台关掉跟读」在这个入口上失效。
 */
const enabledTypes = computed<QuestionType[]>(() => {
  const set = new Set<string>(gameplay.value.enabled_question_types);
  const picked = ALL_QUESTION_TYPES.filter((t) => set.has(t));
  return picked.length ? picked : ALL_QUESTION_TYPES;
});

/**
 * 学习步骤：跟读关掉就没有「读一读」；手机竖屏下默认不给「写一写」——
 * 窄屏里米字格会被压到写不下（手写板需要至少 ~240px 的稳定热区）。
 */
const studySteps = computed<StudyStep[]>(() => {
  const steps: StudyStep[] = ['look', 'listen'];
  if (gameplay.value.enable_speak) steps.push('read');
  steps.push('write');
  return steps;
});

type QueueItem = StageQueueItem<Question>;

const phase = ref<Phase>('loading');
const targets = ref<Character[]>([]);
const studyIndex = ref(0);
const studyStep = ref<StudyStep>('look');
/** 答题队列：新字题 + 按节奏插入的旧字抽查题（阶段检测）。 */
const queue = ref<QueueItem[]>([]);
const quizIndex = ref(0);
const selected = ref<string | null>(null);
const revealed = ref(false);
/** 本题是否答对（不再用选中项反推 —— 跟读题没有「选中项」）。 */
const lastCorrect = ref(false);
const correctCount = ref(0);
const questionStartedAt = ref(0);
const stars = ref(0);

/** 连对计数：只影响鼓励文案，不落库（不是学习数据）。 */
const combo = ref(0);
const bestCombo = ref(0);
/** 本关新解锁的徽章标题（服务端只回 code，标题从内容包里查）。 */
const newBadges = ref<string[]>([]);
/** 这条识字线是否**真的**全部学完（决定结果页要不要放庆祝语）。 */
const celebrate = ref(false);
const { hasCompletedAll } = useTrackProgress();

const lessonId = computed(() => String(route.params.lessonId ?? ''));

/**
 * 当前关卡所在的**内容线**（识字 / 古诗 / 故事）。
 *
 * `daily` / `due` / `wrong` 是三个虚拟关卡（不对应某一条线），
 * 此时没有「下一关」的概念 —— 这是刻意的：临时练习不该把孩子拖进闯关链路，
 * 他练完就该回首页看今天还剩什么。
 */
const isTrackLesson = computed(
  () => !['daily', 'due', 'wrong'].includes(lessonId.value) && Boolean(lessonId.value),
);

const trackLessons = computed<Lesson[]>(() => {
  if (!current.value || !isTrackLesson.value) return [];
  const lesson = content.bundle.lessons.find((l) => l._id === lessonId.value);
  if (!lesson) return [];
  const track = trackOf(lesson);
  return content
    .lessonsOfTrack(current.value.grade, track)
    .filter((l) => trackOf(l) === track);
});

/** 同一条线上的下一关。 */
const next = computed<Lesson | null>(() =>
  isTrackLesson.value ? nextLesson(trackLessons.value, lessonId.value) : null,
);
const studyProgress = computed(() =>
  targets.value.length ? (studyIndex.value + 1) / targets.value.length : 0,
);
/** 题目数组视图（队列的投影）—— 关卡的「总题数 / 正确率」口径都以队列为准。 */
const questions = computed(() => queue.value.map((item) => item.question));
const stageTestCount = computed(() => queue.value.filter((item) => item.kind === 'stage').length);
const quizProgress = computed(() =>
  queue.value.length ? quizIndex.value / queue.value.length : 0,
);
const currentItem = computed<QueueItem | null>(() => queue.value[quizIndex.value] ?? null);
const currentQuestion = computed<Question | null>(() => currentItem.value?.question ?? null);
/** 当前这题是阶段检测（旧字抽查）吗 —— 界面上要让孩子知道「这是在考以前的字」。 */
const isStageCheck = computed(() => currentItem.value?.kind === 'stage');
const currentChar = computed<Character | null>(() => targets.value[studyIndex.value] ?? null);
const accuracy = computed(() =>
  queue.value.length ? correctCount.value / queue.value.length : 0,
);

const stepIndex = computed(() => studySteps.value.indexOf(studyStep.value));

/**
 * 朗读语速：玩法配置里的 `speak_rate` 是**整体档位**（默认 0.8），
 * 单字/词句各自的基速按比例缩放并夹在可听区间内 ——
 * 直接拿档位当绝对语速会让「单字 0.8」比原来的 0.7 更快，与"单字要慢"的初衷相反。
 */
function rateFor(base: number): number {
  const factor = gameplay.value.speak_rate / 0.8;
  return Math.min(1.2, Math.max(0.4, Number((base * factor).toFixed(2))));
}

/**
 * 答题反馈文案。
 *
 * 跟读题没有「选项」，`answer === char`，直接套用「答对啦！水 —— 水」会显得很傻；
 * 单独给一句针对「读」的反馈。表扬语从词库随机抽（utils/feedback），
 * 每题换一句，避免固定「答对啦」被听腻。词库里的 `{伙伴}` 由伙伴名（= 孩子选的头像）填充。
 */
const feedbackOk = computed(() => {
  const q = currentQuestion.value;
  if (!q) return '';
  const praise = pickPraise(companion.name.value);
  return q.question_type === QUESTION_TYPE.speak
    ? `${praise}这个字是「${q.char}」`
    : `${praise}${q.char} —— ${q.answer}`;
});

const feedbackNo = computed(() => {
  const q = currentQuestion.value;
  if (!q) return '';
  return q.question_type === QUESTION_TYPE.speak
    ? `再听一遍正确读音：「${q.char}」，跟着${companion.name.value}慢慢读。`
    : `正确答案是「${q.answer}」，已加入错题本，稍后会再练。`;
});

const isCorrectOption = (option: string | null, question: Question): boolean => {
  if (option === null) return false;
  return question.question_type === QUESTION_TYPE.pinyinMatch
    ? pinyinMatches(option, question.answer)
    : option === question.answer;
};

// ---------------------------------------------------------------------------
// 伙伴引导语：按「阶段 + 处境」给一句口语化的下一步
// ---------------------------------------------------------------------------
const guideText = computed(() => {
  if (phase.value === 'study') {
    const char = currentChar.value?.char ?? '';
    if (studyStep.value === 'look') return `先看看这个「${char}」字长什么样，记住它的样子。`;
    if (studyStep.value === 'listen') return `听听它怎么读，点一下喇叭就能再听一遍。`;
    if (studyStep.value === 'read') return `按住麦克风，大声读「${char}」。`;
    return hasWritten.value
      ? `写好啦！写一遍记得比看三遍牢。`
      : `现在在米字格里写一写「${char}」，照着浅色的字描。`;
  }
  if (phase.value === 'quiz') {
    // 阶段检测与连对已显示为顶部标签，这里只补「此刻该做什么」，
    // 避免同一条信息在屏幕上出现两遍（顶部说「旧字抽查」、
    // 气泡再说「这一题是你以前学过的字」是纯重复）。
    if (quizIndex.value === 0) return '第一题开始！听清题目，选出你认识的答案。';
    if (revealed.value) return lastCorrect.value ? '答对啦！我们接下一题。' : '没关系，答错的字会记住，等会儿再练。';
    if (isDesktop.value) return '慢慢想，不着急。想好了可以按数字键 1–4 选答案。';
    return '慢慢想，不着急，想好了再点。';
  }
  if (phase.value === 'result') {
    if (stars.value === 3) return '全对！你是识字小达人！';
    if (stars.value === 2) return '很不错！再把错的那几个字练一练就更好啦。';
    return '第一次能这样已经很好啦，我们再来一遍好不好？';
  }
  return '我们一起学汉字吧！';
});

const guideMood = computed<'idle' | 'happy' | 'cheer' | 'think'>(() => {
  if (phase.value === 'result') return stars.value >= 2 ? 'happy' : 'think';
  if (phase.value === 'quiz') {
    if (combo.value >= 3) return 'cheer';
    return revealed.value ? (lastCorrect.value ? 'happy' : 'think') : 'idle';
  }
  return 'idle';
});

// ---------------------------------------------------------------------------
// 准备
// ---------------------------------------------------------------------------
/** 解析本次会话的目标字。 */
async function resolveTargets(): Promise<Character[]> {
  const child = current.value;
  if (!child) return [];
  // state 提供到期清单与今日任务；loadChildData 提供错题本明细，两者都是本页需要的
  await Promise.all([
    learning.loadState(child._id, false),
    learning.loadChildData(child._id),
  ]);

  switch (lessonId.value) {
    case 'daily': {
      const task = await learning.ensureDailyTask(child);
      // 出参是 `{ id, _id, char }` 的「增肥」形态（服务端顺带下发了字形），
      // 这里只要 id —— charactersByIds 会从内容包里取完整字卡。
      // 顺序即优先级：错题 > 到期复习 > 新学（与服务端的调度口径一致）。
      return content.charactersByIds([
        ...task.wrong_chars.map((c) => c.id),
        ...task.review_chars.map((c) => c.id),
        ...task.new_chars.map((c) => c.id),
      ]);
    }
    case 'due':
      // 到期判定用服务端下发的清单（`state.due_reviews`），不用本地时钟比时间
      return content.charactersByIds(
        (learning.state?.due_reviews ?? []).map((due) => due.character_id),
      );
    case 'wrong':
      return content.charactersByIds(
        learning.wrongQuestions.filter((w) => !w.resolved).map((w) => w.character_id),
      );
    default: {
      const lesson = content.bundle.lessons.find((l) => l._id === lessonId.value);
      return lesson ? content.charactersByIds(lesson.character_ids) : [];
    }
  }
}

/** 用复习状态里的历史表现驱动题型轮换（越熟练题型越难，01-3 §4.3）。 */
function buildHistory(): Map<string, { correct: number; wrong: number }> {
  const map = new Map<string, { correct: number; wrong: number }>();
  for (const state of learning.reviewStates) {
    map.set(state.character_id, { correct: state.total_correct, wrong: state.total_wrong });
  }
  return map;
}

async function setup(): Promise<void> {
  if (!current.value) {
    phase.value = 'empty';
    return;
  }
  const resolved = await resolveTargets();
  if (!resolved.length) {
    phase.value = 'empty';
    return;
  }
  targets.value = resolved;
  studyIndex.value = 0;
  studyStep.value = 'look';
  // 同路由名只换参数时组件会被复用：不清掉上一关的庆祝状态，
  // 下一关的结果页会一开场就念「全部闯关完成」。
  celebrate.value = false;
  phase.value = 'study';
}

/**
 * 旧字抽查题池（阶段检测用）。
 *
 * 排序即优先级：**到期复习 > 错题 > 其余已学字（越久没复习越靠前）**。
 * 抽查的意义是"提取练习"——让孩子在快要忘的时候自己把字调出来，
 * 因此必须先挑最可能已经忘掉的那些，而不是随便抽几个学过的字。
 */
function buildStagePool(): Character[] {
  const targetIds = new Set(targets.value.map((c) => c._id));
  const seen = new Set<string>();
  const picked: Character[] = [];

  const push = (id: string): void => {
    if (targetIds.has(id) || seen.has(id)) return;
    const char = content.characterMap.get(id);
    if (!char) return;
    seen.add(id);
    picked.push(char);
  };

  for (const due of learning.state?.due_reviews ?? []) push(due.character_id);
  for (const wrong of learning.wrongQuestions) {
    if (!wrong.resolved) push(wrong.character_id);
  }
  // 其余已学字：按下次复习时间升序（最久没碰的排前面）
  const ordered = [...learning.reviewStates].sort((a, b) =>
    String(a.next_review_at ?? '').localeCompare(String(b.next_review_at ?? '')),
  );
  for (const state of ordered) push(state.character_id);

  return picked.slice(0, 24);
}

/** 阶段检测用的旧字题：题型按允许集合轮换，保证同一批抽查里不完全同型。 */
function buildStageQuestions(): Question[] {
  const allowed = enabledTypes.value;
  const history = buildHistory();
  const distractors = content.bundle.characters.filter((c) => c.status === 'published');
  return buildStagePool().map((char, i) =>
    generateQuestion(char, distractors, {
      history,
      optionCount: 4,
      forceType: allowed[i % allowed.length],
      allowedTypes: allowed,
    }),
  );
}

function startQuiz(): void {
  const pool = content.bundle.characters.filter((c) => c.status === 'published');
  const history = buildHistory();
  const learn = generateQuestions(targets.value, pool, {
    history,
    optionCount: 4,
    allowedTypes: enabledTypes.value,
  });

  // 阶段检测：每学 N 个字插一次旧字抽查（N 由后台玩法配置决定）
  queue.value = interleaveStageTests(learn, buildStageQuestions(), {
    every: gameplay.value.stage_test_every,
    perCheck: 1,
    maxChecks: 3,
    // 字太少凑不满一轮时，末尾也查一次；只有 1 个字就不必查了
    alwaysOneCheck: targets.value.length >= 3,
  });

  learning.startSession(questions.value);
  quizIndex.value = 0;
  selected.value = null;
  revealed.value = false;
  lastCorrect.value = false;
  correctCount.value = 0;
  combo.value = 0;
  bestCombo.value = 0;
  questionStartedAt.value = Date.now();
  phase.value = 'quiz';
}

// ---------------------------------------------------------------------------
// 学习阶段
// ---------------------------------------------------------------------------

/**
 * 朗读**内容本身**，不读提示语。
 *
 * ⚠️ 这是刻意的：读「现在轮到你啦，点一下麦克风」这类引导语，孩子听到的是
 * 一句抽象指令而不是汉字，既延长了每步的等待时间，也不是这个阶段要学的东西。
 * 要听的内容是：单字（听读音）、词（听组词）。
 */
const currentSpokenText = computed<string>(() => {
  const char = currentChar.value;
  if (!char) return '';
  switch (studyStep.value) {
    case 'listen':
      return char.char;
    case 'read':
      return char.char;
    case 'write':
      return char.char;
    case 'look':
    default:
      // 「看一看」不自动读：这一步就是安静看字形，自动读会抢掉注意力
      return '';
  }
});

/** 听一听 / 读一读 / 写一写 每次进入都读一遍当前内容。 */
watch(
  () => [phase.value, studyIndex.value, studyStep.value] as const,
  ([, , step]) => {
    if (phase.value !== 'study') return;
    if (step === 'look') return;
    const text = currentSpokenText.value;
    if (!text) return;
    // 失败（未交互 / 不支持）不影响流程，孩子可以自己点喇叭。
    void speak(text, { rate: rateFor(readingPlanForChar(text).rate) });
  },
);

function nextStep(): void {
  if (!writeReady.value) {
    toast.show('先在米字格里写一写吧');
    return;
  }
  if (stepIndex.value + 1 < studySteps.value.length) {
    // 进入下一步即朗读该步的内容（读的是字本身，不是提示语）——
    // watch 会在这里触发；显式调一次是为了让「上一步 → 下一步」的回退也能读。
    studyStep.value = studySteps.value[stepIndex.value + 1];
    if (studyStep.value === 'look') hasWritten.value = false;
    return;
  }
  nextCard();
}

function prevStep(): void {
  if (stepIndex.value > 0) {
    studyStep.value = studySteps.value[stepIndex.value - 1];
    return;
  }
  prevCard();
}
function prevCard(): void {
  if (studyIndex.value > 0) {
    studyIndex.value -= 1;
    studyStep.value = 'look';
  }
}

/** 点大字也能听 —— 孩子最自然的动作是「戳那个字」，不该要求他找喇叭。 */
function speakCurrentChar(): void {
  const char = currentChar.value?.char;
  if (!char) return;
  void speak(char, { rate: rateFor(readingPlanForChar(char).rate) });
}

/**
 * 「看一看」右栏是否展示字源图。
 *
 * ⛔ 必须同时看后台开关：CharCard 内部已经按 `show_pictograph` 判断过一次，
 * 但**关掉开关后这一栏会变成一张只有笔画三格 + 释义的空卡**，
 * 所以这里也读一次，让左栏的字卡与右栏的解释**同时**收起字源图，
 * 避免同一份设置在两处表现不一致。
 */
const showGlyph = computed(
  () => siteConfig.gameplay.show_pictograph && Boolean(currentChar.value?.glyph),
);

/**
 * 写了字之后推进到「下一步」。
 *
 * 为什么要这一步门槛：直接跳过书写等于让孩子一路点「下一步」把四步全划过去，
 * 识字就退化成了「看图认字」。写了才算走过这一关。
 */
const hasWritten = ref(false);
const writeReady = computed(() => studyStep.value !== 'write' || hasWritten.value);

/**
 * 米字格边长（px）。
 *
 * WritingPad 的格子是**内联像素尺寸**（canvas 分辨率、显示尺寸与描红字号
 * 共用这一个值，见组件内的坐标映射），CSS 改不动它 —— 所以这里由 JS
 * 量视口高度来定，这是本页唯一必须用 JS 的自适应。
 *
 * 为什么按高度按比例，而不是给个固定值：
 *   「写一写」这一步一屏里还要放字形提示、「重写 / 看笔顺」两个按钮
 *   和底部的「下一步」—— 格子独占超过三成就必然把它们挤出去，
 *   而这三个才是这一步能不能继续的操作。
 *   手机端上限因此从原来的固定 268 收到 240：在有刘海的机型上，
 *   顶栏安全区 + 底部 Home 指示条会吃掉近 90px，268 的格子会让这一步必须滚动。
 * 下限 180px 是「还能写下一个字」的物理下限：再小就不是练字而是乱戳。
 */
const padSize = computed(() => {
  const cap = isDesktop.value ? 320 : 240;
  const vh = viewportHeight.value;
  // 取不到视口高度（极老内核 / 测试环境）时退回上限，至少不比原来差
  if (!vh) return cap;
  return Math.max(180, Math.min(cap, Math.round(vh * 0.32)));
});

function onWritingChange(payload: { hasInk: boolean }): void {
  hasWritten.value = payload.hasInk;
}

function nextCard(): void {
  if (studyIndex.value + 1 < targets.value.length) {
    studyIndex.value += 1;
    studyStep.value = 'look';
    return;
  }
  // ⛔ 出题必须兜底：`startQuiz` 里 `generateQuestions` 会读内容字段
  //    （`similar_chars` 这类派生字段在后台导入的内容里可能整片缺失）。
  //    不兜底时异常会直接冒泡出这个 async 点击处理器，`phase` 停在 `study`，
  //    表现为**点「开始闯关」毫无反应、永远到不了结果页** —— 识字线会整条线
  //    不可用，而页面上只留一行 console 报错。
  //    宁可给一句明确提示 + 让用户能退回去重进，也不要静默卡死。
  try {
    startQuiz();
  } catch (err) {
    console.error('[lesson] 出题失败', err);
    toast.error('题目没准备好，先回地图重进这一关试试');
  }
}

// ---------------------------------------------------------------------------
// 闯关阶段
// ---------------------------------------------------------------------------
async function submit(params: {
  question: Question;
  answer: string;
  isCorrect: boolean;
}): Promise<void> {
  const child = current.value;
  if (!child) return;

  // ⛔ 连对/计分**先落本地**：这一题答对没答对，在按下选项那一刻就确定了，
  //    跟这次上报成不成功毫无关系。曾经把这段放在 `await` 之后，服务端一 500
  //    就整段被跳过 ⇒ 结果页恒显示「答对 0 / 6、0%」。
  if (params.isCorrect) {
    combo.value += 1;
    bestCombo.value = Math.max(bestCombo.value, combo.value);
  } else {
    combo.value = 0;
  }

  // 上报是「尽力而为」：写不进去只意味着云端少了这条明细（复习状态/错题本晚一点补），
  // 不影响孩子继续闯关，也不影响结果页的成绩。
  // ⛔ 必须 try/catch：这里不兜住就是**未捕获的 Promise 拒绝** ——
  //    控制台只有一行红字、界面上毫无提示，问题会一直从眼皮底下溜过去。
  try {
    const result = await learning.submitAnswer({
      childId: child._id,
      question: params.question,
      answer: params.answer,
      isCorrect: params.isCorrect,
      responseMs: Date.now() - questionStartedAt.value,
    });
    // 服务端会顺带下发新解锁的徽章（可能为空）
    if (result.newly_earned_badges?.length) {
      const titles = result.newly_earned_badges
        .map((b) => b.title)
        .filter((t): t is string => Boolean(t));
      if (titles.length) newBadges.value = [...new Set([...newBadges.value, ...titles])];
    }
  } catch (err) {
    console.error('[lesson] 答题上报失败', err);
    toast.warn('这题没记到云端，成绩先按本机算');
  }
  correctCount.value = learning.sessionCorrect;

  void narrateFeedback(params.question, params.isCorrect);
}

/** 答题后的语音复述：答对读组词（把字放回语境），答错读字（再听一遍正确读音）。 */
async function narrateFeedback(question: Question, isCorrect: boolean): Promise<void> {
  if (!canSpeak || !gameplay.value.enable_speak) return;
  // 跟读题刚刚才读过：读对了不重复念，否则孩子会以为「读错了」；
  // 读错了则补一遍正确读音 —— 失败时最需要的正是「再听一次」。
  if (question.question_type === QUESTION_TYPE.speak) {
    if (!isCorrect) {
      await speak(question.char, { rate: rateFor(readingPlanForChar(question.char).rate) });
    }
    return;
  }

  const word = question.words?.[0];
  if (isCorrect && word) {
    await speak(word, { rate: rateFor(readingPlanForWord(word).rate) });
    return;
  }
  await speak(question.char, { rate: rateFor(readingPlanForChar(question.char).rate) });
}

async function chooseOption(option: string): Promise<void> {
  const question = currentQuestion.value;
  if (!question || !current.value || revealed.value) return;

  const isCorrect = isCorrectOption(option, question);
  selected.value = option;
  revealed.value = true;
  lastCorrect.value = isCorrect;
  await submit({ question, answer: option, isCorrect });
}

/**
 * 跟读题的结果。
 *
 * ⚠️ 判定是**宽松**的（只问「读到了没有」，见 subject-hanzi/reading.ts）。
 * 设备不支持识别时 `degraded=true`，此时按「已读」记录 ——
 * 这是因为「录不到声音」不是孩子的错，不该因此判错、更不该进错题本。
 */
async function onSpeakResult(payload: {
  matched: boolean;
  transcript: string;
  degraded: boolean;
}): Promise<void> {
  const question = currentQuestion.value;
  if (!question || !current.value || revealed.value) return;

  selected.value = payload.transcript || null;
  revealed.value = true;
  lastCorrect.value = payload.matched;
  await submit({
    question,
    answer: payload.matched ? question.answer : payload.transcript,
    isCorrect: payload.matched,
  });
}

async function nextQuestion(): Promise<void> {
  if (!revealed.value) return;
  if (quizIndex.value + 1 < queue.value.length) {
    quizIndex.value += 1;
    selected.value = null;
    revealed.value = false;
    lastCorrect.value = false;
    questionStartedAt.value = Date.now();
    return;
  }

  const child = current.value;
  if (child && queue.value.length) {
    // ⛔ 记流水失败**绝不能挡住结果页**：孩子明明答完了最后一题，
    //    却因为一次网络抖动/500 停在题目上「点了没反应」，是最糟的体验。
    //    （古诗 / 故事线早就是 try/catch + toast 的写法，这里补齐对齐。）
    try {
      const res = await learning.completeLesson({
        childId: child._id,
        lessonId: lessonId.value === 'daily' || lessonId.value === 'due' || lessonId.value === 'wrong'
          ? null
          : lessonId.value,
        // 关卡流水记「本次练到的全部字」——含阶段检测抽到的旧字，
        // 否则关卡记录里的字数会小于孩子实际练过的字数
        characterIds: Array.from(new Set(queue.value.map((item) => item.question.character_id))),
        score: correctCount.value,
        total: queue.value.length,
      });
      // 关卡级徽章（服务端口径）；与答题级徽章合并去重
      const titles = (res.newly_earned_badges ?? [])
        .map((code) => content.bundle.badges.find((b) => b.code === code)?.title ?? code)
        .filter(Boolean);
      if (titles.length) newBadges.value = [...new Set([...newBadges.value, ...titles])];
      // 「今日任务 / 到期复习 / 错题本」不是关卡，不参与「全部闯关完成」的判定
      if (isTrackLesson.value) {
        celebrate.value = await hasCompletedAll(trackLessons.value.map((l) => l._id));
      }
    } catch (err) {
      console.error('[lesson] 关卡流水写入失败', err);
      toast.warn('这次成绩没记上，但你已经闯完这一关啦');
    }
  }
  stars.value = starsForAccuracy(accuracy.value);
  phase.value = 'result';
}

function goHome(): void {
  void router.replace({ name: 'home' });
}

/** 直接进下一关（识字线；古诗/故事由各自的视图处理）。 */
function goNext(): void {
  if (next.value) void router.replace(routeForLesson(next.value));
  else goBackToMap();
}

/** 回地图并停在当前这条线上 —— 完成一关后要看的是「解锁到哪了」。 */
function goBackToMap(): void {
  const lesson = content.bundle.lessons.find((l) => l._id === lessonId.value);
  void router.replace(
    lesson ? { name: 'map', query: { track: trackOf(lesson) } } : { name: 'map' },
  );
}

/**
 * 换条线闯关 —— 去那条线的**第一关**。
 *
 * 为什么不是「第一个未完成的」：关卡页此刻拿不到完整的完成记录
 * （`learning` store 只存当前会话，完整记录要另发一次 `listLearningRecords`），
 * 为一颗按钮多发一次请求不划算。第一关重玩无害（只可能把星星刷高）；
 * 想接着上次的位置就走「回地图」—— 地图上的主按钮本来就是「继续第 N 关」。
 */
function goTrack(key: string): void {
  const child = current.value;
  const track = key as Track;
  const target = child
    ? entryLessonOfTrack(content.lessonsOfTrack(child.grade, track), track)
    : null;
  if (!target) {
    toast.show('这条线暂时还没有关卡，先回地图看看吧');
    goBackToMap();
    return;
  }
  void router.replace(routeForLesson(target));
}

/** 桌面快捷键（02-2 §五）：数字选答案 / 空格下一题 / Esc 退出。 */
function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    goHome();
    return;
  }
  if (phase.value === 'quiz') {
    const question = currentQuestion.value;
    const num = Number.parseInt(event.key, 10);
    if (question && !revealed.value && num >= 1 && num <= question.options.length) {
      // 数字键选第 N 个选项：对外统一传选项文本（与点击路径同一口径）
      void chooseOption(question.options[num - 1].char);
      return;
    }
    if ((event.key === 'Enter' || event.key === ' ') && revealed.value) {
      event.preventDefault();
      void nextQuestion();
    }
  }
  if (phase.value === 'study' && (event.key === 'Enter' || event.key === ' ')) {
    event.preventDefault();
    nextStep();
  }
}

/**
 * 冷启动：先**清干净上一关的残留**再准备内容。
 *
 * ⛔ 为什么必须显式清零：结果页点「下一关」走的是 `router.replace`
 * （同一路由名、只换参数），Vue Router 会**复用组件实例** —— `onMounted`
 * 不会再触发。不清零的话，新一关会带着上一关的星星、连对与徽章开场，
 * 界面上表现为「刚点开就显示上一关的成绩」。
 */
async function boot(): Promise<void> {
  // 先回到 loading：否则换关的一瞬间会闪一下上一关的结果页
  phase.value = 'loading';
  stars.value = 0;
  correctCount.value = 0;
  combo.value = 0;
  bestCombo.value = 0;
  newBadges.value = [];
  queue.value = [];
  selected.value = null;
  revealed.value = false;
  lastCorrect.value = false;
  await setup();
}

function bootSafe(): void {
  void boot().catch(() => {
    toast.error('内容加载失败，请稍后重试');
    phase.value = 'empty';
  });
}

onMounted(() => {
  bootSafe();
  if (isDesktop.value) window.addEventListener('keydown', onKeydown);
});

// 同一组件被复用时（结果页「下一关」、URL 直接换关卡），必须重新准备内容
watch(() => route.params.lessonId, bootSafe);

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown);
});
</script>

<template>
  <!--
    三段式「一屏」骨架（见 styles/learn-screen.css）：
      head 常驻顶部（进度 / 步骤）、body 唯一滚动区、foot 常驻底部（主操作）。
    ⛔ 「下一步 / 下一题」这类**决定流程能否走下去**的按钮必须在 foot —— 放进 body
      就等于把它交给滚动位置决定是否可见，而孩子不会为了找按钮去划屏幕。
  -->
  <section class="learn-page">
    <!-- 准备中 -->
    <div
      v-if="phase === 'loading'"
      class="learn-page__body learn-page__body--center text-muted text-center"
    >
      正在准备…
    </div>

    <!-- 空状态 -->
    <div v-else-if="phase === 'empty'" class="learn-page__body learn-page__body--center">
      <BaseEmpty
        title="这里暂时没有可练的字"
        description="可能是今日任务已完成，或该关卡内容尚未随包提供。"
        icon="🌱"
      >
        <BaseButton @click="goHome">回到首页</BaseButton>
      </BaseEmpty>
    </div>

    <!-- 学习阶段：字卡（看 → 听 → 读 → 写） -->
    <template v-else-if="phase === 'study' && currentChar">
      <header class="learn-page__head">
        <BaseProgress :value="studyProgress" :label="`字卡 ${studyIndex + 1} / ${targets.length}`" />

        <!-- 步骤指示器：让孩子知道「还有几步」，减少中途退出（关掉跟读就只有两步） -->
        <ol class="steps" aria-label="学习步骤">
          <li
            v-for="(step, i) in studySteps"
            :key="step"
            class="steps__item"
            :class="{
              'steps__item--active': step === studyStep,
              'steps__item--done': i < stepIndex,
            }"
          >
            <span class="steps__dot">{{ i < stepIndex ? '✓' : i + 1 }}</span>
            <span class="steps__label">{{ STEP_LABEL[step] }}</span>
          </li>
        </ol>
      </header>

      <div class="learn-page__body">
        <GuideBubble
          :text="guideText"
          :mood="guideMood"
          :auto-speak="false"
          :show-speak="true"
        />

        <div class="lesson-layout lesson-layout--study">
          <!--
            看一看：**左右分栏**（左字形 / 右解释），和「听一听」的观感一致。

            为什么不再竖着摊：CharCard 默认把拼音、字、字源图、部首、笔画、结构、
            释义、组词、例句从上到下堆在一张卡里 —— 9 块信息串成一条，
            在手机上要滚两三屏才看得完，而「看一看」这一步的目标只是**记住字形**。
            分栏后左栏只留字形（视觉重心），右栏承载解释，桌面上一屏可见；
            手机上也在解释之前先看到字。

            `studyCompact` 让 CharCard 收掉与「字形」无关的次要信息。
          -->
          <CharCard
            v-if="studyStep === 'look'"
            :character="currentChar"
            study-compact
          >
            <!-- 喇叭常驻字卡下方：启蒙页最高频的操作，做成大圆钮 -->
            <div class="char-card__audio">
              <SpeakButton
                :text="currentChar.char"
                :rate="rateFor(readingPlanForChar(currentChar.char).rate)"
                label="听读音"
                variant="primary"
                size="lg"
                icon-only
              />
            </div>
          </CharCard>

          <!-- 写一写：米字格描红 + 笔顺 -->
          <div v-else-if="studyStep === 'write'" class="write-step">
            <p class="write-step__char learning-surface" @click="speakCurrentChar">
              {{ currentChar.char }}
            </p>
            <WritingPad
              :key="currentChar._id"
              :char="currentChar.char"
              :stroke-count="currentChar.stroke_count"
              :size="padSize"
              @change="onWritingChange"
            />
          </div>

          <!-- 听一听 / 读一读：只留大字 + 读音，避免视觉干扰 -->
          <div v-else class="focus-card">
            <p class="focus-card__char learning-surface" @click="speakCurrentChar">
              {{ currentChar.char }}
            </p>
            <div class="focus-card__audio">
              <SpeakButton
                :text="currentChar.char"
                :rate="rateFor(readingPlanForChar(currentChar.char).rate)"
                label="听读音"
                variant="primary"
                size="lg"
                icon-only
              />
            </div>
            <template v-if="studyStep === 'read'">
              <ReadAlongButton
                :text="currentChar.char"
                :companion-name="companion.name.value"
                label="按住读一遍"
                size="lg"
                block
              />
              <p class="text-sm text-muted text-center">
                按住按钮别松手，圆圈转满就会听你读。慢慢读，读错了也没关系。
              </p>
            </template>
            <p v-else class="focus-card__pinyin">{{ currentChar.pinyin }}</p>
          </div>

          <aside class="stack">
            <!--
              看一看的右栏：**一张卡承载「解释」**，字源图 / 笔画 / 释义 / 组词都在这里。
              不再拆成多张卡 —— 一屏里出现 3 个带边框的盒子会让页面碎成三段，
              而这些信息本来就是同一组「关于这个字的说明」。
            -->
            <BaseCard v-if="studyStep === 'look'" title="这个字怎么记">
              <!-- 字源图：启蒙靠「图」记字形，放在解释栏最上方 -->
              <figure v-if="showGlyph" class="glyph-panel">
                <GlyphFigure
                  :glyph="currentChar.glyph"
                  :size="40"
                  :alt="`${currentChar.char} 的字源图`"
                />
                <span v-if="currentChar.pictograph" class="glyph-panel__text">
                  {{ currentChar.pictograph }}
                </span>
              </figure>

              <!-- 笔画与结构：两个小方块并排 -->
              <div class="fact-row">
                <div class="fact">
                  <span class="fact__label">部首</span>
                  <span class="fact__value">{{ currentChar.radical || '—' }}</span>
                </div>
                <div class="fact">
                  <span class="fact__label">笔画</span>
                  <span class="fact__value">{{ currentChar.stroke_count ?? '—' }}</span>
                </div>
                <div class="fact">
                  <span class="fact__label">结构</span>
                  <span class="fact__value">{{ currentChar.structure || '—' }}</span>
                </div>
              </div>

              <p class="char-meaning selectable">{{ currentChar.meaning || '（还没有释义）' }}</p>

              <ul v-if="currentChar.words.length" class="word-chips">
                <li v-for="word in currentChar.words.slice(0, 4)" :key="word" class="word-chips__item">
                  <span>{{ word }}</span>
                  <SpeakButton
                    :text="word"
                    :rate="rateFor(readingPlanForWord(word).rate)"
                    label="听"
                    size="sm"
                    variant="ghost"
                    icon-only
                  />
                </li>
              </ul>
            </BaseCard>

            <BaseCard v-else title="读一读这些词">
              <p class="text-sm text-muted">把字放进词语里读，记得更牢。</p>
              <ul class="word-list">
                <li v-for="word in currentChar.words.slice(0, 3)" :key="word" class="word-list__item">
                  <span class="word-list__text">{{ word }}</span>
                  <SpeakButton
                    :text="word"
                    :rate="rateFor(readingPlanForWord(word).rate)"
                    label="听"
                    size="sm"
                    variant="ghost"
                  />
                </li>
              </ul>
            </BaseCard>
          </aside>
        </div>
      </div>

      <footer class="learn-page__foot">
        <!-- 卡点提示放在按钮**上方**：先给原因，再给动作，视线不用回头 -->
        <p
          v-if="studyStep === 'write' && !hasWritten"
          class="text-sm text-muted text-center"
        >
          在米字格里描一遍，就可以继续啦
        </p>
        <div class="lesson-actions">
          <BaseButton
            variant="secondary"
            :disabled="studyIndex === 0 && stepIndex === 0"
            @click="prevStep"
          >
            上一步
          </BaseButton>
          <BaseButton size="lg" :disabled="!writeReady" @click="nextStep">
            {{
              studyIndex + 1 < targets.length || stepIndex + 1 < studySteps.length
                ? '下一步'
                : '开始闯关'
            }}
          </BaseButton>
        </div>
      </footer>
    </template>

    <!-- 闯关阶段 -->
    <template v-else-if="phase === 'quiz' && currentQuestion">
      <!--
        顶部一行收成两件事：**走到哪** + **此刻提示**。
        原来这里连叠四层（进度条 / 阶段检测 / 连对 / 引导气泡），题目被挤到首屏之下；
        阶段检测与连对已合并进引导气泡的文案，不再各占一行。
      -->
      <header class="learn-page__head">
        <div class="quiz-head">
          <BaseProgress :value="quizProgress" :label="`第 ${quizIndex + 1} / ${queue.length} 题`" />
          <div class="quiz-head__flags">
            <span v-if="isStageCheck" class="quiz-flag quiz-flag--check">旧字抽查</span>
            <span v-if="combo >= 2" class="quiz-flag" :class="{ 'quiz-flag--hot': combo >= 3 }">
              连对 {{ combo }} 题
            </span>
          </div>
        </div>
      </header>

      <div class="learn-page__body">
        <div class="quiz-layout">
          <QuestionCard
            :question="currentQuestion"
            :selected="selected"
            :revealed="revealed"
            :disabled="revealed"
            :show-hint="!revealed"
            @select="chooseOption"
            @speak="onSpeakResult"
          />

          <!--
            反馈**紧贴选项下方**，不放侧栏。
            孩子点完要立刻看到对错 —— 塞进侧栏在手机上会被挤到屏幕外，
            那等于「答了但不知道对不对」。
            ⚠️ 只有「文案」留在这里；「下一题」按钮在 foot（见文件顶部说明）。
          -->
          <div
            v-if="revealed"
            class="quiz-feedback"
            :class="lastCorrect ? 'quiz-feedback--ok' : 'quiz-feedback--no'"
          >
            <p class="quiz-feedback__mark" aria-hidden="true">{{ lastCorrect ? '🎉' : '💪' }}</p>
            <p class="quiz-feedback__text">{{ lastCorrect ? feedbackOk : feedbackNo }}</p>
          </div>

          <GuideBubble v-else :text="guideText" :mood="guideMood" :auto-speak="false" />
        </div>
      </div>

      <footer v-if="revealed" class="learn-page__foot learn-page__foot--narrow">
        <BaseButton size="lg" block @click="nextQuestion">
          {{ quizIndex + 1 < queue.length ? '下一题' : '看结果' }}
        </BaseButton>
      </footer>
    </template>

    <!-- 结果 —— 与古诗 / 故事关共用同一张结果卡，闭环一致 -->
    <div v-else-if="phase === 'result'" class="learn-page__body learn-page__body--center">
      <GuideBubble :text="guideText" :mood="guideMood" />

      <LevelResult
        :stars="stars"
        title="本关完成"
        :subtitle="`答对 ${correctCount} / ${queue.length}`"
        :stats="[
          { label: '正确率', value: `${Math.round(accuracy * 100)}%` },
          { label: '新学字数', value: targets.length },
          { label: '最高连对', value: bestCombo },
          ...(stageTestCount ? [{ label: '旧字抽查', value: stageTestCount }] : []),
        ]"
        :badges="newBadges"
        note="复习计划已按记忆曲线安排；下次打开首页即可看到「到期复习」。"
        :has-next="Boolean(next)"
        :celebrate="celebrate"
        next-label="下一关"
        :track-links="[
          { key: 'poem', label: '去古诗闯关' },
          { key: 'story', label: '去读短文' },
        ]"
        @next="goNext"
        @retry="startQuiz"
        @back="goBackToMap"
        @track="goTrack"
      />
    </div>
  </section>
</template>

<style scoped>
/*
 * 页面骨架（.learn-page / __head / __body / __foot）来自 styles/learn-screen.css ——
 * 三条学习线（识字 / 古诗 / 故事）共用一份，保证「一屏内」的规则只写一遍。
 * 本文件只写这一步自己的东西。
 */

/* ---- 「看一看」右栏：解释（字源图 / 笔画 / 释义 / 组词）---- */

/*
 * 字源图放在解释栏最上方：启蒙靠「图」记字形，而右栏一打开就看到图，
 * 比让用户先读完文字再往上翻更符合这一屏的目的。
 */
.glyph-panel {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin: 0 0 var(--space-sm);
  padding: var(--space-sm);
  border-radius: var(--radius-md);
  background: var(--color-surface-alt);
}

.glyph-panel__emoji {
  font-size: 40px;
  line-height: 1;
  flex: none;
}

.glyph-panel__text {
  color: var(--color-text-muted);
  font-size: var(--font-sm);
  line-height: 1.6;
  text-align: left;
}

/* 笔画三格：等宽并排，避免「部首」字多、「笔画」字少导致参差 */
.fact-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-xs);
  margin-bottom: var(--space-sm);
}

.fact {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: var(--space-xs);
  border-radius: var(--radius-sm);
  background: var(--color-surface-alt);
}

.fact__label {
  color: var(--color-text-muted);
  font-size: var(--font-xs);
}

.fact__value {
  font-size: var(--font-md);
  font-weight: 600;
}

.char-meaning {
  margin-bottom: var(--space-sm);
  font-size: var(--font-body);
  line-height: 1.7;
}

/* 组词：标签流式换行，每词自带小喇叭 */
.word-chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-xs);
  list-style: none;
  margin: 0;
  padding: 0;
}

.word-chips__item {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 2px 4px 2px var(--space-sm);
  border-radius: var(--radius-pill);
  background: var(--color-surface-alt);
  font-size: var(--font-sm);
}

/* ---- 步骤指示器 ----
   允许换行：4 步（看/听/读/写）在 360px 宽的屏上会超出容器，
   原来的 nowrap 会让最后一步被裁掉（表现为「只显示三步」）。 */
.steps {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-xs);
  justify-content: center;
}

.steps__item {
  display: inline-flex;
  align-items: center;
  gap: var(--space-xs);
  padding: 2px var(--space-sm);
  border-radius: var(--radius-pill);
  background: var(--color-surface-alt);
  color: var(--color-text-muted);
  font-size: var(--font-sm);
}

.steps__item--active {
  background: var(--color-primary);
  color: var(--color-text);
  font-weight: 600;
}

.steps__item--done {
  color: var(--color-success);
}

.steps__dot {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--color-surface);
  font-size: var(--font-xs);
}

/* ---- 聚焦卡（听 / 读步骤） ---- */
.focus-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-md);
  /* 一屏模式下卡片要用掉内容区的高度，但不许撑破 —— 由内容区自己滚 */
  padding: var(--space-md);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

.focus-card__char {
  /*
   * 字形大小只按宽度算（`dvh` 在旧内核会让整条声明失效、退回继承的 18px，
   * 那比字大了点严重得多 —— 见 styles/learn-screen.css 的说明）。
   * 矮屏由下方的高度媒体查询压档，效果一样但确定。
   */
  font-size: clamp(120px, 32vw, 240px);
  line-height: 1;
  font-weight: 500;
  cursor: pointer;
}

@media (max-height: 700px) {
  .focus-card__char {
    font-size: clamp(88px, 24vw, 160px);
  }
}

.focus-card__pinyin {
  font-size: var(--font-xl);
  color: var(--color-info);
  letter-spacing: 0.08em;
}

/* 喇叭：字卡与聚焦卡都常驻一个大圆钮 */
.focus-card__audio,
.char-card__audio {
  display: flex;
  justify-content: center;
}

.char-card__audio {
  margin-top: var(--space-xs);
}

/* ---- 写一写 ---- */
.write-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-md);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

.write-step__char {
  /* 矮屏上先压这个提示字，把格子与按钮的位置让出来（分档原因同上） */
  font-size: clamp(72px, 18vw, 110px);
  line-height: 1;
  font-weight: 500;
  cursor: pointer;
}

@media (max-height: 700px) {
  .write-step__char {
    font-size: clamp(44px, 12vw, 72px);
  }

  .write-step {
    gap: var(--space-xs);
    padding: var(--space-sm);
  }
}

/* ---- 组词列表 ---- */
.word-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
  margin-top: var(--space-sm);
}

.word-list__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-sm);
  padding: var(--space-2xs) var(--space-sm);
  border-radius: var(--radius-md);
  background: var(--color-surface-alt);
}

.word-list__text {
  font-size: var(--font-body);
}

/* ---- 闯关顶部：进度 + 徽标收成一行 ---- */
.quiz-head {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  flex-wrap: wrap;
  max-width: 720px;
  margin-inline: auto;
  width: 100%;
}

.quiz-head__flags {
  display: flex;
  align-items: center;
  gap: var(--space-xs);
  margin-left: auto;
}

/*
 * 徽标用**小胶囊**而不是原来的一整行文字：
 * 「旧字抽查」「连对 3 题」是状态提示，不是内容 —— 给孩子看的说明文字
 * 不该和题目争版面。颜色上「旧字抽查」用信息蓝（中性、只是说明），
 * 「连对」用暖黄（正反馈），连对 ≥3 才加深，避免一达 2 题就过度庆祝。
 */
.quiz-flag {
  padding: 2px var(--space-sm);
  border-radius: var(--radius-pill);
  background: var(--color-primary);
  color: var(--color-text);
  font-size: var(--font-xs);
  font-weight: 600;
  white-space: nowrap;
}

.quiz-flag--check {
  background: color-mix(in srgb, var(--color-info) 20%, var(--color-surface));
  color: var(--color-info);
}

.quiz-flag--hot {
  animation: combo-pop 420ms ease-out;
}

/* ---- 答题反馈：紧贴选项下方（按钮在 foot，见模板注释） ---- */
.quiz-feedback {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-xs);
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-lg);
  border: 1px solid transparent;
  text-align: center;
  animation: feedback-in 260ms ease-out;
}

.quiz-feedback--ok {
  background: color-mix(in srgb, var(--color-success) 12%, var(--color-surface));
  border-color: color-mix(in srgb, var(--color-success) 34%, transparent);
}

.quiz-feedback--no {
  background: color-mix(in srgb, var(--color-warn) 12%, var(--color-surface));
  border-color: color-mix(in srgb, var(--color-warn) 34%, transparent);
}

.quiz-feedback__mark {
  font-size: 28px;
  line-height: 1;
}

.quiz-feedback__text {
  font-size: var(--font-body);
  line-height: 1.5;
  color: var(--color-text);
}

@keyframes feedback-in {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.lesson-actions {
  display: flex;
  gap: var(--space-md);
  justify-content: space-between;
}

/*
 * 闯关阶段的操作条与题目**同宽居中**。
 * 题目被 `.quiz-layout` 收到 720px 居中（答题是一列单任务，见 responsive.css），
 * 底部的「下一题」若铺满整个内容列（桌面 880px）会比题目宽出一截，
 * 看起来像另一个界面的按钮。
 */
.learn-page__foot--narrow {
  width: 100%;
  max-width: 720px;
  margin-inline: auto;
}

.lesson-actions > :last-child {
  flex: 1;
}

/* ---- 结果页 ----
   星星与「下一关 / 回地图」引导已抽到 `biz/LevelResult.vue`，
   识字 / 古诗 / 故事三条线共用同一份，避免各自的闭环不一样。 */

@keyframes combo-pop {
  from {
    transform: scale(0.85);
  }
  to {
    transform: scale(1);
  }
}
</style>
