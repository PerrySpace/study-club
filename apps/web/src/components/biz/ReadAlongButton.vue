<script setup lang="ts">
/**
 * ReadAlongButton —— 跟读按钮（业务组件）。
 *
 * 三段状态：待读 → 正在听（麦克风亮） → 出结果（随机表扬 / 鼓励再读）。
 *
 * ⚠️ 三条必须守住的纪律：
 *   ① **不给发音分数。** 原生 ASR 只给文本，声调在文本里根本看不见。
 *      界面只说「读到了 / 再听一次」，绝不出「92 分」这类数字（见 reading.ts 顶部说明）。
 *      成功/失败的文案从词库随机抽取（utils/feedback），避免固定一句被听腻。
 *   ② **不支持识别时必须降级，且降级要写在脸上。** Firefox 等内核没有
 *      `SpeechRecognition`，此时按钮变成「我听过了」，并在反馈里说明
 *      「这台设备听不到声音，已帮你记一次」——安静地什么都不做会被当成坏了。
 *   ③ 判定逻辑由**调用方**通过 `matcher` 注入。组件本身不 import 学科包，
 *      这样英语跟读可以直接复用（判据：换成英语单词还成立 → 属通用组件）。
 */
import { computed, onBeforeUnmount, ref } from 'vue';

import { useSpeech } from '@/composables/useSpeech';
import { pickEncouragement, pickPraise } from '@/utils/feedback';

const props = withDefaults(
  defineProps<{
    /** 目标文本（读什么） */
    text: string;
    label?: string;
    size?: 'sm' | 'md' | 'lg';
    block?: boolean;
    /** 是否禁用（如已作答） */
    disabled?: boolean;
    /**
     * 判定「读到没有」。默认做归一化后的包含判定；
     * 学科可用更宽松的规则覆盖（如按覆盖率判定）。
     */
    matcher?: (transcript: string, target: string) => boolean;
  }>(),
  {
    label: '跟读一遍',
    size: 'md',
    block: false,
    disabled: false,
    matcher: undefined,
  },
);

const emit = defineEmits<{
  (e: 'result', payload: { matched: boolean; transcript: string; degraded: boolean }): void;
}>();

const { canListen, listening, listen } = useSpeech();

/** 设备不支持识别：按钮退化为「我听过了」。 */
const degraded = computed(() => !canListen);

const transcript = ref('');
const matched = ref<boolean | null>(null);
const errorText = ref('');
/** 本次结果的表扬/鼓励文案（出结果时从词库随机抽一句） */
const praiseText = ref('');
const encourageText = ref('');
/** 降级模式下是否已确认 */
const acknowledged = ref(false);

