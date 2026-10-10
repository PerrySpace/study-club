<script setup lang="ts">
/**
 * SpeakButton —— 朗读按钮（业务组件）。
 *
 * 用浏览器原生 TTS（`speechSynthesis`）读一段文本，不依赖任何素材与后端。
 *
 * 两条设计约束：
 *   ① 平台不支持朗读时**默认整块不渲染**（`hideWhenUnsupported`）——
 *      启蒙产品的按钮必须「点了就有反应」，留一个哑按钮只会让孩子反复点。
 *   ② 语速由调用方给。同一个字，字卡上要慢（0.7，声调要拖长才听得出来），
 *      整句要接近正常（0.95，逐字放慢会让句子失去韵律）。
 *
 * 文本变化时自动停掉正在播的内容：切到下一个字还在念上一个字，
 * 孩子会以为「读错了」。
 */
import { ref, watch } from 'vue';

import { useSpeech } from '@/composables/useSpeech';

const props = withDefaults(
  defineProps<{
    /** 要朗读的文本 */
    text: string;
    label?: string;
    /** 语速 0.1–10；字卡建议 0.7，词语 0.8，整句 0.95 */
    rate?: number;
    variant?: 'primary' | 'secondary' | 'ghost';
    size?: 'sm' | 'md' | 'lg';
    block?: boolean;
    /** 平台不支持时是否整块隐藏（默认隐藏；设为 false 会渲染成禁用态） */
    hideWhenUnsupported?: boolean;
    /**
     * 只显示图标（不显示文字）。
     *
     * 给「常驻在字卡上的喇叭」用：孩子看到喇叭就知道是「听读音」，
     * 不需要读按钮上的字。尺寸由 `size` 决定，热区仍 ≥ 56px。
     */
    iconOnly?: boolean;
  }>(),
  {
    label: '听一听',
    rate: 0.85,
    variant: 'secondary',
    size: 'md',
    block: false,
    hideWhenUnsupported: true,
    iconOnly: false,
  },
);

const { canSpeak, speak, stopSpeaking } = useSpeech();

/** 本按钮是否正在播**自己**的内容（避免同页面多个按钮一起变成「停止」）。 */
const mine = ref(false);

async function onClick(): Promise<void> {
  if (mine.value) {
    stopSpeaking();
    mine.value = false;
    return;
  }
  mine.value = true;
  try {
    await speak(props.text, { rate: props.rate });
  } finally {
    mine.value = false;
  }
}

watch(
  () => props.text,
  () => {
    if (mine.value) {
      stopSpeaking();
      mine.value = false;
    }
  },
);
</script>

<template>
  <button
    v-if="canSpeak || !hideWhenUnsupported"
    type="button"
    class="speak-btn tap clickable"
    :class="[
      `speak-btn--${variant}`,
      `speak-btn--${size}`,
      {
        'speak-btn--block': block,
        'speak-btn--playing': mine,
        'speak-btn--icon-only': iconOnly,
      },
    ]"
    :disabled="!canSpeak"
    :aria-label="`${label}：${text}`"
    @click="onClick"
  >
    <span class="speak-btn__icon" aria-hidden="true">{{ mine ? '⏹' : '🔊' }}</span>
    <span v-if="!iconOnly" class="speak-btn__label">{{ mine ? '停一停' : label }}</span>
  </button>
</template>

<style scoped>
.speak-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-xs);
  padding: var(--space-xs) var(--space-md);
  border-radius: var(--radius-pill);
  font-weight: 600;
  line-height: 1.3;
  transition: transform 90ms ease-out;
}

.speak-btn--sm {
  min-height: 40px;
  font-size: var(--font-sm);
}

.speak-btn--md {
  min-height: var(--tap-min);
  font-size: var(--font-body);
}

.speak-btn--lg {
  min-height: var(--tap-primary);
  font-size: var(--font-lg);
}

/*
 * 「加大」有两种含义，这里都覆盖到：
 *  ① 尺寸档位（--lg）把最小高度提到 --tap-primary（64px），主操作够大；
 *  ② 圆形图标模式（--icon-only）给 64–72px 的正方形热区 ——
 *     喇叭是启蒙页最高频的操作，纯文字按钮反而让孩子找不着。
 *     尺寸仍受 06-1 §2.9.3 的触控热区下限约束，不为了好看破线。
 */
.speak-btn--block {
  display: flex;
  width: 100%;
}

.speak-btn--icon-only {
  width: var(--tap-primary);
  min-width: var(--tap-primary);
  padding: 0;
  border-radius: 50%;
}

.speak-btn--icon-only.speak-btn--lg {
  width: 72px;
  min-width: 72px;
  min-height: 72px;
}

.speak-btn--icon-only .speak-btn__icon {
  font-size: 26px;
  line-height: 1;
}

.speak-btn--icon-only.speak-btn--lg .speak-btn__icon {
  font-size: 30px;
}

.speak-btn--primary {
  background: var(--color-info);
  color: var(--color-text-invert);
}

.speak-btn--secondary {
  background: var(--color-surface-alt);
  color: var(--color-text);
  border: 1px solid var(--color-border);
}

.speak-btn--ghost {
  background: transparent;
  color: var(--color-text-muted);
}

.speak-btn--playing {
  background: var(--color-primary);
  color: var(--color-text);
  border-color: var(--color-primary-strong);
}

.speak-btn--playing .speak-btn__icon {
  animation: speak-pulse 1s ease-in-out infinite;
}

.speak-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.speak-btn:active:not(:disabled) {
  transform: scale(0.97);
}

@keyframes speak-pulse {
  0%,
  100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.25);
  }
}
</style>