function defaultMatcher(heard: string, target: string): boolean {
  const norm = (s: string): string =>
    s.replace(/[\s\u3000]+/g, '').replace(/[，。、！？；：""''（）《》,.;:!?'"()<>[\]{}~—…·\-]/g, '');
  const h = norm(heard);
  const t = norm(target);
  if (!h || !t) return false;
  return h.includes(t) || t.includes(h);
}

const judge = (heard: string, target: string): boolean =>
  (props.matcher ?? defaultMatcher)(heard, target);

function reset(): void {
  transcript.value = '';
  matched.value = null;
  errorText.value = '';
  praiseText.value = '';
  encourageText.value = '';
  acknowledged.value = false;
}

async function onClick(): Promise<void> {
  if (props.disabled || listening.value || holding.value) return;
  await startListen();
}

/**
 * 长按跟读：按下满 `HOLD_MS` 才算「我要读」，期间进度环走满。
 *
 * 为什么要有长按：短按立即开麦，孩子常常只是「想点一下看看」而不是真要读，
 * 话还没说完就被判成「没读」。长按把启动麦克风变成一个**有意识的动作** ——
 * 按住不动、看见进度环走满，才开始听。
 *
 * 短按仍保留为「直接开始」，两条路都在（长辈/赶时间的场景不必长按）。
 * 提前松手必须**明确说明**为什么没开始，静默无反应会被当成按钮坏了。
 */
const HOLD_MS = 450;
const holding = ref(false);
const holdProgress = ref(0);
const holdHint = ref('');
let holdTimer: number | null = null;
let holdRaf: number | null = null;
let holdStart = 0;

function onPointerDown(): void {
  if (props.disabled || listening.value || holding.value) return;
  holdHint.value = '';
  holding.value = true;
  holdStart = Date.now();

  const tick = (): void => {
    const ratio = Math.min(1, (Date.now() - holdStart) / HOLD_MS);
    holdProgress.value = ratio;
    if (ratio < 1) holdRaf = window.requestAnimationFrame(tick);
  };
  holdRaf = window.requestAnimationFrame(tick);

  holdTimer = window.setTimeout(() => {
    holding.value = false;
    holdProgress.value = 0;
    holdTimer = null;
    if (holdRaf !== null) {
      window.cancelAnimationFrame(holdRaf);
      holdRaf = null;
    }
    void startListen();
  }, HOLD_MS);
}

function cancelHold(): void {
  if (holdTimer !== null) {
    window.clearTimeout(holdTimer);
    holdTimer = null;
  }
  if (holdRaf !== null) {
    window.cancelAnimationFrame(holdRaf);
    holdRaf = null;
  }
  if (holding.value) {
    holding.value = false;
    holdHint.value = '要按住不放，等圆圈转满才会听你读哦';
    window.setTimeout(() => {
      holdHint.value = '';
    }, 2400);
  }
  holdProgress.value = 0;
}

/** 开始一次识别（长按与短按共用同一条路径）。 */
async function startListen(): Promise<void> {
  // 降级路径：没有识别能力就直接记为「已读」，并如实说明原因。
  if (degraded.value) {
    acknowledged.value = true;
    emit('result', { matched: true, transcript: '', degraded: true });
    return;
  }

  reset();
  try {
    const result = await listen();
    transcript.value = result.transcript;
    matched.value = judge(result.transcript, props.text);
    // 表扬/鼓励各抽一句：换词而不是换口径，孩子每次听到的夸奖都不一样
    praiseText.value = pickPraise();
    encourageText.value = pickEncouragement();
    emit('result', {
      matched: matched.value,
      transcript: result.transcript,
      degraded: false,
    });
  } catch (err) {
    matched.value = false;
    const code = err instanceof Error ? err.message : 'SPEECH_ERROR';
    // 把技术错误码翻成孩子/家长能懂的话，而不是把 `SPEECH_NOTALLOWED` 甩到屏幕上
    if (code.includes('NOTALLOWED') || code.includes('SERVICE_NOT_ALLOWED')) {
      errorText.value = '麦克风被挡住了，请在浏览器里允许使用麦克风';
    } else if (code.includes('TIMEOUT') || code.includes('NO_RESULT') || code.includes('EMPTY')) {
      errorText.value = '没听清，凑近一点再读一次吧';
    } else if (code.includes('UNSUPPORTED')) {
      errorText.value = '这台设备暂时听不到声音';
    } else {
      errorText.value = '没听清，再试一次吧';
    }
    emit('result', { matched: false, transcript: '', degraded: false });
  }
}

onBeforeUnmount(cancelHold);
</script>

<template>
  <div class="read-along" :class="{ 'read-along--block': block }">
    <button
      type="button"
      class="read-along__btn tap clickable"
      :class="[
        `read-along__btn--${size}`,
        {
          'read-along__btn--block': block,
          'read-along__btn--on': listening,
          'read-along__btn--ok': matched === true,
          'read-along__btn--no': matched === false,
          'read-along__btn--holding': holding,
        },
      ]"
      :disabled="disabled || listening"
      @click="onClick"
      @pointerdown="onPointerDown"
      @pointerup="cancelHold"
      @pointerleave="cancelHold"
      @pointercancel="cancelHold"
    >
      <!-- 长按进度环：按住时绕按钮转一圈，转满才开始听 -->
      <span
        v-if="holding"
        class="read-along__ring"
        aria-hidden="true"
        :style="{ '--hold': holdProgress }"
      ></span>
      <span class="read-along__icon" aria-hidden="true">{{ listening ? '🎙️' : degraded ? '👂' : '🎤' }}</span>
      <span class="read-along__label">
        {{ listening ? '正在听…' : degraded ? '我听过了' : label }}
      </span>
    </button>

    <p v-if="holding" class="read-along__hint text-sm text-muted">按住别松手…</p>

    <p v-else-if="holdHint" class="read-along__feedback read-along__feedback--no">
      {{ holdHint }}
    </p>

    <p v-else-if="listening" class="read-along__hint text-sm text-muted">
      对着麦克风慢慢读「{{ text }}」
    </p>

    <p v-else-if="matched !== null" class="read-along__feedback">
      <span v-if="matched" class="read-along__feedback--ok">👍 {{ praiseText }}</span>
      <span v-else class="read-along__feedback--no">{{ encourageText }}，慢慢读「{{ text }}」</span>
      <span v-if="transcript" class="read-along__heard text-sm text-muted">（听到的是「{{ transcript }}」）</span>
    </p>

    <p v-else-if="acknowledged" class="read-along__feedback read-along__feedback--ok">
      👍 已记录（这台设备听不到声音）
    </p>

    <p v-else-if="errorText" class="read-along__feedback read-along__feedback--no">
      {{ errorText }}
    </p>
  </div>
</template>

<style scoped>
.read-along {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
  align-items: flex-start;
}

.read-along--block {
  width: 100%;
  align-items: stretch;
}

.read-along__btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-xs);
  padding: var(--space-xs) var(--space-md);
  border-radius: var(--radius-pill);
  background: var(--color-surface-alt);
  color: var(--color-text);
  border: 1px solid var(--color-border);
  font-weight: 600;
  line-height: 1.3;
  transition: transform 90ms ease-out;
}

.read-along__btn--sm {
  min-height: 40px;
  font-size: var(--font-sm);
}

.read-along__btn--md {
  min-height: var(--tap-min);
  font-size: var(--font-body);
}

/*
 * 「读一读」是启蒙页的主操作之一，跟读按钮要和喇叭一样**大** ——
 * 6 岁孩子手部精细动作尚未发育好，小按钮点不准会直接放弃跟读。
 * 主操作下限是 --tap-primary（64px，06-1 §2.9.3）。
 */
.read-along__btn--lg {
  min-height: var(--tap-primary);
  padding: var(--space-sm) var(--space-lg);
  font-size: var(--font-lg);
}

.read-along__btn--lg .read-along__icon {
  font-size: 26px;
  line-height: 1;
}

/* 长按进度环：用 conic-gradient 画一段弧，变量 --hold 是 0–1 的进度 */
.read-along__ring {
  position: absolute;
  inset: -3px;
  border-radius: inherit;
  padding: 3px;
  background: conic-gradient(
    from -90deg,
    var(--color-info) calc(var(--hold) * 360deg),
    transparent 0
  );
  -webkit-mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  pointer-events: none;
}

.read-along__btn--holding {
  transform: scale(0.97);
}

.read-along__btn--block {
  display: flex;
  width: 100%;
}

.read-along__btn--on {
  background: color-mix(in srgb, var(--color-info) 20%, var(--color-surface));
  border-color: var(--color-info);
}

.read-along__btn--on .read-along__icon {
  animation: mic-pulse 1s ease-in-out infinite;
}

.read-along__btn--ok {
  border-color: var(--color-success);
}

.read-along__btn--no {
  border-color: var(--color-warn);
}

.read-along__btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.read-along__btn:active:not(:disabled) {
  transform: scale(0.97);
}

.read-along__feedback {
  display: flex;
  flex-direction: column;
  gap: var(--space-2xs);
  font-size: var(--font-sm);
}

.read-along__feedback--ok {
  color: var(--color-success);
}

.read-along__feedback--no {
  color: var(--color-warn);
}

@keyframes mic-pulse {
  0%,
  100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.25);
  }
}
</style>
